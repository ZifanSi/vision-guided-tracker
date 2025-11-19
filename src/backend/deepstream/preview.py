from multiprocessing import Queue
from threading import Thread
from socket import socket
from select import select
from wsgiref.simple_server import WSGIServer, make_server, WSGIRequestHandler
from socketserver import ThreadingMixIn
import time


class MyWSGIServer(ThreadingMixIn, WSGIServer):
    pass


def create_server(host, port, app, server_class=MyWSGIServer,
                  handler_class=WSGIRequestHandler):
    return make_server(host, port, app, server_class, handler_class)


INDEX_PAGE = b"""
<html>
<head>
    <title>Gstreamer testing</title>
</head>
	<body>
		<h1>Test page for dummy camera with GStreamer</h1>
			<img src="http://100.115.14.44:9000/mjpeg_stream" width="1920"/>
		<hr />
	</body>
</html>
"""

ERROR_404 = b"""
<html>
  <head>
    <title>404 - Not Found</title>
  </head>
  <body>
    <h1>404 - Not Found</h1>
  </body>
</html>
"""


class IPCameraApp(object):
    queues = []

    def __call__(self, environ, start_response):
        print("env=", environ['PATH_INFO'])
        if environ['PATH_INFO'] == '/':
            start_response("200 OK", [
                ("Content-Type", "text/html"),
                ("Content-Length", str(len(INDEX_PAGE)))
            ])
            return iter([INDEX_PAGE])
        elif environ['PATH_INFO'] == '/mjpeg_stream':
            return self.stream(start_response)
        else:
            start_response("404 Not Found", [
                ("Content-Type", "text/html"),
                ("Content-Length", str(len(ERROR_404)))
            ])
            return iter([ERROR_404])

    def stream(self, start_response):
        start_response('200 OK', [('Content-type', 'multipart/x-mixed-replace; boundary=--spionisto')])
        q = Queue(4096)
        self.queues.append(q)
        while True:
            try:
                yield q.get()
                time.sleep(0.001)
            except:
                if q in self.queues:
                    self.queues.remove(q)
                return


def input_loop(app):
    sock = socket()
    sock.bind(('127.0.0.1', 9999))
    sock.listen(1)
    while True:
        print('Waiting for input stream')
        sd, addr = sock.accept()
        print('Accepted input stream from', addr)
        data_flag = True
        while data_flag:
            readable = select([sd], [], [], 0.1)[0]
            for s in readable:
                data = s.recv(1024)
                if not data:
                    break
                for q in app.queues:
                    q.put(data)
                    time.sleep(0.001)
        print('Lost input stream from', addr)


if __name__ == '__main__':

    # Launch an instance of wsgi server
    app = IPCameraApp()
    port = 9000
    print('Launching camera server on port', port)
    httpd = create_server('0.0.0.0', port, app)

    print('Launch input stream thread')
    t1 = Thread(target=input_loop, args=[app])
    # t1.setDaemon(True)
    t1.daemon = True
    t1.start()

    try:
        print('Httpd serve forever')
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.kill()
        print("Shutdown camera server ...")