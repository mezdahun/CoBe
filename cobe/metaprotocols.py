import os
import subprocess
import time
import logging
from getpass import getpass

from cobe.settings import logs
# Setting up file logger
logging.basicConfig(level=logs.log_level, format=logs.log_format)
logger = logs.setup_logger("cobe.metaprotocol")

def single_human():
    """Stopping the docker container, then changes cobe.settings.pmodule, then starts the container again"""
    # stopping the docker container via the cbp-stop enrypoint
    database_process = None
    eyeserver_process = None
    master_pass = getpass("Enter master password: ")
    try:
        env_variables = "set PM_NUM_PREDATORS=1 && " \
                        "set PM_CENTER_PULL_RADIUS=20 && " \
                        "set PM_BATCH_SIZE=8 && " \
                        "set KALMAN_PROCESS_VAR=12 && " \
                        "set KALMAN_MEAS_VAR=0.075 && " \
                        "set MASTER_PASS=" + master_pass + " && "

        delimiter = "\n"
        logger.info(f"Using env variables: {env_variables.replace('&& ', delimiter)}")
        logger.info("Stopping docker container if any is running...")
        os.system("cbp-stop-docker.exe")
        time.sleep(2)

        logger.info("Starting docker container...")
        os.system(env_variables + "cbp-start-docker.exe")
        time.sleep(2)

        logger.info("Starting rendering stack...")
        os.system(env_variables + "cobe-rendering-startup.exe")
        time.sleep(5)

        logger.info(f"Starting database process...")
        # start database process using subprocess.Popen
        database_process = subprocess.Popen(env_variables + "echo y | cbd-start.exe", shell=True)
        time.sleep(2)

        logger.info("Starting eyeservers...")
        eyeserver_process = subprocess.Popen(env_variables + "cbm-start-eyeserver.exe", shell=True)
        time.sleep(5)

        os.system(env_variables + "cbm-start-multieye-kalman.exe --det_target=stick")

        logger.info("Stopping database background process...")
        pid = database_process.pid
        database_process.terminate()
        os.kill(pid, 0)

        logger.info("Shutting down eyeservers...")
        pid = eyeserver_process.pid
        eyeserver_process.terminate()
        os.kill(pid, 0)

    except Exception as e:
        logger.error(f"Error while running metaprotocol: {e}")
        if database_process:
            logger.info("Stopping database background process...")
            pid = database_process.pid
            database_process.terminate()
            os.kill(pid, 0)

        if eyeserver_process:
            logger.info("Shutting down eyeservers...")
            pid = eyeserver_process.pid
            eyeserver_process.terminate()
            os.kill(pid, 0)

def multi_human():
    """Stopping the docker container, then changes cobe.settings.pmodule, then starts the container again"""
    # stopping the docker container via the cbp-stop enrypoint
    database_process = None
    eyeserver_process = None
    master_pass = getpass("Enter master password: ")
    try:
        env_variables = "set PM_NUM_PREDATORS=2 && " \
                        "set PM_CENTER_PULL_RADIUS=20 && " \
                        "set PM_BATCH_SIZE=8 && " \
                        "set KALMAN_PROCESS_VAR=12 && " \
                        "set KALMAN_MEAS_VAR=0.075 && " \
                        "set MASTER_PASS=" + master_pass + " && "

        delimiter = "\n"
        logger.info(f"Using env variables: {env_variables.replace('&& ', delimiter)}")
        logger.info("Stopping docker container if any is running...")
        os.system("cbp-stop-docker.exe")
        time.sleep(2)

        logger.info("Starting docker container...")
        os.system(env_variables + "cbp-start-docker.exe")
        time.sleep(2)

        logger.info("Starting rendering stack...")
        os.system(env_variables + "cobe-rendering-startup.exe")
        time.sleep(5)

        logger.info(f"Starting database process...")
        # start database process using subprocess.Popen
        database_process = subprocess.Popen(env_variables + "echo y | cbd-start.exe", shell=True)
        time.sleep(2)

        logger.info("Starting eyeservers...")
        eyeserver_process = subprocess.Popen(env_variables + "cbm-start-eyeserver.exe", shell=True)
        time.sleep(5)

        os.system(env_variables + "cbm-start-multieye-kalman.exe --det_target=stick")

        logger.info("Stopping database background process...")
        pid = database_process.pid
        database_process.terminate()
        os.kill(pid, 0)

        logger.info("Shutting down eyeservers...")
        pid = eyeserver_process.pid
        eyeserver_process.terminate()
        os.kill(pid, 0)

    except Exception as e:
        logger.error(f"Error while running metaprotocol: {e}")
        if database_process:
            logger.info("Stopping database background process...")
            pid = database_process.pid
            database_process.terminate()
            os.kill(pid, 0)

        if eyeserver_process:
            logger.info("Shutting down eyeservers...")
            pid = eyeserver_process.pid
            eyeserver_process.terminate()
            os.kill(pid, 0)

