import subprocess
import socket

unity_path = 'C:\\Users\\David\\Desktop\\test_build\\CoBe.exe'
port = 13000
ip_address = "127.0.0.1"

class RenderingStack(object):
    
    def __init__(self):
        # Call the Unity app to open without blocking the thread
        subprocess.Popen(unity_path)

        # Create the TCP Sender
        self.sender = self.create_tcp_sender(ip_address, port)

    def create_tcp_sender(self, ip_address: str, port: int) -> socket.socket:
        # Create the TCP Sender object at the ip and port specified in the rendersettings.py file
        sender = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sender.connect((ip_address, port))

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

    def close_sender(self):
        self.sender.close()

