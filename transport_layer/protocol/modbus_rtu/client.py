from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any

try:
    from loguru import logger
    from pymodbus.client import ModbusTcpClient
    from pymodbus.exceptions import ConnectionException
except ImportError as exc:
    raise ImportError(
        "system modules not found. Please install the required dependencies using 'pip install -r requirements.txt'"
    ) from exc

from transport_layer.protocol.modbus_rtu.server import (
    DEFAULT_MODBUS_SLAVE_ID,
    FINISH_PROCESS_COIL_ADDRESS,
    FINISH_STATUS_IDLE,
    FINISH_STATUS_REGISTER_ADDRESS,
    PROCESS_START_COIL_ADDRESS,
    TELEMETRY_FIELDS,
    TELEMETRY_START_ADDRESS,
    decode_telemetry_registers,
)


class ModbusClientErrorCode(Enum):
    """Error codes for Modbus client operations."""

    SUCCESS = 0
    CONNECTION_ERROR = 1
    READ_ERROR = 2
    WRITE_ERROR = 3


class ModbusClient:
    """A small synchronous Modbus TCP client for the LMC PLC telemetry flow."""

    def __init__(self, ip_address: str, port: int,
                 slave_id: int = DEFAULT_MODBUS_SLAVE_ID, timeout: float = 1.0):
        self.ip_address = ip_address
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.client: ModbusTcpClient | None = None


    def connect(self) -> ModbusClientErrorCode:
        """
        Establish a connection to the Modbus server.

        Returns an error code indicating success or failure.
        """

        # pymodbus 3.8 creates asyncio primitives even for sync client mode.
        # Ensure the current thread has an event loop (e.g., MQTT callback thread).
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())

        self.client = ModbusTcpClient(self.ip_address, port=self.port, timeout=self.timeout)
        if not self.client.connect():
            logger.error("Unable to connect to Modbus server at {}:{}", self.ip_address, self.port)
            return ModbusClientErrorCode.CONNECTION_ERROR

        return ModbusClientErrorCode.SUCCESS


    def close(self) -> None:
        """
        Close the connection to the Modbus server.
        """
        if self.client is not None:
            self.client.close()


    def read_holding_registers(self, address: int, count: int) -> list[int] | ModbusClientErrorCode:
        """
        Read holding registers from the Modbus server.

        Args:
            address: The starting address of the registers to read.
            count: The number of registers to read.

        Returns:
            A list of register values or an error code if the read fails.
        """
        if self.client is None:
            return ModbusClientErrorCode.CONNECTION_ERROR

        try:
            response = self.client.read_holding_registers(address, count=count, slave=self.slave_id)
        except ConnectionException as exc:
            logger.error("Modbus read connection error: {}", exc)
            return ModbusClientErrorCode.CONNECTION_ERROR

        if response.isError():
            logger.error("Modbus read error: {}", response)
            return ModbusClientErrorCode.READ_ERROR

        return list(response.registers)


    def write_process_start(self, process_start: bool) -> ModbusClientErrorCode:
        """
        Write the process start coil to the Modbus server.

        Args:
            process_start: The value to write to the process start coil.

        Returns:
            An error code indicating success or failure.
        """
        if self.client is None:
            return ModbusClientErrorCode.CONNECTION_ERROR

        try:
            response = self.client.write_coil(PROCESS_START_COIL_ADDRESS,
                                              process_start, slave=self.slave_id)
        except ConnectionException as exc:
            logger.error(
                "Modbus write connection error while setting process_start={}: {}",
                process_start,
                exc,
            )
            return ModbusClientErrorCode.CONNECTION_ERROR

        if response.isError():
            logger.error("Modbus write error while setting process_start={}: {}", process_start, response)
            return ModbusClientErrorCode.WRITE_ERROR

        return ModbusClientErrorCode.SUCCESS


    def write_finish_process(self) -> ModbusClientErrorCode:
        """
        Send the finish process command to the Modbus server.

        Returns:
            An error code indicating success or failure.
        """

        if self.client is None:
            return ModbusClientErrorCode.CONNECTION_ERROR

        try:
            response = self.client.write_coil(
                FINISH_PROCESS_COIL_ADDRESS,
                True,
                slave=self.slave_id,
            )
        except ConnectionException as exc:
            logger.error("Modbus write connection error while requesting finish process: {}", exc)
            return ModbusClientErrorCode.CONNECTION_ERROR

        if response.isError():
            logger.error("Modbus write error while requesting finish process: {}", response)
            return ModbusClientErrorCode.WRITE_ERROR

        return ModbusClientErrorCode.SUCCESS


    def read_finish_status(self) -> int | ModbusClientErrorCode:
        """
        Read finish sequence status code from the simulator.

        Returns:
            Integer status code or an error code when read fails.
        """

        registers = self.read_holding_registers(FINISH_STATUS_REGISTER_ADDRESS, 1)
        if isinstance(registers, ModbusClientErrorCode):
            return registers

        return int(registers[0])


    def reset_finish_status(self) -> ModbusClientErrorCode:
        """Reset finish sequence status to IDLE before new process start."""

        if self.client is None:
            return ModbusClientErrorCode.CONNECTION_ERROR

        try:
            response = self.client.write_register(
                FINISH_STATUS_REGISTER_ADDRESS,
                FINISH_STATUS_IDLE,
                slave=self.slave_id,
            )
        except ConnectionException as exc:
            logger.error("Modbus write connection error while resetting finish status: {}", exc)
            return ModbusClientErrorCode.CONNECTION_ERROR

        if response.isError():
            logger.error("Modbus write error while resetting finish status: {}", response)
            return ModbusClientErrorCode.WRITE_ERROR

        return ModbusClientErrorCode.SUCCESS


    def read_process_data(self) -> dict[str, Any] | ModbusClientErrorCode:
        """
        Read process data from the Modbus server.

        Returns:
            A dictionary containing the process data or an error code if the read fails.
        """

        registers = self.read_holding_registers(TELEMETRY_START_ADDRESS, len(TELEMETRY_FIELDS))
        if isinstance(registers, ModbusClientErrorCode):
            return registers

        return decode_telemetry_registers(registers)
