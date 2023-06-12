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
import timeit

import cv2
import numpy as np
from Pyro5.api import Proxy
from cobe.settings import network, odmodel, aruco
from time import sleep
import matplotlib.pyplot as plt
from getpass import getpass
from pyzbar.pyzbar import decode


class CoBeMaster(object):
    """The main class of the CoBe project, organizing action flow between detection, processing and projection"""

    def __init__(self):
        """Constructor"""
        # eyes of the network
        self.eyes = self.create_eye_objects()
        # create calibration object for the run
        self.calibrator = CoBeCalib()
        # calculating mapping matrices for each eye (as given matrix in the self.eyes dict)
        self.calculate_calibration_maps()
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

    def calculate_calibration_maps(self):
        """Calculates calibration matrices for each eye by projecting a calibration pattern and collecting
        calibration images from eyes at the same time"""
        # collect calibration images from eyes
        for eye_name, eye_dict in self.eyes.items():
            self.eyes[eye_name]["calibration_map"] = self.calibrator.calibrate(self.eyes[eye_name]["pyro_proxy"])

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

    def start(self):
        """Starts the main action loop of the CoBe project"""
        from pprint import pprint
        # main action loop
        # while True:
        # get inference results from eyes
        # self.initialize_object_detectors()
        try:
            try:
                for eye_name, eye_dict in self.eyes.items():
                    for frid in range(100):
                        try:
                            detections = eye_dict["pyro_proxy"].inference(confidence=20)
                            pprint(detections)
                        except Exception as e:
                            if str(e).find("Original exception: <class 'requests.exceptions.ConnectionError'>") > -1:
                                print("Connection error: Inference server is probably not yet started properly. "
                                      "retrying in 3"
                                      "seconds.")
                                sleep(3)

            except Exception as e:
                print(e)
                print("Cleaning up inference servers after crash...")

        except KeyboardInterrupt:
            print("Cleaning up inference servers...")

        for eye_name, eye_dict in self.eyes.items():
            # stop docker servers
            sleep(3)
            eye_dict["pyro_proxy"].stop_inference_server(self.nano_password)
            # waiting for docker to stop the container
            sleep(3)
            eye_dict["pyro_proxy"].remove_inference_server(self.nano_password)

            #     eye_dict["inference_results"] = eye_dict["pyro_proxy"].get_inference_results()
            # # remap inference results according to calibration matrices
            # for eye_name, eye_dict in self.eyes.items():
            #     eye_dict["remapped_inference_results"] = self.calibrator.remap_inference_results(
            #         eye_dict["inference_results"], eye_dict["calibration_map"])
            # # call Pmodule and consume results
            # self.call_pmodule()
            # agent_coordinates = self.consume_pmodule_results()
            # # pass final results to projection stack via Unity
            # self.pass_results_to_projection_stack(agent_coordinates)



class CoBeCalib(object):
    """The calibration class is responsible for the calibration of the CoBe Eyes and can communicate with the
    projector stack via Resolume"""
    def __init__(self):
        """Constructor, initializing resolume interface"""
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

    def detect_ARUCO_codes(self, eyes):
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
            eye_dict["detected_aruco"] = {"corners": corners, "ids": ids, "rejected_points": rejected_points}
            # saving annotated image
            eye_dict["calibration_frame_annot"] = cv2.aruco.drawDetectedMarkers(eye_dict["calibration_frame"],
                                                                                eye_dict["detected_aruco"]["corners"],
                                                                                eye_dict["detected_aruco"]["ids"])
            # show image
            cv2.imshow(eye_name, eye_dict["calibration_frame_annot"])
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            cv2.waitKey(1)

    def interpolate_xy_maps(self, eyes):
        """Generating a map of xy coordinate maps for each eye that maps any pixel of the camera to the corresponding
        pixel of the projector. This is done by interpolating the xy detections of ARUCO codes in the calibration frames
        of the eyes."""
        # getting x coordinates of detected aruco code centers
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


            # Create grid values first.
            xi = np.linspace(min(x)-0.1, max(x)+0.1, int(max(x)-min(x)))
            yi = np.linspace(min(y)-0.1, max(y)+0.1, int(max(y)-min(y)))

            # Linearly interpolate the data (x, y) on a grid defined by (xi, yi).
            import matplotlib.tri as tri
            triang = tri.Triangulation(x, y)
            interpolator_xreal = tri.LinearTriInterpolator(triang, [aruco.aruco_id_to_proj_pos[ids[i, 0]][0] for i in range(len(ids))])
            interpolator_yreal = tri.LinearTriInterpolator(triang, [aruco.aruco_id_to_proj_pos[ids[i, 0]][1] for i in range(len(ids))])
            Xi, Yi = np.meshgrid(xi, yi)
            xreal = interpolator_xreal(Xi, Yi)
            yreal = interpolator_yreal(Xi, Yi)

            fig, ax = plt.subplots(nrows=2, ncols=2, sharex=True, sharey=True)

            # Show image with detections
            plt.axes(ax[0, 0])
            plt.imshow(eye_dict["calibration_frame_annot"])
            plt.title("Original image with ARUCO detections")

            # Show extracted points
            plt.axes(ax[0, 1])
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


            # Show estimated real x coordinates
            plt.axes(ax[1, 0])
            ax[1, 0].contour(xi, yi, xreal, levels=14, linewidths=0.5, colors='k', origin='lower')
            cntr1 = ax[1, 0].contourf(xi, yi, xreal, levels=14, cmap="RdBu_r")

            ax[1, 0].plot(x, y, 'ko', ms=3)
            plt.xlabel("camera x")
            plt.ylabel("camera y")
            plt.title("Projection coordinate estimate (x)")
            # keep aspect ratio original
            plt.axis('scaled')
            plt.xlim(0, eye_dict["calibration_frame_annot"].shape[1])
            plt.ylim(eye_dict["calibration_frame_annot"].shape[0], 0)

            # Show estimated real y coordinates
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

            # using tight layout
            plt.tight_layout()
            plt.show()

    def generate_calibration_image(self):
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
            calibration_image[yproj-int(padded_code_size/2):yproj+int(padded_code_size/2),
                              xproj-int(padded_code_size/2):xproj+int(padded_code_size/2)] = aruco_code


        # resize image to 25%
        img = cv2.resize(calibration_image, (0, 0), fx=0.25, fy=0.25)

        # show image with matplotlib
        plt.imshow(img, cmap="gray")
        plt.show()


        # return calibration matrix
        W = 10  # image width from camera
        H = 10  # image height from camera
        return np.zeros((W, H, 2))

    def remap_inference_results(self, inference_results, calibration_map):
        """Remaps inference results according to calibration matrix
        :param inference_results: inference results from eye
        :param calibration_map: calibration matrix for the eye"""
        # remap inference results according to calibration matrix
        # return remapped inference results
        return inference_results
