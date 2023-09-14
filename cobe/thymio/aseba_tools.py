from dbus.exceptions import DBusException

from cobe.settings import logs

import logging
import os
import time

logging.basicConfig(level=logs.log_level, format=logs.log_format)
logger = logs.setup_logger("thymio")

THYMIO_DEVICE_PORT = "/dev/ttyACM0"

def asebamedulla_health(network):
    """Checking health of the established connection by requesting robot health"""
    logger.info('Checking asebamedulla connection')
    # Check Thymio's health
    try:
        network.GetVariable("thymio-II", "acc", timeout=5)
        logger.info('Connected!')
        return True
    except DBusException:
        logger.info('Connection not healthy!')
        return False


def asebamedulla_init():
    """Establishing initial connection with the Thymio robot on a predefined interface
        Args: None
        Vars: visualswarm.control.THYMIO_DEVICE_PORT: serial port on which the robot is available for the Pi
        Returns: None
    """
    logger.info(f'Connecting via asebamedulla on {THYMIO_DEVICE_PORT}')
    os.system("(asebamedulla ser:name=Thymio-II &)")  # nosec
    time.sleep(5)
    logger.info('Connected!')


def asebamedulla_end():
    """Killing all established asebamedulla processes"""
    logger.info('Closing connection via asebamedulla')
    os.system("pkill -f asebamedulla")  # nosec
    logger.info(f'Connection Closed!')

