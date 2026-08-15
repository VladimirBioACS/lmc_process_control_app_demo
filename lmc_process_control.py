"""General python imports"""
import sys
from concurrent.futures import ThreadPoolExecutor
from time import sleep

# Importing necessary modules and handling import errors
try:
    import pyfiglet

    from loguru import logger

    from common.common import EXIT_FAILURE, EXIT_SUCCESS

    from core.lmc_calculator import LmcCalculator
    from core.plc_state_machine import (PlcCommandController)
    from core.system_params import (
        APP_CONFIG_PATH,
        MQTT_CONFIG_PATH,
        TL_CONFIG_PATH,
        DEFAULT_LOG_LEVEL,
        DEFAULT_LOG_FILE,
        THERMAL_COUPLE_POSITIONS_MM,
        DESIRED_LMC_GRADIENT_K_PER_CM,
        TL_TEMPERATURE,
        WITHDRAW_MM_PER_MIN,
        FRONT_ANGLE_DEG,
        TL_WINDOW_MM,
        THREAD_POOL_MAX_WORKERS,
        DEFAULT_POLL_INTERVAL_SECONDS,
        MAIN_LOOP_SLEEP_SECONDS,
    )

    from ui.queues import (gauge_furnace,
                           gauge_thermal_couple,
                           lmc_charts_queue,
                           power_system_status_queue,
                           coolant_pump_queue,
                           vacuum_pump_queue,
                           smelting_form_temp_queue,
                           form_heating_furnace_temp_queue,
                           vacuum_value_queue,
                           actuator_queue_speed,
                           actuator_queue_position,
                           aluminium_coolant_pump_queue,
                           aluminium_heating_furnace_queue,
                           aluminium_temperature_queue,
                           alloy_in_chamber_queue,
                           push_latest,
                           clear_ui_queues)

    from ui.uvnk_8p_ui_tasks import (ui_gauges_furnace_temp_thread,
                          ui_gauges_thermal_couples_thread,
                          ui_charts_lmc_thread,
                          ui_charts_actuator_position_thread,
                          ui_svg_power_system_block_thread,
                          ui_svg_coolant_pump_thread,
                          ui_svg_vacuum_pump_thread,
                          ui_svg_main_smelting_form_thread,
                          ui_svg_form_heating_furnace_thread,
                          ui_svg_furnace_vacuum_thread,
                          ui_svg_actuator_thread,
                          ui_svg_aluminium_coolant_pump_thread,
                          ui_svg_aluminium_heating_furnace_thread,
                          ui_svg_aluminium_temperature_thread,
                          ui_svg_alloy_in_chamber_thread,
                          set_ui_runtime_active,
                          stop_event)

    from ui.modules.svg_scheme import SvgSystemStates, SvgSchemeAlloyinChamberStatusTexts

    from ui.buttons import (register_button_callbacks)

    from helpers import config_parser
    from helpers.mapper import (map_boolean_to_svg_state, derive_actuator_status)

    from transport_layer.protocol.mqtt.client import (create_mqtt_client,
                                                      disconnect_mqtt_client,
                                                      loop_mqtt_client)
except ImportError as e:
    print(f"Error importing modules: {e}")

    sys.exit(1)


UI_DATA_QUEUES = [
    gauge_furnace,
    gauge_thermal_couple,
    lmc_charts_queue,
    power_system_status_queue,
    coolant_pump_queue,
    vacuum_pump_queue,
    smelting_form_temp_queue,
    form_heating_furnace_temp_queue,
    vacuum_value_queue,
    actuator_queue_speed,
    actuator_queue_position,
    aluminium_coolant_pump_queue,
    aluminium_heating_furnace_queue,
    aluminium_temperature_queue,
    alloy_in_chamber_queue,
]


