// Tiny API + React hook in one place

import { useCallback, useEffect, useRef, useState } from "react";

/** Base URL for Flask (override with Vite env) */
const BASE = (process?.env?.REACT_APP_API_BASE ?? import.meta?.env?.VITE_API_BASE ??"http://127.0.0.1:5000");

/* --------------------- raw API calls --------------------- */
async function getStatus() {
  const r = await fetch(`${BASE}/api/status`);
  if (!r.ok) throw new Error(`status ${r.status}`);
  return r.json(); // { ok, mode, angle:{az,el}, last_error? }
}

async function setMode(mode /* "manual" | "auto" */) {
  const r = await fetch(`${BASE}/api/mode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  if (!r.ok) throw new Error(`setMode ${r.status}`);
  return r.json();
}

async function move(direction /* "up"|"down"|"left"|"right" */, step = 0.5) {
  const r = await fetch(`${BASE}/api/move/${direction}?step=${encodeURIComponent(step)}`, {
    method: "POST",
  });
  if (!r.ok) throw new Error(`move ${r.status}`);
  return r.json();
}

/* --------------------- React hook --------------------- */
/**
 * useGimbal manages mode/angles/busy and exposes arm/disarm/nudge + onCommand
 */
export function useGimbal({ pollMs = 1000 } = {}) {
  const [mode, setModeState] = useState/** @type {("manual"|"auto"|undefined)} */();
  const [angles, setAngles] = useState({ az: 0, el: 0 });
  const [busy, setBusy] = useState(false);
  const [lastError, setLastError] = useState(null);
  const stopRef = useRef(false);

  // Poll backend for truth (mode + angles)
  useEffect(() => {
    stopRef.current = false;

    const tick = async () => {
      try {
        const s = await getStatus();
        setModeState(s.mode);
        if (s.angle) setAngles(s.angle);
        setLastError(s.last_error ?? null);
      } catch (e) {
        // optional: surface network errors
        setLastError(e instanceof Error ? e.message : String(e));
      }
      if (!stopRef.current) setTimeout(tick, pollMs);
    };

    tick();
    return () => {
      stopRef.current = true;
    };
  }, [pollMs]);

  const arm = useCallback(async () => {
    setBusy(true);
    try {
      const s = await setMode("manual");
      setModeState(s.mode);
      setLastError(s.last_error ?? null);
    } finally {
      setBusy(false);
    }
  }, []);

  const disarm = useCallback(async () => {
    setBusy(true);
    try {
      const s = await setMode("auto");
      setModeState(s.mode);
      setLastError(s.last_error ?? null);
    } finally {
      setBusy(false);
    }
  }, []);

  const nudge = useCallback(async (direction, step = 0.5) => {
    setBusy(true);
    try {
      const s = await move(direction, step);
      // angles will refresh on next poll; s may include angle too
      if (s.angle) setAngles(s.angle);
      setLastError(s.last_error ?? null);
    } finally {
      setBusy(false);
    }
  }, []);

  /** Drop-in handler for GimbalPad's onCommand prop */
  const onCommand = useCallback(
    (cmd) => {
      if (cmd === "arm") return arm();
      if (cmd === "disarm") return disarm();
      // up/down/left/right
      return nudge(cmd, 0.5);
    },
    [arm, disarm, nudge]
  );

  return { mode, angles, busy, lastError, arm, disarm, nudge, onCommand };
}
