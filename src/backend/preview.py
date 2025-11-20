import socket
import threading
from select import select
import time

class MjpegFrameReceiver:
    def __init__(self, host="127.0.0.1", port=5001, boundary="spionisto"):
        self._host = host
        self._port = port
        self._boundary_str = boundary
        self._boundary_bytes = b"--" + boundary.encode("ascii")

        self._lock = threading.Lock()
        self._latest_frame = None  # type: bytes | None
        self._latest_frame_recv_time = None  # type: float | None

        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self._host, self._port))
        self._server_sock.listen()

        threading.Thread(target=self._run, daemon=True).start()


    def get_latest_frame(self):
        with self._lock:
            return self._latest_frame, self._latest_frame_recv_time


    def _run(self):
        while True:
            print("[MjpegFrameReceiver] Waiting for input stream...")
            try:
                sd, addr = self._server_sock.accept()
            except socket.timeout:
                continue

            print("[MjpegFrameReceiver] Accepted input stream from", addr)
            try:
                self._handle_connection(sd)
            finally:
                sd.close()
                print("[MjpegFrameReceiver] Lost input stream from", addr)

    def _handle_connection(self, sd: socket.socket):
        """
        Parse one TCP connection carrying a multipart MJPEG stream.
        """
        sd.setblocking(False)
        buffer = b""
        current_start = None  # index of current frame boundary in buffer

        while True:
            readable, _, _ = select([sd], [], [], 0.5)
            if not readable:
                continue

            try:
                data = sd.recv(4096)
            except BlockingIOError:
                continue

            if not data:
                # EOF
                break

            buffer += data

            # Find first boundary if we don't have one yet
            if current_start is None:
                idx = buffer.find(self._boundary_bytes)
                if idx == -1:
                    # Keep only enough bytes for a potential partial boundary
                    if len(buffer) > len(self._boundary_bytes):
                        buffer = buffer[-len(self._boundary_bytes):]
                    continue
                current_start = idx

            # Repeatedly look for the next boundary to delimit frames
            while True:
                next_idx = buffer.find(
                    self._boundary_bytes,
                    current_start + len(self._boundary_bytes)
                )
                if next_idx == -1:
                    # No full next frame yet; compact buffer
                    if current_start > 0:
                        buffer = buffer[current_start:]
                        current_start = 0
                    break

                # We have a complete multipart part between current_start and next_idx
                part = buffer[current_start:next_idx]
                self._extract_and_store_jpeg(part)

                # Move to next frame
                current_start = next_idx

    def _extract_and_store_jpeg(self, part: bytes):
        """
        Given a multipart part starting with '--boundary', extract the JPEG payload
        and store it as the latest frame.
        """
        # Multipart format is roughly:
        #   --boundary\r\n
        #   Header: value\r\n
        #   Header2: value\r\n
        #   \r\n
        #   <jpeg data>\r\n
        #
        # We find the end of headers (empty line) and take everything after it.

        # Find end of headers (try CRLFCRLF first, then LFLF)
        header_end = part.find(b"\r\n\r\n")
        offset = 4
        if header_end == -1:
            header_end = part.find(b"\n\n")
            offset = 2

        if header_end == -1:
            # Malformed part; skip
            return

        jpeg_data = part[header_end + offset :]

        # Store latest frame atomically
        with self._lock:
            self._latest_frame = jpeg_data
            self._latest_frame_recv_time = time.time()
