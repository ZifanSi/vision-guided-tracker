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
import math
import time

def tap_rhythm(
    dev: GimbalSerial,
    pattern,
    bpm: float = 120.0,
    center_tilt: float = 0.0,
    center_pan: float = 0.0,
    amp_deg: float = 0.6,
    tap_freq_hz: float = 6.0,
    axis: str = "tilt",
    accel_ramp_s: float = 0.08,
):
    """
    用小振幅+低频来“打节拍”。不产生音高，只表达时值（节奏）。

    pattern: 列表，元素是 (beats, pause_beats) 或 beats（单位=拍）
             例如：[1,1,2, 1,1,2] 或 [(1,0.5),(0.5,0.5),(2,1)]
             每个元素会按 tap_freq_hz 抖动指定时长，随后可选静止 pause。
    bpm:     速度；1 拍 = 60/bpm 秒
    axis:    'tilt' or 'pan' 选择在哪个轴上抖动
    """
    assert axis in ("tilt", "pan")
    sec_per_beat = 60.0 / bpm

    def clamp_angle(a):  # 保险：大角度中心位不被轻微漂走
        return max(min(a, 179.0), -179.0)

    center_tilt_c = clamp_angle(center_tilt)
    center_pan_c  = clamp_angle(center_pan)

    def one_burst(duration_s: float):
        # 先做个小的线性跃迁，避免“砸车”
        start = time.monotonic()
        end   = start + duration_s
        # 简单幅度包络（起止都淡入淡出）
        def envelope(t0, t1, t):
            # 0→1→0 的三角包络
            if t <= t0: return 0.0
            if t >= t1: return 0.0
            mid = (t0 + t1) * 0.5
            if t <= mid:
                return (t - t0) / (mid - t0 + 1e-6)
            else:
                return (t1 - t) / (t1 - mid + 1e-6)

        # 目标发送周期（别太快，免得把串口/控制环刷爆）
        send_dt = max(1.0 / (tap_freq_hz * 8.0), 0.01)  # ~每个周期取8个采样，至少10ms
        phase = 0.0
        while True:
            now = time.monotonic()
            if now >= end:
                break
            # 方波比正弦更“硬”，但正弦更温和；这里用正弦
            env = envelope(start, end, now)
            angle = amp_deg * env * math.sin(2 * math.pi * tap_freq_hz * (now - start) + phase)
            if axis == "tilt":
                dev.move_deg(center_tilt_c + angle, center_pan_c)
            else:
                dev.move_deg(center_tilt_c, center_pan_c + angle)
            time.sleep(send_dt)

        # 回到中心位
        dev.move_deg(center_tilt_c, center_pan_c)

    # 统一把 pattern 变成 (beats, pause_beats)
    norm = []
    for item in pattern:
        if isinstance(item, tuple):
            norm.append(item)
        else:
            norm.append((float(item), 0.0))

    for beats, pause_beats in norm:
        play_s  = max(0.0, float(beats) * sec_per_beat)
        pause_s = max(0.0, float(pause_beats) * sec_per_beat)
        # 起止加一个很短的淡入淡出，让机械更舒服
        burst_time = play_s
        if burst_time > 0:
            one_burst(burst_time)
        if pause_s > 0:
            time.sleep(pause_s)
if __name__ == "__main__":
    # gimbal = GimbalSerial(port="/dev/ttyTHS1", baudrate=115200, timeout=0.5)
    with GimbalSerial(port="/dev/ttyTHS1", baudrate=115200, timeout=0.5) as dev:
        # 先把灯关了
        dev.arm_led(True); dev.status_led(True)
        dev.move_deg(0, 0)
