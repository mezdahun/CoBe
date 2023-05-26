import subprocess
import socket
from particlesimulator import ParticleSimulator
import json
from dataclasses import asdict
import sched, time
import rendersettings as rs
import sys

class RenderingStack(object):
    def __init__(self):
        sys.path.insert(0, 'cobesettings.rendersettings')
        # Call the Unity app to open without blocking the thread
        subprocess.Popen(rs.unity_path)
        self.simulator = ParticleSimulator()

        # Create the TCP Sender
        self.sender = self.create_tcp_sender(rs.ip_address, rs.port)

        # Create the loop scheduler
        self.my_scheduler = sched.scheduler(time.time, time.sleep)
        self.consecutive_failures = 0

    def create_tcp_sender(self, ip_address: str, port: int) -> socket.socket:
        """Creates a TCP Client object and attempts to connect to the socket specified by the method arguments

        Args:
            ip_address (str): The IP Address of the desired socket
            port (int): The port of the desired socket

        Returns:
            socket.socket: The connected socket
        """
        sender = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connected = False

        while not connected:
            try:
                sender.connect((ip_address, port))
                connected = True
            except ConnectionRefusedError:
                print("TCP connection was refused, sleeping 2s and trying again")
                time.sleep(2)
                next

        return sender

    def send_message(self, text: str) -> bool:
        """Attempts to send a message via the RenderingStack instance's self.sender client

        Args:
            text (str): The message to be sent

        Returns:
            bool: Whether the message was successfully communicated or not
        """
        try:
            if self.sender.sendall(text.encode()) is None:
                return True
            else:
                return False
        except:
            return False
    
    def start_loop(self):
        """Queues the first loop iteration and then begins execution"""
        self.my_scheduler.enter(rs.sending_frequency, 1, self.scheduled_send)
        self.my_scheduler.run()   

    def scheduled_send(self): 
        """The template for a single loop iteration: queues the next iteration and updates the data set"""
        # Schedule the next call first
        if self.consecutive_failures < rs.failure_limit:
            self.my_scheduler.enter(rs.sending_frequency, 1, self.scheduled_send)
        else:
            print("Consecutive failure limit reached, aborting queue")

        # Serialize the JsonDecompressor into a string & attempt to send
        jsonString = json.dumps(asdict(self.simulator.update())) + "\n"
        if jsonString != "":
            if not self.send_message(jsonString):
                self.consecutive_failures += 1
            else: 
                self.consecutive_failures = 0

    def close_sender(self):
        self.sender.close()


# rStack = RenderingStack()
# rStack.start_loop()





