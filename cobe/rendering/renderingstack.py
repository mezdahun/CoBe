import subprocess
import socket
import time
import cobe.rendering.rendersettings as rs
import sys

class RenderingStack(object):
    def __init__(self):
        # Call the Unity app to open without blocking the thread
        # subprocess.Popen(rs.unity_path)

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

    def close_sender(self):
        self.sender.close()
