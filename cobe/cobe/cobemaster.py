"""
CoBe - CoBe - Master

The Master class is the main entry point for the CoBe project. It is responsible for
They
    - can configure mapping between cameras and reals space by communicating with a Calib object
    - can be started (main action loop)
    - when started in each iteration call Eyes via Pyro5 to get the latest inference results
    - can remap detections according to camera mapping
    - can call the Pmodule and consume its results
    - can pass final coordinate results to the projection stack via Unity

"""
import os
import queue
import time
from datetime import datetime
import cv2
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.tri as tri

from Pyro5.api import Proxy
from time import sleep
from getpass import getpass
from scipy.interpolate import Rbf
from pynput import keyboard

from cobe.settings.pmodulesettings import max_abs_coord
from cobe.settings import network, odmodel, aruco, vision, logs, pmodulesettings, master_settings
from cobe.rendering.renderingstack import RenderingStack
from cobe.pmodule.pmodule import generate_pred_json
from cobe.tools import cropzoomtool, movement_tools

# Setting up file logger
import logging

logging.basicConfig(level=logs.log_level, format=logs.log_format)
logger = logs.setup_logger(__name__.split(".")[-1])

def get_latest_element(target_queue, with_print=False):
    """Get latest element from queue without removing it"""
    if with_print:
        print(target_queue.qsize())
    val = None
    for i in range(target_queue.qsize()):
        try:
            val = target_queue.get_nowait()
            if with_print:
                print(f"Got {val} from queue.")
        except queue.Empty:
            return val

    return val


def filter_detections(detections, det_target="feet"):
    """Choosing correct detectionposition according to body parts
    :param detections: list of detections
    :param det_target: class to filter for
    :return: list of detections with only one detection"""
    # deciding which bunding box to use
    logger.debug("Filtering detections.")
    stick_dets = [det for det in detections if det["class"] == "stick"]
    feet_dets = [det for det in detections if det["class"] == "feet"]
    trunk_dets = [det for det in detections if det["class"] == "trunk"]
    head_dets = [det for det in detections if det["class"] == "head"]
    thymio_dets = [det for det in detections if det["class"] == "thymio"]

    # If a stick is visible we override any other detections, this is the preferred detection
    if det_target == "stick":
        if len(stick_dets) > 0:
            logger.debug("Using stick detection.")
            detections = stick_dets
        else:
            # Otherwise we prefer feet detections, but that is impossible in some positions
            detections = []
    elif det_target == "feet":
        if len(feet_dets) > 0:
            logger.debug("Using feet detection.")
            detections = feet_dets
        else:
            # Otherwise we prefer feet detections, but that is impossible in some positions
            detections = []
    elif det_target == "thymio":
        if len(thymio_dets) > 0:
            logger.debug("Using thymio detection.")
            detections = thymio_dets
        else:
            # Otherwise we prefer feet detections, but that is impossible in some positions
            detections = []
        # if len(feet_dets) > 0:
        #     logger.debug("Using feet detection.")
        #     detections = feet_dets
        # elif len(feet_dets) > 0:
        #     # todo: draw a line from head through trunk and estimate feet position, or alternatively
        #     #  estimate feet position according to the excentricity of trunk and head detections. I.e. if head detected
        #     #  in upper part of image, feet are probably in lower part of image according to radial distortion.
        #     logger.debug("Using feet detection.")
        #     detections = feet_dets
        # elif len(trunk_dets) > 0:
        #     logger.debug("Using trunk detection.")
        #     detections = trunk_dets
        # elif len(head_dets) > 0:
        #     logger.debug("Using head detection.")
        #     detections = head_dets
        # else:
        #     detections = []

    if len(detections) > pmodulesettings.num_predators:
        logger.debug(f"More than 1 detection. Detections before sorting: {detections}")
        detections = sorted(detections, key=lambda x: x["confidence"], reverse=True)
        detections = [detections[i] for i in range(pmodulesettings.num_predators)]
    logger.debug(f"Chosen detection after filtering: {detections}")
    return detections

