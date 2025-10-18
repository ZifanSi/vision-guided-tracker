// src/react-app/src/components/GimbalPad.js
import React, { useState, useEffect } from "react";

/**
 * Props:
 *  - busy: boolean
 *  - onCommand: (cmd: "arm"|"disarm"|"up"|"down"|"left"|"right") => Promise<void>|void
 *  - mode?: "manual" | "auto"    // optional controlled prop from backend status
 *
 * Behavior:
 *  - Click ARM -> ARM button turns orange; DISARM loses orange.
 *  - Click DISARM -> DISARM turns orange; ARM loses orange.
 *  - We optimistically set the highlight; if onCommand throws, we revert.
 */
export default function GimbalPad({ busy = false, onCommand, mode }) {
  // local selected state: "arm" | "disarm" | null
  const [active, setActive] = useState(null);

  // If parent passes `mode` from /api/status, keep UI in sync
  useEffect(() => {
    if (!mode) return;
    setActive(mode === "manual" ? "arm" : "disarm");
  }, [mode]);

  async function handle(cmd) {
    if (busy) return;
    const prev = active;

    // optimistic highlight for ARM/DISARM only
    if (cmd === "arm" || cmd === "disarm") setActive(cmd);

    try {
      await onCommand?.(cmd);
    } catch (e) {
      // revert highlight on error
      setActive(prev);
    }
  }

  return (
    <div className="dpad">
      {/* Top row: ARM / DISARM (highlight the selected one) */}
      <div className="keys">
        <button
          className={`pill ${active === "arm" ? "pill--active" : ""}`}
          disabled={busy}
          onClick={() => handle("arm")}
        >
          ARM
        </button>
        <button
          className={`pill ${active === "disarm" ? "pill--active" : ""}`}
          disabled={busy}
          onClick={() => handle("disarm")}
        >
          DISARM
        </button>
      </div>

      {/* Round control pad */}
      <div className="dpad__pad" role="group" aria-label="Gimbal control pad">
        <button
          className="dpad__btn up"
          disabled={busy}
          onClick={() => handle("up")}
          aria-label="Up"
        >
          ▲
        </button>
        <button
          className="dpad__btn down"
          disabled={busy}
          onClick={() => handle("down")}
          aria-label="Down"
        >
          ▼
        </button>
        <button
          className="dpad__btn left"
          disabled={busy}
          onClick={() => handle("left")}
          aria-label="Left"
        >
          ◀
        </button>
        <button
          className="dpad__btn right"
          disabled={busy}
          onClick={() => handle("right")}
          aria-label="Right"
        >
          ▶
        </button>
      </div>
    </div>
  );
}
