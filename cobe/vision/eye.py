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


@behavior(instance_mode="single")
class CoBeEye(object):
    """Class serving as input generator of CoBe running on nVidia boards to carry out
    object detection on the edge and forward detection coordinates via Pyro5"""

    def __init__(self):
        # Mimicking initialization of eye using e.g. environment parameters or
        # other setting files distributed before
        self.id = random.randint(low=1, high=999)
        self.secret_id = self.id * 5

    def _return_secret_id(self):
        """This is not exposed to the network"""
        print(f"This is private! My secret id is {self.secret_id}")

    @expose
    def return_id(self):
        """This is exposed on the network and can have a return value"""
        print(f"This is reachable via Pyro! My id is {self.id}")
        return self.id

    @expose
    @oneway
    def recalculate_id(self):
        """This is exposed on the network, but can be called only one-way,
         and has no return value"""
        self.id += 2


def main():
    serve({CoBeEye: "cobe.eye"},
          use_ns=False)


if __name__ == "__main__":
    main()
