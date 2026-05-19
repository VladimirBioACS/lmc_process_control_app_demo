from __future__ import annotations

import argparse
import asyncio
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

from core.lmc_calculator import LmcCalculator

from transport_layer.protocol.modbus_rtu.server import (
    DEFAULT_MODBUS_HOST,
    DEFAULT_MODBUS_PORT,
    FINISH_STATUS_FAILED,
    FINISH_STATUS_IDLE,
    FINISH_STATUS_PENDING,
    FINISH_STATUS_SUCCESS,
    ModbusProcessDataStore,
    ModbusServerConfig,
    create_server_context,
    run_server,
)


POLL_INTERVAL_SECONDS = 0.5
RETURN_INTERVAL_SECONDS = 1
RETURN_POSITION_STEP = 5
RETURN_SPEED_UNITS = 100
PREPARATION_DURATION_SECONDS = 160.0
SMELTING_DURATION_SECONDS = 120.0
TOTAL_DURATION_SECONDS = PREPARATION_DURATION_SECONDS + SMELTING_DURATION_SECONDS
DESIRED_GRADIENT_K_PER_CM = 20.0
MIN_THERMAL_COUPLES = 1
MAX_THERMAL_COUPLES = 10
DEFAULT_THERMAL_COUPLES = 5
COOLING_START_POSITION = 35
COOLING_POSITION_STEP = 5
COOLING_LOWER_TEMP_LIMIT = 900
WITHDRAW_MM_PER_MIN = 20.0
FRONT_ANGLE_DEG = 30.0
TL_TEMPERATURE = 1560.0
TL_WINDOW_MM = 10.0

SIMULATION_CONFIG = {
    "thermal_couple_count": DEFAULT_THERMAL_COUPLES,
    "thermal_couple_positions_mm": [float(index * 5) for index in range(DEFAULT_THERMAL_COUPLES)],
}

TEMPERATURE_RANGES = {
    "furnace_heater_temperature": (1510, 1550),
    "aluminium_temperature": (795, 810),
    "smelting_form_temperature": (1520, 1530),
    "aluminium_heater_temperature": (795, 810),
    "form_heating_furnace_temperature": (1510, 1550),
}


def initial_payload() -> dict[str, int | float | bool]:
    """Initial telemetry values for the Modbus datastore before the process starts."""

    return {
        "furnace_heater_temperature": 0,
        "aluminium_temperature": 0,
        "smelting_form_temperature": 0,
        "aluminium_heater_temperature": 0,
        "thermal_couple_1": 0,
        "thermal_couple_2": 0,
        "thermal_couple_3": 0,
        "thermal_couple_4": 0,
        "thermal_couple_5": 0,
        "thermal_couple_6": 0,
        "thermal_couple_7": 0,
        "thermal_couple_8": 0,
        "thermal_couple_9": 0,
        "thermal_couple_10": 0,
        "power_consumption": 0,
        "form_heating_furnace_temperature": 0,
        "vacuum": 0.0,
        "coolant_pump_status": False,
        "vacuum_pump_status": False,
        "speed": 0,
        "position": 0,
        "aluminium_coolant_pump_status": False,
        "plc_connection_status": False,
    }


@dataclass(slots=True)
class SmeltingProcessState:
    """Holds mutable state for one simulated process run."""

    active: bool = False
    elapsed_seconds: float = 0.0
    targets: dict[str, int] = field(default_factory=dict)
    thermal_targets: dict[str, int] = field(default_factory=dict)
    current_payload: dict[str, int | float | bool] = field(default_factory=initial_payload)
    current_position_step: int = 0
    calc: LmcCalculator = field(
        default_factory=lambda: LmcCalculator(
            withdraw_mm_per_min=WITHDRAW_MM_PER_MIN,
            front_angle_deg=FRONT_ANGLE_DEG,
            tl_c=TL_TEMPERATURE,
            tl_window_mm=TL_WINDOW_MM,
        )
    )


def parse_args() -> argparse.Namespace:
    """Parse PLC simulator command-line arguments."""

    parser = argparse.ArgumentParser(description="LMC PLC simulator")
    parser.add_argument(
        "-n",
        "--thermal-couples",
        type=int,
        default=DEFAULT_THERMAL_COUPLES,
        choices=range(MIN_THERMAL_COUPLES, MAX_THERMAL_COUPLES + 1),
        help="Number of active thermal couples to simulate (1-10).",
    )

    return parser.parse_args()


