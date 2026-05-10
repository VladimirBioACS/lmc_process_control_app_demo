"""General python imports"""
import sys
import queue
import threading

from ui.modules.svg_scheme import SvgSchemeAlloyinChamberStatusTexts

# Importing necessary modules and handling import errors
try:
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
                           alloy_in_chamber_queue)

    from ui.modules.charts import UiCharts, ChartType

    from ui.modules.svg_scheme import (SvgMainScheme,
                               SvgSvhemeColors,
                               SvgSystemStates,
                               SvgFlowAnimations,
                               SvgSchemePumpStatusTexts,
                               SvgBlockHatchPatterns,
                               SvgSchemaPowerConnectionStatusTexts)
except ImportError as e:
    print(f"Error importing modules: {e}")

    sys.exit(1)

# Importing loguru for logging and handling import errors
try:
    from loguru import logger
except ImportError as e:
    print(f"Error importing modules: {e}")

    sys.exit(1)


# Event for graceful shutdown
stop_event = threading.Event()
ui_runtime_event = threading.Event()
ui_runtime_event.set()


def set_ui_runtime_active(active: bool) -> None:
    """
    Set the UI runtime event state.

    Args:
        active (bool): If True, set the UI runtime event; if False, clear it.
    """

    if active:
        ui_runtime_event.set()
    else:
        ui_runtime_event.clear()


def wait_for_ui_runtime() -> bool:
    """
    Wait for the UI runtime event to be set, with periodic checks for shutdown.

    Returns:
        bool: True if the UI runtime event is set, False if a shutdown was signaled.
    """

    while not stop_event.is_set():
        if ui_runtime_event.wait(timeout=0.5):
            return True

    return False


def ui_svg_power_system_block_thread(client):
    """
    Thread function to update the mnemoscheme SVG in the UI with the provided data.

    Args:
        client (mqtt.Client): The MQTT client instance to publish the data.
        data (dict): The data to update the chart with.
    """

    power_system = SvgMainScheme(client=client,
                                 block_name="power_system",
                                 data_upper_bound=18,
                                 data_lower_bound=5)

    power_system_status = "OK"
    flow_animation_state = SvgFlowAnimations.PUMP_FLOW_OFF.value
    block_hatch_pattern = SvgBlockHatchPatterns.NORMAL.value

    # Code to update the mnemoscheme SVG in the UI goes here
    while not stop_event.is_set():
        if not wait_for_ui_runtime():
            break

        try:
            data = power_system_status_queue.get(timeout=0.5)
            logger.debug(f"Updating mnemoscheme SVG with data: {data}")

            indicator_value_color = SvgSvhemeColors.NORMAL.value

            if data["power_consumption"] < 15 and data["power_consumption"] > 8:
                indicator_value_color = SvgSvhemeColors.WARNING.value
                power_system_status = SvgSchemaPowerConnectionStatusTexts.ON.value
                flow_animation_state = SvgFlowAnimations.POWER_CONN_ANIM_ON.value
                block_hatch_pattern = SvgBlockHatchPatterns.WARNING.value

            elif data["power_consumption"] < 8 or data["power_consumption"] > 18:
                power_system.set_error(f"Power consumption out of range: {data['power_consumption']} W",
                                       "system-power-module-block-err-sign-id",
                                       error_set_flag=True)
                indicator_value_color = SvgSvhemeColors.CRITICAL.value
                power_system_status = SvgSchemaPowerConnectionStatusTexts.FAULT.value
                flow_animation_state = SvgFlowAnimations.POWER_CONN_ANIM_OFF.value
                block_hatch_pattern = SvgBlockHatchPatterns.CRITICAL.value

            else:
                power_system.set_error(f"Power consumption within range: {data['power_consumption']} W",
                                       "system-power-module-block-err-sign-id",
                                       error_set_flag=False)
                power_system_status = SvgSchemaPowerConnectionStatusTexts.ON.value
                indicator_value_color = SvgSvhemeColors.NORMAL.value
                flow_animation_state = SvgFlowAnimations.POWER_CONN_ANIM_ON.value
                block_hatch_pattern = SvgBlockHatchPatterns.NORMAL.value

            power_system.set_indicator_value("power-system-status-text-id",
                                             power_system_status,
                                             indicator_value_color)
            power_system.set_indicator_value("power-system-power-consumption-text-id",
                                             data["power_consumption"],
                                             indicator_value_color)
            power_system.set_symbol_color("system-power-module-block-status-led-id",
                                          indicator_value_color)

            power_system.set_flow_animation("power-conn-anim-id",
                                            attribute_value=flow_animation_state)

            power_system.set_block_hatch_pattern("system-power-module-block-id",
                                                pattern=block_hatch_pattern)

            power_system_status_queue.task_done()

        except queue.Empty:
            continue


