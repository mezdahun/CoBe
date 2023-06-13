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
import matplotlib.tri as tri
from getpass import getpass
from pyzbar.pyzbar import decode
from scipy.interpolate import Rbf


class CoBeMaster(object):
    """The main class of the CoBe project, organizing action flow between detection, processing and projection"""

    def __init__(self):
        """Constructor"""
        # eyes of the network
        self.eyes = self.create_eye_objects()
        # create calibration object for the run
        self.calibrator = CoBeCalib()
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

    def calculate_calibration_maps(self, with_visualization=False):
        """Calculates the calibration maps for each eye and stores them in the eye dict"""
        for eye_name, eye_dict in self.eyes.items():
            # get a single calibration image from every eye object
            print("Fetching calibration images from eyes...")
            self.calibrator.fetch_calibration_frames(self.eyes)
            # detect the aruco marker mesh on the calibration images and save data in eye dicts
            print("Detecting ARUCO codes...")
            self.calibrator.detect_ARUCO_codes(self.eyes)
            # calculate the calibration maps for each eye and store them in the eye dict
            print("Calculating calibration maps...")
            self.calibrator.interpolate_xy_maps(self.eyes, with_visualization=with_visualization)

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
        self.initialize_object_detectors()
        # at this point eyes are ready for traffic
        try:
            try:
                for eye_name, eye_dict in self.eyes.items():
                    for frid in range(5):
                        num_iterations = 300
                        try:
                            # detections = eye_dict["pyro_proxy"].inference(confidence=20)
                            # pprint(detections)
                            ifp = timeit.timeit(lambda: eye_dict["pyro_proxy"].inference(confidence=20),
                                                number=num_iterations) / num_iterations
                            print("Loop done with framerate: ", 1/ifp)
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

        # for eye_name, eye_dict in self.eyes.items():
        #     # stop docker servers
        #     sleep(3)
        #     eye_dict["pyro_proxy"].stop_inference_server(self.nano_password)
        #     # waiting for docker to stop the container
        #     sleep(3)
        #     eye_dict["pyro_proxy"].remove_inference_server(self.nano_password)

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

    def interpolate_xy_maps(self, eyes, with_visualization=False):
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
            xi = np.linspace(min(x)-0.1, max(x)+0.1, int(max(x)-min(x)))
            yi = np.linspace(min(y)-0.1, max(y)+0.1, int(max(y)-min(y)))

            # Linearly interpolate the data (x, y) on a grid defined by (xi, yi).
            triang = tri.Triangulation(x, y)
            interpolator_xreal = tri.LinearTriInterpolator(triang, [aruco.aruco_id_to_proj_pos[ids[i, 0]][0] for i in range(len(ids))])
            interpolator_yreal = tri.LinearTriInterpolator(triang, [aruco.aruco_id_to_proj_pos[ids[i, 0]][1] for i in range(len(ids))])
            Xi, Yi = np.meshgrid(xi, yi)  # interpolation range (ARUCO covered image area)
            xreal = interpolator_xreal(Xi, Yi)
            yreal = interpolator_yreal(Xi, Yi)
            eye_dict["cmap_xmap_interp"] = xreal
            eye_dict["cmap_ymap_interp"] = yreal
            eye_dict["cmap_x_interp"] = xi
            eye_dict["cmap_y_interp"] = yi

            # Extrapolating data outside the ARUCO covered range
            ext_range = 50
            xs = np.linspace(min(xi)-ext_range, max(xi)+ext_range)
            ys = np.linspace(min(yi)-ext_range, max(yi)+ext_range)
            xnew, ynew = np.meshgrid(xs, ys)  # extrapolation range (whole image area)
            xnew = xnew.flatten()
            ynew = ynew.flatten()

            rbf3_xreal = Rbf(x, y, [aruco.aruco_id_to_proj_pos[ids[i, 0]][0] for i in range(len(ids))], function="multiquadric", smooth=5)
            rbf3_yreal = Rbf(x, y, [aruco.aruco_id_to_proj_pos[ids[i, 0]][1] for i in range(len(ids))], function="multiquadric", smooth=5)
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
                plt.show()

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

        # todo: save image or send to projection stack

    def map_point(self, point, calibration_matrix):
        """Maps a point according to a calibration matrix
        :param point: point to be mapped
        :param calibration_matrix: calibration matrix for the eye"""
        # map point according to calibration matrix
        # Apply the transformation to a point (e.g., (x1, y1))
        result_point = np.dot(calibration_matrix, np.array([[point[0]], [point[1]], [1]]))
        mapped_point = (result_point[0, 0], result_point[1, 0])
        return mapped_point

    def detect_qr_codes(self, calibration_frame):
        """Detecting QR codes on an image using pyzbar"""
        qr_codes = decode(calibration_frame)
        print(f"Found {len(qr_codes)} QR codes on calibration frame")
        found_codes = {}
        for qr in qr_codes:
            found_codes[qr.data.decode("utf-8")] = {"orientation": qr.orientation,
                                                    "rect": qr.rect,
                                                    "center": (qr.rect.left + qr.rect.width / 2,
                                                               qr.rect.top + qr.rect.height / 2)}
        return found_codes


    def remap_inference_results(self, inference_results, calibration_map):
        """Remaps inference results according to calibration matrix
        :param inference_results: inference results from eye
        :param calibration_map: calibration matrix for the eye"""
        # remap inference results according to calibration matrix
        # return remapped inference results
        return inference_results
