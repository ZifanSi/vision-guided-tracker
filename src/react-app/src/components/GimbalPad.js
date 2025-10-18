import React from "react";

/**
 * Props:
 *  - busy: boolean (disables buttons while sending)
 *  - onCommand: (cmd: "arm"|"disarm"|"up"|"down"|"left"|"right") => void|Promise<void>
 */
export default function GimbalPad({ busy, onCommand }) {
  return (
    <div className="dpad">
      <div className="keys">
        <button
          className="pill pill--arm"
          disabled={busy}
          onClick={() => onCommand?.("arm")}
        >
          ARM
        </button>
        <button
          className="pill"
          disabled={busy}
          onClick={() => onCommand?.("disarm")}
        >
          DISARM
        </button>
      </div>

      <div className="dpad__pad" role="group" aria-label="Gimbal control pad">
        <button
          className="dpad__btn up"
          disabled={busy}
          onClick={() => onCommand?.("up")}
          aria-label="Up"
        >
          ▲
        </button>
        <button
          className="dpad__btn down"
          disabled={busy}
          onClick={() => onCommand?.("down")}
          aria-label="Down"
        >
          ▼
        </button>
        <button
          className="dpad__btn left"
          disabled={busy}
          onClick={() => onCommand?.("left")}
          aria-label="Left"
        >
          ◀
        </button>
        <button
          className="dpad__btn right"
          disabled={busy}
          onClick={() => onCommand?.("right")}
          aria-label="Right"
        >
          ▶
        </button>
      </div>
    </div>
  );
}
