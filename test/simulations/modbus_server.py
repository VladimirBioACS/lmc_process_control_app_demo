import asyncio

try:
    from loguru import logger
    from pymodbus.server import StartAsyncTcpServer, ServerAsyncStop
    from pymodbus.device import ModbusDeviceIdentification
    from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
except ImportError as exc:
    raise ImportError("system modules not found. Please install the required dependencies using 'pip install -r requirements.txt'") from exc


_FC_NAMES: dict[int, str] = {
    1:  "read_coils",
    2:  "read_discrete_inputs",
    3:  "read_holding_registers",
    4:  "read_input_registers",
    5:  "write_single_coil",
    6:  "write_single_register",
    15: "write_multiple_coils",
    16: "write_multiple_registers",
    22: "mask_write_register",
    23: "read_write_multiple_registers",
}


class CallbackSlaveContext(ModbusSlaveContext):
    """A ModbusSlaveContext that fires callbacks on every client write or read.

    Pass *on_write* and/or *on_read* callables with the signature::

        def callback(fc: int, address: int, values: list) -> None: ...

    *fc* is the Modbus function code, *address* is the 0-based register
    address from the client request, and *values* is the list of values
    written (on_write) or returned to the client (on_read).
    """

    def __init__(self, *args, on_write=None, on_read=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_write = on_write
        self._on_read = on_read

    def setValues(self, fc_as_hex: int, address: int, values) -> None:
        """Store values then notify the write callback."""
        super().setValues(fc_as_hex, address, values)
        if self._on_write:
            self._on_write(fc_as_hex, address, list(values))

    def getValues(self, fc_as_hex: int, address: int, count: int = 1):
        """Retrieve values then notify the read callback."""
        values = super().getValues(fc_as_hex, address, count)
        if self._on_read:
            self._on_read(fc_as_hex, address, list(values))
        return values


class ModbusServer:
    """A Modbus TCP server for simulating a PLC that provides furnace temperature and thermal couple data."""

    def __init__(self, address: str,
                 port: int,
                 vendor_name: str = "Pymodbus",
                 product_code: str = "PM",
                 vendor_url: str = "http://github.com",
                 product_name: str = "Pymodbus Server",
                 model_name: str = "Pymodbus Server",
                 major_minor_revision: str = "3.0.0"):

        self.address = address
        self.port = port
        self.vendor_name = vendor_name
        self.product_code = product_code
        self.vendor_url = vendor_url
        self.product_name = product_name
        self.model_name = model_name
        self.major_minor_revision = major_minor_revision

        self.server_task = None

    # ------------------------------------------------------------------
    # Callback hooks — override in a subclass or replace at runtime
    # ------------------------------------------------------------------

    def on_client_write(self, fc: int, address: int, values: list) -> None:
        """Called after a client writes data to the datastore."""
        fc_name = _FC_NAMES.get(fc, f"fc=0x{fc:02x}")
        logger.debug(f"[WRITE] {fc_name} | address={address} | values={values}")

    def on_client_read(self, fc: int, address: int, values: list) -> None:
        """Called after a client reads data from the datastore."""
        fc_name = _FC_NAMES.get(fc, f"fc=0x{fc:02x}")
        logger.debug(f"[READ]  {fc_name} | address={address} | values={values}")

    async def start(self):
        """Starts the Modbus TCP server."""

        # Register signal handlers

        # 1. Initialize the data storage (Coils, Discrete Inputs,
        # Holding Registers, Input Registers)
        # Provide enough holding-register space for simulator writes
        # (furnace + 10 thermocouples + 10 positions).
        store = CallbackSlaveContext(
            di=ModbusSequentialDataBlock(0, [0]*100),
            co=ModbusSequentialDataBlock(0, [0]*100),
            hr=ModbusSequentialDataBlock(0, [0]*100),
            ir=ModbusSequentialDataBlock(0, [0]*100),
            on_write=self.on_client_write,
            on_read=self.on_client_read,
        )
        context = ModbusServerContext(slaves=store, single=True)

        # 2. Optional: Set up server identification
        identity = ModbusDeviceIdentification()
        identity.VendorName = self.vendor_name
        identity.ProductCode = self.product_code
        identity.VendorUrl = self.vendor_url
        identity.ProductName = self.product_name
        identity.ModelName = self.model_name
        identity.MajorMinorRevision = self.major_minor_revision

        # 3. Start the server
        logger.info(f"Starting Modbus TCP Server on {self.address}:{self.port}...")

        self.server_task = asyncio.create_task(StartAsyncTcpServer(
            context=context,
            identity=identity,
            address=(self.address, self.port)
        ))

        try:
            await self.server_task
        except asyncio.CancelledError:
            await ServerAsyncStop()

            logger.info("Modbus TCP Server has been stopped.")


    def stop(self):
        """Stops the Modbus TCP server."""
        # This is a placeholder for any cleanup logic if needed.
        logger.info("Stopping Modbus TCP Server...")

        self.server_task.cancel()

        try:
            asyncio.get_event_loop().run_until_complete(self.server_task)
        except asyncio.CancelledError:
            logger.info("Modbus TCP Server has been stopped.")
