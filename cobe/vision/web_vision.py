"""Methods to stream vision of robot via mjpg web server"""
import io
import socketserver
from http import server
from PIL import Image
import logging
import cv2
import numpy as np

PAGE = """\
<html>
<head>
<title>CoBe Eye - Stream</title>
</head>
<body>
<center><h1>CoBe Eye - Stream</h1></center>
<center><img src="stream.mjpg" width="640" height="480"></center>
</body>
</html>
"""

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        global frame
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path.endswith('.mjpg'):
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Pragma-directive', 'no-cache')
            self.send_header('Cache-directive', 'no-cache')
            self.send_header('Expires', '0')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    if self.server.frame is not None:
                        jpg = Image.fromarray(cv2.resize(cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB), self.server.des_res).astype('uint8'))
                        buf = io.BytesIO()
                        jpg.save(buf, format='JPEG')
                        frame_n = buf.getvalue()
                        self.wfile.write(b'--FRAME\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
                        # self.send_header('Content-Length', len(frame_n))
                        self.end_headers()
                        self.wfile.write(frame_n)
                        self.wfile.write(b'\r\n')
                        self.server.frame = None
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, x, y):
        super(StreamingServer, self).__init__(x, y)
        self.frame = None
        self.des_res = None