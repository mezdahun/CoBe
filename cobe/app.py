import argparse
import os
import random
import time

from cobe.cobe.cobemaster import CoBeMaster, CoBeThymioMaster, file_writer_process
from cobe.database.database import database_daemon_process
from fabric import ThreadingGroup as Group, Config
from getpass import getpass
from cobe.settings import network, database, pmodulesettings
import logging
from cobe.settings import logs, master_settings
from multiprocessing import Process, Queue
from cobe.kalmanprocess.kalmanprocess import kalman_process_OD, kalman_process_OD_multipred
import numpy as np
from datetime import datetime

# Setting up file logger
logging.basicConfig(level=logs.log_level, format=logs.log_format)
logger = logs.setup_logger("cobe.app")


def test_stream():
    """Test streaming of all eyes"""
    master = CoBeMaster()
    master.start_test_stream()


def collect_pngs(eye_id=0):
    """Collects pngs from all eyes"""
    args = argparse.ArgumentParser(description="Starts raw video stream and collects pngs from all or only selected eyes")

    # adding optional arguments
    aid = args.add_argument("--eye_id", default=None, help="ID (int) of the eye (nano board) to start stream on accordin to"
                                                           "settings.network")
    args = args.parse_args()

    if args.eye_id is not None:
        eye_ids = [eye['expected_id'] for eye in network.eyes.values()]
        eye_id = int(args.eye_id)
        if eye_id not in eye_ids:
            raise ValueError(f"Eye ID {eye_id} not found in settings.network")
        eye_name = f"eye_{eye_id}"
        logger.info(f"Start image collection on {eye_name} as requested.")
    else:
        logger.info(f"No eye ID provided. Start image collection on eye_0 as default.")

    master = CoBeMaster(target_eye_name=eye_name)
    master.collect_images_from_stream(target_eye_name=eye_name)


def main(eye_id=0):
    args = argparse.ArgumentParser(description="Starts the the whole stack using a single eye.")

    # adding optional arguments
    aid = args.add_argument("--eye_id", default=None, help="ID (int) of the eye (nano board) to start eyeserver on as in"
                                                           "settings.network")
    args = args.parse_args()
    if args.eye_id is not None:
        eye_ids = [eye['expected_id'] for eye in network.eyes.values()]
        eye_id = int(args.eye_id)
        if eye_id not in eye_ids:
            raise ValueError(f"Eye ID {eye_id} not found in settings.network")

    eye_name = f"eye_{eye_id}"

    master = CoBeMaster(target_eye_name=eye_name)
    master.start(target_eye_name=eye_name)


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


def start_database():
    """Starting database process in a different thread"""

    logger.info(f"Starting database daemon consuming {database.database_input_path}...")

    silent = bool(int(float(os.environ.get("DATABASE_DAEMON_SILENT", 0))))
    if silent:
        logger.info("Database daemon will not ask anything from user as started in silent mode...")

    # check if database input folder exists
    if not os.path.exists(database.database_input_path):
        raise FileNotFoundError(f"Database input folder {database.database_input_path} does not exist. ")

    # check if input folder is empty
    if len(os.listdir(database.database_input_path)) != 0:
        logger.warning(f"Database input folder {database.database_input_path} is not empty. ")
        with_wipe_input = input("Do you want to wipe the input folder and only record data from now on? (y/n)").lower() == 'y'
    else:
        with_wipe_input = False

    if silent:
        with_wipe_input = True

    if not silent:
        db_process = Process(target=database_daemon_process, args=(database.database_input_path, with_wipe_input,))
        db_process.start()
        logger.info("Database daemon started.")
        stop_process = input("Press ENTER to stop the database process...")
        logger.info("Stopping database daemon...")
        db_process.terminate()
        db_process.join()
        logger.info("Database daemon stopped. Nothing will be recorded until restarted!")
    else:
        try:
            database_daemon_process(database.database_input_path, with_wipe_input)
        except FileNotFoundError:
            logger.error(f"Database input process got FileNotFoundError. ")


