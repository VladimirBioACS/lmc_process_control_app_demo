from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from time import sleep
from typing import Any, Callable

from loguru import logger

from core.lmc_calculator import LmcCalculator
from transport_layer.protocol.modbus_rtu.client import ModbusClient, ModbusClientErrorCode
from transport_layer.protocol.modbus_rtu.server import (
    FINISH_STATUS_FAILED,
    FINISH_STATUS_PENDING,
    FINISH_STATUS_SUCCESS,
)
from transport_layer.protocol.mqtt.client import publish_message


BUTTON_TOPIC_CONNECT = "buttons/connect_to_plc"
BUTTON_TOPIC_START_PROCESS = "buttons/start_process"
BUTTON_TOPIC_EMERGENCY_STOP = "buttons/emergency_stop"
BUTTON_TOPIC_DISCONNECT = "buttons/disconnect_from_plc"
BUTTON_STATE_TOPIC = "buttons/state"
BUTTON_EVENT_TOPIC = "buttons/events"
LMC_PROCESS_STATUS_TOPIC = "lmc_process_status/"


class AppStateName(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED_IDLE = "connected_idle"
    PROCESS_RUNNING = "process_running"
    EMERGENCY_STOPPED = "emergency_stopped"


@dataclass(slots=True)
class NominalRanges:
    """
    Nominal ranges for key telemetry fields used in process evaluation for UVNK-8P furnace.
    These can be adjusted based on expected operating conditions of the LMC process.
    """

    furnace_heater_temperature_min: float = 1400.0
    furnace_heater_temperature_max: float = 1600.0
    aluminium_temperature_min: float = 760.0
    aluminium_temperature_max: float = 840.0
    smelting_form_temperature_min: float = 1350.0
    smelting_form_temperature_max: float = 1600.0
    aluminium_heater_temperature_min: float = 760.0
    aluminium_heater_temperature_max: float = 840.0
    vacuum_min: float = 0.0
    vacuum_max: float = 10.0


class PlcAppState:
    name: AppStateName

    def connect(self, _controller: PlcCommandController) -> tuple[bool, str]:
        return False, "Unsupported command for current state."

    def start_process(self, _controller: PlcCommandController,
                      _speed_mm_per_sec: float) -> tuple[bool, str]:
        return False, "Unsupported command for current state."

    def disconnect(self, _controller: PlcCommandController) -> tuple[bool, str]:
        return False, "Unsupported command for current state."

    def emergency_stop(self, _controller: PlcCommandController) -> tuple[bool, str]:
        return False, "Unsupported command for current state."


class DisconnectedState(PlcAppState):
    name = AppStateName.DISCONNECTED

    def connect(self, controller: PlcCommandController) -> tuple[bool, str]:
        if not controller.connect_plc():
            return False, "Failed to connect to PLC."

        controller.transition_to(ConnectedIdleState())
        return True, "PLC connection established."

    def start_process(self, _controller: PlcCommandController,
                      _speed_mm_per_sec: float) -> tuple[bool, str]:
        return False, "Cannot start process while disconnected. Connect to PLC first."

    def disconnect(self, _controller: PlcCommandController) -> tuple[bool, str]:
        return True, "PLC is already disconnected."

    def emergency_stop(self, _controller: PlcCommandController) -> tuple[bool, str]:
        return False, "Cannot send emergency stop while disconnected."


class ConnectedIdleState(PlcAppState):
    name = AppStateName.CONNECTED_IDLE

    def connect(self, _controller: PlcCommandController) -> tuple[bool, str]:
        return True, "PLC is already connected."

    def start_process(self, controller: PlcCommandController, speed_mm_per_sec: float) -> tuple[bool, str]:
        if not controller.start_process(speed_mm_per_sec):
            return False, "PLC rejected process start command."

        controller.transition_to(ProcessRunningState())
        return True, f"Casting process started with speed {speed_mm_per_sec:.1f} mm/s."

    def emergency_stop(self, controller: PlcCommandController) -> tuple[bool, str]:
        if not controller.stop_process():
            return False, "Failed to send emergency stop to PLC."

        controller.transition_to(EmergencyStoppedState())
        return True, "Emergency stop command sent."

    def disconnect(self, controller: PlcCommandController) -> tuple[bool, str]:
        if not controller.disconnect_plc():
            return False, "Failed to disconnect from PLC."

        controller.transition_to(DisconnectedState())
        return True, "PLC disconnected successfully."


class ProcessRunningState(PlcAppState):
    name = AppStateName.PROCESS_RUNNING

    def connect(self, _controller: PlcCommandController) -> tuple[bool, str]:
        return True, "PLC is already connected."

    def start_process(self, _controller: PlcCommandController,
                      _speed_mm_per_sec: float) -> tuple[bool, str]:
        return False, "Process is already running."

    def emergency_stop(self, controller: PlcCommandController) -> tuple[bool, str]:
        if not controller.stop_process():
            return False, "Failed to send emergency stop to PLC."

        controller.transition_to(EmergencyStoppedState())
        return True, "Emergency stop command sent."

    def disconnect(self, controller: PlcCommandController) -> tuple[bool, str]:
        # Ensure process is stopped before dropping PLC connection.
        if not controller.stop_process():
            return False, "Failed to stop process before disconnect."

        if not controller.disconnect_plc():
            return False, "Failed to disconnect from PLC."

        controller.transition_to(DisconnectedState())
        return True, "Process stopped and PLC disconnected successfully."


class EmergencyStoppedState(PlcAppState):
    name = AppStateName.EMERGENCY_STOPPED

    def connect(self, controller: PlcCommandController) -> tuple[bool, str]:
        if not controller.is_client_ready():
            if not controller.connect_plc():
                return False, "Failed to reconnect to PLC after emergency stop."

        controller.transition_to(ConnectedIdleState())
        return True, "Emergency acknowledged. PLC is back to idle state."

    def start_process(self, _controller: PlcCommandController,
                      _speed_mm_per_sec: float) -> tuple[bool, str]:
        return False, "Emergency stop is active. Press connect to acknowledge before starting."

    def emergency_stop(self, _controller: PlcCommandController) -> tuple[bool, str]:
        return True, "Emergency stop is already active."

    def disconnect(self, controller: PlcCommandController) -> tuple[bool, str]:
        if not controller.disconnect_plc():
            return False, "Failed to disconnect from PLC."

        controller.transition_to(DisconnectedState())
        return True, "PLC disconnected successfully."


class PlcCommandController:
    """State-driven PLC command controller used by MQTT button callbacks and polling logic."""

    def __init__(
        self,
        mqtt_client: Any,
        modbus_config: dict[str, Any],
        target_gradient: float,
        on_process_stopped: Callable[[], None] | None = None,
        on_process_resumed: Callable[[], None] | None = None,
    ):
        self._mqtt_client = mqtt_client
        self._modbus_config = modbus_config
        self._plc_client: ModbusClient | None = None
        self._state: PlcAppState = DisconnectedState()
        self._lock = threading.RLock()
        self._on_process_stopped = on_process_stopped
        self._on_process_resumed = on_process_resumed

        self._nominal_ranges = NominalRanges()
        self._target_gradient = target_gradient
        self._gradient_tolerance = 0.5
        self._withdraw_mm_per_min = 20.0
        self._pending_nominal_check = False
        self._running_samples_seen = 0
        self._consecutive_nominal_failures = 0
        self._nominal_grace_samples = 3
        self._nominal_failures_to_stop = 4
        self._finish_ack_timeout_seconds = 0.2
        self._finish_ack_poll_seconds = 0.2
        self._awaiting_process_data = False
        self._last_payload_signature: tuple[tuple[str, Any], ...] | None = None
        self._resume_baseline_signature: tuple[tuple[str, Any], ...] | None = None

    @property
    def state_name(self) -> AppStateName:
        return self._state.name


    def handle_connect_command(self) -> tuple[bool, str]:
        with self._lock:
            ok, message = self._state.connect(self)
            self._publish_state_event("connect_to_plc", ok, message)
            return ok, message


    def handle_start_process_command(self, command_payload: dict[str, Any] | None = None) -> tuple[bool, str]:
        payload = command_payload or {}
        speed_mm_per_sec = self._normalize_speed(payload.get("speed_mm_per_sec", 10.0))

        with self._lock:
            ok, message = self._state.start_process(self, speed_mm_per_sec)
            self._publish_state_event("start_process", ok, message, {"speed_mm_per_sec": speed_mm_per_sec})
            return ok, message


    def handle_disconnect_command(self) -> tuple[bool, str]:
        with self._lock:
            ok, message = self._state.disconnect(self)
            self._publish_state_event("disconnect_from_plc", ok, message)
            return ok, message


    def handle_emergency_stop_command(self) -> tuple[bool, str]:
        with self._lock:
            ok, message = self._state.emergency_stop(self)
            self._publish_state_event("emergency_stop", ok, message)
            return ok, message


    def poll_plc_payload(self) -> dict[str, Any] | None:
        with self._lock:
            if not self.is_client_ready():
                return None

            payload = self._plc_client.read_process_data()
            if isinstance(payload, ModbusClientErrorCode):
                logger.warning("Skipping PLC update because Modbus read returned {}", payload.name)
                if payload == ModbusClientErrorCode.CONNECTION_ERROR:
                    self.transition_to(DisconnectedState())
                    self._awaiting_process_data = False
                    self._resume_baseline_signature = None
                    self._notify_process_stopped()
                    self._publish_state_event("connection_lost", False, "Lost connection to PLC.")
                return None

            payload_signature = self._payload_signature(payload)
            if self._awaiting_process_data and (
                self._resume_baseline_signature is None
                or payload_signature != self._resume_baseline_signature
            ):
                self._awaiting_process_data = False
                self._resume_baseline_signature = None
                self._notify_process_resumed()

            self._last_payload_signature = payload_signature
            return payload


    def evaluate_running_process(self, plc_payload: dict[str, Any], gradient: float) -> None:
        with self._lock:
            if self._state.name != AppStateName.PROCESS_RUNNING:
                return

            self._running_samples_seen += 1
            nominal_errors = self._check_nominal_ranges(plc_payload)
            if nominal_errors:
                self._consecutive_nominal_failures += 1

                # Ignore transient startup noise from simulator telemetry.
                if self._running_samples_seen <= self._nominal_grace_samples:
                    return

                # if self._consecutive_nominal_failures >= self._nominal_failures_to_stop:
                #     self.stop_process()
                #     self.transition_to(ConnectedIdleState())
                #     self._pending_nominal_check = False
                #     self._publish_state_event(
                #         "nominal_validation_failed",
                #         False,
                #         "Process stopped because nominal checks failed repeatedly.",
                #         {
                #             "errors": nominal_errors,
                #             "consecutive_failures": self._consecutive_nominal_failures,
                #         },
                #     )
                #     return
            else:
                if self._pending_nominal_check:
                    self._pending_nominal_check = False
                    self._publish_state_event(
                        "nominal_validation_passed",
                        True,
                        "Nominal checks passed. Monitoring gradient for finish condition.",
                    )

                self._consecutive_nominal_failures = 0

            if gradient is None:
                return

            if abs(gradient - self._target_gradient) <= self._gradient_tolerance:
                if self.finish_the_process(gradient):
                    self.transition_to(ConnectedIdleState())
                    self._publish_state_event(
                        "process_finished",
                        True,
                        "Target gradient reached. Finish command sent and PLC returned to idle.",
                        {
                            "gradient_k_per_cm": round(gradient, 2),
                            "target_gradient_k_per_cm": self._target_gradient,
                        },
                    )


    def shutdown(self) -> None:
        with self._lock:
            if self._plc_client is not None:
                self.stop_process()
                self.disconnect_plc()
            self.transition_to(DisconnectedState())


    def transition_to(self, new_state: PlcAppState) -> None:
        logger.info("State transition: {} -> {}", self._state.name.value, new_state.name.value)
        self._state = new_state


    def is_client_ready(self) -> bool:
        return self._plc_client is not None


    def connect_plc(self) -> bool:
        if self._plc_client is not None:
            return True

        client = ModbusClient(
            ip_address=self._modbus_config.get("host", "127.0.0.1"),
            port=self._modbus_config.get("port", 5020),
            slave_id=self._modbus_config.get("slave_id", 1),
            timeout=self._modbus_config.get("timeout_seconds", 1.0),
        )

        logger.info("Connecting to PLC at {}:{}...", client.ip_address, client.port)
        if client.connect() != ModbusClientErrorCode.SUCCESS:
            return False

        self._plc_client = client
        return True


    def disconnect_plc(self) -> bool:
        if self._plc_client is None:
            self._pending_nominal_check = False
            self._awaiting_process_data = False
            self._resume_baseline_signature = None
            return True

        try:
            self._plc_client.close()
        except RuntimeError as exc:
            logger.error("Failed to close PLC client: {}", exc)
            return False

        self._plc_client = None
        self._pending_nominal_check = False
        self._running_samples_seen = 0
        self._consecutive_nominal_failures = 0
        self._awaiting_process_data = False
        self._resume_baseline_signature = None
        return True


    def start_process(self, speed_mm_per_sec: float) -> bool:
        if self._plc_client is None:
            return False

        self._withdraw_mm_per_min = speed_mm_per_sec * 60.0
        result = self._plc_client.write_process_start(True)
        if result != ModbusClientErrorCode.SUCCESS:
            return False

        self._pending_nominal_check = True
        self._running_samples_seen = 0
        self._consecutive_nominal_failures = 0
        self._awaiting_process_data = True
        self._resume_baseline_signature = self._last_payload_signature
        self._plc_client.reset_finish_status()
        return True


    def stop_process(self) -> bool:
        if self._plc_client is None:
            return False

        result = self._plc_client.write_process_start(False)
        self._pending_nominal_check = False
        self._running_samples_seen = 0
        self._consecutive_nominal_failures = 0
        self._awaiting_process_data = False
        self._resume_baseline_signature = None

        success = result == ModbusClientErrorCode.SUCCESS
        if success:
            self._notify_process_stopped()

        return success


    def finish_the_process(self, gradient_k_per_cm: float) -> bool:
        """
        Send finish command to PLC simulator and publish final process status via MQTT.
        """

        if self._plc_client is None:
            return False

        result = self._plc_client.write_finish_process()
        if result != ModbusClientErrorCode.SUCCESS:
            publish_message(
                self._mqtt_client,
                LMC_PROCESS_STATUS_TOPIC,
                {
                    "status": "FAILED",
                    "command": "finish_the_process",
                    "message": f"PLC rejected finish command: {result.name}",
                },
            )
            return False

        elapsed = 0.0
        while elapsed <= self._finish_ack_timeout_seconds:
            finish_status = self._plc_client.read_finish_status()
            if isinstance(finish_status, ModbusClientErrorCode):
                break

            if finish_status == FINISH_STATUS_SUCCESS:
                self._pending_nominal_check = False
                self._running_samples_seen = 0
                self._consecutive_nominal_failures = 0
                self._awaiting_process_data = False
                self._resume_baseline_signature = None
                self._notify_process_stopped()
                publish_message(
                    self._mqtt_client,
                    LMC_PROCESS_STATUS_TOPIC,
                    {
                        "status": "SUCCESS",
                        "command": "finish_the_process",
                        "gradient_k_per_cm": round(gradient_k_per_cm, 2),
                        "target_gradient_k_per_cm": self._target_gradient,
                    },
                )
                return True

            if finish_status == FINISH_STATUS_FAILED:
                break

            if finish_status == FINISH_STATUS_PENDING:
                sleep(self._finish_ack_poll_seconds)
                elapsed += self._finish_ack_poll_seconds
                continue

            sleep(self._finish_ack_poll_seconds)
            elapsed += self._finish_ack_poll_seconds

        publish_message(
            self._mqtt_client,
            LMC_PROCESS_STATUS_TOPIC,
            {
                "status": "FAILED",
                "command": "finish_the_process",
                "message": "Timeout or failure while waiting for simulator finish acknowledgement.",
            },
        )

        return False


    @staticmethod
    def _payload_signature(payload: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
        return tuple(sorted(payload.items()))


    def _notify_process_stopped(self) -> None:
        if self._on_process_stopped is None:
            return

        try:
            self._on_process_stopped()
        except (RuntimeError, ValueError, TypeError) as exc:
            logger.error("Process stopped callback failed: {}", exc)


    def _notify_process_resumed(self) -> None:
        if self._on_process_resumed is None:
            return

        try:
            self._on_process_resumed()
        except (RuntimeError, ValueError, TypeError) as exc:
            logger.error("Process resumed callback failed: {}", exc)


    def _check_nominal_ranges(self, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []

        def check_range(field_name: str, lower: float, upper: float) -> None:
            value = payload.get(field_name)
            if value is None:
                errors.append(f"{field_name}: missing value")
                return

            if not lower <= float(value) <= upper:
                errors.append(f"{field_name}: {value} out of nominal range [{lower}, {upper}]")

        check_range(
            "furnace_heater_temperature",
            self._nominal_ranges.furnace_heater_temperature_min,
            self._nominal_ranges.furnace_heater_temperature_max,
        )
        check_range(
            "aluminium_temperature",
            self._nominal_ranges.aluminium_temperature_min,
            self._nominal_ranges.aluminium_temperature_max,
        )
        check_range(
            "smelting_form_temperature",
            self._nominal_ranges.smelting_form_temperature_min,
            self._nominal_ranges.smelting_form_temperature_max,
        )
        check_range(
            "aluminium_heater_temperature",
            self._nominal_ranges.aluminium_heater_temperature_min,
            self._nominal_ranges.aluminium_heater_temperature_max,
        )
        check_range(
            "vacuum",
            self._nominal_ranges.vacuum_min,
            self._nominal_ranges.vacuum_max,
        )

        if not bool(payload.get("coolant_pump_status", False)):
            errors.append("coolant_pump_status: expected ON")

        if not bool(payload.get("vacuum_pump_status", False)):
            errors.append("vacuum_pump_status: expected ON")

        return errors


    def _normalize_speed(self, raw_speed: Any) -> float:
        try:
            speed = float(raw_speed)
        except (TypeError, ValueError):
            speed = 10.0

        if speed < 5.0:
            return 5.0
        if speed > 30.0:
            return 30.0

        return speed


    def _publish_state_event(
        self,
        command: str,
        success: bool,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        event_payload = {
            "command": command,
            "success": success,
            "state": self._state.name.value,
            "message": message,
        }
        if details:
            event_payload["details"] = details

        publish_message(self._mqtt_client, BUTTON_EVENT_TOPIC, event_payload)
        publish_message(
            self._mqtt_client,
            BUTTON_STATE_TOPIC,
            {
                "state": self._state.name.value,
                "process_running": self._state.name == AppStateName.PROCESS_RUNNING,
                "emergency_active": self._state.name == AppStateName.EMERGENCY_STOPPED,
            },
        )
