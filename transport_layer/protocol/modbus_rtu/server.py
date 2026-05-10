from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

try:
    from loguru import logger
    from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
    from pymodbus.device import ModbusDeviceIdentification
    from pymodbus.server import StartAsyncTcpServer
except ImportError as exc:
    raise ImportError(
        "system modules not found. Please install the required dependencies using 'pip install -r requirements.txt'"
    ) from exc


DEFAULT_MODBUS_HOST = "127.0.0.1"
DEFAULT_MODBUS_PORT = 5020
DEFAULT_MODBUS_SLAVE_ID = 1
PROCESS_START_COIL_ADDRESS = 0
FINISH_PROCESS_COIL_ADDRESS = 1
TELEMETRY_START_ADDRESS = 0
FINISH_STATUS_REGISTER_ADDRESS = 100
FINISH_STATUS_IDLE = 0
FINISH_STATUS_PENDING = 1
FINISH_STATUS_SUCCESS = 2
FINISH_STATUS_FAILED = 3
VACUUM_SCALE_FACTOR = 100
DATASTORE_SIZE = 128

TELEMETRY_FIELDS = (
    "furnace_heater_temperature",
    "aluminium_temperature",
    "smelting_form_temperature",
    "aluminium_heater_temperature",
    "thermal_couple_1",
    "thermal_couple_2",
    "thermal_couple_3",
    "thermal_couple_4",
    "thermal_couple_5",
    "thermal_couple_6",
    "thermal_couple_7",
    "thermal_couple_8",
    "thermal_couple_9",
    "thermal_couple_10",
    "power_consumption",
    "form_heating_furnace_temperature",
    "vacuum",
    "coolant_pump_status",
    "vacuum_pump_status",
    "speed",
    "position",
    "aluminium_coolant_pump_status",
)


@dataclass(slots=True)
class ModbusServerConfig:
    """Configuration for the Modbus TCP server."""

    host: str = DEFAULT_MODBUS_HOST
    port: int = DEFAULT_MODBUS_PORT
    slave_id: int = DEFAULT_MODBUS_SLAVE_ID


def create_server_context() -> ModbusServerContext:
    """Create a single-slave datastore large enough for commands and telemetry."""

    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0] * DATASTORE_SIZE),
        co=ModbusSequentialDataBlock(0, [0] * DATASTORE_SIZE),
        hr=ModbusSequentialDataBlock(0, [0] * DATASTORE_SIZE),
        ir=ModbusSequentialDataBlock(0, [0] * DATASTORE_SIZE),
    )

    return ModbusServerContext(slaves=store, single=True)


def create_server_identity() -> ModbusDeviceIdentification:
    """Build a device identity for the simulator TCP server."""

    identity = ModbusDeviceIdentification()
    identity.VendorName = "LMC"
    identity.ProductCode = "LMC-PLC-SIM"
    identity.VendorUrl = "https://github.com/pymodbus-dev/pymodbus"
    identity.ProductName = "LMC PLC Simulator"
    identity.ModelName = "Modbus TCP PLC Simulator"
    identity.MajorMinorRevision = "1.0.0"
    return identity


def encode_telemetry_payload(payload: dict[str, Any]) -> list[int]:
    """Encode the PLC payload into a contiguous holding-register block."""

    registers: list[int] = []
    for field_name in TELEMETRY_FIELDS:
        value = payload[field_name]

        if field_name == "vacuum":
            registers.append(int(round(float(value) * VACUUM_SCALE_FACTOR)))
            continue

        if isinstance(value, bool):
            registers.append(int(value))
            continue

        registers.append(int(round(float(value))))

    return registers


def decode_telemetry_registers(registers: list[int]) -> dict[str, Any]:
    """Decode the holding-register block into a typed payload."""

    if len(registers) < len(TELEMETRY_FIELDS):
        raise ValueError(
            f"Expected at least {len(TELEMETRY_FIELDS)} holding registers, received {len(registers)}"
        )

    payload: dict[str, Any] = {}
    for index, field_name in enumerate(TELEMETRY_FIELDS):
        value = registers[index]

        if field_name == "vacuum":
            payload[field_name] = value / VACUUM_SCALE_FACTOR
            continue

        if field_name.endswith("_status"):
            payload[field_name] = bool(value)
            continue

        payload[field_name] = value

    return payload


class ModbusProcessDataStore:
    """Server-side helper API used by the PLC simulator."""

    def __init__(self, context: ModbusServerContext, slave_id: int = DEFAULT_MODBUS_SLAVE_ID):
        self.context = context
        self.slave_id = slave_id

    @property
    def slave_context(self) -> ModbusSlaveContext:
        """
        Convenience property to access the slave context directly.
        """

        return self.context[self.slave_id]


    def update_telemetry(self, payload: dict[str, Any]) -> None:
        """
        Update the telemetry registers with the provided payload.

        Args:
            payload: A dictionary containing the telemetry data to be updated in the registers.
        """

        registers = encode_telemetry_payload(payload)
        self.slave_context.setValues(16, TELEMETRY_START_ADDRESS, registers)


    def is_process_started(self) -> bool:
        """
        Check if the process has started.

        Returns:
            True if the process has started, False otherwise.
        """

        coil_values = self.slave_context.getValues(1, PROCESS_START_COIL_ADDRESS, count=1)
        return bool(coil_values[0])


    def set_process_started(self, started: bool) -> None:
        """
        Set the process started coil.

        Args:
            started: True to start the process, False to stop it.
        """
        self.slave_context.setValues(5, PROCESS_START_COIL_ADDRESS, [started])


    def is_finish_requested(self) -> bool:
        """
        Check whether the finish command coil was requested by the control app.

        Returns:
            True if finish sequence was requested, otherwise False.
        """

        coil_values = self.slave_context.getValues(1, FINISH_PROCESS_COIL_ADDRESS, count=1)
        return bool(coil_values[0])


    def acknowledge_finish_request(self) -> None:
        """Reset the finish command coil after simulator handles the request."""

        self.slave_context.setValues(5, FINISH_PROCESS_COIL_ADDRESS, [False])


    def set_finish_status(self, status_code: int) -> None:
        """Persist finish sequence status for app-side acknowledgement polling."""

        self.slave_context.setValues(16, FINISH_STATUS_REGISTER_ADDRESS, [status_code])


    def read_finish_status(self) -> int:
        """Read current finish sequence status code from holding register."""

        values = self.slave_context.getValues(3, FINISH_STATUS_REGISTER_ADDRESS, count=1)
        return int(values[0])


    def read_telemetry(self) -> dict[str, Any]:
        """
        Read the telemetry registers.

        Returns:
            A dictionary containing the telemetry data.
        """

        registers = list(
            self.slave_context.getValues(3, TELEMETRY_START_ADDRESS, count=len(TELEMETRY_FIELDS))
        )
        return decode_telemetry_registers(registers)


async def run_server(
    context: ModbusServerContext,
    config: ModbusServerConfig | None = None,
) -> None:
    """Start the Modbus TCP server and serve forever."""

    server_config = config or ModbusServerConfig()
    logger.info(
        "Starting Modbus TCP server on {}:{} for slave {}",
        server_config.host,
        server_config.port,
        server_config.slave_id,
    )

    await StartAsyncTcpServer(
        context=context,
        identity=create_server_identity(),
        address=(server_config.host, server_config.port),
    )


if __name__ == "__main__":
    asyncio.run(run_server(create_server_context()))
