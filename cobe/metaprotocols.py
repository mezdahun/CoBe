import os
import signal
import subprocess
import time
import logging
from getpass import getpass

from cobe.settings import logs
# Setting up file logger
logging.basicConfig(level=logs.log_level, format=logs.log_format)
logger = logs.setup_logger("cobe.metaprotocol")

import psutil

def kill(proc_pid):
    try:
        process = psutil.Process(proc_pid)
        for proc in process.children(recursive=True):
            proc.kill()
        process.kill()
    except:
        logger.info(f"Pocess with pid {proc_pid} not found")
        pass

def single_human():
    """Metaprotocol to run for single human case"""
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
                        "set MASTER_PASS=" + master_pass + " && " \
                        "set DATABASE_DAEMON_SILENT=1 && "

        delimiter = "\n"
        logger.info(f"Using env variables: {env_variables.replace('&& ', delimiter)}")
        logger.info("Stopping docker container if any is running...")
        os.system("cbp-stop-docker.exe")
        time.sleep(2)

        input(f"Press enter to continue...")

        logger.info("Starting docker container...")
        os.system(env_variables + "cbp-start-docker.exe")
        time.sleep(2)

        input(f"Press enter to continue...")

        logger.info("Starting eyeservers...")
        eyeserver_process = subprocess.Popen(env_variables + "cbv-start-eyeserver-silent.exe", shell=True)
        time.sleep(5)

        input(f"Press enter to continue...")

        logger.info("Starting rendering stack...")
        os.system(env_variables + "cobe-rendering-startup.exe")
        time.sleep(5)

        input(f"Press enter to continue...")

        logger.info(f"Starting database process...")
        # start database process using subprocess.Popen
        database_process = subprocess.Popen(env_variables + "echo y | cbd-start.exe", shell=True)
        time.sleep(2)

        input(f"Press enter to continue...")
        os.system(env_variables + "cbm-start-multieye-kalman.exe --det_target=stick")

        logger.info("Stopping database background process...")
        kill(database_process.pid)

        logger.info("Shutting down eyeservers...")
        kill(eyeserver_process.pid)

        logger.info("Stopping docker container if any is running...")
        os.system("cbp-stop-docker.exe")

    except Exception as e:
        logger.error(f"Error while running metaprotocol: {e}")
        if database_process:
            logger.info("Stopping database background process...")
            kill(database_process.pid)

        if eyeserver_process:
            logger.info("Shutting down eyeservers...")
            kill(eyeserver_process.pid)

        logger.info("Stopping docker container if any is running...")
        os.system("cbp-stop-docker.exe")



def multi_human():
    """Metaprotocol to run for multiple human case"""
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
                        "set MASTER_PASS=" + master_pass + " && " \
                        "set DATABASE_DAEMON_SILENT=1 && "

        delimiter = "\n"
        logger.info(f"Using env variables: {env_variables.replace('&& ', delimiter)}")
        logger.info("Stopping docker container if any is running...")
        os.system("cbp-stop-docker.exe")
        time.sleep(2)

        input(f"Press enter to continue...")

        logger.info("Starting docker container...")
        os.system(env_variables + "cbp-start-docker.exe")
        time.sleep(2)

        input(f"Press enter to continue...")

        logger.info("Starting eyeservers...")
        eyeserver_process = subprocess.Popen(env_variables + "cbv-start-eyeserver-silent.exe", shell=True)
        time.sleep(5)

        input(f"Press enter to continue...")

        logger.info("Starting rendering stack...")
        os.system(env_variables + "cobe-rendering-startup.exe")
        time.sleep(5)

        input(f"Press enter to continue...")

        logger.info(f"Starting database process...")
        # start database process using subprocess.Popen
        database_process = subprocess.Popen(env_variables + "echo y | cbd-start.exe", shell=True)
        time.sleep(2)

        input(f"Press enter to continue...")
        os.system(env_variables + "cbm-start-multieye-kalman.exe --det_target=stick")

        logger.info("Stopping database background process...")
        kill(database_process.pid)

        logger.info("Shutting down eyeservers...")
        kill(eyeserver_process.pid)

        logger.info("Stopping docker container if any is running...")
        os.system("cbp-stop-docker.exe")

    except Exception as e:
        logger.error(f"Error while running metaprotocol: {e}")
        if database_process:
            logger.info("Stopping database background process...")
            kill(database_process.pid)

        if eyeserver_process:
            logger.info("Shutting down eyeservers...")
            kill(eyeserver_process.pid)

        logger.info("Stopping docker container if any is running...")
        os.system("cbp-stop-docker.exe")