def main_multieye_kalman():
    logger.info("Starting CoBe with multi-eye mode WITH Kalman-filtering.")

    args = argparse.ArgumentParser(description="Starts the the whole stack using a multiple eyes.")

    # adding optional arguments
    adt = args.add_argument("--det_target", default=None, help="detection target (stick or thymio)")
    args = args.parse_args()

    if args.det_target is not None:
        det_targ = args.det_target.replace(' ', '')
        if det_targ not in ["stick", "thymio"]:
            raise ValueError(f"Detection target '{det_targ}' not supported. Use 'stick' or 'thymio'.")
        else:
            logger.info(f"Detection target set to: {det_targ}")
    else:
        logger.info(f"No detection target provided. Using 'stick' as default.")
        det_targ = "stick"

    if master_settings.master_pass is None:
        pswd = getpass("Provide master password:")
    else:
        logger.info("Master pass provided via env variable, using it...")
        pswd = master_settings.master_pass

    # Creating common queue to push detections
    pred_queue = Queue()
    # Creating kalman process to run in different thread
    if pmodulesettings.num_predators == 1:
        kalman_process = Process(target=kalman_process_OD, args=(pred_queue, None,))
    else:
        kalman_process = Process(target=kalman_process_OD_multipred, args=(pred_queue, None, ))

    # Creating process to run different eyes in different threads
    master = CoBeMaster(pswd=pswd)

    # Creating detection processes for all eyes
    eye_processes = []
    for eye_name in network.eyes.keys():
        logger.info(f"Starting eye {eye_name}")
        eye_process = Process(target=master.start, args=(False, eye_name, 100000, pred_queue, True, det_targ,))
        eye_processes.append(eye_process)

    # Starting eye processes
    kalman_process.start()
    for eye_process in eye_processes:
        eye_process.start()
        time.sleep(0.05)

    input("Press ENTER to stop...")
    logger.info("Stopping CoBe...")

    # Terminating and joining eye processes
    for eye_process in eye_processes:
        try:
            eye_process.terminate()
            eye_process.join()
        except Exception as e:
            logger.error(f"Error terminating eye process: {e}")

    # Terminating and joining kalman process
    kalman_process.terminate()
    kalman_process.join()
    logger.info("CoBe stopped. Bye!")

def main_multieye():
    logger.info("Starting CoBe with multi-eye mode (no Kalman-filtering).")

    args = argparse.ArgumentParser(description="Starts the the whole stack using a multiple eyes.")

    # adding optional arguments
    adt = args.add_argument("--det_target", default=None, help="detection target (stick or thymio)")
    args = args.parse_args()

    if args.det_target is not None:
        det_targ = args.det_target.replace(' ', '')
        if det_targ not in ["stick", "thymio"]:
            raise ValueError(f"Detection target '{det_targ}' not supported. Use 'stick' or 'thymio'.")
        else:
            logger.info(f"Detection target set to: {det_targ}")
    else:
        logger.info(f"No detection target provided. Using 'stick' as default.")
        det_targ = "stick"

    if master_settings.master_pass is None:
        pswd = getpass("Provide master password:")
    else:
        logger.info("Master pass provided via env variable, using it...")
        pswd = master_settings.master_pass

    # Creating common queue to push detections
    pred_queue = Queue()
    # Creating kalman process to run in different thread
    kalman_process = Process(target=file_writer_process, args=(pred_queue, True, 4,))

    # Creating process to run different eyes in different threads
    master = CoBeMaster(pswd=pswd)

    # Creating detection processes for all eyes
    eye_processes = []
    for eye_name in network.eyes.keys():
        logger.info(f"Starting eye {eye_name}")
        eye_process = Process(target=master.start, args=(False, eye_name, 100000, pred_queue, True, det_targ,))
        eye_processes.append(eye_process)

    # Starting eye processes
    kalman_process.start()
    for eye_process in eye_processes:
        eye_process.start()
        time.sleep(0.05)

    input("Press ENTER to stop...")
    logger.info("Stopping CoBe...")

    # Terminating and joining eye processes
    for eye_process in eye_processes:
        try:
            eye_process.terminate()
            eye_process.join()
        except Exception as e:
            logger.error(f"Error terminating eye process: {e}")

    # Terminating and joining kalman process
    kalman_process.terminate()
    kalman_process.join()
    logger.info("CoBe stopped. Bye!")


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


