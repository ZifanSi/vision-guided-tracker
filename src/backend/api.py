# src/backend/api.py
# pip install flask flask-cors pyserial
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional, Dict
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading, queue, logging, os, time, subprocess, sys
from pathlib import Path

# ====== 尝试导入真实硬件（串口） ======
try:
    from Gimbal import GimbalSerial  # 与本文件同目录的 Gimbal.py
except Exception:
    GimbalSerial = None  # 导入失败时稍后回退到 Fake

# 行为开关（保持你现有 env 变量）
ACK_STRICT = os.getenv("GIMBAL_ACK_STRICT", "1") == "1"
PORT       = os.getenv("GIMBAL_PORT", "/dev/ttyTHS1")
BAUD       = int(os.getenv("GIMBAL_BAUD", "115200"))
TIMEOUT    = float(os.getenv("GIMBAL_TIMEOUT", "0.5"))
# 后台量角频率上限（防止疯狂测量），单位秒
MEASURE_COOLDOWN = float(os.getenv("GIMBAL_MEASURE_COOLDOWN", "0.08"))  # 80ms

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
            logging.info(f"[gimbal/Fake] move_to -> az={self._az:.2f} el={self._el:.2f}")

    def nudge(self, direction: Literal["up","down","left","right"], step_deg: float) -> None:
        with self._lock:
            az, el = self._az, self._el
            if direction == "left":     az -= step_deg
            elif direction == "right":  az += step_deg
            elif direction == "up":       el += step_deg
            elif direction == "down":     el -= step_deg
            self._az, self._el = self._clamp(az, el)
            logging.info(f"[gimbal/Fake] nudge/{direction} -> az={self._az:.2f} el={self._el:.2f} (step={step_deg})")

    def angles(self) -> tuple[float, float]:
        with self._lock:
            return self._az, self._el

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

        # 角度缓存
        self._el, self._az = 0.0, 0.0
        try:
            tilt, pan = self.dev.measure_deg()
            self._el, self._az = float(tilt), float(pan)
        except Exception:
            pass

        # 异步量角控制
        self._measure_guard = threading.Lock()
        self._measure_pending = False
        self._last_measure_ts = 0.0

    def _clamp(self, az: float, el: float) -> tuple[float, float]:
        az = max(self.AZ_MIN, min(self.AZ_MAX, float(az)))
        el = max(self.EL_MIN, min(self.EL_MAX, float(el)))
        return az, el

    # —— 移动命令仅发指令 + 更新缓存；不阻塞等量角 ——
    def move_to(self, az: float, el: float) -> None:
        with self._lock:
            az, el = self._clamp(az, el)
            ok = self.dev.move_deg(el, az)   # (tilt=el, pan=az)
            if ACK_STRICT and not ok:
                raise RuntimeError("move_deg NACK/timeout")
            self._az, self._el = az, el
            logging.info(f"[gimbal] move_to cmd -> az={az:.2f} el={el:.2f}")
            self._kick_measure_async("move_to", az, el)

    def nudge(self, direction: Literal["up","down","left","right"], step_deg: float) -> None:
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
            logging.info(f"[gimbal] nudge/{direction} cmd -> az={az:.2f} el={el:.2f} (step={step_deg})")
            self._kick_measure_async(f"nudge/{direction}", az, el)

    # —— /api/status 不做串口 I/O，只回缓存 ——
    def angles(self) -> tuple[float, float]:
        with self._lock:
            return self._az, self._el

    # —— 一次性“后台量角”，并做冷却去抖，避免高频争用串口 ——
    def _kick_measure_async(self, tag: str, az_cmd: float, el_cmd: float):
        now = time.time()
        if (now - self._last_measure_ts) < MEASURE_COOLDOWN:
            return
        # 避免并发启动多个测量
        with self._measure_guard:
            if self._measure_pending:
                return
            self._measure_pending = True

        def worker():
            try:
                with self._lock:
                    try:
                        tilt, pan = self.dev.measure_deg()
                        self._el, self._az = float(tilt), float(pan)
                        logging.info(
                            f"[gimbal] {tag} measured -> az={self._az:.2f} el={self._el:.2f} "
                            f"(cmd az={az_cmd:.2f} el={el_cmd:.2f})"
                        )
                    except Exception as e:
                        # 测量失败不阻塞主流程，留缓存
                        logging.warning(
                            f"[gimbal] {tag} measure failed, keep cache "
                            f"(cmd az={az_cmd:.2f}, el={el_cmd:.2f}): {e}"
                        )
            finally:
                self._last_measure_ts = time.time()
                with self._measure_guard:
                    self._measure_pending = False

        threading.Thread(target=worker, daemon=True).start()

    def refresh(self) -> None:
        # 供需要时主动刷新；当前实现不在 /api/status 里使用
        self._kick_measure_async("refresh", self._az, self._el)


def build_hw():
    """
    优先尝试真实串口；失败自动回退 Fake。
    环境变量：
      GIMBAL_PORT=/dev/ttyTHS1 或 /dev/ttyUSB0
      GIMBAL_BAUD=115200
      GIMBAL_TIMEOUT=0.5
      GIMBAL_ACK_STRICT=0/1
    """
    try:
        logging.info(
            f"[gimbal] init real device: port={PORT} baud={BAUD} timeout={TIMEOUT} ack_strict={ACK_STRICT}"
        )
        return GimbalHardwareAdapter(PORT, BAUD, TIMEOUT)
    except Exception as e:
        logging.exception(f"[gimbal] init real device failed, fallback to Fake: {e}")
        return FakeHardwareAdapter()

