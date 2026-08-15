"""Centralized application constants and configurable runtime parameters."""

from dataclasses import dataclass


# Configuration and logging
APP_CONFIG_PATH = "configs/app_config.json"
MQTT_CONFIG_PATH = "configs/mqtt_config.json"
TL_CONFIG_PATH = "configs/tl_config.json"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FILE = "logs/app.log"


# MQTT topics
BUTTON_TOPIC_CONNECT = "buttons/connect_to_plc"
BUTTON_TOPIC_START_PROCESS = "buttons/start_process"
BUTTON_TOPIC_EMERGENCY_STOP = "buttons/emergency_stop"
BUTTON_TOPIC_DISCONNECT = "buttons/disconnect_from_plc"
BUTTON_STATE_TOPIC = "buttons/state"
BUTTON_EVENT_TOPIC = "buttons/events"
BUTTON_RESPONSE_TOPIC_PREFIX = "buttons/response"
LMC_PROCESS_STATUS_TOPIC = "lmc_process_status/"


# LMC calculation parameters
THERMAL_COUPLE_POSITIONS_MM = [0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0]
DESIRED_LMC_GRADIENT_K_PER_CM = 20.0
TL_TEMPERATURE = 1560.0
WITHDRAW_MM_PER_MIN = 20.0
FRONT_ANGLE_DEG = 30.0
TL_WINDOW_MM = 10.0


# PLC runtime defaults
DEFAULT_POLL_INTERVAL_SECONDS = 0.5
MAIN_LOOP_SLEEP_SECONDS = 0.1
THREAD_POOL_MAX_WORKERS = 16


# PLC command controller tuning
PLC_DEFAULT_START_SPEED_MM_PER_SEC = 10.0
PLC_MIN_SPEED_MM_PER_SEC = 5.0
PLC_MAX_SPEED_MM_PER_SEC = 30.0

# The tolerance for how close the actual gradient needs to be to the target gradient to
# consider it acceptable.
PLC_GRADIENT_TOLERANCE_K_PER_CM = 1.5

PLC_NOMINAL_GRACE_SAMPLES = 3
PLC_NOMINAL_FAILURES_TO_STOP = 4
PLC_FINISH_ACK_TIMEOUT_SECONDS = 30.0
PLC_FINISH_ACK_POLL_SECONDS = 0.2


# Modbus defaults
MODBUS_DEFAULT_HOST = "127.0.0.1"
MODBUS_DEFAULT_PORT = 5020
MODBUS_DEFAULT_SLAVE_ID = 1
MODBUS_DEFAULT_TIMEOUT_SECONDS = 1.0


@dataclass(slots=True)
class NominalRanges:
    """Nominal ranges for key telemetry fields used in process evaluation."""

    furnace_heater_temperature_min: float = 1300.0
    furnace_heater_temperature_max: float = 1600.0
    aluminium_temperature_min: float = 760.0
    aluminium_temperature_max: float = 840.0
    smelting_form_temperature_min: float = 1350.0
    smelting_form_temperature_max: float = 1600.0
    aluminium_heater_temperature_min: float = 760.0
    aluminium_heater_temperature_max: float = 840.0
    vacuum_min: float = 0.0
    vacuum_max: float = 10.0
