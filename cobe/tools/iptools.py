"""Tools and methods to handle local network connections."""
import socket

def get_local_ip_address():
    # create a socket object
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # connect to any remote server just to get the local IP address
    s.connect(('8.8.8.8', 80))

    # get the local IP address of the socket
    ip_address = s.getsockname()[0]

    # close the socket
    s.close()

    return ip_address