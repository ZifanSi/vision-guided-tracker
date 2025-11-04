import React, { useState, useEffect } from "react";
import "../styles/gimbalpad.css";

export default function GimbalPad({ busy = false, onCommand, mode }) {
  const [active, setActive] = useState(null); // "manual" | "auto" | null

  useEffect(() => {
    if (!mode) return;
    setActive(mode); // mode is "manual" or "auto"
  }, [mode]);

  async function handle(cmd) {
    if (busy) return;
    const prev = active;

    // only optimistic-toggle for mode commands
    if (cmd === "manual" || cmd === "auto") setActive(cmd);

    try {
      await onCommand?.(cmd);
    } catch {
      setActive(prev);
    }
  }

  const padDisabled = busy || active !== "manual"; // optional UX

  return (
    <div className="dpad">
      <div className="keys">
        <button
        className="pill"
        data-role="manual"
        disabled={busy}
        onClick={() => handle("manual")}
        aria-pressed={active === "manual"}
        >
        MANUAL
        </button>

        <button
        className="pill"
        data-role="auto"
        disabled={busy}
        onClick={() => handle("auto")}
        aria-pressed={active === "auto"}
        >
        AUTO
        </button>
      </div>

      <div className="dpad__pad" role="group" aria-label="Gimbal control pad">
        <button
          className="dpad__btn up"
          disabled={padDisabled}
          onClick={() => handle("up")}
          aria-label="Up"
        >
          ▲
        </button>
        <button
          className="dpad__btn down"
          disabled={padDisabled}
          onClick={() => handle("down")}
          aria-label="Down"
        >
          ▼
        </button>
        <button
          className="dpad__btn left"
          disabled={padDisabled}
          onClick={() => handle("left")}
          aria-label="Left"
        >
          ◀
        </button>
        <button
          className="dpad__btn right"
          disabled={padDisabled}
          onClick={() => handle("right")}
          aria-label="Right"
        >
          ▶
        </button>
      </div>
    </div>
  );
}