class CoBeThymioMaster(object):
    """The main class to control thymio robots via pyro5"""
    def __init__(self, pswd=None, target_thymio_name="thymio_0"):
        """Constructor for CoBeMaster"""
        # thymios of the pyro network
        self.target_th_name = target_thymio_name
        self.thymios = self.create_thymio_objects()

    def create_thymio_objects(self):
        """Creates thymio Pyro objects from the network settings"""
        thymios = {}
        for th_name, th_data in network.thymios.items():
            if self.target_th_name is not None and th_name != self.target_th_name:
                logger.info(f"Skipping thymio {th_name} during creating CoBeMaster class because it is not the target thymio.")
                continue
            try:
                thymios[th_name] = {"pyro_proxy": Proxy(
                    th_data["uri"] + th_data["name"] + "@" + th_data["host"] + ":" + th_data["port"])}
                thymios[th_name]["th_data"] = th_data
                # testing created thymio by accessing public Pyro method and comparing outcome with expected ID
                assert int(thymios[th_name]["pyro_proxy"].return_id()) == int(thymios[th_name]["th_data"]["expected_id"])
                logger.debug(f"Eye {th_name} created successfully in CoBeMaster instance.")
            except Exception as e:
                logger.warning(f"Error creating thymio {th_name}: {e}")
                logger.warning(f"This can happen because of a wrong URI or the thymio not being on or the thymioserver not "
                               f"running."
                               f"Proceeding now without this thymio: {th_name}")
                logger.warning(f"If this is not intended please debug according to the wiki! All thymios should be turned on,"
                               f"reachable via ssh (connected to local network) with URIs set in the network settings,"
                               f"and all has to have a running Pyro5 thymioserver.")
                del thymios[th_name]
        return thymios

    def start_remote_control(self):
        """Start main remote control loop"""
        if self.target_th_name is None:
            target = "thymio_0"
            logger.info("No target thymio specified, using thymio_0.")
        else:
            target = self.target_th_name

        logger.info(f"Starting remote control for thymio {target}.")
        thymio = self.thymios[target]["pyro_proxy"]


        logger.info("Controls:"
                    "\n\tW: Move forward, Speed up"
                    "\n\tS: Move backward, Slow down"
                    "\n\tA: Turn left"
                    "\n\tD: Turn right"
                    "\n\tSpace: Stop"
                    "\n\tF1: Quit")
        thymio.light_up_led(0, 0, 32)
        while True:
            # The event listener will be running in this block, check if buttons are pressed
            with keyboard.Events() as events:
                # Block at most one second
                event = events.get(0.1)
                if event is None:
                    thymio.pass_time()
                elif isinstance(event, keyboard.Events.Press):
                    if 'char' in dir(event.key):  # check if char method exists,
                        if event.key.char == "w":
                            thymio.speed_up()
                            logger.info("Forward / Speed up")
                            thymio.pass_time()
                        elif event.key.char == "s":
                            thymio.slow_down()
                            logger.info("Backward / Slow down")
                            thymio.pass_time()
                        elif event.key.char == "a":
                            thymio.turn_left()
                            logger.info("Turning left")
                            continue
                        elif event.key.char == "d":
                            thymio.turn_right()
                            logger.info("Turning right")
                            continue
                    elif event.key == keyboard.Key.f1:
                        logger.info("Quitting")
                        thymio.stop()
                        thymio.light_up_led(0, 32, 0)
                        return
                    elif event.key == keyboard.Key.space:
                        thymio.stop()
                        logger.info("Stopping")
                        thymio.pass_time()
                    else:
                        thymio.pass_time()

                thymio.pass_time()

    def stop_thymios(self):
        """Setting thymio velocities to zero and turn them green"""
        for th_name, th_data in self.thymios.items():
            th_data["pyro_proxy"].stop()
            th_data["pyro_proxy"].light_up_led(0, 32, 0)

    def thymio_autopilot(self, thymio_dets_queue, center_of_mass_queue, with_keyboard=True):
        """Controlling a single thymio automatically to chase the fish swarm's center of mass"""
        if self.target_th_name is None:
            target = "thymio_0"
            logger.info("No target thymio specified, using thymio_0.")
        else:
            target = self.target_th_name

        logger.info(f"Starting autopilot for thymio {target}.")
        thymio = self.thymios[target]["pyro_proxy"]

        #####
        thymio.light_up_led(0, 0, 32)
        prev_thymio_pos = (0, 0)
        update_thymio_pos_in = np.random.randint(0, 5)
        last_pos_update = 0
        prev_com_pos = (0, 0)
        border = pmodulesettings.max_abs_coord
        centralization_border = border * 0.85
        mode = "chase"  # "chase" or "centralize" or "explore"

        chase_distance = 0.45  # percent of arena

        turning_precision_chase = 0.225

        turning_precision_centralize = 0.95
        break_centralize_percent = 0.85

        swarm_center_threshold = 7
        turning_precision_chase_center = 0.16


        prev_thymio_movement_vec = (0, 0)

        max_turning = 0.3
        max_speed = 275

        t = 0
        center_target = (0, 0)
        explore_target = (0, 0)
        num_jitters = 0
        while True:
            time.sleep(0.05)
            # get thymio detections as a list of tuples (x, y)

            thymio_detections = get_latest_element(thymio_dets_queue)
            if thymio_detections is None:
                #time.sleep(0.05)
                continue
            print(f"Queue size: {thymio_dets_queue.qsize()}")
            print(f"Prev thymio pos: {prev_thymio_pos}")
            print(f"Thymio detections: {thymio_detections}")
            # while True:
            # get center of mass of fish swarm

            com_pos = get_latest_element(center_of_mass_queue)
            if com_pos is None:
                com_pos = prev_com_pos
            else:
                print(f"COM: {com_pos}")
                com_pos = com_pos[0]

            # choosing the closest position to the previous one for tracking purpose
            if len(thymio_detections) > 0:
                distances = []
                for det in thymio_detections:
                    distances.append(np.linalg.norm(np.array(det) - np.array(prev_thymio_pos)))

                print(f"Distances: {distances}")
                # refusing to proceed if the closest detection is too far away
                closest_det = thymio_detections[np.argmin(distances)]
                print(f"Closest det: {closest_det}")

            elif len(thymio_detections) == 0:
                print("No detections")
                time.sleep(0.05)
                continue
            else:
                closest_det = thymio_detections[0]

            thymio_pos = closest_det

            # check distance to center of mass
            distance_to_com = np.linalg.norm(np.array(thymio_pos) - np.array(com_pos))
            print(f"Distance to COM: {distance_to_com}")

            # if the thymio is close enough to the center of mass, it will start chasing the fish
            if distance_to_com < chase_distance * pmodulesettings.max_abs_coord * 2:
                if mode == "explore":
                    # if the thymio is close enough to the center of mass, it will start chasing the fish
                    mode = "chase"
                    logger.info("Chasing fish")
                    thymio.light_up_led(0, 0, 32)
                elif mode == "centralize":
                    # if the thymio is not close to the border anymore, it will start chasing the fish
                    if np.linalg.norm(np.array(thymio_pos)) < border*break_centralize_percent:
                        mode = "chase"
                        logger.info("Chasing fish")
                        thymio.light_up_led(0, 0, 32)
                elif mode == "chase":
                    if distance_to_com < swarm_center_threshold:
                        turning_precision = turning_precision_chase_center

            else:
                if mode == "chase":
                    # otherwise it explores the arena
                    mode = "explore"
                    logger.info("Exploring arena")
                    thymio.light_up_led(32, 0, 32)
                    explore_target = (np.random.uniform(-border, border), np.random.uniform(-border, border))
                    logger.info(f"Selecting random target point: {com_pos}")
                elif mode == "explore":
                    if np.linalg.norm(np.array(thymio_pos) - np.array(com_pos)) < 0.1 * pmodulesettings.max_abs_coord:
                        # if the thymio is close enough to the target point, it will select another one
                        com_pos = (np.random.uniform(-border, border), np.random.uniform(-border, border))
                        logger.info(f"Selecting random target point: {com_pos}")

            # If the thymio is currently at the border, it will aim back towards the center of the arena instead of
            # the center of mass of the fish swarm
            # if thymio_pos[0] > border or thymio_pos[0] < -border or thymio_pos[1] > border or thymio_pos[1] < -border:
            print(f"norm: {np.linalg.norm(np.array(thymio_pos))}")
            if np.linalg.norm(np.array(thymio_pos)) > border:
                if mode in ["chase", "explore"]:
                    mode = "centralize"
                    logger.info("Centralizing Thymio as it reached border during chase")
                    thymio.light_up_led(32, 32, 32)
                    # random choice between one of the corners
                    # check in which quadrant the robot is and select the opposite corner
                    if thymio_pos[0] > 0:
                        if thymio_pos[1] > 0:
                            center_target = (-border * 0.5, -border * 0.5)
                        else:
                            center_target = (-border * 0.5, border * 0.5)
                    else:
                        if thymio_pos[1] > 0:
                            center_target = (border * 0.5, -border * 0.5)
                        else:
                            center_target = (border * 0.5, border * 0.5)
                    # center_target = (np.random.choice([-1, 1]) * border * 0.5, np.random.choice([-1, 1]) * border * 0.5)
                    logger.info(f"Selecting random target point: {center_target}")
            # check if the thymio is in the 10% radius range of center of the arena to start exploring / chasing the fish again
            elif np.linalg.norm(np.array(thymio_pos) - np.array(center_target)) < pmodulesettings.max_abs_coord * 0.1:
                if mode == "centralize":
                    mode = "chase"
                    logger.info("Chasing fish again as Thymio reached center of arena during centralization")
                    thymio.light_up_led(0, 0, 32)

            if mode == "centralize":
                # changing the target position to the center of the arena if centralizing
                com_pos = center_target
                turning_precision = turning_precision_centralize
            elif mode == "chase":
                turning_precision = turning_precision_chase
            elif mode == "explore":
                com_pos = explore_target
                turning_precision = turning_precision_chase


            # calculate angle of movement for thymio according to previous and current position
            thymio_movement_vec = np.array(thymio_pos) - np.array(prev_thymio_pos)

            # calculate angle between thymio previous position and center of mass
            com_dir_vec = np.array(com_pos) - np.array(prev_thymio_pos)

            # calculate closed angle
            try:
                closed_angle = movement_tools.angle_between(thymio_movement_vec, com_dir_vec)
                print(closed_angle)

                if np.isnan(closed_angle):
                    closed_angle = 0
            except:
                print("Error in angle calculation")
                time.sleep(0.05)
                continue

            speed = max_speed
            print(f"closed angle before: {closed_angle}")
            # match direction standard
            closed_angle = -closed_angle

            print(f"update thymio prev position: {thymio_pos}")
            # check if the position is coming from a jitter
            if t > 1:
                # check if the direction of movement has opposite signs
                # if np.sign(prev_thymio_movement_vec[0]) != np.sign(thymio_movement_vec[0]) and np.sign(prev_thymio_movement_vec[1]) != np.sign(thymio_movement_vec[1]):
                #     print("Jitter detected, ignoring position")
                #     num_jitters += 1
                #     print(f"num jitters: {num_jitters}")
                # if movement_tools.angle_between(prev_thymio_movement_vec, thymio_movement_vec) < 0:
                #     print(f"Jitter detected with angle: {movement_tools.angle_between(prev_thymio_movement_vec, thymio_movement_vec)}")
                #     num_jitters += 1
                #     print(f"num jitters: {num_jitters}")
                # else:
                logger.info(f"Did not detect jitter with angle {movement_tools.angle_between(prev_thymio_movement_vec, thymio_movement_vec)}")
                if np.abs(t-last_pos_update) >= update_thymio_pos_in:
                    logger.info("Updating Thymio position")
                    prev_thymio_pos = thymio_pos
                    last_pos_update = t
                    update_thymio_pos_in = 1
                prev_thymio_movement_vec = thymio_movement_vec


            if mode in ["chase", "explore"]:
                final_turning = np.sign(closed_angle) * min(max_turning, abs(closed_angle * turning_precision))
                thymio.move_with_speed_and_angle(speed, float(final_turning))
            else:
                final_turning = np.sign(closed_angle) * min(1, abs(closed_angle))
                thymio.move_with_speed_and_angle(speed, float(final_turning))

            logger.info(f"moving with speed {speed} and angle {closed_angle}->{final_turning}")

            prev_com_pos = com_pos

            # The event listener will be running in this block, check if buttons are pressed
            if with_keyboard:
                with keyboard.Events() as events:
                    # Block at most one second
                    event = events.get(0.5)
                    if event is None:
                        pass
                    elif isinstance(event, keyboard.Events.Press):
                        if event.key == keyboard.Key.f2:
                            logger.info("Quitting")
                            thymio.stop()
                            thymio.light_up_led(0, 32, 0)
                            return

            t += 1

