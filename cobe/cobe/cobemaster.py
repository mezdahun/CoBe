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
import timeit
import cv2
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.tri as tri

from Pyro5.api import Proxy
from cobe.settings import network, odmodel, aruco, vision
from cobe.rendering.renderingstack import RenderingStack
from time import sleep
from getpass import getpass
from scipy.interpolate import Rbf


class CoBeMaster(object):
    """The main class of the CoBe project, organizing action flow between detection, processing and projection"""

    def __init__(self):
        """Constructor"""
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
        # requesting master password for nanos
        self.nano_password = getpass("To start inference server on Nano, please enter the admin password:")

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
        for eye_name, eye_dict in self.eyes.items():
            # start docker servers
            eye_dict["pyro_proxy"].start_inference_server(self.nano_password)
            # waiting for server to start
            sleep(2)

        print("Waiting for servers to start...")
        sleep(4)
        for eye_name, eye_dict in self.eyes.items():
            # carry out a single detection to initialize the model weights
            print(f"Initializing model on {eye_name}. Model parameters:")
            eye_dict["pyro_proxy"].initODModel(api_key=odmodel.api_key,
                                               model_name=odmodel.model_name,
                                               model_id=odmodel.model_id,
                                               inf_server_url=odmodel.inf_server_url,
                                               version=odmodel.version)

    def calculate_calibration_maps(self, with_visualization=False, interactive=False, detach=False, with_save=True):
        """Calculates the calibration maps for each eye and stores them in the eye dict"""
        retry = [True for i in range(len(self.eyes))]
        eye_i = 0
        for eye_name, eye_dict in self.eyes.items():
            is_map_loaded = self.load_calibration_map(eye_name, eye_dict)
            if not is_map_loaded:
                while retry[eye_i]:
                    # get a single calibration image from every eye object
                    print("Fetching calibration images from eyes...")
                    self.calibrator.fetch_calibration_frames(self.eyes)
                    # detect the aruco marker mesh on the calibration images and save data in eye dicts
                    print("Detecting ARUCO codes...")
                    self.calibrator.detect_ARUCO_codes(self.eyes)
                    # calculate the calibration maps for each eye and store them in the eye dict
                    print("Calculating calibration maps...")
                    self.calibrator.interpolate_xy_maps(self.eyes, with_visualization=with_visualization, detach=detach)
                    if interactive:
                        retry_input = input("press r to retry calibration, or enter to continue...")
                        if retry_input == "r":
                            retry[eye_i] = True
                        else:
                            print(f"Calibration results accepted by user for {eye_name}.")
                            retry[eye_i] = False
                    else:
                        retry[eye_i] = False

        self.save_calibration_maps()
        if with_visualization:
            # closing all maptlotlib windows after calibration
            plt.close("all")

    def save_calibration_maps(self):
        """Saves the calibration maps and eye settings for each eye json file"""
        if not os.path.isdir(self.calib_data_dir):
            os.makedirs(self.calib_data_dir, exist_ok=True)

        for eye_name, eye_dict in self.eyes.items():
            file_path = os.path.join(self.calib_data_dir, f"{eye_name}_calibdata.json")
            print(f"Saving calibration map for {eye_name} to {file_path}")
            eye_dict_to_save = eye_dict.copy()
            # deleting pyro proxy and detected aruco code from dict as they are not serializable
            del eye_dict_to_save["pyro_proxy"]
            if eye_dict_to_save.get("detected_aruco"):
                del eye_dict_to_save["detected_aruco"]
            # jsonifying dictionary
            for k, v in eye_dict_to_save.items():
                print(k, v)
                if isinstance(v, np.ndarray):
                    eye_dict_to_save[k] = v.tolist()
            # saving json file
            with open(file_path, "w") as f:
                json.dump(eye_dict_to_save, f)

    def load_calibration_map(self, eye_name, eye_dict):
        """Loads the calibration maps and eye settings for each eye json file"""
        file_path = os.path.join(self.calib_data_dir, f"{eye_name}_calibdata.json")
        if os.path.isfile(file_path):
            load_map_input = input(f"Calibration map for {eye_name} found in {file_path}. Do you want to load it? (Y/n)")
            if load_map_input.lower() == "y":
                print(f"Loading calibration map for {eye_name} from {file_path}")
                with open(file_path, "r") as f:
                    loaded_data = json.load(f)
                    # Loading eye settings from json file
                    eye_dict["eye_data"] = loaded_data["eye_data"]
                    # Loading calibration related data from json file
                    eye_dict["calibration_frame"] = np.array(loaded_data["calibration_frame"])
                    # # detected aruco codes are not saved in json file, so we need to detect them again
                    # self.calibrator.detect_ARUCO_codes(eye_dict)
                    # if eye_dict["calibration_score"] != loaded_data["calibration_score"]:
                    #     "Calibration score from json file does not match detected calibration score."
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
                return True
            else:
                print(f"Calibration map for {eye_name} NOT loaded.")
                return False

    def cleanup_inference_servers(self, waitfor=3):
        """Cleans up inference servers on all eyes.
        Waiting for waitfor seconds between each stop and remove operation"""
        for eye_name, eye_dict in self.eyes.items():
            # stop docker servers
            sleep(waitfor)
            eye_dict["pyro_proxy"].stop_inference_server(self.nano_password)
            # waiting for docker to stop the container
            sleep(waitfor)
            eye_dict["pyro_proxy"].remove_inference_server(self.nano_password)

    def shutdown_eyes(self):
        """Shutting down all eye servers by raising KeyboardInterrupt on each eye"""
        self.cleanup_inference_servers()
        print("Waiting for cleanup...")
        sleep(5)
        for eye_name, eye_dict in self.eyes.items():
            eye_dict["pyro_proxy"].shutdown()

    def remap_detection_point(self, eye_dict, xcam, ycam):
        """Remaps a detection point from camera space to real space according to the calibration maps"""
        # First trying to get a more accurate interpolated value from the calibration map
        # find index of closest x value in eyes calibration map to provided xcam
        x_index = np.abs(eye_dict["cmap_x_interp"] - xcam).argmin()
        # find index of closest y value in eyes calibration map to provided ycam
        y_index = np.abs(eye_dict["cmap_y_interp"] - ycam).argmin()
        # return the real space coordinates for the provided camera space coordinates
        xreal, yreal = eye_dict["cmap_xmap_interp"][y_index, x_index], eye_dict["cmap_ymap_interp"][y_index, x_index]
        # todo: implement remapping with extrapolated values if interpolated values are not valid
        # # if the interpolated value is not valid, return the nearest value from the extrapolated calibration map
        # if np.ma.is_masked(xreal) or np.ma.is_masked(yreal):
        #     x_index = np.abs(eye_dict["cmap_x_extrap"] - xcam).argmin()
        #     # find index of closest y value in eyes calibration map to provided ycam
        #     y_index = np.abs(eye_dict["cmap_y_extrap"] - ycam).argmin()
        #     # return the real space coordinates for the provided camera space coordinates
        #     xreal, yreal = eye_dict["cmap_xmap_extrap"][y_index, x_index], eye_dict["cmap_ymap_extrap"][
        #         y_index, x_index]
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

        xs = np.arange(0, vision.capture_width, 50)
        ys = np.arange(0, vision.capture_height, 50)

        for xcam in xs:
            for ycam in ys:
                xreal, yreal = self.remap_detection_point(self.eyes[eye_name], xcam, ycam)
                if np.ma.is_masked(xreal) or np.ma.is_masked(yreal):
                    xreal, yreal = 0, 0
                if xreal != 0 and yreal != 0:
                    print("----")
                    print(xcam, ycam)
                    print(xreal, yreal)

                    plt.axes(axcam)
                    plt.scatter(xcam, ycam, c='r', marker='o')
                    plt.title("Camera space")
                    plt.xlim(0, vision.capture_width)
                    plt.ylim(0, vision.capture_height)

                    plt.axes(axreal)
                    plt.scatter(xreal, yreal, c='r', marker='o', s=80)
                    plt.title("Simulation space")
                    plt.xlim(0, aruco.proj_calib_image_width)
                    plt.ylim(0, aruco.proj_calib_image_width)

                    plt.pause(0.001)

    def start(self, show_simulation_space=True):
        """Starts the main action loop of the CoBe project"""
        self.initialize_object_detectors()
        # at this point eyes are ready for traffic
        # calibrating eyes before starting
        self.calibrator.generate_calibration_image(detach=True)
        self.calculate_calibration_maps(with_visualization=True, interactive=True, detach=True)
        if show_simulation_space:
            chosen_eye = "eye_0"
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

            xs = np.arange(0, vision.capture_width, 50)
            ys = np.arange(0, vision.capture_height, 50)

        # todo save and load calibration maps by default
        inf_img_width, inf_img_height = 320, 200
        try:
            try:
                num_iterations = 300
                for frid in range(num_iterations):
                    for eye_name, eye_dict in self.eyes.items():
                        try:
                            detections = eye_dict["pyro_proxy"].inference(confidence=20, img_width=320, img_height=200)
                            if eye_dict.get("cmap_xmap_interp") is not None:
                                for detection in detections:
                                    xcam, ycam = detection["x"], detection["y"]
                                    # scaling up the coordinates to the original calibration image size
                                    xcam, ycam = xcam * (vision.capture_width / inf_img_width), ycam * (
                                                         vision.capture_height / inf_img_height)
                                    xreal, yreal = self.remap_detection_point(eye_dict, xcam, ycam)
                                    if show_simulation_space:
                                        if np.ma.is_masked(xreal) or np.ma.is_masked(yreal):
                                            xreal, yreal = 0, 0
                                        if xreal != 0 and yreal != 0:
                                            axcam.clear()
                                            axreal.clear()

                                            plt.axes(axcam)
                                            plt.scatter(xcam, ycam, c='r', marker='o')
                                            plt.title("Camera space")
                                            plt.xlim(0, vision.capture_width)
                                            plt.ylim(0, vision.capture_height)

                                            plt.axes(axreal)
                                            plt.scatter(xreal, yreal, c='r', marker='o', s=80)
                                            plt.title("Simulation space")
                                            plt.xlim(0, aruco.proj_calib_image_width)
                                            plt.ylim(0, aruco.proj_calib_image_width)

                                            plt.pause(0.001)

                                    # scaling back down to the inference image size
                                    xreal, yreal = xreal * (inf_img_width / vision.capture_width), yreal * (
                                                            inf_img_height / vision.capture_height)
                                    print(f"(xcam, ycam) = ({xcam}, {ycam}) -> (xreal, yreal) = ({xreal}, {yreal})")
                        except Exception as e:
                            if str(e).find("Original exception: <class 'requests.exceptions.ConnectionError'>") > -1:
                                print("Connection error: Inference server is probably not yet started properly. "
                                      "retrying in 3"
                                      "seconds.")
                                sleep(3)
                            else:
                                print(e)
                                print("Cleaning up inference servers after crash...")
                                break

            except Exception as e:
                print(e)
                print("Cleaning up inference servers after crash...")

        except KeyboardInterrupt:
            print("Cleaning up inference servers...")

        # todo: decide on cleaning up inference servers here or in the cleanup function

        # todo: include remapping

    def project_calibration_image(self, on_master_visualization=False):
        """Projects the calibration image onto the arena surface"""
        # generate calibration image
        projection_image = self.calibrator.generate_calibration_image(return_image=True)

        # transform image to bytearray
        byte_image = cv2.imencode('.jpg', projection_image)[1].tobytes()

        # Showing the image if requested
        if on_master_visualization:
            import matplotlib.pyplot as plt
            plt.imshow(projection_image)
            plt.show()

        print("Removing overlay image if any")
        self.rendering_stack.remove_image()
        time.sleep(3)
        print("Displaying overlay image")
        self.rendering_stack.display_image(byte_image)

    def remove_calibration_image(self):
        """Removes the calibration image from the arena surface"""
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
            eye_dict["pyro_proxy"].get_calibration_frame()

        # Downloading calibration frames from all eyes
        for eye_name, eye_dict in eyes.items():
            print(eye_dict)
            cap = cv2.VideoCapture(f'http://{eye_dict["eye_data"]["host"]}:8000/calibration.mjpg')
            ret, frame = cap.read()
            eye_dict["calibration_frame"] = frame
            cap.release()

    def detect_ARUCO_codes(self, eyes, with_visualization=False):
        """Detects ARUCO codes according to cobe.settings.aruco in fetched calibration images"""

        aruco_dict = aruco.aruco_dict  # dictionary of the code convention
        aruco_parameters = aruco.aruco_params  # detector parameters

        # creating aruco detector (syntax change from cv2 v4.7, does not work with other versions)
        detector = cv2.aruco.ArucoDetector()
        detector.setDictionary(aruco_dict)
        detector.setDetectorParameters(aruco_parameters)
        for eye_name, eye_dict in eyes.items():
            # detect aruco codes
            corners, ids, rejected_points = detector.detectMarkers(eye_dict["calibration_frame"])
            print(f"Detected {len(corners)} ARUCO codes in {eye_name} calibration frame.")
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

    def interpolate_xy_maps(self, eyes, with_visualization=False, detach=False):
        """Generating a map of xy coordinate maps for each eye that maps any pixel of the camera to the corresponding
        pixel of the projector. This is done by interpolating the xy detections of ARUCO codes in the calibration frames
        of the eyes."""
        # getting x coordinates of detected aruco code centers
        for eye_name, eye_dict in eyes.items():
            if eye_dict["calibration_score"] < 0.2:
                print(f"Calibration score of {eye_name} is too low (<0.2). Please check the calibration frame.")
                continue
            else:
                print(f"Calibration score of {eye_name} is {eye_dict['calibration_score']}.")
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

            # Create grid values first.
            xi = np.linspace(min(x) - 0.1, max(x) + 0.1, int(max(x) - min(x)))
            yi = np.linspace(min(y) - 0.1, max(y) + 0.1, int(max(y) - min(y)))

            # Linearly interpolate the data (x, y) on a grid defined by (xi, yi).
            triang = tri.Triangulation(x, y)
            interpolator_xreal = tri.LinearTriInterpolator(triang, [aruco.aruco_id_to_proj_pos[ids[i, 0]][0] for i in
                                                                    range(len(ids))])
            interpolator_yreal = tri.LinearTriInterpolator(triang, [aruco.aruco_id_to_proj_pos[ids[i, 0]][1] for i in
                                                                    range(len(ids))])
            Xi, Yi = np.meshgrid(xi, yi)  # interpolation range (ARUCO covered image area)
            xreal = interpolator_xreal(Xi, Yi)
            yreal = interpolator_yreal(Xi, Yi)
            eye_dict["cmap_xmap_interp"] = xreal
            eye_dict["cmap_ymap_interp"] = yreal
            eye_dict["cmap_x_interp"] = xi
            eye_dict["cmap_y_interp"] = yi

            # Extrapolating data outside the ARUCO covered range
            ext_range = 50
            xs = np.linspace(min(xi) - ext_range, max(xi) + ext_range)
            ys = np.linspace(min(yi) - ext_range, max(yi) + ext_range)
            xnew, ynew = np.meshgrid(xs, ys)  # extrapolation range (whole image area)
            xnew = xnew.flatten()
            ynew = ynew.flatten()

            rbf3_xreal = Rbf(x, y, [aruco.aruco_id_to_proj_pos[ids[i, 0]][0] for i in range(len(ids))],
                             function="multiquadric", smooth=5)
            rbf3_yreal = Rbf(x, y, [aruco.aruco_id_to_proj_pos[ids[i, 0]][1] for i in range(len(ids))],
                             function="multiquadric", smooth=5)
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
                cntr1 = ax[0, 2].contourf(xs, ys, xreal_extra_reshaped, levels=50, cmap="RdBu_r",
                                          vmin=np.min(xreal), vmax=np.max(xreal))
                # showing interpolated values for double check
                ax[0, 2].contour(xi, yi, xreal, levels=14, linewidths=0.5, colors='k', origin='lower')
                cntr1 = ax[0, 2].contourf(xi, yi, xreal, levels=14, cmap="RdBu_r")
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
                cntr1 = ax[1, 2].contourf(xs, ys, yreal_extra_reshaped, levels=50, cmap="RdBu_r",
                                          vmin=np.min(yreal), vmax=np.max(yreal))
                # showing interpolated values for double check
                ax[1, 2].contour(xi, yi, yreal, levels=14, linewidths=0.5, colors='k', origin='lower')
                cntr1 = ax[1, 2].contourf(xi, yi, yreal, levels=14, cmap="RdBu_r")
                ax[1, 2].plot(x, y, 'ko', ms=3)
                plt.xlabel("camera x")
                plt.ylabel("camera y")
                plt.title("Extrapolated coordinate estimate (y)")
                # keep aspect ratio original
                plt.axis('scaled')
                plt.xlim(0, eye_dict["calibration_frame_annot"].shape[1])
                plt.ylim(eye_dict["calibration_frame_annot"].shape[0], 0)

                # using tight layout
                plt.tight_layout()
                plt.show(block=not detach)

    def extrapolate_xy_maps_scipy(self, eyes):
        """Not only interpolating real xy coordinates of the projector for each pixel of the camera, but also
        extrapolating for whole image space outside of the range of presented ARUCO codes. """
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
        for id, (xproj, yproj) in aruco.aruco_id_to_proj_pos.items():
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
            return calibration_image

        # todo: save image or send to projection stack
