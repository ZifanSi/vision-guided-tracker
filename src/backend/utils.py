import os
import logging

logger = logging.getLogger(__name__)

def _list_x11_displays():
    """
    Returns a list of active X11 display names like [":0", ":1", ...]
    by inspecting /tmp/.X11-unix sockets.
    """
    path = "/tmp/.X11-unix"
    displays = []

    if not os.path.isdir(path):
        return displays

    for entry in os.listdir(path):
        # X11 sockets are named like 'X0', 'X1', etc.
        if entry.startswith("X") and entry[1:].isdigit():
            displays.append(f":{entry[1:]}")

    return displays

def set_display_env():
    env_disp = os.environ.get('DISPLAY')
    if env_disp:
        logger.info("Using DISPLAY from environment: %s", env_disp)
    else:
        displays = _list_x11_displays()
        if displays:
            env_disp = displays[0]
            os.environ['DISPLAY'] = env_disp
            logger.info("Using first detected DISPLAY: %s", env_disp)
        else:
            logger.info("No DISPLAY detected")
            exit(1)