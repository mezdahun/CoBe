import json
import os

import numpy as np
from matplotlib import pyplot as plt
from time import sleep
from pynput import keyboard

from cobe.cobe import cobemaster
from datetime import datetime

from cobe.cobe.cobemaster import filter_detections
from cobe.settings import aruco, vision, logs
from cobe.settings import abm_simulation as abms

# Setting up file logger
import logging

logging.basicConfig(level=logs.log_level, format=logs.log_format)
logger = logs.setup_logger(__name__.split(".")[-1])


def generate_pred_json_abm(agent_positions, ps=None):
    """Generating agent positions json file compatibe with p34ABM"""
    # generating filename with timestamp
    filepath = abms.MIDDLEWARE_PATH
    filename = abms.AGENT_LIST_FILENAME

    # generating list of predator dictionaries
    output_list = []
    for id, position in enumerate(agent_positions):
        if id < abms.MAX_NUM_AGENTS:
            output_list.append({
                "ID": id,
                "x0": position[0],
                "x1": position[1],
                "TYPE": "agent",
                "MODE": "explore"
            })

    # writing to file with json.dump
    with open(os.path.join(filepath, filename), 'w') as f:
        json.dump(output_list, f)


class CoBeMasterABM(cobemaster.CoBeMaster):
    def __init__(self, *args, **kwargs):
        # The main clss using pygame simulations for cobe will inherit from the original base class so we can use the
        # same calibration methods as before. We override the start method to add further functionality and replace
        # unity specific components.
        super().__init__(*args, **kwargs)

    def show_simulation_space(self, target_eye_name="eye_0"):
        """Showing calibration of OD cameras"""
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
            # todo: start the abm process here with some input parameters about the
            #  environment. It should then wait for generated files for agent positions
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
            self.show_simulation_space(target_eye_name=target_eye_name)

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

                                    # generating agent positions to be sent to the simulation
                                    agent_positions = []
                                    for detection in detections:
                                        logger.debug(f"Frame in processing was requested at {detection.get('request_ts')}")
                                        xcam, ycam = detection["x"], detection["y"]

                                        # scaling up the coordinates to the original calibration image size
                                        xcam, ycam = xcam * (vision.display_width / vision.display_width), ycam * (
                                                vision.display_height / vision.display_height)

                                        # remapping detection point to simulation space according to ARCO map
                                        xreal, yreal = self.remap_detection_point(eye_dict, xcam, ycam)

                                        if not (xreal == 0 and yreal == 0):
                                            # todo: reqwrite this to scale into the pygame arena size
                                            # scaling down the coordinates from the original calibration image size to the
                                            # simulation space
                                            extrapolation_percentage = (vision.interp_map_res + 2 * vision.extrap_skirt) / \
                                                                       vision.interp_map_res
                                            theoretical_extrap_space_size = (2 * abms.max_abs_coord) * extrapolation_percentage
                                            centering_const = theoretical_extrap_space_size / 2
                                            xreal, yreal = xreal * (
                                                    theoretical_extrap_space_size / aruco.proj_calib_image_width) - centering_const, \
                                                           yreal * (
                                                                   theoretical_extrap_space_size / aruco.proj_calib_image_height) - centering_const

                                            # matching directions in simulation space
                                            xreal, yreal = yreal, xreal

                                            # todo: simplify this by merging the 2 scaling

                                            agent_positions.append([xreal, yreal])
                                            logger.debug(f"Eye {eye_name} detected agent @ ({xreal}, {yreal})")

                                        else:
                                            logger.debug(f"No agent detected on eye {eye_name}")

                                    # filtering unrealistic detections if requested
                                    # todo: add same parameters for abm module settings and rewrite this part
                                    # if pmodulesettings.with_filtering_unrealistic:
                                    #     for position in agent_positions:
                                    #         if abs(position[0]) > pmodulesettings.max_abs_coord_detection or \
                                    #                 abs(position[1]) > pmodulesettings.max_abs_coord_detection:
                                    #             logger.debug(f"Detection @ {position} is unrealistic, removing...")
                                    #             agent_positions.remove(position)

                                    # generating predator position
                                    if len(agent_positions) > 0:
                                        if kalman_queue is not None:
                                            kalman_queue.put((req_ts, datetime.now(), agent_positions))
                                        else:
                                            generate_pred_json_abm(agent_positions)

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
