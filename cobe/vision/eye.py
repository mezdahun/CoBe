"""
CoBe - Vision - Eye

Eyes are functional elements of CoBe stack implemented as single python classes.
They
    - are partly exposed as Pyro5 objects on the local network
    - can run as Pyro5 daemons on nVidia boards
    - can communicate with a triton server and carry out inference on the edge when requested
    - return bounding box coordinates
"""
from Pyro5.api import expose, behavior, serve, oneway
from numpy import random
import argparse
import roboflow
from roboflow.models.object_detection import ObjectDetectionModel
from cobe.settings import vision as visset
import os


@behavior(instance_mode="single")
class CoBeEye(object):
    """Class serving as input generator of CoBe running on nVidia boards to carry out
    object detection on the edge and forward detection coordinates via Pyro5"""

    def __init__(self):
        # Mimicking initialization of eye using e.g. environment parameters or
        # other setting files distributed before
        self.id = os.getenv("EYE_ID", 0)
        # self.detector_model = ObjectDetectionModel(api_key=visset.api_key,
        #                                            name=visset.model_name,
        #                                            id=visset.model_id,
        #                                            local=visset.inf_server_IP,
        #                                            version=visset.version)

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