# ========================= state & controller =========================
@dataclass
class State:
    mode: Literal["manual", "auto"] = "manual"
    last_error: Optional[str] = None


@dataclass(frozen=True)
class Command:
    kind: Literal["SET_MODE", "MOVE"]
    payload: Dict[str, object] = field(default_factory=dict)


class Controller(threading.Thread):
    def __init__(
        self,
        hw: FakeHardwareAdapter | GimbalHardwareAdapter,
        st: State,
        q: "queue.Queue[Command]",
    ) -> None:
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
                    if direction not in ("up", "down", "left", "right"):
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

# ========================= YOLO tracker 控制 =========================
BASE_DIR = Path(__file__).resolve().parent    # .../src
# 你的脚本：src/cv/yolo_v4l2_display.py
TRACKER_SCRIPT = BASE_DIR / "cv" / "yolo_move_r.py"

tracker_proc: subprocess.Popen | None = None


def _tracker_running() -> bool:
    return tracker_proc is not None and tracker_proc.poll() is None

# ========================= Flask =========================
app = Flask(__name__)
CORS(app)  # 开发期放开；生产建议收紧到你的前端域名
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)

HW = build_hw()
STATE = State()
Q: "queue.Queue[Command]" = queue.Queue(maxsize=256)
Controller(HW, STATE, Q).start()


def ok(**extra):
    az, el = HW.angles()
    body = {
        "ok": True,
        "mode": STATE.mode,
        "angle": {"az": az, "el": el},
        "tracking": _tracker_running(),
    }
    if STATE.last_error:
        body["last_error"] = STATE.last_error
    body.update(extra)
    return jsonify(body), 200


def bad_request(msg: str):
    return jsonify({"ok": False, "error": msg}), 400


@app.get("/api/status")
def status():
    # 只读缓存，不做串口 I/O
    return ok()


@app.post("/api/mode")
def set_mode():
    data = request.get_json(silent=True) or {}
    mode = request.args.get("mode") or data.get("mode")
    if mode not in ("manual", "auto"):
        return bad_request("mode must be 'manual' or 'auto'")
    Q.put(Command("SET_MODE", {"mode": mode}))
    STATE.mode = mode
    return ok()


@app.post("/api/move")
def move():
    data = request.get_json(silent=True) or {}
    direction = data.get("direction")
    if direction not in ("up", "down", "left", "right"):
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
    if direction not in ("up", "down", "left", "right"):
        return bad_request("direction must be up/down/left/right")
    step = float(request.args.get("step", "0.5"))
    Q.put(Command("MOVE", {"direction": direction, "step": step}))
    return ok(requested={"direction": direction, "step": step})

# ===== 起 / 停 YOLO 跟踪脚本 =====
@app.post("/api/track/start")
def track_start():
    """启动 YOLO + gimbal 自动跟踪脚本"""
    global tracker_proc

    if _tracker_running():
        # 已经在跑了，直接返回当前状态
        return ok(tracker_started=False)

    try:
        # 确保脚本能 import src.backend.Gimbal
        tracker_env = os.environ.copy()
        project_root = BASE_DIR.parent          # .../  (src 的上一级)
        tracker_env["PYTHONPATH"] = (
            str(project_root)
            + os.pathsep
            + tracker_env.get("PYTHONPATH", "")
        )

        logging.info(f"[track] starting tracker: {TRACKER_SCRIPT}")
        tracker_proc = subprocess.Popen(
            [sys.executable, str(TRACKER_SCRIPT)],
            cwd=str(project_root),
            env=tracker_env,
        )
        # 同时切到 auto 模式（禁用手动摇杆）
        Q.put(Command("SET_MODE", {"mode": "auto"}))
        STATE.mode = "auto"
        return ok(tracker_started=True, pid=tracker_proc.pid)
    except Exception as e:
        logging.exception("track_start failed")
        STATE.last_error = f"track_start failed: {e}"
        return bad_request(f"track_start failed: {e}")


@app.post("/api/track/stop")
def track_stop():
    """停止 YOLO + gimbal 自动跟踪脚本"""
    global tracker_proc

    if _tracker_running():
        logging.info(f"[track] stopping tracker pid={tracker_proc.pid}")
        tracker_proc.terminate()
        try:
            tracker_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            tracker_proc.kill()

    tracker_proc = None

    # 切回 manual 模式（允许手动摇杆）
    Q.put(Command("SET_MODE", {"mode": "manual"}))
    STATE.mode = "manual"
    return ok(tracker_stopped=True)


@app.errorhandler(404)
def _404(_):
    return jsonify({"ok": False, "error": "not found"}), 404


@app.errorhandler(405)
def _405(_):
    return jsonify({"ok": False, "error": "method not allowed"}), 405


if __name__ == "__main__":
    # 本地单机调试；部署用 server.py 以 0.0.0.0 启动
    app.run(host="127.0.0.1", port=5000, debug=True)