def init_logger(log_level: str = DEFAULT_LOG_LEVEL, log_file: str = DEFAULT_LOG_FILE) -> None:
    """
    Initializes the logger with the specified log level and log file.

    Args:
        log_level (str): The logging level (e.g., "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").
        log_file (str): The path to the log file.
    """

    # Remove default logger and add a new one with the specified log level and log file
    logger.remove()

    logger.add(log_file, level=log_level, rotation="10 MB", retention="7 days")
    logger.info(f"Logger initialized with level: {log_level} and log file: {log_file}")

    # Add stdout printing for console output
    logger.add(sys.stdout, level=log_level)


def init_mqtt_client():
    """
    Initializes and returns an MQTT client instance.

    Returns:
        mqtt.Client: The configured MQTT client instance.
    """

    try:
        mqtt_config = config_parser.load_config(MQTT_CONFIG_PATH)

        client = create_mqtt_client(
            broker_address=mqtt_config.get("mqtt_broker", "localhost"),
            broker_port=mqtt_config.get("mqtt_port", 1883),
            username=mqtt_config.get("mqtt_username"),
            password=mqtt_config.get("mqtt_password")
        )

        loop_mqtt_client(client)

        return client

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")

        sys.exit(EXIT_FAILURE)


def handle_exit(client, plc_controller: PlcCommandController | None = None):
    """
    Handles graceful shutdown of the application by stopping the scheduler and disconnecting
    the MQTT client.

    Args:
        client (mqtt.Client): The MQTT client instance to disconnect.
    """

    stop_event.set()

    if plc_controller:
        plc_controller.shutdown()
        logger.info("PLC controller shut down and PLC monitoring command cleared.")

    if client:
        disconnect_mqtt_client(client)
        logger.info("MQTT client disconnected and resources freed.")

    logger.info("Application shutdown complete.")
    logger.remove()


def pause_ui_threads() -> None:
    """
    Signal UI threads to pause consuming data and clear any stale data
    from the queues.
    """

    set_ui_runtime_active(False)
    for q in UI_DATA_QUEUES:
        clear_ui_queues(q)


def resume_ui_threads() -> None:
    """
    Clear any stale data from the queues and allow UI threads to start
    consuming new telemetry.
    """

    set_ui_runtime_active(True)


def calculate_gradient(thermal_couples_data: dict[str, int]) -> float | None:
    """
    Calculates the temperature gradient based on the thermal couple data.

    Args:
        thermal_couples_data (dict): A dictionary containing the thermal couple readings.

    Returns:
        float: The calculated temperature gradient in K/cm.
    """

    try:
        calc = LmcCalculator(
            withdraw_mm_per_min=WITHDRAW_MM_PER_MIN,
            front_angle_deg=FRONT_ANGLE_DEG,
            tl_c=TL_TEMPERATURE,
            tl_window_mm=TL_WINDOW_MM,
        )

        active_points = [
            (
                THERMAL_COUPLE_POSITIONS_MM[index - 1],
                float(thermal_couples_data[f"thermal_couple_{index}"]),
            )
            for index in range(1, len(THERMAL_COUPLE_POSITIONS_MM) + 1)
            if f"thermal_couple_{index}" in thermal_couples_data
            and float(thermal_couples_data[f"thermal_couple_{index}"]) > 0.0
        ]

        if len(active_points) < 2:
            return None

        positions, temperatures = zip(*active_points)
        lmc_data = calc.calculate_lmc(list(positions), list(temperatures))

        return lmc_data

    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Unable to calculate gradient: {}", exc)

        return None


def should_measure_gradient(plc_payload: dict) -> bool:
    """
    Start gradient measurement only while actuator is immersed in coolant.

    This excludes the furnace preparation stage where alloy is not yet in the mold.
    """

    position = float(plc_payload.get("position", 0.0))
    speed = float(plc_payload.get("speed", 0.0))

    # Immersion stage: actuator has started moving down and process is active.
    return position > 0.0 and speed > 0.0