def thymio_remote():
    """Metaprotocol to run for multiple human case"""
    # stopping the docker container via the cbp-stop enrypoint
    database_process = None
    eyeserver_process = None
    od_process = None
    thymio_server_process = None
    remote_process = None

    master_pass = getpass("Enter master password: ")
    try:
        env_variables = "set PM_NUM_PREDATORS=1 && " \
                        "set PM_CENTER_PULL_RADIUS=17 && " \
                        "set PM_BATCH_SIZE=2 && " \
                        "set KALMAN_PROCESS_VAR=0.1 && " \
                        "set KALMAN_MEAS_VAR=0.075 && " \
                        "set MASTER_PASS=" + master_pass + " && " \
                        "set DATABASE_DAEMON_SILENT=1 && "

        delimiter = "\n"
        logger.info(f"Using env variables: {env_variables.replace('&& ', delimiter)}")
        logger.info("Stopping docker container if any is running...")
        os.system("cbp-stop-docker.exe")
        time.sleep(2)

        input(f"Press enter to continue...")

        logger.info("Starting docker container...")
        os.system(env_variables + "cbp-start-docker.exe")
        time.sleep(2)

        input(f"Press enter to continue...")

        logger.info("Starting eyeservers...")
        eyeserver_process = subprocess.Popen(env_variables + "cbv-start-eyeserver-silent.exe", shell=True)
        time.sleep(5)

        input(f"Press enter to continue...")

        logger.info("Starting rendering stack...")
        os.system(env_variables + "cobe-rendering-startup.exe")
        time.sleep(5)

        input(f"Press enter to continue...")

        logger.info(f"Starting database process...")
        # start database process using subprocess.Popen
        database_process = subprocess.Popen(env_variables + "echo y | cbd-start.exe", shell=True)
        time.sleep(2)

        input(f"Press enter to continue...")
        logger.info("Starting thymio servers...")
        thymio_server_process = subprocess.Popen(env_variables + "cbt-start-thymioserver-silent.exe", shell=True)
        time.sleep(3)

        input(f"Press enter to continue...")
        logger.info("Starting remote control...")
        remote_process = subprocess.Popen(env_variables + "cbt-remote.exe", shell=True)

        input(f"Press enter to continue...")
        logger.info("Starting object detection...")
        os.system(env_variables + "cbm-start-multieye-kalman.exe --det_target=thymio")
        time.sleep(2)

        logger.info("Stopping database background process...")
        kill(database_process.pid)

        logger.info("Shutting down eyeservers...")
        kill(eyeserver_process.pid)

        logger.info("Stopping object detection...")
        kill(od_process.pid)

        logger.info("Stopping remote control...")
        kill(remote_process.pid)

        logger.info("Stopping thymio servers...")
        kill(thymio_server_process.pid)

        logger.info("Stopping docker container if any is running...")
        os.system("cbp-stop-docker.exe")


    except Exception as e:
        logger.error(f"Error while running metaprotocol: {e}")
        if database_process:
            logger.info("Stopping database background process...")
            kill(database_process.pid)

        if eyeserver_process:
            logger.info("Shutting down eyeservers...")
            kill(eyeserver_process.pid)

        if od_process:
            logger.info("Stopping object detection...")
            kill(od_process.pid)

        if remote_process:
            logger.info("Stopping remote control...")
            kill(remote_process.pid)

        if thymio_server_process:
            logger.info("Stopping thymio servers...")
            kill(thymio_server_process.pid)

        logger.info("Stopping docker container if any is running...")
        os.system("cbp-stop-docker.exe")


