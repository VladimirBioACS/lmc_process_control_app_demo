# This test should read the furnace data from the plc_simulator and print it to the console.

from time import sleep
from pymodbus.client import ModbusTcpClient


IP_ADDRESS = "127.0.0.1"
PORT = 5020


def read_data(client: ModbusTcpClient) -> None:
    """
    Simulates reading data from the PLC.
    This function reads the furnace temperature and thermal couples data from the
    Modbus TCP server and prints it to the console.

    Args:
        client (ModbusTcpClient): The Modbus TCP client to read data from.
    """

    while True:
        # Read furnace temperature (holding register 0) and thermal couples (holding registers 1-10)
        response = client.read_holding_registers(0, count=11, slave=1)
        if not response.isError():
            furnace_temperature = response.registers[0]
            thermal_couples = response.registers[1:11]
            print(f"Furnace Temperature: {furnace_temperature} °C")
            print("Thermal Couples:", thermal_couples)
        else:
            print(f"Modbus read error: {response}")

        sleep(2)  # Wait for 2 seconds before reading again


if __name__ == "__main__":
    client = ModbusTcpClient(IP_ADDRESS, port=PORT)
    if client.connect():
        print("Connected to Modbus TCP Server.")
        try:
            read_data(client)
        except KeyboardInterrupt:
            print("Stopping data reading.")
        finally:
            client.close()
    else:
        print("Failed to connect to Modbus TCP Server.")