def configure_simulation(thermal_couple_count: int) -> None:
    """Configure active thermal-couple count and positions for current run."""

    SIMULATION_CONFIG["thermal_couple_count"] = thermal_couple_count
    SIMULATION_CONFIG["thermal_couple_positions_mm"] = [
        float(index * 5) for index in range(thermal_couple_count)
    ]

    logger.info(
        "Simulator thermal couples configured: count={}, cooling_start={}, cooling_step={}",
        SIMULATION_CONFIG["thermal_couple_count"],
        COOLING_START_POSITION,
        COOLING_POSITION_STEP,
    )


def _pick_targets() -> tuple[dict[str, int], dict[str, int]]:
    thermal_couple_count = int(SIMULATION_CONFIG["thermal_couple_count"])

    temp_targets = {
        key: random.randint(bounds[0], bounds[1]) for key, bounds in TEMPERATURE_RANGES.items()
    }
    thermal_targets = {
        f"thermal_couple_{index}": random.randint(1520, 1525)
        for index in range(1, thermal_couple_count + 1)
    }

    return temp_targets, thermal_targets


def start_new_process(state: SmeltingProcessState) -> None:
    """Initialize simulator state for a fresh process start command."""

    state.active = True
    state.elapsed_seconds = 0.0
    state.targets, state.thermal_targets = _pick_targets()
    state.current_payload = initial_payload()
    state.current_position_step = 0

    # Keep nominal process auxiliaries stable while process is running.
    state.current_payload["speed"] = 10
    state.current_payload["position"] = 0
    state.current_payload["power_consumption"] = random.randint(15, 17)
    state.current_payload["vacuum"] = round(random.uniform(7.0, 8.0), 2)
    state.current_payload["coolant_pump_status"] = True
    state.current_payload["vacuum_pump_status"] = True
    state.current_payload["aluminium_coolant_pump_status"] = True

    logger.info(
        "Starting simulated smelting process: preparation={}s, smelting={}s, total={}s",
        int(PREPARATION_DURATION_SECONDS),
        int(SMELTING_DURATION_SECONDS),
        int(TOTAL_DURATION_SECONDS),
    )


def _advance_temperature(current: float, target: float, progress: float) -> float:
    """Smoothly approach target temperature with random heating increment."""

    if current >= target:
        return target + random.uniform(-2.0, 2.0)

    # Approximate rising profile with bounded random increments.
    max_step = random.uniform(5.0, 20.0)
    gap = target - current
    shaped_step = min(gap, max_step * max(0.2, 1.0 - progress * 0.7))
    return current + shaped_step


def _calculate_gradient(payload: dict[str, int | float | bool], calc: LmcCalculator) -> float | None:
    thermal_couple_count = int(SIMULATION_CONFIG["thermal_couple_count"])
    thermal_couple_positions_mm = list(SIMULATION_CONFIG["thermal_couple_positions_mm"])

    temperatures = [
        float(payload[f"thermal_couple_{index}"])
        for index in range(1, thermal_couple_count + 1)
    ]

    try:
        lmc_data = calc.calculate_lmc(thermal_couple_positions_mm, temperatures)
    except (TypeError, ValueError):
        return None

    return float(lmc_data["G_K_per_cm"])


def _update_preparation_phase(state: SmeltingProcessState) -> None:
    """Ramp all configured temperatures from 0 to target ranges."""

    thermal_couple_count = int(SIMULATION_CONFIG["thermal_couple_count"])
    progress = min(1.0, state.elapsed_seconds / PREPARATION_DURATION_SECONDS)
    payload = state.current_payload

    for field_name, target in state.targets.items():
        payload[field_name] = int(round(_advance_temperature(float(payload[field_name]), float(target), progress)))

    for index in range(1, thermal_couple_count + 1):
        key = f"thermal_couple_{index}"
        target = state.thermal_targets[key]
        payload[key] = int(round(_advance_temperature(float(payload[key]), float(target), progress)))

    # Keep unused channels neutral while preserving register compatibility.
    for index in range(thermal_couple_count + 1, 11):
        payload[f"thermal_couple_{index}"] = 0

    payload["position"] = 0
    payload["speed"] = 10


