import json
import sys

try:
    from loguru import logger

    from core.plc_state_machine import (PlcCommandController,
                                            BUTTON_TOPIC_CONNECT,
                                            BUTTON_TOPIC_DISCONNECT,
                                            BUTTON_TOPIC_START_PROCESS,
                                            BUTTON_TOPIC_EMERGENCY_STOP)

    from transport_layer.protocol.mqtt.client import (publish_message, register_recv_message_callback)
except ImportError as e:
    print(f"Error importing modules: {e}")

    sys.exit(1)

BUTTON_RESPONSE_TOPIC_PREFIX = "buttons/response"


def decode_mqtt_payload(message_payload: bytes) -> dict:
    """Decode MQTT bytes payload into a dictionary payload."""

    if not message_payload:
        return {}

    payload_str = message_payload.decode("utf-8", errors="ignore").strip()
    if not payload_str:
        return {}

    try:
        parsed = json.loads(payload_str)
    except json.JSONDecodeError:
        # Accept simple non-JSON payloads from basic UI nodes/buttons.
        return {"value": payload_str}

    if isinstance(parsed, dict):
        return parsed

    if isinstance(parsed, (int, float, str, bool)):
        return {"value": parsed}

    return {}


def register_button_callbacks(client, plc_controller: PlcCommandController) -> None:
    """Register MQTT callbacks for PLC control button topics."""


    def _publish_button_response(command_name: str,
                                 success: bool,
                                 message: str = "") -> None:
        publish_message(
            client,
            f"{BUTTON_RESPONSE_TOPIC_PREFIX}/{command_name}",
            {
                "success": success,
                "message": message,
            },
        )


    def _safe_callback_call(action_name: str, action) -> None:
        try:
            action()
        except RuntimeError as exc:
            logger.error("Runtime error while handling MQTT action '{}': {}", action_name, exc)
            _publish_button_response(action_name, False, str(exc))
        except ValueError as exc:
            logger.error("Value error while handling MQTT action '{}': {}", action_name, exc)
            _publish_button_response(action_name, False, str(exc))


    def on_connect_to_plc(_client, _userdata, msg):
        def _action() -> None:
            _ = decode_mqtt_payload(msg.payload)
            success, status_message = plc_controller.handle_connect_command()
            _publish_button_response("connect_to_plc", success, status_message)

        _safe_callback_call("connect_to_plc", _action)


    def on_start_process(_client, _userdata, msg):
        def _action() -> None:
            payload = decode_mqtt_payload(msg.payload)
            success, status_message = plc_controller.handle_start_process_command(payload)
            _publish_button_response("start_process", success, status_message)

        _safe_callback_call("start_process", _action)


    def on_disconnect_from_plc(_client, _userdata, msg):
        def _action() -> None:
            _ = decode_mqtt_payload(msg.payload)
            success, status_message = plc_controller.handle_disconnect_command()
            _publish_button_response("disconnect_from_plc", success, status_message)

        _safe_callback_call("disconnect_from_plc", _action)


    def on_emergency_stop(_client, _userdata, msg):
        def _action() -> None:
            _ = decode_mqtt_payload(msg.payload)
            success, status_message = plc_controller.handle_emergency_stop_command()
            _publish_button_response("emergency_stop", success, status_message)

        _safe_callback_call("emergency_stop", _action)

    register_recv_message_callback(client, BUTTON_TOPIC_CONNECT, on_connect_to_plc)
    register_recv_message_callback(client, BUTTON_TOPIC_DISCONNECT, on_disconnect_from_plc)
    register_recv_message_callback(client, BUTTON_TOPIC_START_PROCESS, on_start_process)
    register_recv_message_callback(client, BUTTON_TOPIC_EMERGENCY_STOP, on_emergency_stop)
