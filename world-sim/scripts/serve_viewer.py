import http.server
import os
import socketserver

VIEWER = r"S:\Genesis Kernel World Sim\world-sim\viewer"
os.chdir(VIEWER)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


with Server(("0.0.0.0", 8090), Quiet) as httpd:
    httpd.serve_forever()
