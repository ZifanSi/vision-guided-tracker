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

  // pad only works in MANUAL mode
  const padDisabled = busy || active !== "manual";

  return (
    <div className="dpad">
      {/* mode buttons */}
      <div className="keys">
        <button
          className="pill"
          data-role="manual"
          disabled={busy}
          onClick={() => handle("manual")}
          aria-pressed={active === "manual"}
        >
          IDLE
        </button>

        <button
          className="pill"
          data-role="auto"
          disabled={busy}
          onClick={() => handle("auto")}
          aria-pressed={active === "auto"}
        >
          ARMED
        </button>
      </div>

      {/* radial gimbal pad */}
      <div
        className="radial-pad"
        role="group"
        aria-label="Gimbal control pad"
      >
        <button
          className="slice up"
          disabled={padDisabled}
          onClick={() => handle("up")}
          aria-label="Up"
        >
        </button>
        <button
          className="slice right"
          disabled={padDisabled}
          onClick={() => handle("right")}
          aria-label="Right"
        />
        <button
          className="slice down"
          disabled={padDisabled}
          onClick={() => handle("down")}
          aria-label="Down"
        />
        <button
          className="slice left"
          disabled={padDisabled}
          onClick={() => handle("left")}
          aria-label="Left"
        />

        <div className="center" />
      </div>
    </div>
  );
}