def publish_plc_payload_to_ui(payload: dict, lmc_data: dict | None = None) -> None:
    """
    Transforms the raw PLC payload into the appropriate formats and pushes it to the respective
    UI queues.

    Args:
        payload (dict): The raw data payload read from the PLC.
        lmc_data (dict, optional): The calculated LMC data to be included
                                   in the UI payload. Defaults to None.
    """

    furnace_temperature_data = {
        "furnace_heater_temperature": payload["furnace_heater_temperature"],
        "aluminium_temperature": payload["aluminium_temperature"],
        "smelting_form_temperature": payload["smelting_form_temperature"],
        "aluminium_heater_temperature": payload["aluminium_heater_temperature"],
    }

    thermal_couples_data = {
        f"thermal_couple_{index}": payload[f"thermal_couple_{index}"]
        for index in range(1, 11)
    }

    lmc_charts_data = {
        "gradient": float(f"{lmc_data['G_K_per_cm'] :.2f}") if lmc_data else None,
        "cooling_speed": float(f"{lmc_data['R_K_per_min'] :.2f}") if lmc_data else None,
        "linear_aprox": float(f"{lmc_data['R2'] :.2f}") if lmc_data else None,
    }

    push_latest(gauge_furnace, furnace_temperature_data)
    push_latest(gauge_thermal_couple, thermal_couples_data)
    push_latest(lmc_charts_queue, lmc_charts_data)

    power_status = {"power_consumption": payload["power_consumption"]}

    push_latest(power_system_status_queue, power_status)

    furnace_block_data = {
        "form_heating_furnace_temperature": payload["form_heating_furnace_temperature"],
        "vacuum": payload["vacuum"],
        "smelting_form_temperature": payload["smelting_form_temperature"],
        "coolant_pump_status": map_boolean_to_svg_state(payload["coolant_pump_status"]),
        "vacuum_pump_status": map_boolean_to_svg_state(payload["vacuum_pump_status"]),
    }

    push_latest(coolant_pump_queue, furnace_block_data)
    push_latest(vacuum_pump_queue, furnace_block_data)
    push_latest(smelting_form_temp_queue, furnace_block_data)
    push_latest(form_heating_furnace_temp_queue, furnace_block_data)
    push_latest(vacuum_value_queue, furnace_block_data)

    actuator_data = {
        "speed": payload["speed"],
        "position": payload["position"],
        "status": derive_actuator_status(payload["speed"]),
    }

    push_latest(actuator_queue_speed, actuator_data)
    push_latest(actuator_queue_position, actuator_data)

    push_latest(
        aluminium_coolant_pump_queue,
        {
            "aluminium_coolant_pump_status": map_boolean_to_svg_state(
                payload["aluminium_coolant_pump_status"]
            )
        },
    )

    push_latest(
        aluminium_heating_furnace_queue,
        {
            "temperature": payload["aluminium_heater_temperature"],
            "status": SvgSystemStates.ON.value,
        },
    )

    aluminium_temp = {"temperature": payload["aluminium_temperature"]}

    push_latest(aluminium_temperature_queue, aluminium_temp)

    alloy_in_chamber_status = {
            "alloy_in_chamber": SvgSchemeAlloyinChamberStatusTexts.PRESENT.value
            if payload["position"] > 0
            else SvgSchemeAlloyinChamberStatusTexts.ABSCENT.value
    }

    push_latest(alloy_in_chamber_queue, alloy_in_chamber_status)


def get_data_from_plc(plc_controller: PlcCommandController, poll_interval_seconds: float) -> None:
    """
    Polls data from the PLC over Modbus TCP and pushes it to the queues used by the UI.
    """

    while not stop_event.is_set():

        plc_payload = plc_controller.poll_plc_payload()
        if plc_payload is None:
            sleep(poll_interval_seconds)

            continue

        lmc_data = calculate_gradient(plc_payload) if should_measure_gradient(plc_payload) else None

        publish_plc_payload_to_ui(plc_payload, lmc_data)

        plc_controller.evaluate_running_process(plc_payload,
                                                gradient=lmc_data["G_K_per_cm"]
                                                if lmc_data else None)

        sleep(poll_interval_seconds)


