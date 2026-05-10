import sys
from enum import Enum

try:
    from common.common import *
    from loguru import logger
    from transport_layer.protocol.mqtt.client import publish_message
except ImportError as e:
    print(f"Error importing modules: {e}")

    sys.exit(1)

class SvgSchemeAlloyinChamberStatusTexts(Enum):
    """Enumeration for different status texts of the alloying chamber in the SVG scheme."""
    PRESENT = "Сплав присутній у камері"
    ABSCENT = "Сплав відсутній у камері"

class SvgSchemePumpStatusTexts(Enum):
    """Enumeration for different status texts used in the SVG scheme."""
    OPEN = "Відкрито"
    CLOSED = "Закрито"
    FAULT = "Аварія"


class SvgSchemaPowerConnectionStatusTexts(Enum):
    """Enumeration for different power connection status texts used in the SVG scheme."""
    ON = "Вкл"
    OFF = "Викл"
    FAULT = "Аварія"

class SvgValveStatesColor(Enum):
    """Enumeration for different states of valves in the SVG scheme."""
    OPEN = "#FFFFFF"  # White
    CLOSED = "#000000"  # Black


class SvgSvhemeColors(Enum):
    """Enumeration for different colors used in the SVG scheme."""
    NORMAL = "#00FF00"  # Green
    WARNING = "#FF9900"  # Orange
    CRITICAL = "#FF0000"  # Red
    OFF = "#808080"  # Gray


class SvgSystemStates(Enum):
    """Enumeration for different states of symbols in the SVG scheme."""
    ON = 0x1
    OFF = 0x0
    FAULT = 0x2


class SvgFlowAnimationStates(Enum):
    """Enumeration for different states of flow animations in the SVG scheme."""
    ON = 0x1
    OFF = 0x0


class SvgBlockHatchPatterns(Enum):
    """Enumeration for different hatch patterns used in the SVG scheme."""
    NORMAL = "url(#mx-pattern-hatch-1.5-_e6e6e6-0)"
    WARNING = "url(#mx-pattern-hatch-orange)"
    CRITICAL = "url(#mx-pattern-hatch-red)"


class SvgFlowAnimations(Enum):
    """Enumeration for different flow animations in the SVG scheme."""
    PUMP_FLOW_ON = "stroke: rgb(0, 110, 175); animation: 500ms linear 0s infinite normal none running ge-flow-animation; stroke-dashoffset: 16; stroke-dasharray: 8;"
    PUMP_FLOW_REVERSE = "stroke: rgb(0, 110, 175); animation: 500ms linear 0s infinite reverse none running ge-flow-animation; stroke-dashoffset: 16; stroke-dasharray: 8;"
    PUMP_FLOW_OFF = "stroke: rgb(128, 128, 128);"
    PLC_CONN_ANIM_ON = "stroke: rgb(81, 255, 0); animation: 500ms linear 0s infinite normal none running ge-flow-animation; stroke-dashoffset: 16; stroke-dasharray: 8;"
    PLC_CONN_ANIM_OFF = "stroke: rgb(128, 128, 128);"
    POWER_CONN_ANIM_ON = "stroke: rgb(255, 255, 0); animation: 500ms linear 0s infinite normal none running ge-flow-animation; stroke-dashoffset: 16; stroke-dasharray: 8;"
    POWER_CONN_ANIM_OFF = "stroke: rgb(128, 128, 128);"


