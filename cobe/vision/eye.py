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
import os
import subprocess
from Pyro5.api import expose, behavior, serve, oneway
from roboflow.models.object_detection import ObjectDetectionModel
from cobe.settings import vision as visset
from cobe.tools.iptools import get_local_ip_address


@behavior(instance_mode="single")
class CoBeEye(object):
    """Class serving as input generator of CoBe running on nVidia boards to carry out
    object detection on the edge and forward detection coordinates via Pyro5"""

    def __init__(self):
        # Mimicking initialization of eye using e.g. environment parameters or
        # other setting files distributed before
        self.id = os.getenv("EYE_ID", 0)
        self.local_ip = get_local_ip_address()
        self.detector_model = None
        self.inference_server_id = None

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
        pid = os.system('echo %s|sudo -S %s' % (nano_password, command))
        print("Inference server stopped with pid ", pid)
        return pid

    @expose
    def return_id(self):
        """This is exposed on the network and can have a return value"""
        print(f"This is reachable via Pyro! My id is {self.id}")
        return self.id


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
