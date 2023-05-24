import subprocess
import socket
from particlesimulator import ParticleSimulator
import json
from dataclasses import asdict
import sched, time

unity_path = 'C:\\Users\\David\\Desktop\\test_build\\CoBe.exe'
port = 13000
ip_address = "127.0.0.1"
failure_limit = 250
sending_frequency = 0.02

class RenderingStack(object):
    def __init__(self):
        # Call the Unity app to open without blocking the thread
        subprocess.Popen(unity_path)
        self.simulator = ParticleSimulator()

        # Create the TCP Sender
        self.sender = self.create_tcp_sender(ip_address, port)

        # Create the loop scheduler
        self.my_scheduler = sched.scheduler(time.time, time.sleep)
        self.consecutive_failures = 0

    def create_tcp_sender(self, ip_address: str, port: int) -> socket.socket:
        # Create the TCP Sender object at the ip and port specified in the rendersettings.py file
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
        # Send a JSON string to the Unity TCP Listener
        # Once Unity starts receiving data on the fish port, the calibration image is automatically closed
        try:
            if self.sender.sendall(text.encode()) is None:
                return True
            else:
                return False
        except:
            return False
    
    def start_loop(self):
        self.my_scheduler.enter(sending_frequency, 1, self.scheduled_send)
        self.my_scheduler.run()   

    def scheduled_send(self): 
        # schedule the next call first
        if self.consecutive_failures < failure_limit:
            self.my_scheduler.enter(sending_frequency, 1, self.scheduled_send)
        else:
            print("Consecutive failure limit reached, aborting queue")

        # Serialize the JsonDecompressor into a string
        jsonString = json.dumps(asdict(self.simulator.update())) + "\n"
        if jsonString != "":
            if not self.send_message(jsonString):
                self.consecutive_failures += 1
            else: 
                self.consecutive_failures = 0

    def close_sender(self):
        self.sender.close()


rs = RenderingStack()
rs.start_loop()





