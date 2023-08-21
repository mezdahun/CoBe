import time

from cobe.cobe.cobemaster import CoBeMaster
from fabric import ThreadingGroup as Group, Config
from getpass import getpass
from cobe.settings import network
import logging
from cobe.settings import logs
from multiprocessing import Process, Queue
from cobe.kalmanprocess.kalmanprocess import kalman_process_OD
import numpy as np
from datetime import datetime

# Setting up file logger
logging.basicConfig(level=logs.log_level, format=logs.log_format)
logger = logs.setup_logger("cobe.app")


def test_stream():
    """Test streaming of all eyes"""
    master = CoBeMaster()
    master.start_test_stream()


def collect_pngs():
    """Collects pngs from all eyes"""
    master = CoBeMaster()
    master.collect_images_from_stream()


def main():
    master = CoBeMaster()
    master.start()


def main_kalman():
    # Creating queue to push real detection coordinates
    od_to_kalman_queue = Queue()
    # Creating process to run kalman filter in different thread
    kalman_process = Process(target=kalman_process_OD, args=(od_to_kalman_queue, None, ))
    # Starting kalman process
    kalman_process.start()
    # Starting cobe master and passing shared queue
    master = CoBeMaster()
    master.start(kalman_queue=od_to_kalman_queue)
    # Terminating kalman process when master finished
    kalman_process.terminate()
    kalman_process.join()


def cleanup_inf_servers():
    """Cleans up the inference servers on all eyes"""
    master = CoBeMaster()
    master.cleanup_inference_servers()


def shutdown_eyes():
    """Shuts down all eyes"""
    master = CoBeMaster()
    master.shutdown_eyes()


def shutdown_rendering():
    """Shuts down all rendering"""
    master = CoBeMaster()
    master.shutdown_rendering_stack()


def startup_rendering():
    master = CoBeMaster()
    master.startup_rendering_stack()


def start_eyeserver():
    """Starts the pyro eyeserver on the eyes defined by settins.network via fabric"""
    logger.info("Starting eye servers...")
    PSWD = getpass('sudo password to start eyeservers: ')
    eye_ips = [eye['host'] for eye in network.eyes.values()]
    config = Config(overrides={'sudo': {'password': PSWD}})
    eyes = Group(*eye_ips, user=network.nano_username, config=config)
    for c in eyes:
        c.connect_kwargs.password = PSWD
        c.run(f'cd {network.nano_cobe_installdir} && '
              'git stash && '
              'git pull && '
              'git stash pop && '
              'ls && '
              'dtach -n /tmp/tmpdtach '
              f'python3 cobe/vision/eye.py --host={c.host} --port={network.unified_eyeserver_port}',
              hide=True,
              pty=False)
        logger.info(f'Started eyeserver on host {c.host}')
        time.sleep(5)

        getpass('Eye servers started. Press any key to stop the eye servers...')

        logger.info('Killing eye-server processes by collected PIDs...')
        for c in eyes:
            logger.info(f'Stopping eyeserver on host {c.host}')
            c.connect_kwargs.password = PSWD
            start_result = c.run('ps ax  | grep "python3 cobe/vision/eye.py"')
            PID = start_result.stdout.split()[0]  # get PID of first subrocess of python3
            logger.info(f"Found server process with PID: {PID}, killing it...")
            # sending INT SIG to the main process will trigger graceful exit (equivalent to KeyboardInterrup)
            c.run(f'kill -INT -{int(PID)}')
            logger.info(f"Killed eyeserver on host {c.host}")
        time.sleep(5)

        # Shutting down the physical nvidia boards if requested
        is_shutdown = input("Do you want to shutdown the eyes? (y/n): ")
        if is_shutdown.lower() == "y":
            logger.info("Shutting down eyes...")
            for c in eyes:
                c.connect_kwargs.password = PSWD
                c.sudo(f'shutdown -h now', warn=True, shell=False)
                logger.info(f"Shutting down host {c.host}")
            logger.info("Shutdown complete.")


def calibrate():
    """Test Calibration of all eyes interactively"""
    master = CoBeMaster()
    master.calibrate(with_visualization=True, interactive=True, detach=True)
    # master.calibrator.generate_calibration_image(detach=True)