def start_eyeserver_silent():
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
    if master_settings.master_pass is None:
        PSWD = getpass("Provide master password:")
    else:
        logger.info("Master pass provided via env variable, using it...")
        PSWD = master_settings.master_pass

    eye_ips = [eye['host'] for eye in network.eyes.values() if eye['expected_id'] in eye_ids]
    config = Config(overrides={'sudo': {'password': PSWD}})
    eyes = Group(*eye_ips, user=network.nano_username, config=config)
    logger.info(f"Starting eyeservers on {eye_ips}")
    # f any eyes fail to startup we will delete them from the list and ask the user if he wants to proceed
    eyes_to_delete = []
    for ci, c in enumerate(eyes):
        c.connect_kwargs.password = PSWD

        # checking for already running eyeserver instances
        try:
            start_result = c.run('ps ax  | grep "python3 cobe/vision/eye.py"')
        except Exception as e:
            logger.error(f"Error while checking for eyeserver on host {c.host}: {e}\n"
                         f"This can be caused by the nvidia board not being turned on, not being properly\n"
                         f"connected to the local network or having a wrong IP in cobe.settings.network.")

            if ci < len(eyes) - 1:
                proceed = input("Do you want to proceed with the next eye? (y/n): ").lower() == "y"
            else:
                proceed = True

            if proceed:
                eyes_to_delete.append(c)
                continue
            else:
                logger.info("Exiting...")
                return

        num_found_procs = len(start_result.stdout.split("\n"))
        PID = start_result.stdout.split()[0]  # get PID of first subrocess of python3
        found_eye_servers = num_found_procs > 3

        # asking user if they want to restart the eyeserver if already running
        if found_eye_servers:
            logger.info(f"Found {num_found_procs} processes running on host {c.host}.")
            logger.info(f"Seems like eyeserver is already running with PID {PID}, restarting it!")
            restart_eyeserver = True
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
    if master_settings.master_pass is None:
        PSWD = getpass("Provide master password:")
    else:
        logger.info("Master pass provided via env variable, using it...")
        PSWD = master_settings.master_pass

    eye_ips = [eye['host'] for eye in network.eyes.values() if eye['expected_id'] in eye_ids]
    config = Config(overrides={'sudo': {'password': PSWD}})
    eyes = Group(*eye_ips, user=network.nano_username, config=config)
    logger.info(f"Starting eyeservers on {eye_ips}")
    # f any eyes fail to startup we will delete them from the list and ask the user if he wants to proceed
    eyes_to_delete = []
    for ci, c in enumerate(eyes):
        c.connect_kwargs.password = PSWD

        # checking for already running eyeserver instances
        try:
            start_result = c.run('ps ax  | grep "python3 cobe/vision/eye.py"')
        except Exception as e:
            logger.error(f"Error while checking for eyeserver on host {c.host}: {e}\n"
                         f"This can be caused by the nvidia board not being turned on, not being properly\n"
                         f"connected to the local network or having a wrong IP in cobe.settings.network.")

            if ci < len(eyes) - 1:
                proceed = input("Do you want to proceed with the next eye? (y/n): ").lower() == "y"
            else:
                proceed = True

            if proceed:
                eyes_to_delete.append(c)
                continue
            else:
                logger.info("Exiting...")
                return

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

    # deleting eyes that failed to start
    for c in eyes_to_delete:
        logger.info(f"Deleting eye {c.host} from list of eyes as it failed to start...")
        eyes.remove(c)

    if len(eyes) > 0:
        getpass(f'Eye servers started on {[c.host for c in eyes]}. Press any key to stop the eye servers...')

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
    else:
        logger.info("No eyeservers started, exiting...")

def stop_eyeserver():
    """Stops the pyro eyeserver on the eyes defined by settins.network via fabric. Can be used when
    eyeserver keeps running in the background blocking new connections"""
    logger.info("Stopping eye servers...")

    if master_settings.master_pass is None:
        PSWD = getpass("Provide master password:")
    else:
        logger.info("Master pass provided via env variable, using it...")
        PSWD = master_settings.master_pass

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


