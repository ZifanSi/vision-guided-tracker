# src/backend/api.py
# pip install flask flask-cors pyserial
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional, Dict
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading, queue, logging, os, time

# ====== 尝试导入真实硬件（串口） ======
try:
    from Gimbal import GimbalSerial  # 与本文件同目录的 Gimbal.py
except Exception:
    GimbalSerial = None  # 导入失败时稍后回退到 Fake

# 环境变量
ACK_STRICT = os.getenv("GIMBAL_ACK_STRICT", "1") == "1"         # 1=严格等待ACK
POLL_MS    = int(os.getenv("GIMBAL_POLL_MS", "120"))            # 后台量角周期（毫秒）
PORT       = os.getenv("GIMBAL_PORT", "/dev/ttyTHS1")
BAUD       = int(os.getenv("GIMBAL_BAUD", "115200"))
TIMEOUT    = float(os.getenv("GIMBAL_TIMEOUT", "0.5"))

# ========================= hardware adapters =========================
class FakeHardwareAdapter:
    """纯软件假设备（兜底）"""
    AZ_MIN, AZ_MAX = -180.0, 180.0
    EL_MIN, EL_MAX =  -45.0,  90.0

    def __init__(self) -> None:
        self._az = 0.0
        self._el = 0.0
        self._lock = threading.RLock()

    def _clamp(self, az: float, el: float) -> tuple[float, float]:
        az = max(self.AZ_MIN, min(self.AZ_MAX, az))
        el = max(self.EL_MIN, min(self.EL_MAX, el))
        return az, el

    def move_to(self, az: float, el: float) -> None:
        with self._lock:
            az, el = self._clamp(az, el)
            self._az, self._el = az, el
            logging.info(f"[Fake] move_to -> az={self._az:.2f} el={self._el:.2f}")

    def nudge(self, direction: Literal["up","down","left","right"], step_deg: float) -> None:
        with self._lock:
            az, el = self._az, self._el
            if direction == "left":     az -= step_deg
            elif direction == "right":  az += step_deg
            elif direction == "up":       el += step_deg
            elif direction == "down":     el -= step_deg
            self._az, self._el = self._clamp(az, el)
            logging.info(f"[Fake] nudge/{direction} -> az={self._az:.2f} el={self._el:.2f} (step={step_deg})")

    def angles(self) -> tuple[float, float]:
        with self._lock:
            return self._az, self._el

    # 供采样线程保持统一接口（Fake不需要真正量角）
    def refresh(self) -> None:
        return


class GimbalHardwareAdapter:
    """
    真实云台适配：UI 的 (az, el) ↔ 串口的 (pan, tilt)
    GimbalSerial.move_deg(tilt, pan) / measure_deg() -> (tilt, pan)
    """
    AZ_MIN, AZ_MAX = -180.0, 180.0
    EL_MIN, EL_MAX =  -45.0,  90.0

    def __init__(self, port: str, baud: int = 115200, timeout: float = 0.5):
        if GimbalSerial is None:
            raise RuntimeError("GimbalSerial not available")
        self._lock = threading.RLock()
        self.dev = GimbalSerial(port=port, baudrate=baud, timeout=timeout)
        # 初始化角度缓存（允许失败）
        try:
            tilt, pan = self.dev.measure_deg()  # (el, az)
            self._el, self._az = float(tilt), float(pan)
        except Exception:
            self._el, self._az = 0.0, 0.0

    def _clamp(self, az: float, el: float) -> tuple[float, float]:
        az = max(self.AZ_MIN, min(self.AZ_MAX, float(az)))
        el = max(self.EL_MIN, min(self.EL_MAX, float(el)))
        return az, el

    def move_to(self, az: float, el: float) -> None:
        # 仅发命令 + 乐观更新缓存，不同步量角（避免阻塞下一条命令）
        with self._lock:
            az, el = self._clamp(az, el)
            ok = self.dev.move_deg(el, az)   # (tilt=el, pan=az)
            if ACK_STRICT and not ok:
                raise RuntimeError("move_deg NACK/timeout")
            self._az, self._el = az, el
            logging.info(f"[HW] move_to cmd -> az={az:.2f} el={el:.2f}")

    def nudge(self, direction: Literal["up","down","left","right"], step_deg: float) -> None:
        # 同上，仅发命令 + 乐观更新
        with self._lock:
            az, el = self._az, self._el
            if direction == "left":     az -= step_deg
            elif direction == "right":  az += step_deg
            elif direction == "up":       el += step_deg
            elif direction == "down":     el -= step_deg
            az, el = self._clamp(az, el)
            ok = self.dev.move_deg(el, az)
            if ACK_STRICT and not ok:
                raise RuntimeError("move_deg NACK/timeout")
            self._az, self._el = az, el
            logging.info(f"[HW] nudge/{direction} cmd -> az={az:.2f} el={el:.2f} (step={step_deg})")

    def angles(self) -> tuple[float, float]:
        # 仅返回缓存，不阻塞
        with self._lock:
            return self._az, self._el

    def refresh(self) -> None:
        # 后台被动量角，更新缓存（失败静默）
        with self._lock:
            try:
                tilt, pan = self.dev.measure_deg()
                self._el, self._az = float(tilt), float(pan)
            except Exception:
                pass


