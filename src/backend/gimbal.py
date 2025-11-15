import struct
import serial
from typing import Optional, Tuple


class GimbalSerial:
    """
    Serial protocol helper for a device that exchanges small, fixed-format packets
    with an 8-bit CRC at byte 0 and a 1-byte request identifier at byte 1.

    General framing (requests built via create_request_data)
    Bytes:  [0] [1] [2..N-1]
             │   │  └──┬───┘
             │   │     │
             │   │     └─ Payload (command-specific)
             │   └─ request_id (uint8)
             └─ CRC-8/SMBUS over bytes [1..N-1]

    CRC-8/SMBUS parameters:
      width=8  poly=0x07  init=0x00  refin=false  refout=false  xorout=0x00
      check=0xF4  residue=0x00

    Endianness:
      Unless otherwise stated, all 32-bit floating point values are IEEE-754
      little-endian ("<f" in Python struct notation).

    Typical responses:
      • For simple set/command requests (LEDs, move): device replies with a
        single byte 0x00 to acknowledge success. Any other value or a timeout
        is treated as failure.
      • For measurement (request_id=0x03): device returns 9 bytes:
            [0..3] float32 tilt (LE)
            [4..7] float32 pan  (LE)
            [8]    CRC-8/SMBUS over bytes [0..7]

    I/O behavior and errors:
      • Methods raise RuntimeError if the serial port is closed, a write is
        short, a read times out, or the CRC check fails (where applicable).
      • Methods that expect a 1-byte ACK return bool (True on 0x00).

    Usage pattern:
        with GimbalSerial("/dev/ttyUSB0", 115200, 0.5) as dev:
            dev.arm_led(True)
            dev.status_led(False)
            ok = dev.move_deg(12.5, 3.25)
            tilt, pan = dev.measure_deg()
    """

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.5):
        """
        Open the serial port.

        Args:
          port: e.g. "/dev/ttyUSB0", "/dev/ttyACM0".
          baudrate: serial bit rate (default 115200).
          timeout: read timeout in seconds (default 0.5).
        """
        self.ser = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)

    def close(self) -> None:
        """Close the serial port if open."""
        if self.ser and self.ser.is_open:
            self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    # ── CRC implementation ─────────────────────────────────────────────────────
    @staticmethod
    def _crc8_smbus(data: bytes) -> int:
        """Compute CRC-8/SMBUS over the provided bytes (see class doc)."""
        crc = 0x00
        poly = 0x07
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 0x80:
                    crc = ((crc << 1) & 0xFF) ^ poly
                else:
                    crc = (crc << 1) & 0xFF
        return crc

    def _read_exact(self, n: int) -> Optional[bytes]:
        """Read exactly n bytes or return None on timeout/short read."""
        buf = bytearray()
        while len(buf) < n:
            chunk = self.ser.read(n - len(buf))
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)

    # ── Packet construction ────────────────────────────────────────────────────
    def create_request_data(self, request_id: int, payload: bytes) -> bytes:
        """
        Construct a request packet with the class's standard framing.

        Fields (by offset):
          [0]  uint8  CRC-8/SMBUS over bytes [1..]
          [1]  uint8  request_id
          [2..] bytes payload (opaque, command-specific)

        Args:
          request_id: command identifier (0..255). Known values:
            0x00=arm_led, 0x01=status_led, 0x02=move_deg, 0x03=measure_deg
          payload: command-specific bytes. Can be empty (b"").

        Returns:
          bytes ready to send via serial.write().

        Raises:
          TypeError: if payload is not bytes-like.
        """
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("payload must be bytes-like")
        data = bytearray(2 + len(payload))
        data[0] = 0x00  # placeholder until CRC calculated
        data[1] = request_id & 0xFF
        if payload:
            data[2:] = payload
        # CRC over [1..end]
        data[0] = self._crc8_smbus(bytes(data[1:]))
        return bytes(data)

    def _send_simple(self, request_id: int, payload: bytes) -> bool:
        """
        Send a request and expect a 1-byte 0x00 ACK.

        Request format: see create_request_data().
        Response format: one byte, 0x00 indicates success.

        Returns:
          True if exactly one byte 0x00 is received. False otherwise.
        """
        packet = self.create_request_data(request_id, payload)
        written = self.ser.write(packet)
        if written != len(packet):
            return False
        resp = self._read_exact(1)
        return resp == b"\x00"

    # ── Commands ───────────────────────────────────────────────────────────────
    def arm_led(self, state: bool) -> bool:
        """
        Set the ARM indication LED.

        request_id: 0x00
        payload:    [2] uint8 state, 1 for True, 0 for False
        request:    [0]=CRC([1..2]), [1]=0x00, [2]=state
        response:   1 byte 0x00 ACK on success

        Returns:
          True on ACK 0x00, False on NACK/timeout/short write.

        Raises:
          RuntimeError if the serial port is not open.
        """
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial port is not open")
        payload = bytes([1 if state else 0])
        return self._send_simple(0x00, payload)

    def status_led(self, state: bool) -> bool:
        """
        Set the STATUS indication LED.

        request_id: 0x01
        payload:    [2] uint8 state, 1 for True, 0 for False
        request:    [0]=CRC([1..2]), [1]=0x01, [2]=state
        response:   1 byte 0x00 ACK on success

        Returns:
          True on ACK 0x00, False on NACK/timeout/short write.

        Raises:
          RuntimeError if the serial port is not open.
        """
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial port is not open")
        payload = bytes([1 if state else 0])
        return self._send_simple(0x01, payload)

    def move_deg(self, tilt: float, pan: float) -> bool:
        """
        Command the device to move to the specified tilt/pan angles (degrees).

        request_id: 0x02
        payload:    [2..5] float32 tilt (LE)
                    [6..9] float32 pan  (LE)
        packet len: 10 bytes total
        request:    [0]=CRC([1..9]), [1]=0x02, [2..5]=tilt, [6..9]=pan
        response:   1 byte 0x00 ACK on success

        Returns:
          True on ACK 0x00, False on NACK/timeout/short write.

        Raises:
          RuntimeError if the serial port is not open.
        """
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial port is not open")
        payload = struct.pack("<ff", float(tilt), float(pan))
        return self._send_simple(0x02, payload)

    def measure_deg(self) -> Tuple[float, float]:
        """
        Request current tilt and pan angles from the device.

        request_id: 0x03
        payload:    none (empty)
        request:    [0]=CRC([1]), [1]=0x03

        response (9 bytes):
          [0..3] float32 tilt (LE)
          [4..7] float32 pan  (LE)
          [8]    uint8  CRC-8/SMBUS over bytes [0..7]

        Returns:
          (tilt_deg, pan_deg) as floats.

        Raises:
          RuntimeError on port closed, short write, timeout, or CRC mismatch.
        """
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial port is not open")
        packet = self.create_request_data(0x03, b"")
        written = self.ser.write(packet)
        if written != len(packet):
            raise RuntimeError("Short write for measure_deg request")
        resp = self._read_exact(9)
        if resp is None or len(resp) != 9:
            raise RuntimeError("Timeout or short read on measure_deg response")
        crc_expected = self._crc8_smbus(resp[:8])
        crc_received = resp[8]
        if crc_expected != crc_received:
            raise RuntimeError(
                f"CRC mismatch: got 0x{crc_received:02X}, expected 0x{crc_expected:02X}"
            )
        tilt = struct.unpack("<f", resp[0:4])[0]
        pan = struct.unpack("<f", resp[4:8])[0]
        return tilt, pan

if __name__ == "__main__":
    # gimbal = GimbalSerial(port="/dev/ttyTHS1", baudrate=115200, timeout=0.5)
    with GimbalSerial(port="/dev/ttyTHS1", baudrate=115200, timeout=0.5) as dev:
        # 先把灯关了
        dev.arm_led(True); dev.status_led(True)
        dev.move_deg(0, 0)