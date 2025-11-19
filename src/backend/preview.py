#!/usr/bin/env python3
import socket
import threading
import time
from select import select


class MjpegFrameReceiver:
    """
    Receive a multipart MJPEG stream from GStreamer over TCP and expose
    the latest JPEG frame as raw bytes.

    Expected GStreamer pipeline example:

        gst-launch-1.0 videotestsrc pattern=ball ! videoconvert ! \
            video/x-raw, framerate=15/1, width=640, height=480 ! \
            jpegenc ! multipartmux boundary=spionisto ! \
            tcpclientsink host=127.0.0.1 port=9999
    """

    def __init__(self, host="127.0.0.1", port=9999, boundary="spionisto"):
        self.host = host
        self.port = port
        self.boundary_str = boundary
        self.boundary_bytes = b"--" + boundary.encode("ascii")

        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._latest_frame = None  # type: bytes | None

    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------

    def start(self):
        """
        Start the background thread that receives and parses the MJPEG stream.
        Safe to call multiple times; second call is a no-op if already running.
        """
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def get_latest_frame(self):
        """
        Return the latest JPEG frame as bytes, or None if no frame has been received yet.
        If you write these bytes to disk, they should be a valid .jpg file.
        """
        with self._lock:
            return self._latest_frame

    def stop(self):
        """
        Optional: request the background thread to stop.
        Note: the thread will only exit once the current accept/recv cycle breaks.
        """
        self._stop_event.set()

    # ------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------

    def _run(self):
        """
        Main loop: listen for a GStreamer TCP connection and parse
        a multipart MJPEG stream into individual JPEG frames.
        """
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen(1)

        print(f"[MjpegFrameReceiver] Listening on {self.host}:{self.port}")

        try:
            while not self._stop_event.is_set():
                print("[MjpegFrameReceiver] Waiting for input stream...")
                server_sock.settimeout(1.0)
                try:
                    sd, addr = server_sock.accept()
                except socket.timeout:
                    continue

                print("[MjpegFrameReceiver] Accepted input stream from", addr)
                try:
                    self._handle_connection(sd)
                finally:
                    sd.close()
                    print("[MjpegFrameReceiver] Lost input stream from", addr)
        finally:
            server_sock.close()
            print("[MjpegFrameReceiver] Server socket closed")

    def _handle_connection(self, sd: socket.socket):
        """
        Parse one TCP connection carrying a multipart MJPEG stream.
        """
        sd.setblocking(False)
        buffer = b""
        current_start = None  # index of current frame boundary in buffer

        while not self._stop_event.is_set():
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
                idx = buffer.find(self.boundary_bytes)
                if idx == -1:
                    # Keep only enough bytes for a potential partial boundary
                    if len(buffer) > len(self.boundary_bytes):
                        buffer = buffer[-len(self.boundary_bytes):]
                    continue
                current_start = idx

            # Repeatedly look for the next boundary to delimit frames
            while True:
                next_idx = buffer.find(
                    self.boundary_bytes,
                    current_start + len(self.boundary_bytes)
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


# ----------------------------------------------------------------------
# Example usage
# ----------------------------------------------------------------------
if __name__ == "__main__":
    receiver = MjpegFrameReceiver(host="127.0.0.1", port=9999, boundary="spionisto")
    receiver.start()

    print("Receiver started. Waiting for frames...")

    try:
        while True:
            frame = receiver.get_latest_frame()
            if frame is not None:
                # Example: write once then exit
                with open("latest.jpg", "wb") as f:
                    f.write(frame)
                print("Wrote latest.jpg")
                break

            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        receiver.stop()
        print("Stopping receiver...")
