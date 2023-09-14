### Thymio2 submodule of CoBe that allows to start a Pyro5 server on the Thymio2 robot
### so that one can control them remotely according to simulation data in CoBe

import argparse
from Pyro5.api import expose, behavior, oneway
from Pyro5.server import Daemon
import os

import logging  # must be imported and set before pyro
from cobe.settings import logs, network
from cobe.tools.iptools import get_local_ip_address

logging.basicConfig(level=logs.log_level, format=logs.log_format)
logger = logs.setup_logger("thymio")


@behavior(instance_mode="single")
@expose
class CoBeThymio(object):
    """Class serving as robot controller on Thymio robots exposed via Pyro5"""

    def __init__(self):
        # Mimicking initialization of eye using e.g. environment parameters or
        # other setting files distributed before
        # ID of the Nano module
        self.id = os.getenv("EYE_ID", 0)
        self.th_name = "thymio_" + str(self.id)
        self.eye_params = network.thymios[self.th_name]
        self.local_ip = get_local_ip_address()
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

    def is_running(self):
        """Returns the running status of the eye"""
        return self._is_running

    @expose
    def return_id(self):
        """This is exposed on the network and can have a return value"""
        logger.debug(f"ID was requested and returned: {self.id}")
        return self.id


def main(host="localhost", port=9090):
    """Starts the Pyro5 daemon exposing the CoBeThymio class"""
    # Parse command line arguments if called from the command line
    args = argparse.ArgumentParser(description="Starts the Pyro5 daemon exposing the CoBeThymio class")

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
        th_instance = CoBeThymio()
        uri = daemon.register(th_instance, objectId="cobe.eye")
        logger.info(f"Pyro5 Thymio daemon started on {host}:{port} with URI {uri}")
        daemon.requestLoop(th_instance.is_running)


if __name__ == "__main__":
    main()