def thymio_remote():
    """Metaprotocol for scenario when a single thymio is controlled remotely"""
    # stopping the docker container via the cbp-stop enrypoint
    database_process = None
    eyeserver_process = None
    od_process = None
    thymio_server_process = None
    master_pass = getpass("Enter master password: ")
    try:
        env_variables = "set PM_NUM_PREDATORS=1 && " \
                        "set PM_CENTER_PULL_RADIUS=17 && " \
                        "set PM_BATCH_SIZE=2 && " \
                        "set KALMAN_PROCESS_VAR=0.1 && " \
                        "set KALMAN_MEAS_VAR=0.075 && " \
                        "set MASTER_PASS=" + master_pass + " && "

        delimiter = "\n"
        logger.info(f"Using env variables: {env_variables.replace('&& ', delimiter)}")
        logger.info("Stopping docker container if any is running...")
        os.system("cbp-stop-docker.exe")
        time.sleep(2)

        logger.info("Starting docker container...")
        os.system(env_variables + "cbp-start-docker.exe")
        time.sleep(2)

        logger.info("Starting rendering stack...")
        os.system(env_variables + "cobe-rendering-startup.exe")
        time.sleep(5)

        logger.info(f"Starting database process...")
        # start database process using subprocess.Popen
        database_process = subprocess.Popen(env_variables + "echo y | cbd-start.exe", shell=True)
        time.sleep(2)

        logger.info("Starting eyeservers...")
        eyeserver_process = subprocess.Popen(env_variables + "cbm-start-eyeserver.exe", shell=True)
        time.sleep(6)

        logger.info("Starting object detection...")
        od_process = subprocess.Popen(env_variables + "cbm-start-multieye-kalman.exe --det_target=thymio", shell=True)
        time.sleep(2)

        logger.info("Starting thymio servers...")
        thymio_server_process = subprocess.Popen(env_variables + "cbt-start-thymio-server.exe", shell=True)
        time.sleep(3)

        logger.info("Starting remote control...")
        os.system(env_variables + "cbt-remote.exe")

        logger.info("Stopping thymio servers...")
        pid = thymio_server_process.pid
        thymio_server_process.terminate()
        os.kill(pid, 0)

        logger.info("Stopping object detection...")
        pid = od_process.pid
        od_process.terminate()
        os.kill(pid, 0)

        logger.info("Stopping database background process...")
        pid = database_process.pid
        database_process.terminate()
        os.kill(pid, 0)

        logger.info("Shutting down eyeservers...")
        pid = eyeserver_process.pid
        eyeserver_process.terminate()
        os.kill(pid, 0)

    except Exception as e:
        logger.error(f"Error while running metaprotocol: {e}")
        if database_process:
            logger.info("Stopping database background process...")
            pid = database_process.pid
            database_process.terminate()
            os.kill(pid, 0)

        if eyeserver_process:
            logger.info("Shutting down eyeservers...")
            pid = eyeserver_process.pid
            eyeserver_process.terminate()
            os.kill(pid, 0)

        if od_process:
            logger.info("Stopping object detection...")
            pid = od_process.pid
            od_process.terminate()
            os.kill(pid, 0)

        if thymio_server_process:
            logger.info("Stopping thymio servers...")
            pid = thymio_server_process.pid
            thymio_server_process.terminate()
            os.kill(pid, 0)


def thymio_autopilot():
    """Metaprotocol for scenario when a single thymio is controlled remotely"""
    # stopping the docker container via the cbp-stop enrypoint
    eyeserver_process = None
    od_process = None
    thymio_server_process = None
    master_pass = getpass("Enter master password: ")
    try:
        env_variables = "set PM_NUM_PREDATORS=1 && " \
                        "set PM_CENTER_PULL_RADIUS=17 && " \
                        "set PM_BATCH_SIZE=1 && " \
                        "set KALMAN_PROCESS_VAR=0.1 && " \
                        "set KALMAN_MEAS_VAR=0.075 && " \
                        "set MASTER_PASS=" + master_pass + " && "

        delimiter = "\n"
        logger.info(f"Using env variables: {env_variables.replace('&& ', delimiter)}")
        logger.info("Stopping docker container if any is running...")
        os.system("cbp-stop-docker.exe")
        time.sleep(2)

        logger.info("Starting docker container...")
        os.system(env_variables + "cbp-start-docker.exe")
        time.sleep(2)

        logger.info("Starting eyeservers...")
        eyeserver_process = subprocess.Popen(env_variables + "cbm-start-eyeserver.exe", shell=True)
        time.sleep(3)

        logger.info("Starting rendering stack...")
        os.system(env_variables + "cobe-rendering-startup.exe")
        time.sleep(3)

        logger.info("Starting object detection...")
        od_process = subprocess.Popen(env_variables + "cbm-start-multieye-kalman.exe --det_target=thymio", shell=True)
        time.sleep(2)

        logger.info("Starting thymio servers...")
        thymio_server_process = subprocess.Popen(env_variables + "cbt-start-thymio-server.exe", shell=True)
        time.sleep(3)

        logger.info("Starting remote control...")
        os.system(env_variables + "cbt-autopilot.exe")

        logger.info("Stopping thymio servers...")
        pid = thymio_server_process.pid
        thymio_server_process.terminate()
        os.kill(pid, 0)

        logger.info("Stopping object detection...")
        pid = od_process.pid
        od_process.terminate()
        os.kill(pid, 0)

        logger.info("Stopping database background process...")
        pid = database_process.pid
        database_process.terminate()
        os.kill(pid, 0)

        logger.info("Shutting down eyeservers...")
        pid = eyeserver_process.pid
        eyeserver_process.terminate()
        os.kill(pid, 0)

    except Exception as e:
        logger.error(f"Error while running metaprotocol: {e}")

        if eyeserver_process:
            logger.info("Shutting down eyeservers...")
            pid = eyeserver_process.pid
            eyeserver_process.terminate()
            os.kill(pid, 0)

        if od_process:
            logger.info("Stopping object detection...")
            pid = od_process.pid
            od_process.terminate()
            os.kill(pid, 0)

        if thymio_server_process:
            logger.info("Stopping thymio servers...")
            pid = thymio_server_process.pid
            thymio_server_process.terminate()
            os.kill(pid, 0)




