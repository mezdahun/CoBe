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
import cv2
import os
import subprocess
import threading

import numpy as np
from Pyro5.api import expose, behavior, serve, oneway
from Pyro5.server import Daemon
from roboflow.models.object_detection import ObjectDetectionModel
from cobe.tools.iptools import get_local_ip_address
from cobe.tools.detectiontools import annotate_detections
from cobe.settings import vision
from cobe.vision import web_vision


def gstreamer_pipeline(
        capture_width=vision.capture_width,
        capture_height=vision.capture_height,
        display_width=vision.display_width,
        display_height=vision.display_height,
        framerate=vision.frame_rate,
        flip_method=vision.flip_method,
):
    """Returns a GStreamer pipeline string to start stream with the CSI camera
    on nVidia Jetson Nano"""
    # "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
    framerate = 59.999
    return (
            "nvarguscamerasrc ! "
            "video/x-raw(memory:NVMM), "
            "width=1280, height=720, "
            "format=(string)NV12, framerate=(fraction)%d/1 ! "
            "nvvidconv flip-method=%d left=140 right=1140 top=60 bottom=660 ! "
            "video/x-raw, width=1000, height=600, format=(string)BGRx ! "
            "videoconvert ! "
            "video/x-raw, format=(string)BGR ! appsink drop=true sync=false"
            % (
                framerate,
                flip_method
            )
    )


