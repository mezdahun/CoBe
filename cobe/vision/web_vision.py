"""Methods to stream vision of robot via mjpg web server"""
import io
import socketserver
from http import server
from PIL import Image
import logging
import cv2
import numpy as np


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        global frame
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = """\
                    <html>
                    <head>
                    <title>CoBe Eye - Stream</title>
                    </head>
                    <body>
                    <center><h1>CoBe Eye id: """ + str(self.server.eye_id) + """ - Stream</h1></center>
                    <center><img src="stream.mjpg" width="640" height="480"></center>
                    </body>
                    </html>
                    """
            content = content.encode('utf-8')
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
                    jpg = None
                    if self.server.frame is not None and self.path.endswith('stream.mjpg'):
                        # Streaming inference frame for monitoring
                        jpg = Image.fromarray(
                            cv2.resize(cv2.cvtColor(self.server.frame, cv2.COLOR_BGR2RGB), self.server.des_res).astype(
                                'uint8'))
                    if self.server.calib_frame is not None and self.path.endswith('calibration.mjpg'):
                        # Streaming high-resolution calibration frame for calibration
                        jpg = Image.fromarray(
                            cv2.cvtColor(self.server.calib_frame, cv2.COLOR_BGR2RGB).astype('uint8'))
                    if jpg is not None:
                        buf = io.BytesIO()
                        jpg.save(buf, format='JPEG')
                        frame_n = buf.getvalue()
                        self.wfile.write(b'--FRAME\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
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
        # frame to attach to monitoring mJPG stream
        self.frame = None
        # highres frame to attach to calibration mJPG stream
        self.calib_frame = None
        # desired resolution of the stream
        self.des_res = None
        # id of the CoBeEye to stream
        self.eye_id = None
