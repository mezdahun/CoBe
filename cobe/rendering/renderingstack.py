import subprocess
import socket
import time
import cobe.settings.rendersettings as rs
import psutil
import base64

class RenderingStack(object):
    """The main class of the CoBe project organizing projection and rendering"""
    def __init__(self):
        # Call the Unity app to open without blocking the thread if it's not open already
        if not self.is_file_running("CoBe.exe"):
            subprocess.Popen(rs.unity_path)
        
        if not self.is_file_running("Arena.exe"):
            subprocess.Popen(rs.resolume_path)

        # Create the TCP Sender
        self.sender = self.create_tcp_sender(rs.ip_address, rs.port)

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

    def send_message(self, byte_object: bytes) -> bool:
        """Attempts to send a message via the RenderingStack instance's self.sender client
        Args:
            byte_object: (byte-like): The message to be sent converted to bytes, such as produced by file.read()
        Returns:
            bool: Whether the message was successfully communicated or not
        """
        try:
            if self.sender.sendall(byte_object) is None:
                return True
            else:
                return False
        except:
            return False

    def close_sender(self):
        self.sender.close()

    def display_image(self, byte_array: bytearray):
        """Displays the passed image atop the Unity rendering stack
        Args:
            byte_array: (bytearray): The image to be displayed represented as a byte array
        """
        converted_string = base64.b64encode(byte_array)
        self.send_message(converted_string)

    def remove_image(self):
        self.send_message("0".encode())
    
    def is_file_running(self, name: str) -> bool:
        """Checks if a process is running on the system by comparing the name of each running process"""
        for pid in psutil.pids():
            p = psutil.Process(pid)
            if p.name() == name:
                # process found
                return True
        return False



# # Testing suite for loading image from disk and passing to Unity
# image_file_path = "C:\\Users\\David\\Pictures\\test_image2.jpeg"
# rs = RenderingStack()
# with open(image_file_path, "rb") as image:
#     rs.display_image(image.read())

# rs.remove_image()

