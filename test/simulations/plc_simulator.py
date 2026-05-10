from __future__ import annotations

import asyncio
import random
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

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


async def finish_the_process(datastore: ModbusProcessDataStore) -> bool:
    """
    Placeholder finish sequence for the PLC simulator.

    Returns:
        True to simulate successful process finish.
    """

    logger.info("finish_the_process command received. Running simulated finish sequence...")
    datastore.set_finish_status(FINISH_STATUS_PENDING)
    await asyncio.sleep(0.1)

    # Placeholder for future actuator/cooldown/finalization logic.
    datastore.set_process_started(False)
    datastore.set_finish_status(FINISH_STATUS_SUCCESS)
    logger.info("Simulated finish sequence completed successfully.")
    return True


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
        "plc_connection_status": False
    }


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

    while True:
        if datastore.is_finish_requested():
            finish_success = await finish_the_process(datastore)
            datastore.acknowledge_finish_request()

            if finish_success:
                logger.info("Finish request acknowledged. Telemetry generation paused.")
            else:
                datastore.set_finish_status(FINISH_STATUS_FAILED)
                logger.error("Finish request failed in simulator placeholder sequence.")

        current_state = datastore.is_process_started()
        if current_state and not process_started:
            datastore.set_finish_status(FINISH_STATUS_IDLE)
            logger.info("Received process_start command. Telemetry generation enabled.")
        elif process_started and not current_state:
            logger.info("Received process_stop command. Telemetry generation paused.")

        process_started = current_state

        if process_started:
            payload = build_mock_payload()
            datastore.update_telemetry(payload)
            logger.debug("Updated simulator telemetry: {}", payload)

        await asyncio.sleep(interval_seconds)


async def main() -> None:
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
