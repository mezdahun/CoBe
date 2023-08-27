import argparse
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


def start_eyeserver(eye_id=None):
    """Starts the pyro eyeserver on the eyes defined by settins.network via fabric"""

    args = argparse.ArgumentParser(description="Starts the pyro5 eye servers on the chosen eyes")

    # adding optional arguments
    aid = args.add_argument("--eye_id", default=None, help="ID (int) of the eye (nano board) to start eyeserver on as in"
                                                           "settings.network")
    args = args.parse_args()

    if args.eye_id is not None:
        eye_ids = [eye['expected_id'] for eye in network.eyes.values()]
        eye_id = int(args.eye_id)
        if eye_id not in eye_ids:
            raise ValueError(f"Eye ID {eye_id} not found in settings.network")
        eye_ids = [eye_id]
    else:
        eye_ids = [eye['expected_id'] for eye in network.eyes.values()]

    logger.info("Starting eye servers...")
    PSWD = getpass('sudo password to start eyeservers: ')
    eye_ips = [eye['host'] for eye in network.eyes.values() if eye['expected_id'] in eye_ids]
    config = Config(overrides={'sudo': {'password': PSWD}})
    eyes = Group(*eye_ips, user=network.nano_username, config=config)
    logger.info(f"Starting eyeservers on {eye_ips}")
    for ci, c in enumerate(eyes):
        c.connect_kwargs.password = PSWD

        # checking for already running eyeserver instances
        start_result = c.run('ps ax  | grep "python3 cobe/vision/eye.py"')
        num_found_procs = len(start_result.stdout.split("\n"))
        PID = start_result.stdout.split()[0]  # get PID of first subrocess of python3
        found_eye_servers = num_found_procs > 3

        # asking user if they want to restart the eyeserver if already running
        if found_eye_servers:
            logger.info(f"Found {num_found_procs} processes running on host {c.host}.")
            logger.info(f"Seems like eyeserver is already running with PID {PID}, skipping...")
            restart_eyeserver = input("Do you want to restart/update the eyeserver? (y/n): ").lower() == "y"
        else:
            restart_eyeserver = False

        # restarting eyeserver if requested
        if restart_eyeserver:
            c.run(f'kill -INT -{int(PID)}')
            logger.info(f"Killed eyeserver on host {c.host}, will restart now...")
        else:
            logger.info(f"Eyeserver stop/restart was not requested on host {c.host}. Maybe no instance was running"
                        f"or requested to skip restarting.")

        # starting a new eye server if it was not running or a restart was requested
        if not found_eye_servers or restart_eyeserver:
            # starting eyeserver
            logger.info(f'Starting eyeserver on host {c.host}')
            c.run(f'cd {network.nano_cobe_installdir} && '
                  'git pull && '
                  'ls && '
                  f'EYE_ID={eye_ids[ci]} dtach -n /tmp/tmpdtach '
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


def stop_eyeserver():
    """Stops the pyro eyeserver on the eyes defined by settins.network via fabric. Can be used when
    eyeserver keeps running in the background blocking new connections"""
    logger.info("Stopping eye servers...")
    PSWD = getpass('sudo password to start eyeservers: ')
    eye_ips = [eye['host'] for eye in network.eyes.values()]
    config = Config(overrides={'sudo': {'password': PSWD}})
    eyes = Group(*eye_ips, user=network.nano_username, config=config)
    for c in eyes:
        c.connect_kwargs.password = PSWD
        logger.info('Killing eye-server processes by collected PIDs...')
        for c in eyes:
            logger.info(f'Stopping eyeserver on host {c.host}')
            c.connect_kwargs.password = PSWD
            start_result = c.run('ps ax  | grep "python3 cobe/vision/eye.py"')
            num_found_procs = len(start_result.stdout.split("\n"))
            PID = start_result.stdout.split()[0]  # get PID of first subrocess of python3
            found_eye_servers = num_found_procs > 3
            if found_eye_servers:
                logger.info(f"Found server process with PID: {PID}, killing it...")
                # sending INT SIG to the main process will trigger graceful exit (equivalent to KeyboardInterrup)
                c.run(f'kill -INT -{int(PID)}')
                logger.info(f"Killed eyeserver on host {c.host}")
            else:
                logger.info(f"Seems like eyeserver is not running on host {c.host}, skipping...")
        time.sleep(5)


def calibrate(eye_id=-1, on_screen=False):
    """Test Calibration of all eyes interactively
    :param eye_id: ID of the eye to be calibrated as in settings.network. If -1 (default) all eyes will be calibrated.
    """
    args = argparse.ArgumentParser(description="Calibrates the mapping of CoBe eyes via projected ARUCO codes")

    # adding optional arguments
    aid = args.add_argument("--eye_id", default=None, help="ID (int) of the eye (nano board) to be calibrated as in "
                                                           "settings.network")
    aos = args.add_argument("--on_screen", default=False, help="If set to True, the calibration target will be "
                                                               "displayed on the computer screen instead "
                                                               "of the projectors")
    args = args.parse_args()

    if args.eye_id is not None:
        eye_id = int(args.eye_id)
    if args.on_screen is not None:
        on_screen = bool(args.on_screen)


    master = CoBeMaster()
    if on_screen:
        # generaating calibration image on screen if requested
        master.calibrator.generate_calibration_image(detach=True)
    ## Start calibration
    master.calibrate(with_visualization=True, interactive=True, detach=True, eye_id=eye_id)
