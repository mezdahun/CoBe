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

import logging  # must be imported and set before pyro
from cobe.settings import logs
logging.basicConfig(level=logs.log_level, format=logs.log_format)
logger = logs.setup_logger("vision")

import numpy as np
from Pyro5.api import expose, behavior, oneway
from Pyro5.server import Daemon
from roboflow.models.object_detection import ObjectDetectionModel
from cobe.tools.iptools import get_local_ip_address
from cobe.tools.detectiontools import annotate_detections
from cobe.settings import vision, odmodel
from cobe.vision import web_vision


def gstreamer_pipeline(
        capture_width=vision.capture_width,
        capture_height=vision.capture_height,
        start_x=vision.start_x,
        start_y=vision.start_y,
        end_x=vision.end_x,
        end_y=vision.end_y,
        display_width=vision.display_width,
        display_height=vision.display_height,
        framerate=vision.frame_rate,
        flip_method=vision.flip_method,
):
    """Returns a GStreamer pipeline string to start stream with the CSI camera
    on nVidia Jetson Nano"""
    logger.info("Creating GStreamer pipeline string with the following parameters:"
                "capture_width: %d, "
                "capture_height: %d, "
                "start_x: %d, "
                "start_y: %d, "
                "end_x: %d, "
                "end_y: %d, "
                "display_width: %d, "
                "display_height: %d, "
                "framerate: %d, "
                "flip_method: %d" % (
                    capture_width,
                    capture_height,
                    start_x,
                    start_y,
                    end_x,
                    end_y,
                    display_width,
                    display_height,
                    framerate,
                    flip_method
                ))
    return (
            "nvarguscamerasrc ! "
            "video/x-raw(memory:NVMM), "
            "width=(int)%d, height=(int)%d, "  # sensor width and height according to sensor mode of the camera
            "format=(string)NV12, framerate=(fraction)%d/1 ! "  # framerate according to sensor mode
            "nvvidconv flip-method=%d left=%d right=%d top=%d bottom=%d ! "  # flip and crop image
            "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "  # resize image
            "videoconvert ! "
            "video/x-raw, format=(string)BGR ! appsink drop=true sync=false"
            % (
                capture_width,
                capture_height,
                framerate,
                flip_method,
                start_x,
                end_x,
                start_y,
                end_y,
                display_width,
                display_height
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

        # sudo pswd
        self.pswd = None

    @expose
    def has_pswd(self):
        """Returns whether the eye has a password set"""
        logger.debug("Password status requested.")
        if self.pswd is None:
            return False
        else:
            return True

    @expose
    def set_pswd(self, pswd):
        """Sets the password of the eye"""
        self.pswd = pswd
        logger.info("Password set.")

    @expose
    def set_fisheye_calibration_map(self, calibration_map):
        """Sets the fisheye calibration map for the eye"""
        self.fisheye_calibration_map = calibration_map
        logger.info("Fisheye calibration map set.")

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
        logger.info("Streaming server started with address %s and port %d" % (self.local_ip, port))

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
        logger.info("Object detection model initialized with parameters: %s, %s, %s, %s" % (
                    model_name, inf_server_url, model_id, version))

    def search_for_docker_container(self):
        """Searches for a docker container with a given container name"""
        command = 'docker ps --filter=name=%s' % odmodel.inf_server_cont_name
        logger.info("created command")
        response = subprocess.getoutput('echo %s|sudo -S %s' % (self.pswd, command)).splitlines()
        # logger.info("got response")
        # if len(response) > 0:
        #     container_id = response[1].split()[0]
        #     logger.info("Found docker container with id %s" % container_id)
        # else:
        #     container_id = None
        #     logger.info("No docker container found with name %s" % odmodel.inf_server_cont_name)
        # self.inference_server_id = container_id
        return response

    @expose
    def start_inference_server(self):
        """Starts the roboflow inference server via docker."""
        print("HELLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL")
        # # First searching for a previously created inference container.
        # # Note, if you want to deploy a newly trained model, first cleanup the containers, so they won't be found
        cid = self.search_for_docker_container()
        print("HELLLLOOOOOOOO", cid)
        # if self.inference_server_id is None:
        #     command = "docker run --name %s --net=host --gpus all -d roboflow/inference-server:jetson" % odmodel.inf_server_cont_name
        #     # calling command with os.system and saving the resulting  STD output in string variable
        #     pid = subprocess.getoutput('echo %s|sudo -S %s' % (self.pswd, command))
        #     logger.info("Inference server container created and started with pid ", pid)
        #     self.inference_server_id = pid
        # else:
        #     command = "docker start %s" % self.inference_server_id
        #     pid = subprocess.getoutput('echo %s|sudo -S %s' % (self.pswd, command))
        #     logger.info("Inference server container was found and (re)started with pid ", pid)
        #     logger.warning("If you want to deploy a newly trained model, first cleanup the containers, so they "
        #                    "won't be found. For the first time you will need internet access to download the model.")
        return cid

    @expose
    def stop_inference_server(self):
        """Stops the roboflow inference server via docker."""
        if self.inference_server_id is None:
            logger.warning("Inference server not found. Nothing to stop!")
            return None

        command = "docker stop " + str(self.inference_server_id)
        pid = subprocess.getoutput('echo %s|sudo -S %s' % (self.pswd, command))
        logger.info("Inference server container was stopped with pid ", pid)
        return pid

    @oneway
    @expose
    def remove_inference_server(self):
        """Removes the roboflow inference server via docker."""
        if self.inference_server_id is None:
            logger.warning("Inference server not found. Nothing to remove!")
            return None

        command = "docker rm " + str(self.inference_server_id)
        pid = subprocess.getoutput('echo %s|sudo -S %s' % (self.pswd, command))
        logger.info("Inference server container was removed with pid ", pid)
        self.inference_server_id = None
        return pid

    @expose
    def return_id(self):
        """This is exposed on the network and can have a return value"""
        logger.debug(f"ID was requested and returned: {self.id}")
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
        logger.debug("Taking single frame.")
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
            width = vision.display_width
        if height is None:
            height = vision.display_height
        # taking single image with max possible resolution given the GStreamer pipeline
        img, t_cap = self.get_frame(img_width=width, img_height=height)
        # adding high resolution image to calibration frame to publish on local network
        if self.publish_mjpeg_stream:
            if self.streaming_server is None:
                self.setup_streaming_server()
            self.streaming_server.calib_frame = img
        else:
            logger.error("MJPEG stream not enabled when eye was initialized. Cannot publish calibration frame."
                         "Set vision.publish_mjpeg_stream to True and restart eye.")

    @expose
    def shutdown(self):
        """Shutting down the eye by setting the Daemon's loop condition to False"""
        self._is_running = False
        logger.info("Eye shutdown initiated.")

    @expose
    def inference(self, confidence=40, img_width=416, img_height=416):
        """Carrying out inference on the edge on single captured fram and returning the bounding box coordinates"""
        img, t_cap = self.get_frame(img_width=img_width, img_height=img_height)

        try:
            detections = self.detector_model.predict(img, confidence=confidence)
        except KeyError:
            logger.error("KeyError in roboflow inference code, can mean that your authentication"
                         "is invalid to the inference server or you are over quota.")

        preds = detections.json().get("predictions")

        # removing image path from predictions as it will hold the whole array
        for pred in preds:
            del pred["image_path"]

        logger.debug(f"Number of predictions: {len(preds)}")

        # annotating the image with bounding boxes and labels and publish on mjpeg streaming server
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
        logger.info(f"Pyro5 daemon started on {host}:{port} with URI {uri}")
        daemon.requestLoop(eye_instance.is_running)


if __name__ == "__main__":
    main()