@behavior(instance_mode="single")
@expose
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
        self.cap = cv2.VideoCapture(gstreamer_pipeline(), cv2.CAP_GSTREAMER)

        # Opening fisheye unwarping calibration maps
        self.fisheye_calibration_map = None
        self.map1 = None
        self.map2 = None

        # creating streaming server for image data (slows stream)
        self.publish_mjpeg_stream = vision.publish_mjpeg_stream
        self.streaming_server = None
        self.streaming_thread = None
        if self.publish_mjpeg_stream:
            self.setup_streaming_server()

        # pyro5 daemon stopping flag
        self._is_running = True

    @expose
    def set_fisheye_calibration_map(self, calibration_map):
        """Sets the fisheye calibration map for the eye"""
        self.fisheye_calibration_map = calibration_map

    def is_running(self):
        """Returns the running status of the eye"""
        return self._is_running

    def setup_streaming_server(self, port=vision.mjpeg_stream_port):
        """Sets up a streaming server for the image data from the camera"""
        address = (self.local_ip, port)
        self.streaming_server = web_vision.StreamingServer(address, web_vision.StreamingHandler)
        self.streaming_server.des_res = (int(vision.capture_width / 2), int(vision.capture_height / 2))
        self.streaming_server.eye_id = self.id
        self.streaming_thread = threading.Thread(target=self.streaming_server.serve_forever)
        self.streaming_thread.start()

    @expose
    def initODModel(self, api_key, model_name, inf_server_url, model_id, version):
        """Initialize the object detection model with desired model parameters"""
        print("Initializing object detection model")
        # Definign the object detection model instance
        self.detector_model = ObjectDetectionModel(api_key=api_key,
                                                   name=model_name,
                                                   id=model_id,
                                                   local=inf_server_url,
                                                   version=version)
        print(model_name, inf_server_url, model_id, version)
        # Carry out a single prediction to initialize the model weights
        # todo: carry out a single prediction but with a wrapper that also captures a single image from camera
        # self.detector_model.predict(None)
        print("Object detector initialized for eye ", self.id)
        print(self.detector_model.api_url)

    @oneway
    @expose
    def start_inference_server(self, nano_password):
        """Starts the roboflow inference server via docker."""
        if self.inference_server_id is None:
            command = "docker run --net=host --gpus all -d roboflow/inference-server:jetson"
            # calling command with os.system and saving the resulting  STD output in string variable
            pid = subprocess.getoutput('echo %s|sudo -S %s' % (nano_password, command))
            print("Inference server started with pid ", pid)
            self.inference_server_id = pid
        else:
            print("Inference server already running with pid ", self.inference_server_id)
        return pid

    @oneway
    @expose
    def stop_inference_server(self, nano_password):
        """Stops the roboflow inference server via docker."""
        if self.inference_server_id is None:
            print("Inference server not found. Nothing to stop!")
            return None

        command = "docker stop " + str(self.inference_server_id)
        pid = subprocess.getoutput('echo %s|sudo -S %s' % (nano_password, command))
        print("Inference server stopped with pid ", pid)
        return pid

    @oneway
    @expose
    def remove_inference_server(self, nano_password):
        """Removes the roboflow inference server via docker."""
        if self.inference_server_id is None:
            print("Inference server not found. Nothing to remove!")
            return None

        command = "docker rm " + str(self.inference_server_id)
        pid = subprocess.getoutput('echo %s|sudo -S %s' % (nano_password, command))
        print("Inference server removed with pid ", pid)
        self.inference_server_id = None
        return pid

    @expose
    def return_id(self):
        """This is exposed on the network and can have a return value"""
        print(f"ID requested and returned: {self.id}")
        return self.id

    def get_frame(self, img_width, img_height):
        """getting single camera frame according to stream parameters and resizing it to desired dimensions"""
        # if self.map1 is None and self.fisheye_calibration_map is not None:
        #     cmap_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calibration_maps', self.fisheye_calibration_map)
        #     print(f"Fisheye map file provided but not yet loaded, loading it first from {cmap_path}...")
        #     maps = np.load(cmap_path)
        #     self.map1, self.map2 = maps["map1"], maps["map2"]
        #     print("Fisheye map file loaded successfully")

        t_cap = datetime.datetime.now()
        print("Taking single frame")
        # getting single frame in high resolution
        ret_val, imgo = self.cap.read()

        # if self.map1 is not None:
        #     # undistorting image according to fisheye calibration map
        #     imgo = cv2.remap(imgo, self.map1, self.map2, interpolation=cv2.INTER_LINEAR,
        #                      borderMode=cv2.BORDER_CONSTANT)

        # resizing image to requested w and h
        img = cv2.resize(imgo, (img_width, img_height))
        # returning image and timestamp
        return img, t_cap

    @expose
    def get_calibration_frame(self, width=None, height=None):
        """Used for calibrating the camera with ARUCO codes by publishing a single high resolution image on the
        local network."""
        if width is None:
            width = vision.capture_width
        if height is None:
            height = vision.capture_height
        # taking single image with max possible resolution given the GStreamer pipeline
        img, t_cap = self.get_frame(img_width=width, img_height=height)
        # adding high resolution image to calibration frame to publish on local network
        if self.publish_mjpeg_stream:
            if self.streaming_server is None:
                self.setup_streaming_server()
            self.streaming_server.calib_frame = img
        else:
            print("MJPEG stream not enabled when eye was initialized. Cannot publish calibration frame."
                  "Set vision.publish_mjpeg_stream to True and restart eye.")


    @expose
    def test_dict_return_latency(self):
        """Testing return latency of dictionaries via Pyro5"""
        test_dict = {"test": "test"}
        return test_dict, datetime.datetime.now()

    @expose
    def shutdown(self):
        """Shutting down the eye by setting the Daemon's loop condition to False"""
        self._is_running = False

    @expose
    def inference(self, confidence=40, img_width=320, img_height=200):
        """Carrying out inference on the edge on single captured fram and returning the bounding box coordinates"""
        img, t_cap = self.get_frame(img_width=img_width, img_height=img_height)

        try:
            detections = self.detector_model.predict(img, confidence=confidence)
        except KeyError:
            print("KeyError in roboflow inference code, can mean that your authentication"
                  "is invalid to the inference server.")

        preds = detections.json().get("predictions")

        # removing image path from predictions
        for pred in preds:
            del pred["image_path"]

        # # annotating the image with bounding boxes and labels and publish on mjpeg streaming server
        if self.publish_mjpeg_stream:
            if self.streaming_server is None:
                self.setup_streaming_server()
            self.streaming_server.frame = annotate_detections(img, preds)

        return preds


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

    # Starting Pyro5 Daemon
    with Daemon(host, port) as daemon:
        eye_instance = CoBeEye()
        uri = daemon.register(eye_instance, objectId="cobe.eye")
        print(uri)
        daemon.requestLoop(eye_instance.is_running)


if __name__ == "__main__":
    main()