def thymio_remote_control(thymio_id=0):
    """Starts Thymio remote control to selected thymio"""

    args = argparse.ArgumentParser(description="Starts the the whole stack using a single eye.")

    # adding optional arguments
    aid = args.add_argument("--thymio_id", default=None, help="ID (int) of the thymio (nano board) to start thymioserver on as in"
                                                           "settings.network")
    args = args.parse_args()
    if args.thymio_id is not None:
        thymio_ids = [thymio['expected_id'] for thymio in network.thymios.values()]
        thymio_id = int(args.thymio_id)
        if thymio_id not in thymio_ids:
            raise ValueError(f"thymio ID {thymio_id} not found in settings.network")

    if f"thymio_{thymio_id}" not in network.thymios.keys():
        raise ValueError(f"Thymio ID {thymio_id} not found in settings.network")


    thymio_controller = CoBeThymioMaster(target_thymio_name=f"thymio_{thymio_id}")
    thymio_controller.start_remote_control()

def rand_filler_proc(output_queue, start_position=np.array([0, 0])):
    """Random filler process to test queue-based processes"""
    prev_position = start_position
    while True:
        random_position = np.array([random.randint(-20, 20)/20, random.randint(-20, 20)/20])
        new_position = prev_position + random_position
        output_queue.put([new_position])
        print(f"putting {new_position} into queue")
        prev_position = new_position
        time.sleep(0.1)

def thymio_autopilot():
    # creating process to fill com_queue with random positions
    logger.info("Creating center of mass queue...")
    com_queue = Queue()
    # filler_proc = Process(target=rand_filler_proc, args=(com_queue, np.array([0, 0]),))
    # filler_proc.start()

    # cretaing process to fill thymio_queue with random positions
    logger.info("Creating thymio queue...")
    thymio_queue = Queue()
    # thymio_proc = Process(target=rand_filler_proc, args=(thymio_queue, np.array([2, -2]),))
    # thymio_proc.start()

    # start database process that read json files writed db and forwards them to the thymio
    logger.info(f"Starting database daemon consuming {database.database_input_path}...")

    # check if database input folder exists
    if not os.path.exists(database.database_input_path):
        raise FileNotFoundError(f"Database input folder {database.database_input_path} does not exist. ")

    # check if input folder is empty
    with_wipe_input = True

    db_process = Process(target=database_daemon_process, args=(database.database_input_path, with_wipe_input,
                                                               com_queue, thymio_queue,))

    thmyio_master = CoBeThymioMaster(target_thymio_name="thymio_0")

    autopilot_process = Process(target=thmyio_master.thymio_autopilot, args=(thymio_queue, com_queue, False,))

    db_process.start()
    logger.info("Database daemon started and passed com and thymio queues.")
    autopilot_process.start()
    logger.info("Autopilot started.")

    input("Press enter to stop autopilot...")

    logger.info("Stopping autopilot...")
    autopilot_process.terminate()
    autopilot_process.join()
    logger.info("Autopilot stopped.")

    logger.info("Stopping thymios")
    thmyio_master.stop_thymios()

    logger.info("Stopping database daemon...")
    db_process.terminate()
    db_process.join()
    logger.info("Database daemon stopped.")