class CoBeMaster(object):
    """The main class of the CoBe project, organizing action flow between detection, processing and projection"""
    def __init__(self, pswd=None, target_eye_name=None):
        """Constructor for CoBeMaster"""
        # eyes of the network
        self.target_eye_name = target_eye_name
        self.eyes = self.create_eye_objects()
        # create calibration object for the run
        self.calibrator = CoBeCalib()
        # create rendering stack
        self.rendering_stack = RenderingStack()
        # path of current files directory's parent directory
        self.file_dir_path = os.path.dirname(os.path.abspath(__file__))
        # parent directory
        self.cobe_root_dir = os.path.abspath(os.path.join(self.file_dir_path, os.pardir))
        # calib data dir
        self.calib_data_dir = os.path.join(self.cobe_root_dir, "settings", "calibration_data")
        # requesting master password for nanos if they are not set yet
        self.check_pswds(pswd)

    def check_pswds(self, pswd=None):
        """Checking if the password is already set on the eyes and if not asking from user"""
        ask_for_pswd = False
        if pswd is None:
            for eye_name, eye_dict in self.eyes.items():
                if not eye_dict["pyro_proxy"].has_pswd():
                    logger.info(f"Eye {eye_name} does not have a password set.")
                    ask_for_pswd = True
                    break

        if ask_for_pswd:

            if master_settings.master_pass is None:
                nano_password = getpass("Provide master password:")
            else:
                logger.info("Master pass provided via env variable, using it...")
                nano_password = master_settings.master_pass

            for eye_name, eye_dict in self.eyes.items():
                eye_dict["pyro_proxy"].set_pswd(nano_password)
        elif pswd is not None:
            for eye_name, eye_dict in self.eyes.items():
                eye_dict["pyro_proxy"].set_pswd(pswd)

    def create_eye_objects(self):
        """Creates eye Pyro objects from the network settings"""
        eyes = {}
        for eye_name, eye_data in network.eyes.items():
            if self.target_eye_name is not None and eye_name != self.target_eye_name:
                logger.info(f"Skipping eye {eye_name} during creating CoBeMaster class because it is not the target eye.")
                continue
            try:
                eyes[eye_name] = {"pyro_proxy": Proxy(
                    eye_data["uri"] + eye_data["name"] + "@" + eye_data["host"] + ":" + eye_data["port"])}
                eyes[eye_name]["eye_data"] = eye_data
                # # adding fisheye calibration map for eye
                eyes[eye_name]["pyro_proxy"].set_fisheye_calibration_map(eye_data["fisheye_calibration_map"])
                # testing created eye by accessing public Pyro method and comparing outcome with expected ID
                assert int(eyes[eye_name]["pyro_proxy"].return_id()) == int(eyes[eye_name]["eye_data"]["expected_id"])
                logger.debug(f"Eye {eye_name} created successfully in CoBeMaster instance.")
            except Exception as e:
                logger.warning(f"Error creating eye {eye_name}: {e}")
                logger.warning(f"This can happen because of a wrong URI or the eye not being on or the eyeserver not "
                               f"running."
                               f"Proceeding now without this eye: {eye_name}")
                logger.warning(f"If this is not intended please debug according to the wiki! All eyes should be turned on,"
                               f"reachable via ssh (connected to local network) with URIs set in the network settings,"
                               f"and all has to have a running Pyro5 eyeserver.")
                del eyes[eye_name]
        return eyes

    def initialize_object_detectors(self, target_eye_name=None):
        """Starting the roboflow inference servers on all the eyes and carry out a single detection to initialize
        the model weights. This needs WWW access on the eyes as it downloads model weights from Roboflow"""
        logger.info("Initializing object detectors...")
        if target_eye_name is not None:
            eye_ids = [eye["expected_id"] for eye in network.eyes.values()]
        else:
            eye_ids = [self.eyes[target_eye_name]["eye_data"]["expected_id"]]

        for eye_name, eye_dict in self.eyes.items():
            if eye_dict["eye_data"]["expected_id"] in eye_ids:
                # start docker servers
                logger.info(f"Starting inference server on {eye_name}.")
                eye_dict["pyro_proxy"].start_inference_server()
                sleep(2)

        logger.info("Waiting for inference servers to start...")
        sleep(5)
        for eye_name, eye_dict in self.eyes.items():
            if eye_dict["eye_data"]["expected_id"] in eye_ids:
                # carry out a single detection to initialize the model weights
                logger.debug(f"Initializing model on {eye_name}. Model parameters: {odmodel.model_name}, "
                             f"{odmodel.model_id}, {odmodel.inf_server_url}, {odmodel.version}")
                eye_dict["pyro_proxy"].initODModel(api_key=odmodel.api_key,
                                                   model_name=odmodel.model_name,
                                                   model_id=odmodel.model_id,
                                                   inf_server_url=odmodel.inf_server_url,
                                                   version=odmodel.version)

    def calculate_calibration_maps(self, with_visualization=False, interactive=False, detach=False, with_save=True, eye_id=-1):
        """Calculates the calibration maps for each eye and stores them in the eye dict
        :param with_visualization: if True, the calibration maps are visualized
        :param interactive: if True, the calibration maps are regenerated until the user agrees with quality
        :param detach: if True, the calibration maps are calculated in a separate thread
        :param with_save: if True, the calibration maps are saved to disk as json files
        :param eye_id: id of eye to be calibrated. if -1 all of them will be claibrated 1-by-1"""

        if eye_id == -1:
            eyes_to_calib = [i for i in range(len(self.eyes))]
        else:
            eyes_to_calib = [eye_id]

        logger.info(f"Eyes with ID {eyes_to_calib} will be calibrated.")
        retry = {eye_name: True for eye_name in self.eyes.keys()}


        for eye_name, eye_dict in self.eyes.items():
            eye_i = int(eye_name.split('_')[-1])
            if eye_i in eyes_to_calib:
                logger.info(f"Calibrating eye {eye_name} as requested.")
                is_map_loaded = self.load_calibration_map(eye_name, eye_dict)
                is_pattern_projected = False
                if not is_map_loaded:
                    logger.info(f"Calculating calibration maps for {eye_name}.")
                    logger.debug("Sending calibration image to projectors...")
                    try:
                        self.project_calibration_image()
                        sleep(3)
                        is_pattern_projected = True
                    except Exception as e:
                        logger.error(f"Exception while projecting calibration image: {e}")
                        logger.error("Trying to continue without projecting calibration image.")

                    while retry[eye_name]:
                        eyes_in_calib = {eye_name: eye_dict}
                        # get a single calibration image from every eye object
                        logger.debug("Fetching calibration images from eyes...")
                        self.calibrator.fetch_calibration_frames(eyes_in_calib)

                        # detect the aruco marker mesh on the calibration images and save data in eye dicts
                        logger.debug("Detecting ARUCO codes...")
                        self.calibrator.detect_ARUCO_codes(eyes_in_calib)

                        # calculate the calibration maps for each eye and store them in the eye dict
                        logger.debug("Calculating calibration maps...")
                        self.calibrator.interpolate_xy_maps(eyes_in_calib, with_visualization=with_visualization, detach=detach)

                        if interactive:
                            retry_input = input("Press r to retry calibration, or enter to continue...")
                            if retry_input == "r":
                                retry[eye_name] = True
                            else:
                                logger.info(f"Calibration results accepted by user for {eye_name}.")
                                retry[eye_name] = False
                                self.eyes[eye_name] = eyes_in_calib[eye_name]
                            if with_visualization:
                                # closing all matplotlib windows after calibration
                                plt.close("all")
                        else:
                            retry[eye_name] = False
                            self.eyes[eye_name] = eyes_in_calib[eye_name]

                if is_pattern_projected:
                    logger.debug("Removing calibration image from projectors...")
                    self.remove_calibration_image()
                    sleep(3)
            else:
                logger.info(f"Skipping calibration for {eye_name} according to calibration agruments.")

        self.save_calibration_maps(eye_id=eye_id)
        if with_visualization:
            # closing all matplotlib windows after calibration
            plt.close("all")

        logger.info("Calibration maps calculated and saved.")

    def save_calibration_maps(self, eye_id=-1):
        """Saves the calibration maps and eye settings for each eye's predefined json file"""

        if not os.path.isdir(self.calib_data_dir):
            logger.info(f"Creating calibration data directory at {self.calib_data_dir} as it does not exist.")
            os.makedirs(self.calib_data_dir, exist_ok=True)

        if eye_id == -1:
            eye_names = self.eyes.keys()
        else:
            eye_names = [f"eye_{eye_id}"]

        for eye_name, eye_dict in self.eyes.items():
            if eye_name in eye_names:
                # creating file path
                file_path = os.path.join(self.calib_data_dir, f"{eye_name}_calibdata.json")
                eye_dict_to_save = eye_dict.copy()

                # deleting pyro proxy and detected aruco code from dict as they are not serializable
                del eye_dict_to_save["pyro_proxy"]
                if eye_dict_to_save.get("detected_aruco"):
                    del eye_dict_to_save["detected_aruco"]

                # jsonifying dictionary
                for k, v in eye_dict_to_save.items():
                    if isinstance(v, np.ndarray):
                        eye_dict_to_save[k] = v.tolist()

                # saving json file
                with open(file_path, "w") as f:
                    json.dump(eye_dict_to_save, f)
                logger.info(f"Calibration map for {eye_name} saved to {file_path}.")

    def load_calibration_map(self, eye_name, eye_dict, force_load=False):
        """Loads the calibration maps and eye settings for each eye from json files
        :param eye_name: name of the eye
        :param eye_dict: dictionary containing the eye data
        :return: True if calibration map was loaded, False if not"""
        # creating file path
        file_path = os.path.join(self.calib_data_dir, f"{eye_name}_calibdata.json")
        if os.path.isfile(file_path):
            if not force_load:
                load_map_input = input(
                    f"Calibration map for {eye_name} found in {file_path}. Do you want to load it? (Y/n)")
            else:
                load_map_input = "y"
            if load_map_input.lower() == "y":
                logger.info(f"Loading calibration map for {eye_name} from {file_path}")
                with open(file_path, "r") as f:
                    loaded_data = json.load(f)
                    # Loading eye settings from json file
                    eye_dict["eye_data"] = loaded_data["eye_data"]
                    # Loading calibration related data from json file
                    eye_dict["calibration_frame"] = np.array(loaded_data["calibration_frame"])
                    eye_dict["calibration_score"] = loaded_data["calibration_score"]
                    eye_dict["calibration_frame_annot"] = np.array(loaded_data["calibration_frame_annot"])
                    eye_dict["cmap_xmap_interp"] = np.array(loaded_data["cmap_xmap_interp"])
                    eye_dict["cmap_ymap_interp"] = np.array(loaded_data["cmap_ymap_interp"])
                    eye_dict["cmap_x_interp"] = np.array(loaded_data["cmap_x_interp"])
                    eye_dict["cmap_y_interp"] = np.array(loaded_data["cmap_y_interp"])
                    eye_dict["cmap_xmap_extrap"] = np.array(loaded_data["cmap_xmap_extrap"])
                    eye_dict["cmap_ymap_extrap"] = np.array(loaded_data["cmap_ymap_extrap"])
                    eye_dict["cmap_x_extrap"] = np.array(loaded_data["cmap_x_extrap"])
                    eye_dict["cmap_y_extrap"] = np.array(loaded_data["cmap_y_extrap"])
                logger.info(f"Calibration map for {eye_name} loaded.")
                return True
            else:
                logger.info(f"Calibration map for {eye_name} **NOT** loaded.")
                return False
        else:
            # no calibration map found so a new map is necessary
            return False

    def cleanup_inference_servers(self, waitfor=3):
        """Cleans up inference servers on all eyes.
        Waiting for waitfor seconds between each stop and remove operation"""
        for eye_name, eye_dict in self.eyes.items():
            # stop docker servers
            sleep(waitfor)
            logger.info(f"Stopping inference server on {eye_name}...")
            eye_dict["pyro_proxy"].stop_inference_server()

            # waiting for docker to stop the container
            sleep(waitfor)
            logger.info(f"Removing inference server on {eye_name}...")
            eye_dict["pyro_proxy"].remove_inference_server()

    def shutdown_eyes(self, waitfor=5):
        """Shutting down all eye servers by raising KeyboardInterrupt on each eye"""
        sleep(waitfor)
        for eye_name, eye_dict in self.eyes.items():
            eye_dict["pyro_proxy"].shutdown()

    def remap_detection_point(self, eye_dict, xcam, ycam):
        """Remaps a detection point from camera space to real space according to the calibration maps."""
        # First trying to get a more accurate interpolated value from the calibration map
        # find index of closest x value in eyes calibration map to provided xcam
        # x_index = np.abs(eye_dict["cmap_x_interp"] - xcam).argmin()
        # logger.debug(f"xcam: {xcam}, x_index: {x_index}")
        # # find index of closest y value in eyes calibration map to provided ycam
        # y_index = np.abs(eye_dict["cmap_y_interp"] - ycam).argmin()
        # logger.debug(f"ycam: {ycam}, y_index: {y_index}")
        # # return the real space coordinates for the provided camera space coordinates
        # xreal, yreal = eye_dict["cmap_xmap_interp"][y_index, x_index], eye_dict["cmap_ymap_interp"][y_index, x_index]
        # # todo: implement remapping with extrapolated values if interpolated values are not valid
        # # # if the interpolated value is not valid, return the nearest value from the extrapolated calibration map
        # if xreal is None or yreal is None:
        # x_index = np.abs(eye_dict["cmap_x_interp"] - xcam).argmin()
        # # find index of closest y value in eyes calibration map to provided ycam
        # logger.debug("No interpolated value found for xcam!")
        # y_index = np.abs(eye_dict["cmap_y_interp"] - ycam).argmin()
        # # find index of closest y value in eyes calibration map to provided ycam
        # logger.debug("No interpolated value found for ycam!")
        # xreal = eye_dict["cmap_xmap_interp"][y_index, x_index]
        # yreal = eye_dict["cmap_ymap_interp"][y_index, x_index]
        # logger.warning(f"xcam: {xcam}, x_index interpol: {x_index}")
        # logger.warning(f"ycam: {ycam}, y_index interpol: {y_index}")
        # logger.warning(f"xreal interpol: {xreal}, yreal interpol: {yreal}")

        x_index = np.abs(eye_dict["cmap_x_extrap"] - xcam).argmin()
        # find index of closest y value in eyes calibration map to provided ycam
        logger.debug("No interpolated value found for xcam!")
        y_index = np.abs(eye_dict["cmap_y_extrap"] - ycam).argmin()
        # find index of closest y value in eyes calibration map to provided ycam
        logger.debug("No interpolated value found for ycam!")
        xreal = eye_dict["cmap_xmap_extrap"][y_index, x_index]
        yreal = eye_dict["cmap_ymap_extrap"][y_index, x_index]
        # logger.info(f"X  - min extrap: {np.min(eye_dict['cmap_xmap_extrap'])}, max: {np.max(eye_dict['cmap_xmap_extrap'])}")
        # logger.info(f"Y  - min extrap: {np.min(eye_dict['cmap_ymap_extrap'])}, max: {np.max(eye_dict['cmap_ymap_extrap'])}")
        # logger.info(f"X  - min interp: {np.nanmin(eye_dict['cmap_xmap_interp'][eye_dict['cmap_xmap_interp'] != None])}, max: {np.nanmax(eye_dict['cmap_xmap_interp'][eye_dict['cmap_xmap_interp'] != None])}")
        # logger.info(f"Y  - min interp: {np.nanmin(eye_dict['cmap_ymap_interp'][eye_dict['cmap_xmap_interp'] != None])}, max: {np.nanmax(eye_dict['cmap_ymap_interp'][eye_dict['cmap_xmap_interp'] != None])}")
        # logger.warning(f"xcam: {xcam}, x_index extrapol: {x_index}")
        # logger.warning(f"ycam: {ycam}, y_index extrapol: {y_index}")
        # logger.warning(f"xreal extrapol: {xreal}, yreal extrapol: {yreal}")
        # xreal, yreal = 0, 0

        # todo: remove double switching of coordinates
        xreal, yreal = yreal, xreal
        logger.debug(f"xreal: {xreal}, yreal: {yreal}")
        return xreal, yreal

    def demo_remapping(self, eye_name="eye_0"):
        """Demo function to show the remapping of a detection point from camera space to simulation space"""
        plt.ion()
        fig, (axcam, axreal) = plt.subplots(ncols=2)
        fig.canvas.draw()

        aruco_image = self.calibrator.generate_calibration_image(return_image=True)

        # Showing the recorded calibration frame to visualize camera space
        plt.axes(axcam)
        plt.imshow(self.eyes[eye_name]["calibration_frame_annot"])
        plt.title("Calibration frame with ARUCO detections")

        # Showing the calibration image with the ARUCO codes to visualize camera space
        plt.axes(axreal)
        plt.imshow(aruco_image, cmap='gray')
        plt.title("Original calibration image on simulation space")

        xs = np.arange(0, vision.display_width, 50)
        ys = np.arange(0, vision.display_height, 50)

        for xcam in xs:
            for ycam in ys:
                xreal, yreal = self.remap_detection_point(self.eyes[eye_name], xcam, ycam)
                if np.ma.is_masked(xreal) or np.ma.is_masked(yreal):
                    xreal, yreal = 0, 0
                if xreal != 0 and yreal != 0:
                    logger.info("----")
                    logger.info(xcam, ycam)
                    logger.info(xreal, yreal)

                    plt.axes(axcam)
                    plt.scatter(xcam, ycam, c='r', marker='o')
                    plt.title("Camera space")
                    plt.xlim(0, vision.display_width)
                    plt.ylim(0, vision.display_height)

                    plt.axes(axreal)
                    plt.scatter(xreal, yreal, c='r', marker='o', s=80)
                    plt.title("Simulation space")
                    plt.xlim(0, aruco.proj_calib_image_width)
                    plt.ylim(0, aruco.proj_calib_image_width)

                    plt.pause(0.001)

    def calibrate(self, with_visualization=True, interactive=True, detach=True, eye_id=-1):
        """Calibrating eyes using the projection stack
        :param with_visualization: if True, the calibration process will be visualized
        :param interactive: if True, the calibration process will be interactive and will be retried if quality is not
                            sufficient
        :param detach: if True, the calibration process will be detached from the main process"""
        logger.debug("Starting calibration...")
        self.calculate_calibration_maps(with_visualization=with_visualization, interactive=interactive, detach=detach, eye_id=eye_id)
        sleep(2)

    def start_test_stream(self, t=300):
        """Starting a test stream on all eyes for t iterations without any inference to measure FPS/camera position."""
        for it in range(t):
            for eye_name, eye_dict in self.eyes.items():
                # timing framerate of calibration frames
                start_time = datetime.now()
                # getting calibration frame and publishing on the streaming server
                eye_dict["pyro_proxy"].get_calibration_frame()
                # timing framerate of calibration frames
                end_time = datetime.now()
                delta_time = end_time - start_time
                # print FPS with overwriting previous line
                logger.info(f"FPS~ on eye {eye_name}: ", int(1 / delta_time.total_seconds()))

    def collect_images_from_stream(self, t_max=3000, target_eye_name="eye_0", auto_freq=1.5):
        """Collecting and saving images from all eyes when s button is pressed.
        Quitting when q button is pressed.
        :param t_max: maximum number of iterations after which automatically quitting
        :param target_eye_name: name of the eye for which images should be collected
        :param auto_freq: 1/frequency in seconds at which images should be collected automatically
        :interact space: press space to save image
        :interact q: press q to quit
        interact up: press up arrow to start automatic image collection"""
        # attributes for autocapture feature
        auto_on = False
        timer = datetime.now()
        switch_time = datetime.now()
        # path of current file
        file_path = os.path.dirname(os.path.realpath(__file__))
        # path of current directory
        dir_path = os.path.dirname(file_path)
        # path of parent directory
        root_path = os.path.dirname(dir_path)
        save_path = os.path.join(root_path, "data", "calibration_images")
        # create directory if it does not exist
        if not os.path.exists(save_path):
            os.makedirs(save_path, exist_ok=True)

        logger.info(f"Starting to collect images from eye {target_eye_name}...\n"
                    f"Press: \n"
                    f"--ESC \t\tto quit,\n"
                    f"--SPACE \tto save image to {save_path},\n"
                    f"--UP \t\tarrow to turn on/off autocapture in every {auto_freq} seconds\n"
                    f"--DOWN \t\tarrow to start setting Crop/Zoom of camera")
        for it in range(t_max):
            for eye_name, eye_dict in self.eyes.items():
                if eye_name == target_eye_name:
                    eye_dict["pyro_proxy"].get_calibration_frame()

                    # check timer and autocapture status
                    if (datetime.now() - timer).total_seconds() > auto_freq and auto_on:
                        # saving frame as image in every auto_freq seconds
                        cap = cv2.VideoCapture(f'http://{eye_dict["eye_data"]["host"]}:8000/calibration.mjpg')
                        ret, frame = cap.read()
                        cv2.imwrite(os.path.join(save_path, f"{eye_name}_{it}.png"), frame)
                        logger.info(f"Auto-saved image {eye_name}_{it}.png")
                        # reset timer
                        timer = datetime.now()

                    # The event listener will be running in this block, check if buttons are pressed
                    with keyboard.Events() as events:
                        # Block at most one second
                        event = events.get(0.1)
                        if event is None:
                            pass
                        elif event.key == keyboard.Key.esc:
                            logger.info("Quitting")
                            return
                        elif event.key == keyboard.Key.space:
                            # saving frame as image
                            # todo: cleanup the mjpeg server paths as global settings
                            cap = cv2.VideoCapture(f'http://{eye_dict["eye_data"]["host"]}:8000/calibration.mjpg')
                            ret, frame = cap.read()
                            cv2.imwrite(os.path.join(save_path, f"{eye_name}_{it}.png"), frame)
                            logger.info(f"Saved image {eye_name}_{it}.png")
                        elif event.key == keyboard.Key.down:
                            cap = cv2.VideoCapture(f'http://{eye_dict["eye_data"]["host"]}:8000/calibration.mjpg')
                            ret, frame = cap.read()
                            cropzoomtool.cropzoomparameters(eye_name, frame)
                        elif event.key == keyboard.Key.up:
                            if auto_on and (datetime.now() - switch_time).total_seconds() > 1:
                                auto_on = False
                                logger.info("Autocapture OFF")
                                timer = datetime.now()
                                switch_time = datetime.now()
                            elif not auto_on and (datetime.now() - switch_time).total_seconds() > 1:
                                auto_on = True
                                logger.info("Autocapture ON")
                                timer = datetime.now()
                                switch_time = datetime.now()
        logger.info("Finished collecting images. Bye Bye!")

    def start(self, show_simulation_space=False, target_eye_name="eye_0", t_max=10000, kalman_queue=None, no_calib=False, det_target="stick"):
        """Starts the main action loop of the CoBe project
        :param show_simulation_space: if True, the remapping to simulation space will be visualized as
                                        matplotlib plot
        :param target_eye_name: name of the eye for which remapping should be visualized (only if show_simulation_space
                                is True)
        :param t_max: maximum number of iterations after which automatically quitting, otherwise press ESC
        :param kalman_queue: queue for sending data to the Kalman filter"""

        # Preparing eyes for running
        try:
            logger.info("Starting rendering stack...")
            self.startup_rendering_stack()
        except Exception as e:
            logger.error(f"Could not start rendering stack: {e}")
            proceed = input("Do you want to proceed without rendering stack? (y/n)")
            if proceed == "y":
                pass
            else:
                logger.info("Quitting...")
                return

        if not no_calib:
            logger.info("Calibrating eyes...")
            self.calibrate(with_visualization=True, interactive=True, detach=True, eye_id=int(target_eye_name.split("_")[-1]))
        else:
            eye_name = target_eye_name
            eye_dict = self.eyes[eye_name]
            is_map_loaded = self.load_calibration_map(eye_name, eye_dict, force_load=True)
            logger.info("Requested no calibration so loading calibration map from file. Success: " + str(is_map_loaded))

        logger.info("Starting OD detection on eyes...")
        self.initialize_object_detectors(target_eye_name=target_eye_name)

        # setting up visualization if requested
        if show_simulation_space:
            chosen_eye = target_eye_name
            # setting up matplotlib canvas (slow)
            plt.ion()
            fig, (axcam, axreal) = plt.subplots(ncols=2)
            fig.canvas.draw()

            aruco_image = self.calibrator.generate_calibration_image(return_image=True)

            # Showing the recorded calibration frame to visualize camera space
            plt.axes(axcam)
            plt.imshow(self.eyes[chosen_eye]["calibration_frame_annot"], origin='upper')
            plt.title("Calibration frame with ARUCO detections")

            # Showing the calibration image with the ARUCO codes to visualize camera space
            plt.axes(axreal)
            plt.imshow(aruco_image, cmap='gray', origin='upper')
            plt.title("Original calibration image on simulation space")

            xs = np.arange(0, vision.display_width, 50)
            ys = np.arange(0, vision.display_height, 50)
        logger.info(f"Detecting {det_target} as default...")
        log_every_n_frame = 20
        sum_inf_time = 0
        try:
            try:
                logger.info("CoBe has been started! Press F1 to change detection target and F2 quit.")
                for frid in range(t_max):
                    logger.debug(f"Frame {frid}")
                    for eye_name, eye_dict in self.eyes.items():
                        if eye_name == target_eye_name:
                            try:
                                # timing framerate of calibration frames
                                start_time = datetime.now()
                                logger.debug(f"Asking for inference results from eye {eye_name}...")
                                # eye_dict["pyro_proxy"].get_calibration_frame()
                                req_ts = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S.%f")
                                detections = eye_dict["pyro_proxy"].inference(confidence=vision.inf_confidence,
                                                                              img_width=vision.display_width,
                                                                              img_height=vision.display_height,
                                                                              req_ts=req_ts)
                                logger.debug("Received inference results!")
                                logger.debug(f"Detections: {detections}")

                                if eye_dict.get("cmap_xmap_interp") is not None:
                                    # choosing which detections to use and what does that mean
                                    detections = filter_detections(detections, det_target=det_target)

                                    # generating predator positions to be sent to the simulation
                                    predator_positions = []
                                    for detection in detections:
                                        logger.debug(f"Frame in processing was requested at {detection.get('request_ts')}")
                                        xcam, ycam = detection["x"], detection["y"]

                                        # scaling up the coordinates to the original calibration image size
                                        xcam, ycam = xcam * (vision.display_width / vision.display_width), ycam * (
                                                vision.display_height / vision.display_height)

                                        # remapping detection point to simulation space according to ARCO map
                                        xreal, yreal = self.remap_detection_point(eye_dict, xcam, ycam)

                                        if not (xreal == 0 and yreal == 0):
                                            # showing predator coordinates if requested
                                            if show_simulation_space:
                                                if np.ma.is_masked(xreal) or np.ma.is_masked(yreal):
                                                    logger.warning("Masked remapped values detected!")
                                                    xreal, yreal = 0, 0

                                                axcam.clear()
                                                axreal.clear()

                                                plt.axes(axcam)
                                                plt.scatter(xcam, ycam, c='r', marker='o')
                                                plt.title("Camera space")
                                                plt.xlim(0, vision.display_width)
                                                plt.ylim(0, vision.display_height)

                                                plt.axes(axreal)
                                                plt.scatter(xreal, yreal, c='r', marker='o', s=80)
                                                plt.title("Simulation space")
                                                plt.xlim(0, aruco.proj_calib_image_width)
                                                plt.ylim(0, aruco.proj_calib_image_width)

                                                plt.pause(0.001)

                                            # scaling down the coordinates from the original calibration image size to the
                                            # simulation space
                                            extrapolation_percentage = (vision.interp_map_res + 2 * vision.extrap_skirt) / \
                                                                       vision.interp_map_res
                                            theoretical_extrap_space_size = (2 * max_abs_coord) * extrapolation_percentage
                                            centering_const = theoretical_extrap_space_size / 2
                                            xreal, yreal = xreal * (
                                                    theoretical_extrap_space_size / aruco.proj_calib_image_width) - centering_const, \
                                                           yreal * (
                                                                   theoretical_extrap_space_size / aruco.proj_calib_image_height) - centering_const

                                            # matching directions in simulation space
                                            xreal, yreal = yreal, -xreal

                                            # moving the detected coordinate closer to origin proprtionally to how far it is to origin
                                            x_eccentricity_percent = xreal / centering_const
                                            y_eccentricity_percent = yreal / centering_const
                                            xreal, yreal = xreal - x_eccentricity_percent * 1, yreal - y_eccentricity_percent * 1

                                            predator_positions.append([xreal, yreal])
                                            logger.debug(f"Eye {eye_name} detected predator @ ({xreal}, {yreal})")

                                        else:
                                            logger.debug(f"No predator detected on eye {eye_name}")

                                    # filtering unrealistic detections if requested
                                    if pmodulesettings.with_filtering_unrealistic:
                                        for position in predator_positions:
                                            if abs(position[0]) > pmodulesettings.max_abs_coord_detection or \
                                                    abs(position[1]) > pmodulesettings.max_abs_coord_detection:
                                                logger.debug(f"Detection @ {position} is unrealistic, removing...")
                                                predator_positions.remove(position)

                                    # generating predator position
                                    if len(predator_positions) > 0:
                                        if kalman_queue is not None:
                                            kalman_queue.put((req_ts, datetime.now(), predator_positions))
                                        else:
                                            generate_pred_json(predator_positions)

                                    # timing framerate of calibration frames
                                    end_time = datetime.now()
                                    logger.debug(
                                        f"Frame {frid} took {(end_time - start_time).total_seconds()} seconds, FR: {1 / (end_time - start_time).total_seconds()}")
                                    if frid % log_every_n_frame == 0 and frid != 0:
                                        avg_inf_time = sum_inf_time / log_every_n_frame
                                        logger.info(
                                            f"Health - {eye_name} - Average FR in last {log_every_n_frame} frames: {1  / avg_inf_time}")
                                        sum_inf_time = 0
                                    else:
                                        sum_inf_time += (end_time - start_time).total_seconds()

                                else:
                                    raise Exception(f"No remapping available for eye {eye_name}. Please calibrate first!")

                                if not no_calib:
                                    with keyboard.Events() as events:
                                        # Block at most 0.1 second
                                        event = events.get(0.001)
                                        if event is None:
                                            pass
                                        elif event.key == keyboard.Key.f2:
                                            logger.info("Quitting requested by user. Exiting...")
                                            return
                                        elif event.key == keyboard.Key.f1:
                                            if det_target == "thymio":
                                                det_target = "stick"
                                            elif det_target == "stick":
                                                det_target = "thymio"
                                            logger.info(f"Switching detection target to {det_target}!")

                                # logger.info("Sleeping for 3 seconds...")
                                # time.sleep(5)

                            except Exception as e:
                                if str(e).find("Original exception: <class 'requests.exceptions.ConnectionError'>") > -1:
                                    logger.warning(
                                        "Connection error: Inference server is probably not yet started properly. "
                                        "retrying in 3"
                                        "seconds.")
                                    sleep(3)
                                else:
                                    logger.error(e)
                                    break

            except Exception as e:
                logger.error(e)

        except KeyboardInterrupt:
            logger.error("Interrupt requested by user. Exiting... (For normal business press 'ENTER' long to quit!)")

        # todo: decide on cleaning up inference servers here or in the cleanup function

    def startup_rendering_stack(self):
        """Starts all apps of the rendering stack"""
        logger.debug("Starting rendering stack...")
        self.rendering_stack.open_apps()

    def shutdown_rendering_stack(self):
        """Starts all apps of the rendering stack"""
        logger.debug("Shutting down rendering stack...")
        self.rendering_stack.close_apps()

    def project_calibration_image(self, on_master_visualization=False):
        """Projects the calibration image onto the arena surface"""
        # Start rendering stack
        logger.info("Starting rendering stack")
        self.startup_rendering_stack()

        # generate calibration image
        projection_image = self.calibrator.generate_calibration_image(return_image=True)

        # transform image to bytearray
        byte_image = cv2.imencode('.jpg', projection_image)[1].tobytes()

        # Showing the image if requested
        if on_master_visualization:
            plt.imshow(projection_image)
            plt.show()

        logger.debug("Removing overlay image if any.")
        self.rendering_stack.remove_image()
        time.sleep(3)
        logger.debug("Displaying overlay image.")
        self.rendering_stack.display_image(byte_image)

    def remove_calibration_image(self):
        """Removes the calibration image from the arena surface"""
        logger.debug("Removing calibration image")
        self.rendering_stack.remove_image()


