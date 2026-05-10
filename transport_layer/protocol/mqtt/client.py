# paho-mqtt client for connection to the Node-RED dashboard.

import sys
import json

from common.common import EXIT_SUCCESS, EXIT_FAILURE

try:
    from loguru import logger
    import paho.mqtt.client as mqtt
except ImportError:
    print("Please use pip install -r requirements.txt")

    sys.exit(EXIT_FAILURE)


def on_connect(client, userdata, flags, rc):
    """
    Callback function for when the client connects to the MQTT broker.

    Args:
        client (mqtt.Client): The MQTT client instance.
        userdata: The private user data as set in Client() or userdata_set().
        flags (dict): Response flags sent by the broker.
        rc (int): The connection result code.
    """

    if rc == 0:
        logger.debug("Connected to MQTT Broker successfully")
    else:
        logger.error(f"Failed to connect to MQTT Broker. Return code: {rc}")


def on_disconnect(client, userdata, rc):
    """
    Callback function for when the client disconnects from the MQTT broker.

    Args:
        client (mqtt.Client): The MQTT client instance.
        userdata: The private user data as set in Client() or userdata_set().
        rc (int): The disconnection result code.
    """

    if rc != 0:
        logger.warning("Unexpected disconnection from MQTT Broker")
    else:
        logger.debug("Disconnected from MQTT Broker successfully")


def on_publish(client, userdata, mid):
    """
    Callback function for when a message is published.

    Args:
        client (mqtt.Client): The MQTT client instance.
        userdata: The private user data as set in Client() or userdata_set().
        mid (int): The message ID.
    """

    logger.debug(f"Message published with mid: {mid}")


def publish_message(client: mqtt.Client, topic: str, payload: dict):
    """
    Publishes a message to the specified MQTT topic.

    Args:
        client (mqtt.Client): The MQTT client instance.
        topic (str): The MQTT topic to publish the message to.
        payload (dict): The message payload as a dictionary.
    """

    try:
        payload_str = json.dumps(payload)

        result = client.publish(topic, payload_str)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.error(f"Failed to publish message to {topic}. Error code: {result.rc}")
        else:
            logger.debug(f"Message published to {topic}")

    except mqtt.WebsocketConnectionError as e:
        logger.error(f"Error publishing message: {e}")


def create_mqtt_client(broker_address: str,
                       broker_port: int,
                       username: str = None,
                       password: str = None) -> mqtt.Client:
    """
    Creates and returns an MQTT client instance.

    Args:
        broker_address (str): The address of the MQTT broker.
        broker_port (int): The port of the MQTT broker.
        username (str, optional): The username for MQTT authentication. Defaults to None.
        password (str, optional): The password for MQTT authentication. Defaults to None.

    Returns:
        mqtt.Client: The configured MQTT client instance.
    """

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish = on_publish

    if username and password:
        client.username_pw_set(username, password)

    try:
        client.connect(broker_address, broker_port)
        logger.debug(f"Connecting to MQTT Broker at {broker_address}:{broker_port}")
    except mqtt.WebsocketConnectionError as e:
        logger.error(f"Failed to connect to MQTT Broker: {e}")

        sys.exit(EXIT_FAILURE)

    return client


def loop_mqtt_client(client: mqtt.Client):
    """
    Starts the MQTT client loop to process network traffic and dispatch callbacks.

    Args:
        client (mqtt.Client): The MQTT client instance to start the loop for.
    """

    try:
        client.loop_start()
        logger.debug("Starting MQTT client loop")
    except mqtt.WebsocketConnectionError as e:
        logger.error(f"Failed to start MQTT client loop: {e}")


def register_recv_message_callback(client: mqtt.Client, topic: str, callback):
    """
    Registers a callback function for when a message is received on particular topic.

    Args:
        client (mqtt.Client): The MQTT client instance.
        topic (str): The MQTT topic to subscribe to for receiving messages.
        callback: The callback function to be called when a message is received.
    """
    client.subscribe(topic)
    client.message_callback_add(topic, callback)

    logger.debug(f"Registered callback for receiving MQTT messages on topic {topic}")


def disconnect_mqtt_client(client: mqtt.Client):
    """
    Disconnects the MQTT client from the broker.

    Args:
        client (mqtt.Client): The MQTT client instance to disconnect.
    """

    try:
        client.loop_stop()
        logger.debug("Stopping MQTT client loop")
        client.disconnect()
        logger.debug("Disconnecting from MQTT Broker")
    except mqtt.WebsocketConnectionError as e:
        logger.error(f"Failed to disconnect from MQTT Broker: {e}")
