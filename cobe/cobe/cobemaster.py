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
from cobe.settings import network, odmodel, aruco, vision, logs
from cobe.rendering.renderingstack import RenderingStack
from cobe.pmodule.pmodule import generate_pred_json

# Setting up file logger
import logging

logging.basicConfig(level=logs.log_level, format=logs.log_format)
logger = logs.setup_logger(__name__.split(".")[-1])


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

    if len(detections) > 1:
        logger.debug(f"More than 1 detection. Detections before sorting: {detections}")
        detections = sorted(detections, key=lambda x: x["confidence"], reverse=True)
        detections = [detections[0]]
    logger.debug(f"Chosen detection after filtering: {detections}")
    return detections


class CoBeMaster(object):
    """The main class of the CoBe project, organizing action flow between detection, processing and projection"""

    def __init__(self):
        """Constructor for CoBeMaster"""
        # eyes of the network
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
        self.check_pswds()

    def check_pswds(self):
        """Checking if the password is already set on the eyes and if not asking from user"""
        ask_for_pswd = False
        for eye_name, eye_dict in self.eyes.items():
            if not eye_dict["pyro_proxy"].has_pswd():
                logger.info(f"Eye {eye_name} does not have a password set.")
                ask_for_pswd = True
                break

        if ask_for_pswd:
            nano_password = getpass("Please enter password for nanos: ")
            for eye_name, eye_dict in self.eyes.items():
                eye_dict["pyro_proxy"].set_pswd(nano_password)

    def create_eye_objects(self):
        """Creates eye Pyro objects from the network settings"""
        eyes = {}
        for eye_name, eye_data in network.eyes.items():
            eyes[eye_name] = {"pyro_proxy": Proxy(
                eye_data["uri"] + eye_data["name"] + "@" + eye_data["host"] + ":" + eye_data["port"])}
            eyes[eye_name]["eye_data"] = eye_data
            # adding fisheye calibration map for eye
            eyes[eye_name]["pyro_proxy"].set_fisheye_calibration_map(eye_data["fisheye_calibration_map"])
            # testing created eye by accessing public Pyro method and comparing outcome with expected ID
            assert eyes[eye_name]["pyro_proxy"].return_id() == eyes[eye_name]["eye_data"]["expected_id"]
        return eyes

    def initialize_object_detectors(self):
        """Starting the roboflow inference servers on all the eyes and carry out a single detection to initialize
        the model weights. This needs WWW access on the eyes as it downloads model weights from Roboflow"""
        logger.info("Initializing object detectors...")
        for eye_name, eye_dict in self.eyes.items():
            # start docker servers
            logger.info(f"Starting inference server on {eye_name}.")
            eye_dict["pyro_proxy"].start_inference_server()
            sleep(2)

        logger.info("Waiting for inference servers to start...")
        sleep(5)
        for eye_name, eye_dict in self.eyes.items():
            # carry out a single detection to initialize the model weights
            logger.debug(f"Initializing model on {eye_name}. Model parameters: {odmodel.model_name}, "
                         f"{odmodel.model_id}, {odmodel.inf_server_url}, {odmodel.version}")
            eye_dict["pyro_proxy"].initODModel(api_key=odmodel.api_key,
                                               model_name=odmodel.model_name,
                                               model_id=odmodel.model_id,
                                               inf_server_url=odmodel.inf_server_url,
                                               version=odmodel.version)

    def calculate_calibration_maps(self, with_visualization=False, interactive=False, detach=False, with_save=True):
        """Calculates the calibration maps for each eye and stores them in the eye dict
        :param with_visualization: if True, the calibration maps are visualized
        :param interactive: if True, the calibration maps are regenerated until the user agrees with quality
        :param detach: if True, the calibration maps are calculated in a separate thread
        :param with_save: if True, the calibration maps are saved to disk as json files"""
        retry = [True for i in range(len(self.eyes))]
        eye_i = 0
        for eye_name, eye_dict in self.eyes.items():
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

                while retry[eye_i]:
                    # get a single calibration image from every eye object
                    logger.debug("Fetching calibration images from eyes...")
                    self.calibrator.fetch_calibration_frames(self.eyes)

                    # detect the aruco marker mesh on the calibration images and save data in eye dicts
                    logger.debug("Detecting ARUCO codes...")
                    self.calibrator.detect_ARUCO_codes(self.eyes)

                    # calculate the calibration maps for each eye and store them in the eye dict
                    logger.debug("Calculating calibration maps...")
                    self.calibrator.interpolate_xy_maps(self.eyes, with_visualization=with_visualization, detach=detach)

                    if interactive:
                        retry_input = input("Press r to retry calibration, or enter to continue...")
                        if retry_input == "r":
                            retry[eye_i] = True
                        else:
                            logger.info(f"Calibration results accepted by user for {eye_name}.")
                            retry[eye_i] = False
                    else:
                        retry[eye_i] = False
            if is_pattern_projected:
                logger.debug("Removing calibration image from projectors...")
                self.remove_calibration_image()
                sleep(3)
        self.save_calibration_maps()
        if with_visualization:
            # closing all matplotlib windows after calibration
            plt.close("all")

        logger.info("Calibration maps calculated and saved.")

    def save_calibration_maps(self):
        """Saves the calibration maps and eye settings for each eye's predefined json file"""

        if not os.path.isdir(self.calib_data_dir):
            logger.info(f"Creating calibration data directory at {self.calib_data_dir} as it does not exist.")
            os.makedirs(self.calib_data_dir, exist_ok=True)

        for eye_name, eye_dict in self.eyes.items():
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

    def load_calibration_map(self, eye_name, eye_dict):
        """Loads the calibration maps and eye settings for each eye from json files
        :param eye_name: name of the eye
        :param eye_dict: dictionary containing the eye data
        :return: True if calibration map was loaded, False if not"""
        # creating file path
        file_path = os.path.join(self.calib_data_dir, f"{eye_name}_calibdata.json")
        if os.path.isfile(file_path):
            load_map_input = input(
                f"Calibration map for {eye_name} found in {file_path}. Do you want to load it? (Y/n)")
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

    def calibrate(self, with_visualization=True, interactive=True, detach=True):
        """Calibrating eyes using the projection stack
        :param with_visualization: if True, the calibration process will be visualized
        :param interactive: if True, the calibration process will be interactive and will be retried if quality is not
                            sufficient
        :param detach: if True, the calibration process will be detached from the main process"""
        logger.debug("Starting calibration...")
        self.calculate_calibration_maps(with_visualization=with_visualization, interactive=interactive, detach=detach)
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

        logger.info(f"Starting to collect images from eye {target_eye_name}...\nPress s to save image, ESC to quit, "
                    f"SPACE to save image and UP to turn on/off autocapture")
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

    def start(self, show_simulation_space=False, target_eye_name="eye_0", t_max=10000, kalman_queue=None):
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
        logger.info("Calibrating eyes...")
        self.calibrate(with_visualization=True, interactive=True, detach=True)
        logger.info("Starting OD detection on eyes...")
        self.initialize_object_detectors()

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

        try:
            try:
                logger.info("CoBe has been started! Press ESC long to quit.")
                for frid in range(t_max):
                    logger.debug(f"Frame {frid}")
                    for eye_name, eye_dict in self.eyes.items():
                        try:
                            # timing framerate of calibration frames
                            start_time = datetime.now()
                            logger.info("Asking for inference results...")
                            # eye_dict["pyro_proxy"].get_calibration_frame()
                            req_ts = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S.%f")
                            detections = eye_dict["pyro_proxy"].inference(confidence=35, img_width=416, img_height=416, req_ts=req_ts)
                            logger.info("Received inference results!")
                            logger.info(detections)

                            if eye_dict.get("cmap_xmap_interp") is not None:
                                # choosing which detections to use and what does that mean
                                detections = filter_detections(detections)

                                # generating predator positions to be sent to the simulation
                                predator_positions = []
                                for detection in detections:
                                    logger.info(f"Frame in processing was requested at {detection.get('request_ts')}")
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

                                        # todo: simplify this by merging the 2 scaling commandscobe-pm

                                        predator_positions.append([xreal, yreal])
                                        logger.info(f"Eye {eye_name} detected predator @ ({xreal}, {yreal})")

                                    else:
                                        logger.info(f"No predator detected on eye {eye_name}")

                                # generating predator position
                                if len(predator_positions) > 0:
                                    if kalman_queue is not None:
                                        kalman_queue.put((req_ts, datetime.now(), predator_positions))
                                    else:
                                        generate_pred_json(predator_positions)

                                # timing framerate of calibration frames
                                end_time = datetime.now()
                                logger.error(f"Frame {frid} took {(end_time - start_time).total_seconds()} seconds, FR: {1 / (end_time - start_time).total_seconds()}")
                            else:
                                raise Exception(f"No remapping available for eye {eye_name}. Please calibrate first!")

                            with keyboard.Events() as events:
                                # Block at most 0.1 second
                                event = events.get(0.01)
                                if event is None:
                                    pass
                                elif event.key == keyboard.Key.esc:
                                    logger.info("Quitting requested by user. Exiting...")
                                    return

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
            logger.error("Interrupt requested by user. Exiting... (For normal business press 'ESC' long to quit!)")

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
                                                                                    eye_dict["detected_aruco"]["corners"],
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

            #todo: cleanup
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
                fig, ax = plt.subplots(nrows=2, ncols=4, sharex=True, sharey=True)

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
                ax[0, 2].imshow(xreal_extra_reshaped, cmap="RdBu_r", origin='lower',vmin=np.nanmin(yreal), vmax=np.nanmax(yreal))
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
                ax[1, 2].imshow(yreal_extra_reshaped, cmap="RdBu_r", origin='lower',vmin=np.nanmin(yreal), vmax=np.nanmax(yreal))
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
                error = xreal_extra_reshaped[ext_num_points:-ext_num_points, ext_num_points:-ext_num_points] - x_real_nonans

                # show extrapolated x coordinates
                plt.axes(ax[0, 3])
                # showing extrapolated values
                ax[0, 3].imshow(error, cmap="RdBu_r", origin='lower')
                ax[0, 3].plot(x, y, 'ko', ms=3)
                plt.xlabel("camera x")
                plt.ylabel("camera y")
                plt.title("Extrapolation error (x)")
                # keep aspect ratio original
                plt.axis('scaled')
                plt.xlim(0, eye_dict["calibration_frame_annot"].shape[1])
                plt.ylim(eye_dict["calibration_frame_annot"].shape[0], 0)

                #todo: show extrapolation error, possibly replace inner values to interpolated ones and only use extra
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