def ui_svg_vacuum_pump_thread(client):
    """
    Thread function to update the main heating furnace vacuum pump

    Args:
        client (mqtt.Client): The MQTT client instance to publish the data.
    """

    vacuum_pump = SvgMainScheme(client=client,
                                block_name="vacuum_pump",
                                data_upper_bound=0,
                                data_lower_bound=0)

    while not stop_event.is_set():
        if not wait_for_ui_runtime():
            break

        try:
            data = vacuum_pump_queue.get(timeout=0.5)

            match data["vacuum_pump_status"]:
                case SvgSystemStates.ON.value:
                    vacuum_pump.set_indicator_value("vacuum-pump-status-text-id",
                                                    SvgSchemePumpStatusTexts.OPEN.value,
                                                    SvgSvhemeColors.NORMAL.value)
                    vacuum_pump.set_flow_animation("vacuum-pipe-anim-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_ON.value)
                    vacuum_pump.set_flow_animation("vacuum-pipe-anim-1-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_ON.value)
                    vacuum_pump.set_valve_state("vacuum-pump-valve-id", True)
                    vacuum_pump.set_symbol_color("vacuum-pump-symbol-id",
                                                SvgSvhemeColors.NORMAL.value)
                    vacuum_pump.set_indicator_value("vacuum-pump-valve-status-text-id",
                                                     SvgSchemePumpStatusTexts.OPEN.value,
                                                     SvgSvhemeColors.NORMAL.value)
                    vacuum_pump.set_error(f"pump status: {data['vacuum_pump_status']}",
                                            "vacuum-pump-err-sign-id",
                                            error_set_flag=False)

                case SvgSystemStates.OFF.value:
                    vacuum_pump.set_indicator_value("vacuum-pump-status-text-id",
                                                    SvgSchemePumpStatusTexts.CLOSED.value,
                                                    SvgSvhemeColors.OFF.value)
                    vacuum_pump.set_flow_animation("vacuum-pipe-anim-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    vacuum_pump.set_flow_animation("vacuum-pipe-anim-1-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    vacuum_pump.set_valve_state("vacuum-pump-valve-id", False)
                    vacuum_pump.set_symbol_color("vacuum-pump-symbol-id",
                                                SvgSvhemeColors.OFF.value)
                    vacuum_pump.set_indicator_value("vacuum-pump-valve-status-text-id",
                                                     SvgSchemePumpStatusTexts.CLOSED.value,
                                                     SvgSvhemeColors.OFF.value)
                    vacuum_pump.set_error(f"pump status: {data['vacuum_pump_status']}",
                                            "vacuum-pump-err-sign-id",
                                            error_set_flag=False)

                case SvgSystemStates.FAULT.value:
                    vacuum_pump.set_indicator_value("vacuum-pump-status-text-id",
                                                    SvgSchemePumpStatusTexts.FAULT.value,
                                                    SvgSvhemeColors.CRITICAL.value)
                    vacuum_pump.set_flow_animation("vacuum-pipe-anim-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    vacuum_pump.set_flow_animation("vacuum-pipe-anim-1-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    vacuum_pump.set_valve_state("vacuum-pump-valve-id", False)
                    vacuum_pump.set_symbol_color("vacuum-pump-symbol-id",
                                                SvgSvhemeColors.CRITICAL.value)
                    vacuum_pump.set_indicator_value("vacuum-pump-valve-status-text-id",
                                                     SvgSchemePumpStatusTexts.FAULT.value,
                                                     SvgSvhemeColors.CRITICAL.value)
                    vacuum_pump.set_error(f"pump status: {data['vacuum_pump_status']}",
                                            "vacuum-pump-err-sign-id",
                                            error_set_flag=True)

                # default case where the pump is closed
                case _:
                    vacuum_pump.set_indicator_value("vacuum-pump-status-text-id",
                                                    SvgSchemePumpStatusTexts.CLOSED.value,
                                                    SvgSvhemeColors.OFF.value)
                    vacuum_pump.set_flow_animation("vacuum-pipe-anim-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    vacuum_pump.set_flow_animation("vacuum-pipe-anim-1-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    vacuum_pump.set_valve_state("vacuum-pump-valve-id", False)
                    vacuum_pump.set_symbol_color("vacuum-pump-symbol-id",
                                                SvgSvhemeColors.OFF.value)
                    vacuum_pump.set_indicator_value("vacuum-pump-valve-status-text-id",
                                                     SvgSchemePumpStatusTexts.CLOSED.value,
                                                     SvgSvhemeColors.OFF.value)
                    vacuum_pump.set_error(f"pump status: {data['vacuum_pump_status']}",
                                            "vacuum-pump-err-sign-id",
                                            error_set_flag=False)

            vacuum_pump_queue.task_done()

        except queue.Empty:
            continue


def ui_svg_coolant_pump_thread(client):
    """
    Thread function to update the main heating furnace coolant pump

    Args:
        client (mqtt.Client): The MQTT client instance to publish the data.
    """

    # Code to update the main heating furnace SVG in the UI goes here
    coolant_pump = SvgMainScheme(client=client,
                                 block_name="coolant_pump",
                                 data_upper_bound=0,
                                 data_lower_bound=0)

    while not stop_event.is_set():
        if not wait_for_ui_runtime():
            break

        try:
            data = coolant_pump_queue.get(timeout=0.5)

            match data["coolant_pump_status"]:
                case SvgSystemStates.ON.value:
                    coolant_pump.set_indicator_value("furnace-coolant-pump-status-text-id",
                                                    SvgSchemePumpStatusTexts.OPEN.value,
                                                    SvgSvhemeColors.NORMAL.value)
                    coolant_pump.set_flow_animation("furnace-coolant-pipe-anim-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_ON.value)
                    coolant_pump.set_flow_animation("furnace-coolant-pipe-anim-1-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_REVERSE.value)
                    coolant_pump.set_valve_state("furnace-cooling-pump-valve-id", True)
                    coolant_pump.set_symbol_color("furnace-coolant-pump-symbol-id",
                                                SvgSvhemeColors.NORMAL.value)
                    coolant_pump.set_indicator_value("furnace-coolant-pump-valve-status-text-id",
                                                     SvgSchemePumpStatusTexts.OPEN.value,
                                                     SvgSvhemeColors.NORMAL.value)
                    coolant_pump.set_error(f"pump status: {data['coolant_pump_status']}",
                                            "furnace-coolant-pump-err-sign-id",
                                            error_set_flag=False)

                case SvgSystemStates.OFF.value:
                    coolant_pump.set_indicator_value("furnace-coolant-pump-status-text-id",
                                                    SvgSchemePumpStatusTexts.CLOSED.value,
                                                    SvgSvhemeColors.OFF.value)
                    coolant_pump.set_flow_animation("furnace-coolant-pipe-anim-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    coolant_pump.set_flow_animation("furnace-coolant-pipe-anim-1-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    coolant_pump.set_valve_state("furnace-cooling-pump-valve-id", False)
                    coolant_pump.set_symbol_color("furnace-coolant-pump-symbol-id",
                                                SvgSvhemeColors.OFF.value)
                    coolant_pump.set_indicator_value("furnace-coolant-pump-valve-status-text-id",
                                                     SvgSchemePumpStatusTexts.CLOSED.value,
                                                     SvgSvhemeColors.OFF.value)
                    coolant_pump.set_error(f"pump status: {data['coolant_pump_status']}",
                                            "furnace-coolant-pump-err-sign-id",
                                            error_set_flag=False)

                case SvgSystemStates.FAULT.value:
                    coolant_pump.set_indicator_value("furnace-coolant-pump-status-text-id",
                                                    SvgSchemePumpStatusTexts.FAULT.value,
                                                    SvgSvhemeColors.CRITICAL.value)
                    coolant_pump.set_flow_animation("furnace-coolant-pipe-anim-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    coolant_pump.set_flow_animation("furnace-coolant-pipe-anim-1-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    coolant_pump.set_valve_state("furnace-cooling-pump-valve-id", False)
                    coolant_pump.set_symbol_color("furnace-coolant-pump-symbol-id",
                                                    SvgSvhemeColors.CRITICAL.value)
                    coolant_pump.set_indicator_value("furnace-coolant-pump-valve-status-text-id",
                                                     SvgSchemePumpStatusTexts.FAULT.value,
                                                     SvgSvhemeColors.CRITICAL.value)
                    coolant_pump.set_error(f"Invalid coolant pump status: {data['coolant_pump_status']}",
                                            "furnace-coolant-pump-err-sign-id",
                                            error_set_flag=True)

                # default case where the pump is closed
                case _:
                    coolant_pump.set_indicator_value("furnace-coolant-pump-status-text-id",
                                                    SvgSchemePumpStatusTexts.CLOSED.value,
                                                    SvgSvhemeColors.OFF.value)
                    coolant_pump.set_flow_animation("furnace-coolant-pipe-anim-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    coolant_pump.set_flow_animation("furnace-coolant-pipe-anim-1-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    coolant_pump.set_valve_state("furnace-cooling-pump-valve-id", False)
                    coolant_pump.set_symbol_color("furnace-coolant-pump-symbol-id",
                                                SvgSvhemeColors.OFF.value)
                    coolant_pump.set_indicator_value("furnace-coolant-pump-valve-status-text-id",
                                                     SvgSchemePumpStatusTexts.CLOSED.value,
                                                     SvgSvhemeColors.OFF.value)
                    coolant_pump.set_error(f"Invalid coolant pump status: {data['coolant_pump_status']}",
                                            "furnace-coolant-pump-err-sign-id",
                                            error_set_flag=True)

            coolant_pump_queue.task_done()

        except queue.Empty:
            continue


def ui_svg_main_smelting_form_thread(client):
    """
    Thread function to update the main smelting form SVG in the UI with the provided data.

    Args:
        client (mqtt.Client): The MQTT client instance to publish the data.
    """

    smelting_form = SvgMainScheme(client=client,
                                 block_name="smelting_form",
                                 data_upper_bound=2000,
                                 data_lower_bound=0)

    while not stop_event.is_set():
        if not wait_for_ui_runtime():
            break

        try:
            data = smelting_form_temp_queue.get(timeout=0.5)

            logger.debug(f"Updating main smelting form SVG with data: {data}")

            # Check if temperature is within normal range and set error if not
            if data["smelting_form_temperature"] < 1500 or data["smelting_form_temperature"] > 1550:
                smelting_form.set_error(f"Smelting form temperature out of range: {data['smelting_form_temperature']} °C",
                                        "smelting-form-temp-err-sign-id",
                                        error_set_flag=True)

                smelting_form.set_indicator_value("smelting-form-temp-text-id",
                                                  data['smelting_form_temperature'],
                                                  SvgSvhemeColors.CRITICAL.value)

                smelting_form.set_symbol_color("smelting-form-symbol-id",
                                                SvgSvhemeColors.CRITICAL.value)

            else:
                smelting_form.set_error(f"Smelting form temperature within range: {data['smelting_form_temperature']} °C",
                                        "smelting-form-temp-err-sign-id",
                                        error_set_flag=False)

                smelting_form.set_indicator_value("smelting-form-temp-text-id",
                                                  data['smelting_form_temperature'],
                                                  SvgSvhemeColors.NORMAL.value)

                smelting_form.set_symbol_color("smelting-form-symbol-id",
                                                SvgSvhemeColors.NORMAL.value)

            smelting_form_temp_queue.task_done()

        except queue.Empty:
            continue


def ui_svg_form_heating_furnace_thread(client):
    """
    Thread function to update the main heating furnace SVG in the UI with the provided data.

    Args:
        client (mqtt.Client): The MQTT client instance to publish the data.
    """

    heating_furnace = SvgMainScheme(client=client,
                                 block_name="form_heating_furnace",
                                 data_upper_bound=2000,
                                 data_lower_bound=0)

    while not stop_event.is_set():
        if not wait_for_ui_runtime():
            break

        try:
            data = form_heating_furnace_temp_queue.get(timeout=0.5)

            # Check if temperature is within normal range and set error if not
            if data["form_heating_furnace_temperature"] < 1500 or data["form_heating_furnace_temperature"] > 1550:
                heating_furnace.set_error(f"Form heating furnace temperature out of range: {data['form_heating_furnace_temperature']} °C",
                                        "form-heating-furnace-err-sign-id",
                                        error_set_flag=True)

                heating_furnace.set_indicator_value("smelting-form-heating-furnace-temp-text-id",
                                                  data['form_heating_furnace_temperature'],
                                                  SvgSvhemeColors.CRITICAL.value)

                heating_furnace.set_symbol_color("smelting-form-heating-furnace-symbol-id",
                                                SvgSvhemeColors.CRITICAL.value)

            else:
                heating_furnace.set_error(f"Form heating furnace temperature within range: {data['form_heating_furnace_temperature']} °C",
                                        "form-heating-furnace-err-sign-id",
                                        error_set_flag=False)

                heating_furnace.set_indicator_value("smelting-form-heating-furnace-temp-text-id",
                                                  data['form_heating_furnace_temperature'],
                                                  SvgSvhemeColors.NORMAL.value)

                heating_furnace.set_symbol_color("smelting-form-heating-furnace-symbol-id",
                                                SvgSvhemeColors.NORMAL.value)

            form_heating_furnace_temp_queue.task_done()

        except queue.Empty:
            continue


def ui_svg_furnace_vacuum_thread(client):
    """
    Thread function to update the main heating furnace vacuum status in the SVG in
    the UI with the provided data.

    Args:
        client (mqtt.Client): The MQTT client instance to publish the data.
    """

    furnace_vacuum = SvgMainScheme(client=client,
                                 block_name="furnace_vacuum",
                                 data_upper_bound=8,
                                 data_lower_bound=0)

    while not stop_event.is_set():
        if not wait_for_ui_runtime():
            break

        try:
            data = vacuum_value_queue.get(timeout=0.5)

            # Check if vacuum value is within normal range and set error if not
            if data["vacuum"] < 5 or data["vacuum"] > 8:
                furnace_vacuum.set_error(f"Furnace vacuum out of range: {data['vacuum']} Pa",
                                        "vacuum-chamber-preasure-err-sign-id",
                                        error_set_flag=True)

                furnace_vacuum.set_indicator_value("vacuum-in-chamber-text-id",
                                                  data['vacuum'],
                                                  SvgSvhemeColors.CRITICAL.value)

                furnace_vacuum.set_block_hatch_pattern("vacuum-chamber-module-block-id",
                                                        pattern=SvgBlockHatchPatterns.CRITICAL.value)

            else:
                furnace_vacuum.set_error(f"Furnace vacuum within range: {data['vacuum']} Pa",
                                        "vacuum-chamber-preasure-err-sign-id",
                                        error_set_flag=False)

                furnace_vacuum.set_indicator_value("vacuum-in-chamber-text-id",
                                                  data['vacuum'],
                                                  SvgSvhemeColors.NORMAL.value)

                furnace_vacuum.set_block_hatch_pattern("vacuum-chamber-module-block-id",
                                                        pattern=SvgBlockHatchPatterns.NORMAL.value)

            vacuum_value_queue.task_done()

        except queue.Empty:
            continue


def ui_svg_actuator_thread(client):
    """
    Thread function to update the actuator status in the SVG in the UI with the
    provided data.

    Args:
        client (mqtt.Client): The MQTT client instance to publish the data.
    """

    actuator_scheme = SvgMainScheme(client=client,
                                 block_name="actuator",
                                 data_upper_bound=100,
                                 data_lower_bound=0)

    logger.debug("Starting actuator thread")

    while not stop_event.is_set():
        if not wait_for_ui_runtime():
            break

        try:
            data = actuator_queue_speed.get(timeout=0.5)
            logger.debug(f"Actuator data received: {data}")

            match data["status"]:
                case "OK":
                    actuator_scheme.set_symbol_color("actuator-motor-symbol-id",
                                                     SvgSvhemeColors.NORMAL.value)
                    actuator_scheme.set_error(f"Actuator status: {data['status']}",
                                              "actuator-status-err-sign-id",
                                              error_set_flag=False)
                    actuator_scheme.set_block_hatch_pattern("actuator-speed-module-block-id",
                                                        pattern=SvgBlockHatchPatterns.NORMAL.value)
                    actuator_scheme.set_indicator_value("actuator-speed-value-text-id",
                                                    data['speed'],
                                                    SvgSvhemeColors.NORMAL.value)
                case "WARNING":
                    actuator_scheme.set_symbol_color("actuator-motor-symbol-id",
                                                     SvgSvhemeColors.WARNING.value)
                    actuator_scheme.set_error(f"Actuator status: {data['status']}",
                                              "actuator-status-err-sign-id",
                                              error_set_flag=False)
                    actuator_scheme.set_block_hatch_pattern("actuator-speed-module-block-id",
                                                        pattern=SvgBlockHatchPatterns.WARNING.value)
                    actuator_scheme.set_indicator_value("actuator-speed-value-text-id",
                                                    data['speed'],
                                                    SvgSvhemeColors.WARNING.value)
                case "CRITICAL":
                    actuator_scheme.set_symbol_color("actuator-motor-symbol-id",
                                                     SvgSvhemeColors.CRITICAL.value)
                    actuator_scheme.set_error(f"Actuator status: {data['status']}",
                                              "actuator-status-err-sign-id",
                                              error_set_flag=True)
                    actuator_scheme.set_block_hatch_pattern("actuator-speed-module-block-id",
                                                        pattern=SvgBlockHatchPatterns.CRITICAL.value)

                    actuator_scheme.set_indicator_value("actuator-speed-value-text-id",
                                                    data['speed'],
                                                    SvgSvhemeColors.CRITICAL.value)
                case _:
                    actuator_scheme.set_symbol_color("actuator-motor-symbol-id",
                                                     SvgSvhemeColors.OFF.value)
                    actuator_scheme.set_error(f"Actuator status: {data['status']}",
                                              "actuator-status-err-sign-id",
                                              error_set_flag=False)
                    actuator_scheme.set_block_hatch_pattern("actuator-speed-module-block-id",
                                                        pattern=SvgBlockHatchPatterns.NORMAL.value)
                    actuator_scheme.set_indicator_value("actuator-speed-value-text-id",
                                                    data['speed'],
                                                    SvgSvhemeColors.OFF.value)

            logger.debug(f"Updating actuator position with data: {data}")

            actuator_queue_speed.task_done()

        except queue.Empty:
            continue

        except KeyError as e:
            logger.error(f"KeyError in actuator thread: {e}")

            continue


def ui_svg_aluminium_heating_furnace_thread(client):
    """
    Thread function to update the aluminium heating furnace temperature in the SVG in the UI with the
    provided data.

    Args:
        client (mqtt.Client): The MQTT client instance to publish the data.
    """

    aluminium_heating_furnace = SvgMainScheme(client=client,
                                 block_name="aluminium_heating_furnace",
                                 data_upper_bound=2000,
                                 data_lower_bound=0)

    while not stop_event.is_set():
        if not wait_for_ui_runtime():
            break

        try:
            data = aluminium_heating_furnace_queue.get(timeout=0.5)

            match data["status"]:

                case SvgSystemStates.ON.value:
                    aluminium_heating_furnace.set_symbol_color("aluminium-heating-furnace-symbol-id",
                                                            SvgSvhemeColors.NORMAL.value)
                    aluminium_heating_furnace.set_indicator_value("aluminium-heating-furnace-temp-text-id",
                                                                data["temperature"],
                                                                SvgSvhemeColors.NORMAL.value)
                    aluminium_heating_furnace.set_error(f"Aluminium heating furnace status: {data['status']}, temperature: {data['temperature']} °C",
                                                     "aluminium-heating-furnace-err-sign-id",
                                                     error_set_flag=False)
                    aluminium_heating_furnace.set_block_hatch_pattern("aluminium-tank-module-block-id",
                                                                     pattern=SvgBlockHatchPatterns.NORMAL.value)
                case SvgSystemStates.OFF.value:
                    aluminium_heating_furnace.set_symbol_color("aluminium-heating-furnace-symbol-id",
                                                            SvgSvhemeColors.OFF.value)
                    aluminium_heating_furnace.set_indicator_value("aluminium-heating-furnace-temp-text-id",
                                                                data["temperature"],
                                                                SvgSvhemeColors.OFF.value)
                    aluminium_heating_furnace.set_error(f"Aluminium heating furnace status: {data['status']}, temperature: {data['temperature']} °C",
                                                     "aluminium-heating-furnace-err-sign-id",
                                                     error_set_flag=False)
                    aluminium_heating_furnace.set_block_hatch_pattern("aluminium-tank-module-block-id",
                                                                     pattern=SvgBlockHatchPatterns.NORMAL.value)
                case SvgSystemStates.FAULT.value:
                    aluminium_heating_furnace.set_symbol_color("aluminium-heating-furnace-symbol-id",
                                                            SvgSvhemeColors.CRITICAL.value)
                    aluminium_heating_furnace.set_indicator_value("aluminium-heating-furnace-temp-text-id",
                                                                data["temperature"],
                                                                SvgSvhemeColors.CRITICAL.value)
                    aluminium_heating_furnace.set_error(f"Aluminium heating furnace status: {data['status']}, temperature: {data['temperature']} °C",
                                                     "aluminium-heating-furnace-err-sign-id",
                                                     error_set_flag=True)
                    aluminium_heating_furnace.set_block_hatch_pattern("aluminium-tank-module-block-id",
                                                                     pattern=SvgBlockHatchPatterns.CRITICAL.value)
                case _:
                    aluminium_heating_furnace.set_symbol_color("aluminium-heating-furnace-symbol-id",
                                                            SvgSvhemeColors.OFF.value)
                    aluminium_heating_furnace.set_indicator_value("aluminium-heating-furnace-temp-text-id",
                                                                data["temperature"],
                                                                SvgSvhemeColors.OFF.value)
                    aluminium_heating_furnace.set_error(f"Aluminium heating furnace status: {data['status']}, temperature: {data['temperature']} °C",
                                                     "aluminium-heating-furnace-err-sign-id",
                                                     error_set_flag=False)
                    aluminium_heating_furnace.set_block_hatch_pattern("aluminium-tank-module-block-id",
                                                                     pattern=SvgBlockHatchPatterns.NORMAL.value)

            aluminium_heating_furnace_queue.task_done()

        except queue.Empty:
            continue

        except KeyError as e:
            logger.error(f"KeyError in aluminium heating furnace thread: {e}")

            continue


def ui_svg_alloy_in_chamber_thread(client):
    """
    Thread function to update the alloy presence in the chamber status in the SVG in the UI with the
    provided data.

    Args:
        client (mqtt.Client): The MQTT client instance to publish the data.
    """

    alloy_in_chamber = SvgMainScheme(client=client,
                                 block_name="alloy_in_chamber",
                                 data_upper_bound=0,
                                 data_lower_bound=0)

    while not stop_event.is_set():
        if not wait_for_ui_runtime():
            break

        try:
            data = alloy_in_chamber_queue.get(timeout=0.5)

            match data["alloy_in_chamber"]:
                case SvgSchemeAlloyinChamberStatusTexts.PRESENT.value:
                    alloy_in_chamber.set_indicator_value("alloy-status-in-chamber-text-id",
                                                        SvgSchemeAlloyinChamberStatusTexts.PRESENT.value,
                                                        SvgSvhemeColors.NORMAL.value)

                    alloy_in_chamber.set_error(f"Alloy in chamber status: {data['alloy_in_chamber']}",
                                               "alloy-in-chamber-module-block-err-sign-id",
                                               error_set_flag=False)

                    alloy_in_chamber.set_block_hatch_pattern("alloy-in-chamber-module-block-id",
                                                            pattern=SvgBlockHatchPatterns.NORMAL.value)

                case SvgSchemeAlloyinChamberStatusTexts.ABSCENT.value:
                    alloy_in_chamber.set_indicator_value("alloy-status-in-chamber-text-id",
                                                        SvgSchemeAlloyinChamberStatusTexts.ABSCENT.value,
                                                        SvgSvhemeColors.CRITICAL.value)

                    alloy_in_chamber.set_error(f"Alloy in chamber status: {data['alloy_in_chamber']}",
                                               "alloy-in-chamber-module-block-err-sign-id",
                                               error_set_flag=True)

                    alloy_in_chamber.set_block_hatch_pattern("alloy-in-chamber-module-block-id",
                                                             pattern=SvgBlockHatchPatterns.CRITICAL.value)
                case _:
                    alloy_in_chamber.set_indicator_value("alloy-status-in-chamber-text-id",
                                                        "---",
                                                        SvgSvhemeColors.NORMAL.value)

                    alloy_in_chamber.set_error(f"Unknown alloy in chamber status: {data['alloy_in_chamber']}",
                                               "alloy-in-chamber-module-block-err-sign-id",
                                               error_set_flag=True)

                    alloy_in_chamber.set_block_hatch_pattern("alloy-in-chamber-module-block-id",
                                                             pattern=SvgBlockHatchPatterns.NORMAL.value)

            alloy_in_chamber_queue.task_done()

        except queue.Empty:
            continue

        except KeyError as e:
            logger.error(f"KeyError in alloy in chamber thread: {e}")


def ui_svg_aluminium_temperature_thread(client):
    """
    Thread function to update the aluminium temperature in the SVG in the UI with the
    provided data.

    Args:
        client (mqtt.Client): The MQTT client instance to publish the data.
    """

    aluminium_temperature = SvgMainScheme(client=client,
                                 block_name="aluminium_temperature",
                                 data_upper_bound=850,
                                 data_lower_bound=0)

    while not stop_event.is_set():
        if not wait_for_ui_runtime():
            break

        try:
            data = aluminium_temperature_queue.get(timeout=0.5)

            # Check if temperature is within normal range and set error if not
            if data["temperature"] < 790 or data["temperature"] > 850:
                aluminium_temperature.set_error(f"Aluminium temperature out of range: {data['temperature']} °C",
                                        "aluminium-tank-temperature-err-sign-id",
                                        error_set_flag=True)

                aluminium_temperature.set_indicator_value("aluminium-temp-value-text-id",
                                                  data['temperature'],
                                                  SvgSvhemeColors.CRITICAL.value)

                aluminium_temperature.set_symbol_color("aluminium-tank-symbol-id",
                                                SvgSvhemeColors.CRITICAL.value)

            else:
                aluminium_temperature.set_error(f"Aluminium temperature within range: {data['temperature']} °C",
                                        "aluminium-tank-temperature-err-sign-id",
                                        error_set_flag=False)

                aluminium_temperature.set_indicator_value("aluminium-temp-value-text-id",
                                                  data['temperature'],
                                                  SvgSvhemeColors.NORMAL.value)

                aluminium_temperature.set_symbol_color("aluminium-tank-symbol-id",
                                                SvgSvhemeColors.NORMAL.value)

            aluminium_temperature_queue.task_done()

        except queue.Empty:
            continue

        except KeyError as e:
            logger.error(f"KeyError in aluminium temperature thread: {e}")

            continue


def ui_svg_aluminium_coolant_pump_thread(client):
    """
    Thread function to update the aluminium coolant pump status in the SVG in the UI with the
    provided data.

    Args:
        client (mqtt.Client): The MQTT client instance to publish the data.
    """

    aluminium_coolant_pump = SvgMainScheme(client=client,
                                 block_name="aluminium_coolant_pump",
                                 data_upper_bound=0,
                                 data_lower_bound=0)

    while not stop_event.is_set():
        if not wait_for_ui_runtime():
            break

        try:
            data = aluminium_coolant_pump_queue.get(timeout=0.5)

            match data["aluminium_coolant_pump_status"]:
                case SvgSystemStates.ON.value:
                    aluminium_coolant_pump.set_indicator_value("aluminium-coolant-pump-status-text-id",
                                                               SvgSchemePumpStatusTexts.OPEN.value,
                                                               SvgSvhemeColors.NORMAL.value)

                    aluminium_coolant_pump.set_flow_animation("aluminium-coolant-pipe-anim-id",
                                                              attribute_value=SvgFlowAnimations.PUMP_FLOW_ON.value)
                    aluminium_coolant_pump.set_flow_animation("aluminium-coolant-pipe-anim-1-id",
                                                              attribute_value=SvgFlowAnimations.PUMP_FLOW_ON.value)

                    aluminium_coolant_pump.set_valve_state("aluminium-cooling-pump-valve-id", True)
                    aluminium_coolant_pump.set_indicator_value("aluminium-coolant-pump-valve-status-text-id",
                                                               SvgSchemePumpStatusTexts.OPEN.value,
                                                               SvgSvhemeColors.NORMAL.value)

                    aluminium_coolant_pump.set_symbol_color("aluminium-coolant-pump-symbol-id",
                                                            SvgSvhemeColors.NORMAL.value)

                    aluminium_coolant_pump.set_error(f"pump status: {data['aluminium_coolant_pump_status']}",
                                                     "aluminium-cooling-pump-err-sign-id",
                                                     error_set_flag=False)

                case SvgSystemStates.OFF.value:
                    aluminium_coolant_pump.set_indicator_value("aluminium-coolant-pump-status-text-id",
                                                    SvgSchemePumpStatusTexts.CLOSED.value,
                                                    SvgSvhemeColors.OFF.value)
                    aluminium_coolant_pump.set_flow_animation("aluminium-coolant-pipe-anim-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    aluminium_coolant_pump.set_flow_animation("aluminium-coolant-pipe-anim-1-id",
                                                              attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    aluminium_coolant_pump.set_valve_state("aluminium-cooling-pump-valve-id", False)
                    aluminium_coolant_pump.set_symbol_color("aluminium-coolant-pump-symbol-id",
                                                SvgSvhemeColors.OFF.value)
                    aluminium_coolant_pump.set_indicator_value("aluminium-coolant-pump-valve-status-text-id",
                                                     SvgSchemePumpStatusTexts.CLOSED.value,
                                                     SvgSvhemeColors.OFF.value)
                    aluminium_coolant_pump.set_error(f"pump status: {data['aluminium_coolant_pump_status']}",
                                            "aluminium-cooling-pump-err-sign-id",
                                            error_set_flag=False)

                case SvgSystemStates.FAULT.value:
                    aluminium_coolant_pump.set_indicator_value("aluminium-coolant-pump-status-text-id",
                                                    SvgSchemePumpStatusTexts.FAULT.value,
                                                    SvgSvhemeColors.CRITICAL.value)
                    aluminium_coolant_pump.set_flow_animation("aluminium-coolant-pipe-anim-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    aluminium_coolant_pump.set_flow_animation("aluminium-coolant-pipe-anim-1-id",
                                                              attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    aluminium_coolant_pump.set_valve_state("aluminium-cooling-pump-valve-id", False)
                    aluminium_coolant_pump.set_symbol_color("aluminium-coolant-pump-symbol-id",
                                                SvgSvhemeColors.CRITICAL.value)
                    aluminium_coolant_pump.set_indicator_value("aluminium-coolant-pump-valve-status-text-id",
                                                     SvgSchemePumpStatusTexts.FAULT.value,
                                                     SvgSvhemeColors.CRITICAL.value)
                    aluminium_coolant_pump.set_error(f"pump status: {data['aluminium_coolant_pump_status']}",
                                            "aluminium-cooling-pump-err-sign-id",
                                            error_set_flag=True)

                # default case where the pump is closed
                case _:
                    aluminium_coolant_pump.set_indicator_value("aluminium-coolant-pump-status-text-id",
                                                    SvgSchemePumpStatusTexts.CLOSED.value,
                                                    SvgSvhemeColors.OFF.value)
                    aluminium_coolant_pump.set_flow_animation("aluminium-coolant-pipe-anim-id",
                                                attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    aluminium_coolant_pump.set_flow_animation("aluminium-coolant-pipe-anim-1-id",
                                                              attribute_value=SvgFlowAnimations.PUMP_FLOW_OFF.value)
                    aluminium_coolant_pump.set_valve_state("aluminium-cooling-pump-valve-id", False)
                    aluminium_coolant_pump.set_symbol_color("aluminium-coolant-pump-symbol-id",
                                                SvgSvhemeColors.OFF.value)
                    aluminium_coolant_pump.set_indicator_value("aluminium-coolant-pump-valve-status-text-id",
                                                     SvgSchemePumpStatusTexts.CLOSED.value,
                                                     SvgSvhemeColors.OFF.value)
                    aluminium_coolant_pump.set_error(f"pump status: {data['aluminium_coolant_pump_status']}",
                                            "aluminium-cooling-pump-err-sign-id",
                                            error_set_flag=True)

            aluminium_coolant_pump_queue.task_done()
        except queue.Empty:
            continue


def ui_gauges_furnace_temp_thread(client):
    """
    Thread function to update the furnace temperature gauges in the UI with the provided data.

    Args:
        client (mqtt.Client): The MQTT client instance to publish the data.
    """

    gauges = UiCharts(chart_name="furnace_temperatures",
                     min_value=0,
                     max_value=2000,
                     chart_type=ChartType.GAUGE,
                     client=client)

    while not stop_event.is_set():
        if not wait_for_ui_runtime():
            break

        try:
            data = gauge_furnace.get(timeout=0.5)

            logger.debug(f"Updating furnace temperature gauges with data: {data}")

            gauges.update_chart(data)

            gauge_furnace.task_done()
        except queue.Empty:
            continue


def ui_gauges_thermal_couples_thread(client):
    """
    Thread function to update the thermal couples gauges in the UI with the provided data.

    Args:
        client (mqtt.Client): The MQTT client instance to publish the data.
    """

    gauges = UiCharts(chart_name="thermal_couples",
                     min_value=0,
                     max_value=2000,
                     chart_type=ChartType.GAUGE,
                     client=client)

    while not stop_event.is_set():
        if not wait_for_ui_runtime():
            break

        try:
            data = gauge_thermal_couple.get(timeout=0.5)

            logger.debug(f"Updating thermal couples gauges with data: {data}")

            gauges.update_chart(data)

            gauge_thermal_couple.task_done()
        except queue.Empty:
            continue


def ui_charts_lmc_thread(client):
    """
    Thread function to update the LMC charts in the UI with the provided data.

    Args:
        client (mqtt.Client): The MQTT client instance to publish the data.
    """

    charts = UiCharts(chart_name="lmc_charts",
                     min_value=0,
                     max_value=120,
                     chart_type=ChartType.CHART,
                     client=client)

    while not stop_event.is_set():
        if not wait_for_ui_runtime():
            break

        try:
            data = lmc_charts_queue.get(timeout=0.5)

            logger.debug(f"Updating LMC charts with data: {data}")

            charts.update_chart(data)

            lmc_charts_queue.task_done()
        except queue.Empty:
            continue


def ui_charts_actuator_position_thread(client):
    """
    Thread function to update the actuator position chart in the UI with the provided data.

    Args:
        client (mqtt.Client): The MQTT client instance to publish the data.
    """

    actuator_position_chart = UiCharts(chart_name="actuator_position",
                                min_value=0,
                                max_value=100,
                                chart_type=ChartType.BAR,
                                client=client)

    while not stop_event.is_set():
        if not wait_for_ui_runtime():
            break

        try:
            data = actuator_queue_position.get(timeout=0.5)

            logger.debug(f"Updating actuator position chart with data: {data}")

            actuator_position_chart.update_chart({"position": data["position"]})

            actuator_queue_position.task_done()
        except queue.Empty:
            continue
        except KeyError as e:
            logger.error(f"KeyError in actuator position chart thread: {e}")

            continue