def start_thymioserver(th_id=None):
    """Starts the pyro thymioserver on the thymios defined by settins.network via fabric"""

    args = argparse.ArgumentParser(description="Starts the pyro5 thymio servers on the chosen thymios")

    # adding optional arguments
    aid = args.add_argument("--thymio_id", default=None, help="ID (int) of the thymio (rpi board) to start thymioserver on as in"
                                                           "settings.network.thymios")
    args = args.parse_args()

    if args.thymio_id is not None:
        th_ids = [thymio['expected_id'] for thymio in network.thymios.values()]
        th_id = int(args.thymio_id)
        if th_id not in th_ids:
            raise ValueError(f"Thymio ID {th_id} not found in settings.network")
        th_ids = [th_id]
    else:
        th_ids = [th['expected_id'] for th in network.thymios.values()]

    logger.info("Starting thymio servers...")

    if master_settings.master_pass is None:
        PSWD = getpass("Provide master password:")
    else:
        logger.info("Master pass provided via env variable, using it...")
        PSWD = master_settings.master_pass

    th_ips = [thymio['host'] for thymio in network.thymios.values() if thymio['expected_id'] in th_ids]
    config = Config(overrides={'sudo': {'password': PSWD}})
    thymios = Group(*th_ips, user=network.pi_username, config=config)
    logger.info(f"Starting thymioservers on {th_ips}")
    # if any thymios fail to startup we will delete them from the list and ask the user if he wants to proceed
    thymios_to_delete = []
    for ci, c in enumerate(thymios):
        c.connect_kwargs.password = PSWD

        # checking for already running thymioserver instances
        try:
            start_result = c.run('ps ax  | grep "cobe-thymio-start"')
        except Exception as e:
            logger.error(f"Error while checking for thymioserver on host {c.host}: {e}\n"
                         f"This can be caused by the nvidia board not being turned on, not being properly\n"
                         f"connected to the local network or having a wrong IP in cobe.settings.network.")

            if ci < len(thymios) - 1:
                proceed = input("Do you want to proceed with the next thymio? (y/n): ").lower() == "y"
            else:
                proceed = True

            if proceed:
                thymios_to_delete.append(c)
                continue
            else:
                logger.info("Exiting...")
                return

        num_found_procs = len(start_result.stdout.split("\n"))
        PID = start_result.stdout.split()[0]  # get PID of first subrocess of python3
        found_thymio_servers = num_found_procs > 3

        # asking user if they want to restart the thymioserver if already running
        if found_thymio_servers:
            logger.info(f"Found {num_found_procs} processes running on host {c.host}.")
            logger.info(f"Seems like thymioserver is already running with PID {PID}, skipping...")
            restart_thymioserver = input("Do you want to restart/update the thymioserver? (y/n): ").lower() == "y"
        else:
            restart_thymioserver = False

        # restarting thymioserver if requested
        if restart_thymioserver:
            c.run(f'kill -INT -{int(PID)}')
            logger.info(f"Killed thymioserver on host {c.host}, will restart now...")
        else:
            logger.info(f"thymioserver stop/restart was not requested on host {c.host}. Maybe no instance was running"
                        f"or requested to skip restarting.")

        # starting a new thymio server if it was not running or a restart was requested
        if not found_thymio_servers or restart_thymioserver:
            # starting thymioserver
            logger.info(f'Starting thymioserver on host {c.host}')
            c.run(f'cd {network.pi_cobe_installdir} && '
                  'git pull && '
                  'ls && '
                  f'ROBOT_ID={th_ids[ci]} dtach -n /tmp/tmpdtach '
                  f'pipenv run cobe-thymio-start --host={c.host} --port={network.unified_thymioserver_port}',
                  hide=True,
                  pty=False)
            logger.info(f'Started thymioserver on host {c.host}')
        time.sleep(5)

    # deleting thymios that failed to start
    for c in thymios_to_delete:
        logger.info(f"Deleting thymio {c.host} from list of thymios as it failed to start...")
        thymios.remove(c)

    if len(thymios) > 0:
        getpass(f'thymio servers started on {[c.host for c in thymios]}. Press any key to stop the thymio servers...')

        logger.info('Killing thymio-server processes by collected PIDs...')
        for c in thymios:
            logger.info(f'Stopping thymioserver on host {c.host}')
            c.connect_kwargs.password = PSWD
            start_result = c.run('ps ax  | grep "cobe-thymio-start"')
            PID = start_result.stdout.split()[0]  # get PID of first subrocess of python3
            logger.info(f"Found server process with PID: {PID}, killing it...")
            # sending INT SIG to the main process will trigger graceful exit (equivalent to KeyboardInterrup)
            c.run(f'kill -INT -{int(PID)}')
            logger.info(f"Killed thymioserver on host {c.host}")
        time.sleep(5)

        # Shutting down the physical nvidia boards if requested
        is_shutdown = input("Do you want to shutdown the thymios? (y/n): ")
        if is_shutdown.lower() == "y":
            logger.info("Shutting down thymios...")
            for c in thymios:
                c.connect_kwargs.password = PSWD
                c.sudo(f'shutdown -h now', warn=True, shell=False)
                logger.info(f"Shutting down host {c.host}")
            logger.info("Shutdown complete.")
    else:
        logger.info("No thymio servers started, exiting...")


