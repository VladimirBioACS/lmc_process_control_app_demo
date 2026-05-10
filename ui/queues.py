# Separate queues for separate consumers
import queue
from typing import Any, Dict

# These queues are used to pass data from the PLC to the UI components.
gauge_furnace: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
gauge_thermal_couple: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
lmc_charts_queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
power_system_status_queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
coolant_pump_queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
vacuum_pump_queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
smelting_form_temp_queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
form_heating_furnace_temp_queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
vacuum_value_queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
actuator_queue_speed: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
actuator_queue_position: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
aluminium_coolant_pump_queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
aluminium_heating_furnace_queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
aluminium_temperature_queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
alloy_in_chamber_queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)

# node_red_health_check_queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)


def push_latest(q: queue.Queue, data: Dict[str, Any]) -> None:
    """
    Keep only the most recent item in the queue.
    This is often useful for UI updates, because the UI usually needs
    the latest state, not a backlog of old states.

    Args:
        q (queue.Queue): The queue to push data into.
        data (Dict[str, Any]): The data to push into the queue.
    """

    try:
        q.put_nowait(data)
    except queue.Full:
        try:
            q.get_nowait()   # Remove stale item
        except queue.Empty:
            pass
        q.put_nowait(data)


def clear_ui_queues(q: queue.Queue) -> None:
    """Drop stale UI payloads so resume always starts from fresh simulator data."""

    while True:
        try:
            q.get_nowait()
        except queue.Empty:
            break