def _update_smelting_phase(state: SmeltingProcessState) -> None:
    """Move actuator and cool thermal couples after position >= 50."""

    thermal_couple_count = int(SIMULATION_CONFIG["thermal_couple_count"])
    payload = state.current_payload
    smelting_elapsed = max(0.0, state.elapsed_seconds - PREPARATION_DURATION_SECONDS)
    descent_progress = min(1.0, smelting_elapsed / SMELTING_DURATION_SECONDS)
    new_position = min(100, int(round(descent_progress * 100.0)))

    # Position changes with 1-step resolution.
    payload["position"] = new_position
    payload["speed"] = 10

    state.current_position_step = new_position

    # Staggered cooling: deepest couple cools first, shallower couples start later.
    cooling_positions = {
        index: COOLING_START_POSITION + (thermal_couple_count - index) * COOLING_POSITION_STEP
        for index in range(1, thermal_couple_count + 1)
    }

    for index, start_position in cooling_positions.items():
        key = f"thermal_couple_{index}"
        current_temp = int(payload[key])
        if new_position >= start_position and current_temp > COOLING_LOWER_TEMP_LIMIT:
            # Apply cooling every tick until the lower limit is reached, including at position 100.
            step_drop = random.randint(1, 2)
            payload[key] = max(COOLING_LOWER_TEMP_LIMIT, current_temp - step_drop)
        elif new_position < start_position:
            # Fluctuate uncooled channels within the nominal 1520..1530 °C band.
            fluctuated = current_temp + random.randint(-5, 5)
            payload[key] = max(1520, min(1525, fluctuated))

    # Gradually shape thermal profile toward the desired gradient after cooling begins.
    if new_position >= COOLING_START_POSITION:
        spread_progress = min(1.0, (new_position - COOLING_START_POSITION) / max(1.0, 100.0 - COOLING_START_POSITION))
        desired_spread = int(round((DESIRED_GRADIENT_K_PER_CM / 10.0) * 20.0 * spread_progress))
        tc1_value = int(payload["thermal_couple_1"])

        for index in range(2, thermal_couple_count + 1):
            key = f"thermal_couple_{index}"
            ratio = (index - 1) / max(1, thermal_couple_count - 1)
            desired_temp = int(round(tc1_value - desired_spread * ratio))
            current_value = int(payload[key])
            if current_value > desired_temp:
                correction_cap = max(1, int(round(1 + 3 * spread_progress)))
                correction = min(current_value - desired_temp, random.randint(1, correction_cap))
                payload[key] = current_value - correction

    # Keep furnace temps stabilized with slight jitter during smelting.
    for field_name, target in state.targets.items():
        jitter = random.randint(-3, 3)
        payload[field_name] = int(round(max(target - 20, min(target + 20, int(payload[field_name]) + jitter))))

    for index in range(thermal_couple_count + 1, 11):
        payload[f"thermal_couple_{index}"] = 0


def build_process_payload(state: SmeltingProcessState, interval_seconds: float) -> dict[str, int | float | bool]:
    """Advance process timeline and return current telemetry sample."""

    if not state.active:
        start_new_process(state)

    state.elapsed_seconds = min(TOTAL_DURATION_SECONDS, state.elapsed_seconds + interval_seconds)

    if state.elapsed_seconds <= PREPARATION_DURATION_SECONDS:
        _update_preparation_phase(state)
    else:
        _update_smelting_phase(state)

    gradient = _calculate_gradient(state.current_payload, state.calc)
    if gradient is not None and gradient >= DESIRED_GRADIENT_K_PER_CM:
        logger.info(
            "Simulator reached desired gradient {:.2f} K/cm at t={:.1f}s and position={}",
            gradient,
            state.elapsed_seconds,
            state.current_payload["position"],
        )

    return state.current_payload