def start_thymioserver_silent(th_id=None):
    """Starts the pyro thymioserver on the thymios defined by settins.network via fabric"""

    args = argparse.ArgumentParser(description="Starts the pyro5 thymio servers on the chosen thymios")

    # adding optional arguments
    aid = args.add_argument("--thymio_id", default=None, help="ID (int) of the thymio (rpi board) to start thymioserver on as in"
                                                           "settings.network.thymios")
    args = args.parse_args()

    if args.thymio_id is not None:
        th_ids = [thymio['expected_id'] for thymio in network.thymios.values()]
        th_id = int(args.thymio_id)
        if th_id not in th_ids:
            raise ValueError(f"Thymio ID {th_id} not found in settings.network")
        th_ids = [th_id]
    else:
        th_ids = [th['expected_id'] for th in network.thymios.values()]

    logger.info("Starting thymio servers...")

    if master_settings.master_pass is None:
        PSWD = getpass("Provide master password:")
    else:
        logger.info("Master pass provided via env variable, using it...")
        PSWD = master_settings.master_pass

    th_ips = [thymio['host'] for thymio in network.thymios.values() if thymio['expected_id'] in th_ids]
    config = Config(overrides={'sudo': {'password': PSWD}})
    thymios = Group(*th_ips, user=network.pi_username, config=config)
    logger.info(f"Starting thymioservers on {th_ips}")
    # if any thymios fail to startup we will delete them from the list and ask the user if he wants to proceed
    thymios_to_delete = []
    for ci, c in enumerate(thymios):
        c.connect_kwargs.password = PSWD

        # checking for already running thymioserver instances
        try:
            start_result = c.run('ps ax  | grep "cobe-thymio-start"')
        except Exception as e:
            logger.error(f"Error while checking for thymioserver on host {c.host}: {e}\n"
                         f"This can be caused by the nvidia board not being turned on, not being properly\n"
                         f"connected to the local network or having a wrong IP in cobe.settings.network.")

            if ci < len(thymios) - 1:
                proceed = input("Do you want to proceed with the next thymio? (y/n): ").lower() == "y"
            else:
                proceed = True

            if proceed:
                thymios_to_delete.append(c)
                continue
            else:
                logger.info("Exiting...")
                return

        num_found_procs = len(start_result.stdout.split("\n"))
        PID = start_result.stdout.split()[0]  # get PID of first subrocess of python3
        found_thymio_servers = num_found_procs > 3

        # asking user if they want to restart the thymioserver if already running
        if found_thymio_servers:
            logger.info(f"Found {num_found_procs} processes running on host {c.host}.")
            logger.info(f"Seems like thymioserver is already running with PID {PID}, skipping...")
            restart_thymioserver = True
        else:
            restart_thymioserver = False

        # restarting thymioserver if requested
        if restart_thymioserver:
            c.run(f'kill -INT -{int(PID)}')
            logger.info(f"Killed thymioserver on host {c.host}, will restart now...")
        else:
            logger.info(f"thymioserver stop/restart was not requested on host {c.host}. Maybe no instance was running"
                        f"or requested to skip restarting.")

        # starting a new thymio server if it was not running or a restart was requested
        if not found_thymio_servers or restart_thymioserver:
            # starting thymioserver
            logger.info(f'Starting thymioserver on host {c.host}')
            c.run(f'cd {network.pi_cobe_installdir} && '
                  'git pull && '
                  'ls && '
                  f'ROBOT_ID={th_ids[ci]} dtach -n /tmp/tmpdtach '
                  f'pipenv run cobe-thymio-start --host={c.host} --port={network.unified_thymioserver_port}',
                  hide=True,
                  pty=False)
            logger.info(f'Started thymioserver on host {c.host}')
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

    if eye_id == -1:
        master_target_eye_name = None
    else:
        master_target_eye_name = f"eye_{eye_id}"

    master = CoBeMaster(target_eye_name=master_target_eye_name)
    if on_screen:
        # generaating calibration image on screen if requested
        master.calibrator.generate_calibration_image(detach=True)
    ## Start calibration
    master.calibrate(with_visualization=True, interactive=True, detach=True, eye_id=eye_id)
