import React, { useState, useEffect } from "react";

export default function GimbalPad({ busy = false, onCommand, mode }) {
  const [active, setActive] = useState(null);

  useEffect(() => {
    if (!mode) return;
    setActive(mode === "manual" ? "arm" : "disarm");
  }, [mode]);

  async function handle(cmd) {
    if (busy) return;
    const prev = active;
    if (cmd === "arm" || "disarm") setActive(cmd);
    try {
      await onCommand?.(cmd);
    } catch {
      setActive(prev);
    }
  }

  return (
    <div className="dpad">
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
