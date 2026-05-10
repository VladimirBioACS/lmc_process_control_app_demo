"""General python imports"""
import sys
from enum import Enum

try:
    from common.common import EXIT_FAILURE
    from transport_layer.protocol.mqtt.client import publish_message
except ImportError as e:
    print(f"Error importing modules: {e}")

    sys.exit(1)

try:
    from loguru import logger
except ImportError as e:
    print(f"Error importing modules: {e}")

    sys.exit(EXIT_FAILURE)


class ChartType(Enum):
    """Enumeration for different types of charts."""
    GAUGE = "gauge"
    CHART = "chart"
    BAR = "bar"


class UiCharts:
    """Class for managing UI charts."""

    def __init__(self, chart_name, min_value, max_value, chart_type: ChartType, client=None):
        self.chart_name = chart_name
        self.min_value = min_value
        self.max_value = max_value
        self.chart_type = chart_type
        self.client = client


    def update_chart(self, data: dict) -> None:
        """
        Updates the chart with the given data.

        Args:
            data (dict): The new data to set on the chart.
        """

        numeric_data = {
            key: value for key, value in data.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }

        if not numeric_data:
            logger.warning(f"Skipping {self.chart_name} chart update because it contains no numeric values: {data}")
            return

        if len(numeric_data) != len(data):
            ignored_keys = [key for key in data if key not in numeric_data]
            logger.warning(f"Ignoring non-numeric chart fields for {self.chart_name}: {ignored_keys}")

        if all(self.min_value <= value <= self.max_value for value in numeric_data.values()):
            # Code to update the chart in the UI goes here
            logger.debug(f"Updating {self.chart_name} chart with data: {numeric_data}")
            if self.client:
                publish_message(self.client, f"charts/{self.chart_name}", numeric_data)
                logger.debug(f"Published {self.chart_name} chart data to MQTT topic charts/{self.chart_name}")

        else:
            logger.warning(f"Data {numeric_data} contains values out of range for {self.chart_name} chart")


    def reset_chart(self) -> None:
        """
        Resets the chart to its default state.
        """

        # Code to reset the chart in the UI goes here
        logger.debug(f"Resetting {self.chart_name} chart to default state")

        match self.chart_type:
            case ChartType.GAUGE:
                default_data = 0
            case ChartType.CHART:
                default_data = "[]"
            case ChartType.BAR:
                default_data = 0
            case _:
                logger.error(f"Unsupported chart type: {self.chart_type}")
                return

        if self.client:
            publish_message(self.client, f"charts/{self.chart_name}/reset", default_data)
            logger.debug(f"Published reset data for {self.chart_name} chart to MQTT topic charts/{self.chart_name}/reset")