def schedule_app_tasks(client, plc_controller: PlcCommandController,
                       poll_interval_seconds: float) -> None:
    """
    Schedules application tasks to run at regular intervals.

    Args:
        client (mqtt.Client): The MQTT client instance to pass to the scheduled tasks.
    """

    with ThreadPoolExecutor(max_workers=THREAD_POOL_MAX_WORKERS,
                            thread_name_prefix="lmc_monitoring") as executor:
        # Schedule UI update threads and the PLC data fetching thread
        executor.submit(ui_gauges_furnace_temp_thread, client)
        executor.submit(ui_gauges_thermal_couples_thread, client)
        executor.submit(ui_charts_lmc_thread, client)
        executor.submit(ui_svg_power_system_block_thread, client)
        executor.submit(ui_svg_coolant_pump_thread, client)
        executor.submit(ui_svg_vacuum_pump_thread, client)
        executor.submit(ui_svg_main_smelting_form_thread, client)
        executor.submit(ui_svg_form_heating_furnace_thread, client)
        executor.submit(ui_svg_furnace_vacuum_thread, client)
        executor.submit(ui_svg_actuator_thread, client)
        executor.submit(ui_svg_aluminium_coolant_pump_thread, client)
        executor.submit(ui_svg_aluminium_heating_furnace_thread, client)
        executor.submit(ui_svg_aluminium_temperature_thread, client)
        executor.submit(ui_svg_alloy_in_chamber_thread, client)
        executor.submit(ui_charts_actuator_position_thread, client)

        # Schedule the PLC threads
        executor.submit(get_data_from_plc, plc_controller, poll_interval_seconds)


def main() -> None:
    """
    The main entry point of the application.
    """

    client = None
    plc_controller = None

    try:
        header = pyfiglet.figlet_format("LMC Process Control")
        print(header)

        app_config = config_parser.load_config(APP_CONFIG_PATH)
        tl_config = config_parser.load_config(TL_CONFIG_PATH)
        modbus_config = tl_config.get("modbus_tcp", {})

        init_logger(app_config.get("log_level", DEFAULT_LOG_LEVEL),
                    app_config.get("log_file", DEFAULT_LOG_FILE))


        client = init_mqtt_client()
        if client is None:
            logger.error("Failed to initialize MQTT client. Exiting application.")

            sys.exit(EXIT_FAILURE)

        logger.info("MQTT client initialized successfully.")

        plc_controller = PlcCommandController(
            client,
            modbus_config,
            DESIRED_LMC_GRADIENT_K_PER_CM,
            on_process_stopped=pause_ui_threads,
            on_process_resumed=resume_ui_threads,
        )
        register_button_callbacks(client, plc_controller)

        logger.info("PLC button callbacks registered successfully.")

        # Start with UI workers paused until process telemetry resumes.
        pause_ui_threads()

        schedule_app_tasks(client,
                           plc_controller,
                           modbus_config.get("poll_interval_seconds",
                                             DEFAULT_POLL_INTERVAL_SECONDS))

        # Keep the main thread alive to allow background threads to run
        while not stop_event.is_set():
            sleep(MAIN_LOOP_SLEEP_SECONDS)

    except (KeyboardInterrupt, SystemExit):
        logger.info("Keyboard interrupt received. Shutting down...")
        handle_exit(client, plc_controller)

        sys.exit(EXIT_SUCCESS)

    except KeyError as e:
        logger.error(f"Missing configuration key: {e}")
        handle_exit(client, plc_controller)

        sys.exit(EXIT_FAILURE)

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        handle_exit(client, plc_controller)

        sys.exit(EXIT_FAILURE)


if __name__ == "__main__":
    main()