async def finish_the_process(
    datastore: ModbusProcessDataStore,
    state: SmeltingProcessState,
) -> bool:
    """
    Placeholder finish sequence for the PLC simulator.

    Returns:
        True to simulate successful process finish.
    """

    logger.info("finish_the_process command received. Running simulated finish sequence...")
    datastore.set_finish_status(FINISH_STATUS_PENDING)

    payload = state.current_payload if state.current_payload else initial_payload()
    current_position = int(payload.get("position", 0))

    if current_position > 0:
        logger.info(
            "Returning actuator to home position from {} at max speed {}...",
            current_position,
            RETURN_SPEED_UNITS,
        )

    # Simulate return stroke to home position before reporting successful finish.
    while current_position > 0:
        current_position = max(0, current_position - RETURN_POSITION_STEP)
        payload["position"] = current_position
        payload["speed"] = RETURN_SPEED_UNITS
        state.current_position_step = current_position
        datastore.update_telemetry(payload)
        await asyncio.sleep(RETURN_INTERVAL_SECONDS)

    payload["position"] = 0
    payload["speed"] = 0
    state.current_payload = payload
    state.active = False

    datastore.set_process_started(False)
    datastore.set_finish_status(FINISH_STATUS_SUCCESS)
    logger.info("Simulated finish sequence completed successfully.")
    return True


def build_mock_payload() -> dict[str, int | float | bool]:
    """Generate one PLC telemetry sample for the Modbus datastore."""

    return {
        "furnace_heater_temperature": random.randint(1510, 1550),
        "aluminium_temperature": random.randint(790, 810),
        "smelting_form_temperature": random.randint(1520, 1530),
        "aluminium_heater_temperature": random.randint(790, 810),
        "thermal_couple_1": random.randint(1560, 1600),
        "thermal_couple_2": random.randint(1560, 1600),
        "thermal_couple_3": random.randint(1560, 1600),
        "thermal_couple_4": random.randint(1560, 1600),
        "thermal_couple_5": random.randint(1560, 1600),
        "thermal_couple_6": random.randint(1560, 1600),
        "thermal_couple_7": random.randint(1560, 1600),
        "thermal_couple_8": random.randint(1560, 1600),
        "thermal_couple_9": random.randint(1560, 1600),
        "thermal_couple_10": random.randint(1560, 1600),
        "power_consumption": random.randint(15, 17),
        "form_heating_furnace_temperature": random.randint(1510, 1540),
        "vacuum": random.uniform(7, 8),
        "coolant_pump_status": True,
        "vacuum_pump_status": True,
        "speed": 10,
        "position": random.randint(0, 100),
        "aluminium_coolant_pump_status": True
    }


async def telemetry_loop(datastore: ModbusProcessDataStore, interval_seconds: float) -> None:
    """Update the server datastore only after the app sends process_start=true."""

    process_started = False
    process_state = SmeltingProcessState()

    while True:
        if datastore.is_finish_requested():
            finish_success = await finish_the_process(datastore, process_state)
            datastore.acknowledge_finish_request()

            if finish_success:
                logger.info("Finish request acknowledged. Telemetry generation paused.")
            else:
                datastore.set_finish_status(FINISH_STATUS_FAILED)
                logger.error("Finish request failed in simulator placeholder sequence.")

        current_state = datastore.is_process_started()
        if current_state and not process_started:
            datastore.set_finish_status(FINISH_STATUS_IDLE)
            process_state.active = False
            logger.info("Received process_start command. Telemetry generation enabled.")
        elif process_started and not current_state:
            process_state.active = False
            process_state.current_payload = initial_payload()
            datastore.update_telemetry(process_state.current_payload)
            logger.info("Received process_stop command. Telemetry generation paused.")

        process_started = current_state

        if process_started:
            payload = build_process_payload(process_state, interval_seconds)
            datastore.update_telemetry(payload)
            logger.debug("Updated simulator telemetry: {}", payload)

        await asyncio.sleep(interval_seconds)


async def main() -> None:
    args = parse_args()
    configure_simulation(args.thermal_couples)

    context = create_server_context()
    datastore = ModbusProcessDataStore(context)
    server_config = ModbusServerConfig(host=DEFAULT_MODBUS_HOST, port=DEFAULT_MODBUS_PORT)
    producer_task = asyncio.create_task(telemetry_loop(datastore, POLL_INTERVAL_SECONDS))

    try:
        await run_server(context, server_config)
    finally:
        producer_task.cancel()
        await asyncio.gather(producer_task, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("PLC simulator stopped.")
