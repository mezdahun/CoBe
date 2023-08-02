import base64
import subprocess
import socket
import time
import psutil

import cobe.settings.rendersettings as rs

from cobe.tools.filetools import is_process_running
from cobe.settings import logs

# Setting up file logger
import logging
logging.basicConfig(level=logs.log_level, format=logs.log_format)
logger = logs.setup_logger("rendering")


class RenderingStack(object):
    """The main class of the CoBe project organizing projection and rendering"""

    def __init__(self):
        # Label the instance TCP Sender
        # Moving the creation into the send_message() method ensures that it's only created if needed
        self.sender = None
        self.unity_process = None
        self.resolume_process = None
    
    def close_apps(self):
        """Closing all apps necessary to use visualization stack, i.e. Resolume and Unity App"""
        # If the process is already stored, just terminate it
        logger.info("Closing rendering apps...")
        if self.unity_process:
            self.unity_process.terminate()
        else:
            # If the process isn't stored, but is found, terminate that process
            unity_pid = is_process_running(rs.unity_app_executable_name)
            if unity_pid:
                self.unity_process = psutil.Process(unity_pid)
                self.unity_process.terminate()

        self.unity_process = None
        logger.info("Closed Unity...")
        
        if self.resolume_process:
            self.resolume_process.terminate()
        else:
            resolume_pid = is_process_running(rs.resolume_app_executable_name)
            if resolume_pid:
                self.resolume_process = psutil.Process(resolume_pid)
                self.resolume_process.terminate()
        
        self.resolume_process = None
        logger.info("Closed Resolume...")

    def open_apps(self):
        """Opens all apps necessary to use visualization stack, i.e. Resolume and Unity App"""
        # if the process isn't stored, see if it's running
        if not self.unity_process:
            unity_pid = is_process_running(rs.unity_app_executable_name)

            # if process is already running then store it
            if unity_pid:
                logger.info(f"[UNITY] {rs.unity_app_executable_name} already running...")
                self.unity_process = psutil.Process(unity_pid)
            else:
                # otherwise, open it and store that process
                logger.info(f"Opening [UNITY] {rs.unity_app_executable_name}...")
                self.unity_process = subprocess.Popen(rs.unity_path)
                time.sleep(rs.start_up_delay)
        
        if not self.resolume_process:
            resolume_pid = is_process_running(rs.resolume_app_executable_name)

            if resolume_pid:
                logger.info(f"[RESOLUME] {rs.resolume_app_executable_name} already running...")
                self.resolume_process = psutil.Process(resolume_pid)
            else:
                logger.info(f"Opening [RESOLUME] {rs.resolume_app_executable_name}...")
                self.resolume_process = subprocess.Popen(rs.resolume_path)
                time.sleep(rs.start_up_delay)

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
                logger.warning("TCP connection was refused, sleeping 2s and trying again")
                time.sleep(2)
                next

        logger.info(f"[UNITY] TCP listener connected to {ip_address}:{port}")
        return sender

    def send_message(self, byte_object: bytes) -> bool:
        """Attempts to send a message via the RenderingStack instance's self.sender client
        Args:
            byte_object: (byte-like): The message to be sent converted to bytes, such as produced by file.read()
        Returns:
            bool: Whether the message was successfully communicated or not
        """
        if not self.sender:
            logger.warning("TCP sender does not exist, creating sender...")
            self.sender = self.create_tcp_sender(rs.ip_address, rs.port)
            logger.debug("sender created: ", self.sender)

        try:
            logger.info("Sending message to TCP sender...")
            if self.sender.sendall(byte_object) is None:
                return True
            else:
                return False
        except Exception as e:
            logger.error(e)
            logger.error("Error during sending message to sender!")
            return False

    def close_sender(self):
        """Closes the TCP sender client"""
        self.sender.close()
        self.sender = None
        logger.debug("TCP sender closed")

    def display_image(self, byte_array: bytearray):
        """Displays the passed image atop the Unity rendering stack
        Args:
            byte_array: (bytearray): The image to be displayed represented as a byte array
        """
        logger.info("Displaying image using Unity TCP protocol")
        converted_string = base64.b64encode(byte_array)
        self.send_message(converted_string)
        self.close_sender()

    def remove_image(self):
        logger.info("Removing image using Unity TCP protocol")
        self.send_message("0".encode())
        self.close_sender()