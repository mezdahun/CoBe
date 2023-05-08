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
import numpy as np
from Pyro5.api import Proxy
from cobe.settings import network, odmodel
from time import sleep
import matplotlib.pyplot as plt


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
        # initializing object detectors on eyes
        self.nano_password = input("To start inference server on Nano, please enter the admin password:")
        self.initialize_object_detectors()
        # at this point eyes are read for traffic

    def create_eye_objects(self):
        """Creates eye Pyro objects from the network settings"""
        eyes = {}
        for eye_name, eye_data in network.eyes.items():
            eyes[eye_name] = {"pyro_proxy": Proxy(
                eye_data["uri"] + eye_data["name"] + "@" + eye_data["host"] + ":" + eye_data["port"])}
            eyes[eye_name]["eye_data"] = eye_data
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
            print(odmodel.api_key, odmodel.model_name, odmodel.model_id, odmodel.inf_server_url, odmodel.version)
            eye_dict["pyro_proxy"].initODModel(api_key=odmodel.api_key,
                                               model_name=odmodel.model_name,
                                               model_id=odmodel.model_id,
                                               inf_server_url=odmodel.inf_server_url,
                                               version=odmodel.version)

    def start(self):
        """Starts the main action loop of the CoBe project"""
        from pprint import pprint
        # main action loop
        # while True:
        # get inference results from eyes
        # self.initialize_object_detectors()
        for eye_name, eye_dict in self.eyes.items():
            for frid in range(100):
                # img_ser, t = eye_dict["pyro_proxy"].get_calibration_frame()
                # # print(img_ser)
                # # deserialize image from list to numpy array
                # img = np.asarray(img_ser)
                # print(f"Captured frame {frid}", img.shape, t)
                # plt.imshow(img)
                # plt.show()
                try:
                    detections = eye_dict["pyro_proxy"].inference(confidence=20)
                    pprint(detections)
                except Exception as e:
                    if e.find("Original exception: <class 'requests.exceptions.ConnectionError'>") > -1:
                        print("Connection error. Inference server is probably not yet started properly. retrying in 3 "
                              "seconds.")
                        sleep(3)

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


        for eye_name, eye_dict in self.eyes.items():
            # stop docker servers
            eye_dict["pyro_proxy"].stop_inference_server(self.nano_password)
            # waiting for docker to stop the container
            sleep(2)
            eye_dict["pyro_proxy"].remove_inference_server(self.nano_password)



class CoBeCalib(object):
    """The calibration class is responsible for the calibration of the CoBe Eyes and can communicate with the
    projector stack via Resolume"""
    def __init__(self):
        """Constructor, initializing resolume interface"""
        pass

    def calibrate(self, pyro_proxy):
        """Calibrates the CoBe system
        :param pyro_proxy: Pyro proxy object of the eye to calibrate"""
        # project calibration image via resolume
        # collect calibration image from eye
        # calculate calibration matrix
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
