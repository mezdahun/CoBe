"""
CoBe - Vision - Eye

Eyes are functional elements of CoBe stack implemented as single python classes.
They
    - are partly exposed as Pyro5 objects on the local network
    - can run as Pyro5 daemons on nVidia boards
    - can communicate with a triton server and carry out inference on the edge when requested
    - return bounding box coordinates
"""
import argparse
import datetime
import os
import pickle

import cv2
import subprocess
from Pyro5.api import expose, behavior, serve, oneway
from roboflow.models.object_detection import ObjectDetectionModel
from cobe.tools.iptools import get_local_ip_address


def gstreamer_pipeline(
        capture_width=320,
        capture_height=200,
        display_width=320,
        display_height=200,
        framerate=30,
        flip_method=0,
):
    return (
            "nvarguscamerasrc ! "
            "video/x-raw(memory:NVMM), "
            "width=(int)%d, height=(int)%d, "
            "format=(string)NV12, framerate=(fraction)%d/1 ! "
            "nvvidconv flip-method=%d ! "
            "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
            "videoconvert ! "
            "video/x-raw, format=(string)BGR ! appsink"
            % (
                capture_width,
                capture_height,
                framerate,
                flip_method,
                display_width,
                display_height,
            )
    )


@behavior(instance_mode="single")
class CoBeEye(object):
    """Class serving as input generator of CoBe running on nVidia boards to carry out
    object detection on the edge and forward detection coordinates via Pyro5"""

    def __init__(self):
        # Mimicking initialization of eye using e.g. environment parameters or
        # other setting files distributed before
        # ID of the Nano module
        self.id = os.getenv("EYE_ID", 0)
        # IP address of the Nano module in the local network
        self.local_ip = get_local_ip_address()
        # ObjectDetectionModel instance to carry out predictions on a roboflow server
        self.detector_model = None
        # Docker ID of the roboflow inference server running on the Nano module
        self.inference_server_id = None
        # Starting cv2 capture stream from camera
        # print(gstreamer_pipeline(flip_method=0))
        self.cap = cv2.VideoCapture(gstreamer_pipeline(flip_method=0), cv2.CAP_GSTREAMER)

    @oneway
    @expose
    def initODModel(self, api_key, model_name, inf_server_url, model_id, version):
        """Initialize the object detection model with desired model parameters"""
        # Definign the object detection model instance
        self.detector_model = ObjectDetectionModel(api_key=api_key,
                                                   name=model_name,
                                                   id=model_id,
                                                   local=inf_server_url,
                                                   version=version)
        # Carry out a single prediction to initialize the model weights
        # todo: carry out a single prediction but with a wrapper that also captures a single image from camera
        # self.detector_model.predict(None)
        print("Object detector initialized for eye ", self.id)

    @oneway
    @expose
    def start_inference_server(self, nano_password):
        """Starts the roboflow inference server via docker."""
        command = "docker run --net=host --gpus all -d roboflow/inference-server:jetson"
        # calling command with os.system and saving the resulting  STD output in string variable
        pid = subprocess.getoutput('echo %s|sudo -S %s' % (nano_password, command))
        print("Inference server started with pid ", pid)
        self.inference_server_id = pid
        return pid

    @oneway
    @expose
    def stop_inference_server(self, nano_password):
        """Stops the roboflow inference server via docker."""
        if self.inference_server_id is None:
            print("Inference server not running. Nothing to stop!")
            return None

        command = "docker stop " + str(self.inference_server_id)
        pid = subprocess.getoutput('echo %s|sudo -S %s' % (nano_password, command))
        print("Inference server stopped with pid ", pid)
        return pid

    @expose
    def return_id(self):
        """This is exposed on the network and can have a return value"""
        print(f"This is reachable via Pyro! My id is {self.id}")
        return self.id

    def read_model_parameters(self):
        """Reading internal parameters of the initialized ObjectDetection Model"""
        # fill self.OD_model_parameters dictionary with parameters
        pass

    def get_frame(self):
        """getting single camera frame, according to the OD model"""
        # getting single frame according to self.OD_model_parameters parameters using the opencv module
        pass

    @expose
    def get_calibration_frame(self):
        """calibrating the camera by returning a single high resolution image to CoBe main node"""
        # getting single frame in high resolution
        # set capture timestamp
        t_cap = datetime.datetime.now()
        ret_val, img = self.cap.read()
        # serializing numpy.ndarray to list
        img_ser = img.tolist()
        # returning image data
        return img_ser, t_cap

    @expose
    def test_dict_return_latency(self):
        """Testing return latency of dictionaries via Pyro5"""
        test_dict = {"test": "test"}
        return test_dict, datetime.datetime.now()

    @expose
    def inference(self):
        """Carrying out inference on the edge on single captured fram and returning the bounding box coordinates"""
        frame = self.get_frame()
        detections = self.detector_model.predict(frame)
        return detections


def main(host="localhost", port=9090):
    """Starts the Pyro5 daemon exposing the CoBeEye class"""
    # Parse command line arguments if called from the command line
    args = argparse.ArgumentParser(description="Starts the Pyro5 daemon exposing the CoBeEye class")

    # adding optional help message to the arguments
    ahost = args.add_argument("--host", default=None, help="Host address to use for the Pyro5 daemon")
    aport = args.add_argument("--port", default=None, help="Port to use for the Pyro5 daemon")
    args = args.parse_args()
    if args.host is not None:
        host = args.host
    if args.port is not None:
        port = int(args.port)

    # Start the daemon
    serve({CoBeEye: "cobe.eye"},
          use_ns=False,
          host=host,
          port=port)


if __name__ == "__main__":
    main()