# ========================= 后台采样线程 =========================
class AngleSampler(threading.Thread):
    def __init__(self, hw, interval_ms: int):
        super().__init__(daemon=True)
        self.hw = hw
        self.dt = max(10, int(interval_ms)) / 1000.0  # 最短10ms，防误配
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        # 周期性量角，更新缓存；不打印高频日志，避免刷屏
        while not self._stop:
            try:
                self.hw.refresh()
            finally:
                time.sleep(self.dt)


def build_hw():
    """
    优先尝试真实串口；失败自动回退 Fake。
    环境变量：
      GIMBAL_PORT=/dev/ttyTHS1 或 /dev/ttyUSB0
      GIMBAL_BAUD=115200
      GIMBAL_TIMEOUT=0.5
      GIMBAL_ACK_STRICT=0/1
      GIMBAL_POLL_MS=120
    """
    try:
        logging.info(f"[gimbal] init real device: port={PORT} baud={BAUD} timeout={TIMEOUT} ack_strict={ACK_STRICT}")
        return GimbalHardwareAdapter(PORT, BAUD, TIMEOUT)
    except Exception as e:
        logging.exception(f"[gimbal] init real device failed, fallback to Fake: {e}")
        return FakeHardwareAdapter()

# ========================= state & controller =========================
@dataclass
class State:
    mode: Literal["manual","auto"] = "manual"
    last_error: Optional[str] = None

@dataclass(frozen=True)
class Command:
    kind: Literal["SET_MODE","MOVE"]
    payload: Dict[str, object] = field(default_factory=dict)

class Controller(threading.Thread):
    def __init__(self, hw: FakeHardwareAdapter | GimbalHardwareAdapter,
                 st: State, q: "queue.Queue[Command]") -> None:
        super().__init__(daemon=True)
        self.hw, self.state, self.q = hw, st, q

    def run(self) -> None:
        while True:
            cmd = self.q.get()
            try:
                if cmd.kind == "SET_MODE":
                    mode = cmd.payload.get("mode")
                    if mode not in ("manual", "auto"):
                        raise ValueError("mode must be 'manual' or 'auto'")
                    self.state.mode = mode  # type: ignore[attr-defined]
                    logging.info(f"[gimbal] set_mode -> {mode}")

                elif cmd.kind == "MOVE":
                    if self.state.mode != "manual":
                        raise RuntimeError("movement is only allowed in MANUAL mode")
                    direction = cmd.payload.get("direction")
                    if direction not in ("up","down","left","right"):
                        raise ValueError("direction must be up/down/left/right")
                    step = float(cmd.payload.get("step", 0.5))
                    if step <= 0:
                        raise ValueError("step must be positive")
                    self.hw.nudge(direction, step)  # type: ignore[arg-type]

                self.state.last_error = None
            except Exception as e:
                logging.exception("Controller command failed: %s", e)
                self.state.last_error = str(e)
            finally:
                self.q.task_done()

# ========================= Flask =========================
app = Flask(__name__)
CORS(app)  # 开发期放开；生产建议收紧到你的前端域名
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

HW = build_hw()
STATE = State()
Q: "queue.Queue[Command]" = queue.Queue(maxsize=256)

Controller(HW, STATE, Q).start()
# 仅当是“真实硬件”时启动后台采样；Fake启动也无害
_sampler = AngleSampler(HW, POLL_MS)
_sampler.start()

def ok(**extra):
    az, el = HW.angles()
    body = {"ok": True, "mode": STATE.mode, "angle": {"az": az, "el": el}}
    if STATE.last_error:
        body["last_error"] = STATE.last_error
    body.update(extra)
    return jsonify(body), 200

def bad_request(msg: str):
    return jsonify({"ok": False, "error": msg}), 400

@app.get("/api/status")
def status():
    # 直接读缓存 -> 不阻塞串口
    return ok()

@app.post("/api/mode")
def set_mode():
    # 兼容 JSON 和查询串：/api/mode?mode=manual（可减少预检）
    data = request.get_json(silent=True) or {}
    mode = request.args.get("mode") or data.get("mode")
    if mode not in ("manual", "auto"):
        return bad_request("mode must be 'manual' or 'auto'")
    Q.put(Command("SET_MODE", {"mode": mode}))
    return ok()

@app.post("/api/move")
def move():
    data = request.get_json(silent=True) or {}
    direction = data.get("direction")
    if direction not in ("up","down","left","right"):
        return bad_request("direction must be up/down/left/right")
    step = data.get("step", 0.5)
    try:
        step = float(step)
    except Exception:
        return bad_request("step must be a number")
    if step <= 0:
        return bad_request("step must be positive")
    Q.put(Command("MOVE", {"direction": direction, "step": step}))
    return ok(requested={"direction": direction, "step": step})

@app.post("/api/move/<direction>")
def move_quick(direction: str):
    if direction not in ("up","down","left","right"):
        return bad_request("direction must be up/down/left/right")
    step = float(request.args.get("step", "0.5"))
    Q.put(Command("MOVE", {"direction": direction, "step": step}))
    return ok(requested={"direction": direction, "step": step})

@app.errorhandler(404)
def _404(_):
    return jsonify({"ok": False, "error": "not found"}), 404

@app.errorhandler(405)
def _405(_):
    return jsonify({"ok": False, "error": "method not allowed"}), 405

if __name__ == "__main__":
    # 本地单机调试；部署用 server.py 以 0.0.0.0 启动
    app.run(host="127.0.0.1", port=5000, debug=True)