class CoBeCalib(object):
    """The calibration class is responsible for the calibration of the CoBe Eyes and can communicate with the
    projector stack via Resolume"""

    def __init__(self):
        pass

    def fetch_calibration_frames(self, eyes):
        """Fetches calibration frames from all eyes"""
        # Generate and publish calibration frames for all eyes
        for eye_name, eye_dict in eyes.items():
            logger.info(f"Fetching calibration frame from eye {eye_name}")
            eye_dict["pyro_proxy"].get_calibration_frame()

        # Downloading calibration frames from all eyes
        for eye_name, eye_dict in eyes.items():
            logger.debug(eye_dict)
            cap = cv2.VideoCapture(f'http://{eye_dict["eye_data"]["host"]}:8000/calibration.mjpg')
            ret, frame = cap.read()
            eye_dict["calibration_frame"] = frame
            cap.release()

        logger.info("Calibration frames fetched.")

    def detect_ARUCO_codes(self, eyes, with_visualization=False):
        """Detects ARUCO codes according to cobe.settings.aruco in fetched calibration images
        and stores the results in the eyes dictionary
        :param eyes: dictionary of eyes
        :param with_visualization: if True, the ARUCO codes are visualized in the calibration images for teh user"""

        aruco_dict = aruco.aruco_dict  # dictionary of the code convention
        aruco_parameters = aruco.aruco_params  # detector parameters

        # creating aruco detector (syntax change from cv2 v4.7, does not work with other versions)
        detector = cv2.aruco.ArucoDetector()
        detector.setDictionary(aruco_dict)
        detector.setDetectorParameters(aruco_parameters)
        for eye_name, eye_dict in eyes.items():
            # detect aruco codes
            try:
                corners, ids, rejected_points = detector.detectMarkers(eye_dict["calibration_frame"])
                logger.info(f"Detected {len(corners)} ARUCO codes in {eye_name} calibration frame.")
                eye_dict["detected_aruco"] = {"corners": corners, "ids": ids, "rejected_points": rejected_points}
                eye_dict["calibration_score"] = len(corners) / (aruco.num_codes_per_row ** 2)
                # saving annotated image
                eye_dict["calibration_frame_annot"] = cv2.aruco.drawDetectedMarkers(eye_dict["calibration_frame"],
                                                                                    eye_dict["detected_aruco"][
                                                                                        "corners"],
                                                                                    eye_dict["detected_aruco"]["ids"])
                if with_visualization:
                    # show image
                    cv2.imshow(eye_name, eye_dict["calibration_frame_annot"])
                    cv2.waitKey(0)
                    cv2.destroyAllWindows()
                    cv2.waitKey(1)

            except Exception as e:
                logger.error(e)
                logger.error(f"Could not detect ARUCO codes in {eye_name} calibration frame. This can either come from "
                             f"an empty calibration image or from no codes on the image. Be sure that the camera module"
                             f"is intact, the calibration image is properly projected and the streaming server on the"
                             f"eye is enabled (cobe.settings.vision.publish_mjpeg_stream = True)!")

    def interpolate_xy_maps(self, eyes, with_visualization=False, detach=False):
        """Generating a map of xy coordinate maps for each eye that maps any pixel of the camera to the corresponding
        pixel of the projector. This is done by interpolating the xy detections of ARUCO codes in the calibration frames
        of the eyes.
        :param eyes: dictionary of eyes
        :param with_visualization: if True, the ARUCO codes are visualized in the calibration images for the user
        :param detach: if True, the interpolation is done in a separate process"""
        # getting x coordinates of detected aruco code centers
        for eye_name, eye_dict in eyes.items():
            if eye_dict["calibration_score"] < 0.2:
                logger.info(f"Calibration score of {eye_name} is too low (<0.2). Please check the calibration frame.")
                continue
            else:
                logger.info(f"Calibration score of {eye_name} is {eye_dict['calibration_score']}.")
            # get corners of detected aruco codes
            corners = eye_dict["detected_aruco"]["corners"]
            # get ids of detected aruco codes
            ids = eye_dict["detected_aruco"]["ids"]
            # get center coordinates of detected aruco codes
            centers = np.array([np.mean(corners[i][0], axis=0) for i in range(len(corners))])
            # get x coordinates of detected aruco code centers
            x = centers[:, 0]
            # get y coordinates of detected aruco code centers
            y = centers[:, 1]

            num_data_points = vision.interp_map_res  # resolution of the interpolated map will be shape N x N
            skirt = 0.1  # number of pixels to add to the border of the map to avoid edge effects

            # todo: cleanup
            # Create grid values first.
            xi = np.linspace(min(x) - 0.1, max(x) + 0.1, num=num_data_points)
            dx = (max(x) + 0.1 - (min(x) - 0.1)) / (num_data_points - 1)
            yi = np.linspace(min(y) - 0.1, max(y) + 0.1, num=num_data_points)
            dy = (max(y) + 0.1 - (min(y) - 0.1)) / (num_data_points - 1)

            # # Linearly interpolate the data (x, y) on a grid defined by (xi, yi).
            # triang = tri.Triangulation(x, y)
            # interpolator_xreal = tri.LinearTriInterpolator(triang, [aruco.aruco_id_to_proj_pos[ids[i, 0]][0] for i in
            #                                                         range(len(ids))])
            # interpolator_yreal = tri.LinearTriInterpolator(triang, [aruco.aruco_id_to_proj_pos[ids[i, 0]][1] for i in
            #                                                         range(len(ids))])
            Xi, Yi = np.meshgrid(xi, yi)  # interpolation range (ARUCO covered image area)
            # xreal = interpolator_xreal(Xi, Yi)
            # yreal = interpolator_yreal(Xi, Yi)

            from scipy.interpolate import LinearNDInterpolator, InterpolatedUnivariateSpline

            # Linearly interpolate the data (x, y) on a grid defined by (xi, yi).
            interp_xreal = LinearNDInterpolator(list(zip(x, y)),
                                                [aruco.aruco_id_to_proj_pos[ids[i, 0]][0] for i in range(len(ids))])
            xreal = interp_xreal(Xi, Yi)
            interp_yreal = LinearNDInterpolator(list(zip(x, y)),
                                                [aruco.aruco_id_to_proj_pos[ids[i, 0]][1] for i in range(len(ids))])
            yreal = interp_yreal(Xi, Yi)

            eye_dict["cmap_xmap_interp"] = xreal
            eye_dict["cmap_ymap_interp"] = yreal
            eye_dict["cmap_x_interp"] = xi
            eye_dict["cmap_y_interp"] = yi

            # Extrapolating data outside the ARUCO covered range
            ext_num_points = vision.extrap_skirt  # number of points to extrapolate
            ext_range_x = ext_num_points * dx  # extrapolation range (whole image area)
            ext_range_y = ext_num_points * dy  # extrapolation range (whole image area)
            num_data_points = num_data_points + 2 * ext_num_points  # resolution of the interpolated map will be shape N x N
            xs = np.linspace(min(xi) - ext_range_x, max(xi) + ext_range_x, num=num_data_points)
            ys = np.linspace(min(yi) - ext_range_y, max(yi) + ext_range_y, num=num_data_points)
            xnew, ynew = np.meshgrid(xs, ys)  # extrapolation range (whole image area)
            xnew = xnew.flatten()
            ynew = ynew.flatten()

            rbf3_xreal = Rbf(x, y, [aruco.aruco_id_to_proj_pos[ids[i, 0]][0] for i in range(len(ids))],
                             function="multiquadric", smooth=0)
            rbf3_yreal = Rbf(x, y, [aruco.aruco_id_to_proj_pos[ids[i, 0]][1] for i in range(len(ids))],
                             function="multiquadric", smooth=0)
            xreal_extra = rbf3_xreal(xnew, ynew)
            yreal_extra = rbf3_yreal(xnew, ynew)
            xreal_extra_reshaped = xreal_extra.reshape((len(ys), len(xs)))
            yreal_extra_reshaped = yreal_extra.reshape((len(ys), len(xs)))
            eye_dict["cmap_xmap_extrap"] = xreal_extra_reshaped
            eye_dict["cmap_ymap_extrap"] = yreal_extra_reshaped
            eye_dict["cmap_x_extrap"] = xs
            eye_dict["cmap_y_extrap"] = ys

            if with_visualization:
                # Visualization
                fig, ax = plt.subplots(nrows=2, ncols=3, sharex=True, sharey=True)

                # Show image with detections
                plt.axes(ax[0, 0])
                plt.imshow(eye_dict["calibration_frame_annot"])
                plt.title("Original image with ARUCO detections")

                # Show extracted points
                plt.axes(ax[1, 0])
                plt.scatter(x, y, c="blue")
                # showing corners
                for i in range(len(corners)):
                    plt.scatter(corners[i][0][:, 0], corners[i][0][:, 1], c="red")
                plt.title("Tag corners and centers")
                plt.xlabel("camera x")
                plt.ylabel("camera y")
                # keep aspect ratio original
                plt.axis('scaled')
                plt.xlim(0, eye_dict["calibration_frame_annot"].shape[1])
                plt.ylim(eye_dict["calibration_frame_annot"].shape[0], 0)

                # Show interpolated real x coordinates
                plt.axes(ax[0, 1])
                ax[0, 1].contour(xi, yi, xreal, levels=14, linewidths=0.5, colors='k', origin='lower')
                ax[0, 1].imshow(xreal, cmap="RdBu_r", origin='lower')
                cntr1 = ax[0, 1].contourf(xi, yi, xreal, levels=14, cmap="RdBu_r")

                ax[0, 1].plot(x, y, 'ko', ms=3)
                plt.xlabel("camera x")
                plt.ylabel("camera y")
                plt.title("Projection coordinate estimate (x)")
                # keep aspect ratio original
                plt.axis('scaled')
                plt.xlim(0, eye_dict["calibration_frame_annot"].shape[1])
                plt.ylim(eye_dict["calibration_frame_annot"].shape[0], 0)

                # Show interpolated real y coordinates
                plt.axes(ax[1, 1])
                ax[1, 1].contour(xi, yi, yreal, levels=14, linewidths=0.5, colors='k', origin='lower')
                ax[1, 1].imshow(yreal, cmap="RdBu_r", origin='lower')
                cntr1 = ax[1, 1].contourf(xi, yi, yreal, levels=14, cmap="RdBu_r")

                ax[1, 1].plot(x, y, 'ko', ms=3)
                plt.xlabel("camera x")
                plt.ylabel("camera y")
                plt.title("Projection coordinate estimate (y)")
                # keep aspect ratio original
                plt.axis('scaled')
                plt.xlim(0, eye_dict["calibration_frame_annot"].shape[1])
                plt.ylim(eye_dict["calibration_frame_annot"].shape[0], 0)

                # show extrapolated x coordinates
                plt.axes(ax[0, 2])
                # showing extrapolated values
                ax[0, 2].contour(xs, ys, xreal_extra_reshaped, levels=50, linewidths=0.5, colors='k', origin='lower')
                ax[0, 2].imshow(xreal_extra_reshaped, cmap="RdBu_r", origin='lower', vmin=np.nanmin(yreal),
                                vmax=np.nanmax(yreal))
                cntr1 = ax[0, 2].contourf(xs, ys, xreal_extra_reshaped, levels=50, cmap="RdBu_r",
                                          vmin=np.nanmin(yreal), vmax=np.nanmax(yreal))

                ax[0, 2].plot(x, y, 'ko', ms=3)
                plt.xlabel("camera x")
                plt.ylabel("camera y")
                plt.title("Extrapolated coordinate estimate (x)")
                # keep aspect ratio original
                plt.axis('scaled')
                plt.xlim(0, eye_dict["calibration_frame_annot"].shape[1])
                plt.ylim(eye_dict["calibration_frame_annot"].shape[0], 0)

                # show extrapolated y coordinates
                plt.axes(ax[1, 2])
                # showing extrapolated values
                ax[1, 2].contour(xs, ys, yreal_extra_reshaped, levels=50, linewidths=0.5, colors='k', origin='lower')
                ax[1, 2].imshow(yreal_extra_reshaped, cmap="RdBu_r", origin='lower', vmin=np.nanmin(yreal),
                                vmax=np.nanmax(yreal))
                cntr1 = ax[1, 2].contourf(xs, ys, yreal_extra_reshaped, levels=50, cmap="RdBu_r",
                                          vmin=np.nanmin(yreal), vmax=np.nanmax(yreal))
                # showing interpolated values for double check
                # ax[1, 2].contour(xi, yi, yreal, levels=14, linewidths=0.5, colors='k', origin='lower')
                # cntr1 = ax[1, 2].contourf(xi, yi, yreal, levels=14, cmap="RdBu_r")
                ax[1, 2].plot(x, y, 'ko', ms=3)
                plt.xlabel("camera x")
                plt.ylabel("camera y")
                plt.title("Extrapolated coordinate estimate (y)")
                # keep aspect ratio original
                plt.axis('scaled')
                plt.xlim(0, eye_dict["calibration_frame_annot"].shape[1])
                plt.ylim(eye_dict["calibration_frame_annot"].shape[0], 0)

                x_real_nonans = xreal
                x_real_nonans[np.isnan(xreal)] = 0
                error = xreal_extra_reshaped[ext_num_points:-ext_num_points,
                        ext_num_points:-ext_num_points] - x_real_nonans

                # # show extrapolated x coordinates
                # plt.axes(ax[0, 3])
                # # showing extrapolated values
                # ax[0, 3].imshow(error, cmap="RdBu_r", origin='lower')
                # ax[0, 3].plot(x, y, 'ko', ms=3)
                # plt.xlabel("camera x")
                # plt.ylabel("camera y")
                # plt.title("Extrapolation error (x)")
                # # keep aspect ratio original
                # plt.axis('scaled')
                # plt.xlim(0, eye_dict["calibration_frame_annot"].shape[1])
                # plt.ylim(eye_dict["calibration_frame_annot"].shape[0], 0)

                # todo: show extrapolation error, possibly replace inner values to interpolated ones and only use extra
                # polation when interpolation is not available.

                # using tight layout
                plt.tight_layout()
                plt.show(block=not detach)

    def extrapolate_xy_maps_scipy(self, eyes):
        """Not only interpolating real xy coordinates of the projector for each pixel of the camera, but also
        extrapolating for whole image space outside the range of presented ARUCO codes.
        :param eyes: dictionary containing eye information"""
        for eye_name, eye_dict in eyes.items():
            # get corners of detected aruco codes
            corners = eye_dict["detected_aruco"]["corners"]
            # get ids of detected aruco codes
            ids = eye_dict["detected_aruco"]["ids"]
            # get center coordinates of detected aruco codes
            centers = np.array([np.mean(corners[i][0], axis=0) for i in range(len(corners))])
            # get x coordinates of detected aruco code centers
            x = centers[:, 0]
            # get y coordinates of detected aruco code centers
            y = centers[:, 1]
            # get 3D value of x, y coordinates, i.e. the ids
            z = ids[:, 0]

            # Create extrapolation range
            # some extrapolation over the whole image
            xs = np.linspace(0, eye_dict["calibration_frame_annot"].shape[1])
            ys = np.linspace(0, eye_dict["calibration_frame_annot"].shape[0])
            xnew, ynew = np.meshgrid(xs, ys)
            xnew = xnew.flatten()
            ynew = ynew.flatten()

            # Interpolation with scipy.interpolate.Rbf
            from scipy.interpolate import Rbf
            rbf3 = Rbf(x, y, z, function="multiquadric", smooth=5)
            znew = rbf3(xnew, ynew)

            import matplotlib.pyplot as plt
            from mpl_toolkits.mplot3d import axes3d

            fig = plt.figure(figsize=(10, 6))
            ax = axes3d.Axes3D(fig)
            ax.scatter3D(xnew, ynew, znew)
            plt.show()

    def generate_calibration_image(self, return_image=False, detach=False):
        """Generates an image with ARUCO codes encoding the x,y coordinates of the real space/arena."""
        aruco_dict = aruco.aruco_dict  # dictionary of the code convention
        aruco_parameters = aruco.aruco_params  # detector parameters
        # plain white image
        calibration_image = np.ones((aruco.proj_calib_image_height, aruco.proj_calib_image_width), dtype=np.uint8) * 255
        # generate QR codes
        logger.debug("Generating ARUCO codes for calibration image")
        for id, (xproj, yproj) in aruco.aruco_id_to_proj_pos.items():
            logger.debug(f"Encoding ARUCO code {id} at position ({xproj}, {yproj})")
            # generate ARUCO code
            aruco_code = aruco_dict.generateImageMarker(id, aruco.code_size)
            aruco_code = np.pad(aruco_code, aruco.pad_size, mode='constant', constant_values=255)
            padded_code_size = aruco.code_size + 2 * aruco.pad_size
            # merge code on calibration image according to (xproj, yproj)
            calibration_image[yproj - int(padded_code_size / 2):yproj + int(padded_code_size / 2),
            xproj - int(padded_code_size / 2):xproj + int(padded_code_size / 2)] = aruco_code

        if not return_image:
            # resize image to 25%
            img = cv2.resize(calibration_image, (0, 0), fx=0.25, fy=0.25)

            # show image with matplotlib
            plt.imshow(img, cmap="gray")
            plt.show(block=not detach)
        else:
            logger.debug("Returning calibration image")
            return calibration_image


def file_writer_process(input_queue, with_averaging=False, averaging_window=2):
    from queue import Empty
    pred_memory = []
    while True:
        # try to get element from queue
        try:
            while input_queue.qsize() > 1:
                input_queue.get_nowait()
            od_element = input_queue.get_nowait()
            (tcap_str, tpush, pred_positions) = od_element

            if with_averaging:
                pred_memory.append(pred_positions)
                pred_positions_new = []

                for pred_position in pred_positions:
                    # finding the closest detection in each memory element and taking average over them
                    num_average = 1
                    average = np.array(pred_position)
                    for memory in pred_memory:
                        if len(memory) == 0:
                            continue
                        closest_detection = np.argmin(np.array([np.linalg.norm(np.array(m) - np.array(pred_position)) for m in memory]))
                        # if the closest detection is too far away we simply don't take it in the average
                        if np.linalg.norm(np.array(memory[closest_detection]) - np.array(pred_position)) > 1:
                            continue
                        average += np.array(memory[closest_detection])
                        num_average += 1

                    average /= num_average
                    pred_positions_new.append(average)

                if len(pred_memory) > averaging_window:
                    pred_memory.pop(0)

                pred_positions = pred_positions_new

            generate_pred_json(pred_positions)
        except Empty:
            pass