class SvgMainScheme:
    """
    Class representing the SVG scheme for the UVNK-8P process control system.
    """

    def __init__(self, client=None,
                 block_name=None,
                 data_upper_bound=None,
                 data_lower_bound=None):

        self.client = client
        self.block_name = block_name
        self.data_upper_bound = data_upper_bound
        self.data_lower_bound = data_lower_bound


    def set_valve_state(self, valve_id: str, is_open: bool) -> int:
        """
        Updates the SVG scheme with the given valve state.

        Args:
            valve_id (str): The ID of the valve to update.
            is_open (bool): The new state of the valve (True for open, False for closed).
        """

        try:
            color = SvgValveStatesColor.OPEN.value if is_open else SvgValveStatesColor.CLOSED.value

            data = {
                "command": "update_style",
                "selector": f"#{valve_id}",
                "attributeName": "fill",
                "attributeValue": color
            }

            # Check if the block name is set before publishing the message
            if not self.block_name:
                logger.error("Block name is not set for the SVG scheme. Cannot publish message.")
                return EXIT_FAILURE

            if not self.client:
                logger.error("MQTT client is not set for the SVG scheme. Cannot publish message.")
                return EXIT_FAILURE

            topic = f"svg_scheme/{self.block_name}/valves"

            publish_message(self.client, topic, data)
            logger.debug(f"Published data to {topic}")

            return EXIT_SUCCESS

        except KeyError as e:
            logger.error(f"Missing key in data for {self.block_name} SVG scheme: {e}")

            return EXIT_FAILURE


    def set_symbol_color(self, symbol_id: str, color: str) -> int:
        """
        Updates the SVG scheme with the given data.

        Args:
            symbol_id (str): The ID of the symbol to update.
            color (str): The new color to set on the symbol.
        """

        try:
            if color not in [c.value for c in SvgSvhemeColors]:
                logger.error(f"Invalid color value: {color}.")

                return EXIT_FAILURE

            data = {
                "command": "update_style",
                "selector": f"#{symbol_id}",
                "attributeName": "fill",
                "attributeValue": color
            }

            # Check if the block name is set before publishing the message
            if not self.block_name:
                logger.error("Block name is not set for the SVG scheme. Cannot publish message.")
                return EXIT_FAILURE

            if not self.client:
                logger.error("MQTT client is not set for the SVG scheme. Cannot publish message.")
                return EXIT_FAILURE

            topic = f"svg_scheme/{self.block_name}/symbols"

            publish_message(self.client, topic, data)
            logger.debug(f"Published data to {topic}")

            return EXIT_SUCCESS

        except KeyError as e:
            logger.error(f"Missing key in data for {self.block_name} SVG scheme: {e}")

            return EXIT_FAILURE

        except Exception as e:
            logger.error(f"Error updating {self.block_name} SVG scheme: {e}")

            return EXIT_FAILURE


    def set_indicator_value(self, text_id: str, value: float | str, color: str) -> None:
        """
        Updates the measurement indicators in the SVG scheme with the given data.

        Args:
            text_id (str): The ID of the text element to update.
            value (float): The new value to set on the measurement indicators in the SVG scheme.
            color (str): The color to set on the measurement indicators in the SVG scheme.
        """

        try:
            if color not in [c.value for c in SvgSvhemeColors]:
                logger.error(f"Invalid color value: {color}.")

                return EXIT_FAILURE

            if not self.block_name:
                logger.error("Block name is not set for the SVG scheme. Cannot publish message.")

                return EXIT_FAILURE

            if not self.client:
                logger.error("MQTT client is not set for the SVG scheme. Cannot publish message.")

                return EXIT_FAILURE

            data = [
                {
                    "command": "update_text",
                    "selector": f"#{text_id}",
                    "textContent": "empty"
                },
                {
                    "command": "update_style",
                    "selector": f"#{text_id}",
                    "attributeName": "fill",
                    "attributeValue": color
                }
            ]

            if isinstance(value, (str)):
                data[0]["textContent"] = value
                topic = f"svg_scheme/{self.block_name}/text_indicators"

                publish_message(self.client, topic, data)
                logger.debug(f"Published data to {topic}")

                return EXIT_SUCCESS

            if isinstance(value, (int, float)) and \
            (self.data_lower_bound <= value <= self.data_upper_bound):
                data[0]["textContent"] = f"{value:.2f}"
                topic = f"svg_scheme/{self.block_name}/measurement_indicators"

                publish_message(self.client, topic, data)
                logger.debug(f"Published data to {topic}")

                return EXIT_SUCCESS

            return EXIT_FAILURE

        except KeyError as e:
            logger.error(f"Missing key in data for {self.block_name} SVG scheme: {e}")

            return EXIT_FAILURE

        except Exception as e:
            logger.error(f"Error updating text in {self.block_name} SVG scheme: {e}")

            return EXIT_FAILURE


    def set_flow_animation(self, flow_id: str, attribute_value: str) -> None:
        """
        Sets the animation state of a flow in the SVG scheme.

        Args:
            flow_id (str): The ID of the flow to update.
            attribute_value (str): The value to set for the animation attribute.
        """

        # Code to update the flow animation state in the SVG scheme goes here
        try:
            if not self.block_name:
                logger.error("Block name is not set for the SVG scheme. Cannot publish message.")

                return EXIT_FAILURE

            if not self.client:
                logger.error("MQTT client is not set for the SVG scheme. Cannot publish message.")

                return EXIT_FAILURE

            data = {
                "command": "set_attribute",
                "selector": f"#{flow_id}",
                "attributeName": "style",
                "attributeValue": attribute_value
            }

            topic = f"svg_scheme/{self.block_name}/flow_animations"

            publish_message(self.client, topic, data)
            logger.debug(f"Published data to {topic}")

            return EXIT_SUCCESS

        except KeyError as e:
            logger.error(f"Missing key in data for {self.block_name} SVG scheme: {e}")

            return EXIT_FAILURE

        except Exception as e:
            logger.error(f"Error setting flow animation in {self.block_name} SVG scheme: {e}")

            return EXIT_FAILURE


    def set_error(self, error_message: str, error_sign_id: str, error_set_flag: bool) -> None:
        """
        Sets an error state on the SVG scheme with the given error message.

        Args:
            error_message (str): The error message to display on the SVG scheme.
            error_sign_id (str): The ID of the error sign to update in the SVG scheme.
            error_set_flag (bool): Flag indicating whether to set or clear the error state.
        """

        # Code to set the error state on the SVG scheme goes here
        try:

            if not self.block_name:
                logger.error("Block name is not set for the SVG scheme. Cannot publish message.")

                return EXIT_FAILURE

            if not self.client:
                logger.error("MQTT client is not set for the SVG scheme. Cannot publish message.")

                return EXIT_FAILURE

            logger.error(f"Setting error state in {self.block_name} SVG scheme: {error_message}")

            data = {
                "command": "update_style",
                "selector": f"#{error_sign_id}",
                "attributeName": "visibility",
                "attributeValue": "visible"
            }

            if error_set_flag:
                data["attributeValue"] = "visible"
            else:
                data["attributeValue"] = "hidden"

            topic = f"svg_scheme/{self.block_name}/errors"

            publish_message(self.client, topic, data)
            logger.debug(f"Published data to {topic}")

            return EXIT_SUCCESS

        except KeyError as e:
            logger.error(f"Missing key in data for {self.block_name} SVG scheme: {e}")

            return EXIT_FAILURE

        except Exception as e:
            logger.error(f"Error setting error state in {self.block_name} SVG scheme: {e}")

            return EXIT_FAILURE


    def set_block_hatch_pattern(self, block_id: str, pattern: SvgBlockHatchPatterns) -> None:
        """
        Sets the hatch pattern of a block in the SVG scheme.

        Args:
            block_id (str): The ID of the block to update.
            pattern (SvgBlockHatchPatterns): The hatch pattern to set on the block.
        """

        # Code to update the block hatch pattern in the SVG scheme goes here
        try:
            if not self.block_name:
                logger.error("Block name is not set for the SVG scheme. Cannot publish message.")

                return EXIT_FAILURE

            if not self.client:
                logger.error("MQTT client is not set for the SVG scheme. Cannot publish message.")

                return EXIT_FAILURE

            data = {
                "command": "update_style",
                "selector": f"#{block_id}",
                "attributeName": "fill",
                "attributeValue": pattern
            }

            topic = f"svg_scheme/{self.block_name}/block_hatches"

            publish_message(self.client, topic, data)
            logger.debug(f"Published data to {topic}")

            return EXIT_SUCCESS

        except KeyError as e:
            logger.error(f"Missing key in data for {self.block_name} SVG scheme: {e}")

            return EXIT_FAILURE

        except Exception as e:
            logger.error(f"Error setting block hatch pattern in {self.block_name} SVG scheme: {e}")

            return EXIT_FAILURE


    def set_element_position(self, element_id: str, x: float, y: float) -> None:
        """
        Sets the position of an element in the SVG scheme.

        Args:
            element_id (str): The ID of the element to update.
            x (float): The new x-coordinate for the element.
            y (float): The new y-coordinate for the element.
        """

        # Code to update the element position in the SVG scheme goes here
        try:
            if not self.block_name:
                logger.error("Block name is not set for the SVG scheme. Cannot publish message.")

                return EXIT_FAILURE

            if not self.client:
                logger.error("MQTT client is not set for the SVG scheme. Cannot publish message.")

                return EXIT_FAILURE

            data = {
                "command": "update_position",
                "selector": f"#{element_id}",
                "x": x,
                "y": y
            }

            topic = f"svg_scheme/{self.block_name}/element_positions"

            publish_message(self.client, topic, data)
            logger.debug(f"Published data to {topic}")

            return EXIT_SUCCESS

        except KeyError as e:
            logger.error(f"Missing key in data for {self.block_name} SVG scheme: {e}")

            return EXIT_FAILURE

        except Exception as e:
            logger.error(f"Error setting element position in {self.block_name} SVG scheme: {e}")

            return EXIT_FAILURE