def thymio_autopilot():
        # stopping the docker container via the cbp-stop enrypoint
    database_process = None
    eyeserver_process = None
    od_process = None
    thymio_server_process = None
    remote_process = None

    master_pass = getpass("Enter master password: ")
    try:
        env_variables = "set PM_NUM_PREDATORS=1 && " \
                        "set PM_CENTER_PULL_RADIUS=17 && " \
                        "set PM_BATCH_SIZE=1 && " \
                        "set KALMAN_PROCESS_VAR=0.1 && " \
                        "set KALMAN_MEAS_VAR=0.075 && " \
                        "set MASTER_PASS=" + master_pass + " && " \
                        "set DATABASE_DAEMON_SILENT=1 && "

        delimiter = "\n"
        logger.info(f"Using env variables: {env_variables.replace('&& ', delimiter)}")
        logger.info("Stopping docker container if any is running...")
        os.system("cbp-stop-docker.exe")
        time.sleep(2)

        input(f"Press enter to continue...")

        logger.info("Starting docker container...")
        os.system(env_variables + "cbp-start-docker.exe")
        time.sleep(2)

        input(f"Press enter to continue...")

        logger.info("Starting eyeservers...")
        eyeserver_process = subprocess.Popen(env_variables + "cbv-start-eyeserver-silent.exe", shell=True)
        time.sleep(5)

        input(f"Press enter to continue...")

        logger.info("Starting rendering stack...")
        os.system(env_variables + "cobe-rendering-startup.exe")
        time.sleep(5)

        input(f"Press enter to continue...")

        # logger.info(f"Starting database process...")
        # # start database process using subprocess.Popen
        # database_process = subprocess.Popen(env_variables + "echo y | cbd-start.exe", shell=True)
        # time.sleep(2)

        input(f"Press enter to continue...")
        logger.info("Starting thymio servers...")
        thymio_server_process = subprocess.Popen(env_variables + "cbt-start-thymioserver-silent.exe", shell=True)
        time.sleep(3)

        input(f"Press enter to continue...")
        logger.info("Starting remote control...")
        remote_process = subprocess.Popen(env_variables + "cbt-autopilot.exe", shell=True)

        input(f"Press enter to continue...")
        logger.info("Starting object detection...")
        os.system(env_variables + "cbm-start-multieye-kalman.exe --det_target=thymio")
        time.sleep(2)

        logger.info("Stopping database background process...")
        kill(database_process.pid)

        logger.info("Shutting down eyeservers...")
        kill(eyeserver_process.pid)

        logger.info("Stopping object detection...")
        kill(od_process.pid)

        logger.info("Stopping remote control...")
        kill(remote_process.pid)

        logger.info("Stopping thymio servers...")
        kill(thymio_server_process.pid)

        logger.info("Stopping docker container if any is running...")
        os.system("cbp-stop-docker.exe")


    except Exception as e:
        logger.error(f"Error while running metaprotocol: {e}")
        if database_process:
            logger.info("Stopping database background process...")
            kill(database_process.pid)

        if eyeserver_process:
            logger.info("Shutting down eyeservers...")
            kill(eyeserver_process.pid)

        if od_process:
            logger.info("Stopping object detection...")
            kill(od_process.pid)

        if remote_process:
            logger.info("Stopping remote control...")
            kill(remote_process.pid)

        if thymio_server_process:
            logger.info("Stopping thymio servers...")
            kill(thymio_server_process.pid)

        logger.info("Stopping docker container if any is running...")
        os.system("cbp-stop-docker.exe")




