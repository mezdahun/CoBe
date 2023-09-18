import os
import subprocess
import time
import logging

from cobe.settings import logs
# Setting up file logger
logging.basicConfig(level=logs.log_level, format=logs.log_format)
logger = logs.setup_logger("cobe.metaprotocol")

def single_human():
    """Stopping the docker container, then changes cobe.settings.pmodule, then starts the container again"""
    # stopping the docker container via the cbp-stop enrypoint
    database_process = None
    try:
        env_variables = "set PM_NUM_PREDATORS=1 && " \
                        "set PM_CENTER_PULL_RADIUS=20 && " \
                        "set PM_BATCH_SIZE=8 && " \
                        "set KALMAN_PROCESS_VAR=12 && " \
                        "set KALMAN_MEAS_VAR=0.075 && "

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

        os.system(env_variables + "cbm-start-multieye-kalman.exe --det_target=stick")

        logger.info("Stopping database background process...")
        pid = database_process.pid
        database_process.terminate()
        os.kill(pid, 0)

    except Exception as e:
        logger.error(f"Error while running metaprotocol: {e}")
        if database_process:
            logger.info("Stopping database background process...")
            pid = database_process.pid
            database_process.terminate()
            os.kill(pid, 0)






