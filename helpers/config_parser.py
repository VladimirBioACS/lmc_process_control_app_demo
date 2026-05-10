# Configuration Parser Helper Functions. Used to read and parse the application's configuration file
import json
import os


def load_config(config_path: str) -> dict:
    """
    Loads the configuration from a JSON file.

    Args:
        config_path (str): The path to the configuration file.
    Returns:
        dict: The configuration as a dictionary.
    """

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as config_file:
        try:
            config = json.load(config_file)
            return config
        except json.JSONDecodeError as e:
            raise ValueError("Error parsing configuration file") from e
