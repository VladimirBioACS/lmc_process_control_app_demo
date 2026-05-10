try:
    from ui.modules.svg_scheme import SvgSystemStates
except ImportError as exc:
    raise ImportError(
        "UI modules not found. Please ensure the UI components are properly set up and dependencies are installed."
    ) from exc


def map_boolean_to_svg_state(value: bool) -> int:
    """
    Maps a boolean value to the corresponding SVG system state integer.

    Args:
        value (bool): The boolean value to map.

    Returns:
        int: The corresponding SVG system state integer.
    """

    return SvgSystemStates.ON.value if value else SvgSystemStates.OFF.value


def derive_actuator_status(speed: int) -> str:
    """
    Derives the actuator status based on its speed.

    Args:
        speed (int): The current speed of the actuator.

    Returns:
        str: The derived status of the actuator ("OK", "WARNING", "CRITICAL").
    """

    if speed >= 30:
        return "WARNING"

    return "OK"
