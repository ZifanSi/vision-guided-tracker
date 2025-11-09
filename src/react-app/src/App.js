import React, { useEffect, useState, useCallback } from "react";
import "./styles/theme.css";
import "./styles/layout.css";

import NavBar from "./components/NavBar";
import ControllerPage from "./pages/ControllerPage";
import VideosPage from "./pages/VideosPage";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

/* -------- inline API (no gimbalClient) -------- */
const BASE = import.meta?.env?.VITE_API_BASE || "http://127.0.0.1:5000";

async function apiGetStatus() {
  const r = await fetch(`${BASE}/api/status`);
  if (!r.ok) throw new Error(`status ${r.status}`);
  return r.json();
}
async function apiSetMode(mode) {
  const r = await fetch(`${BASE}/api/mode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  if (!r.ok) throw new Error(`setMode ${r.status}`);
  return r.json();
}
async function apiMove(direction, step = 0.5) {
  const r = await fetch(`${BASE}/api/move`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ direction, step }),
  });
  if (!r.ok) throw new Error(`move ${r.status}`);
  return r.json();
}

/* -------- tiny inline hook -------- */
function useGimbalInline() {
  const [mode, setModeState] = useState/** @type {("manual"|"auto"|undefined)} */();
  const [angles, setAngles] = useState({ az: 0, el: 0 });
  const [busy, setBusy] = useState(false);
  const [lastError, setLastError] = useState(null);

  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const s = await apiGetStatus();
        setModeState(s.mode);
        if (s.angle) setAngles(s.angle);
        setLastError(s.last_error ?? null);
      } catch (e) {
        setLastError(e instanceof Error ? e.message : String(e));
      }
      if (!stop) setTimeout(tick, 1000);
    };
    tick();
    return () => { stop = true; };
  }, []);

  const onCommand = useCallback(async (cmd) => {
    if (busy) return;
    setBusy(true);
    try {
      if (cmd === "manual" || cmd === "auto") {
        const s = await apiSetMode(cmd);
        setModeState(s.mode);
        if (s.angle) setAngles(s.angle);
        setLastError(s.last_error ?? null);
        return;
      }
      const s = await apiMove(cmd, 0.5); // up/down/left/right
      if (s.angle) setAngles(s.angle);
      setLastError(s.last_error ?? null);
    } finally {
      setBusy(false);
    }
  }, [busy]);

  return { mode, angles, busy, lastError, onCommand };
}

/* -------- app with nav + routes; default = /controller -------- */
export default function App() {
  // use the hook, but grab arm/disarm/nudge so we can apply custom step
  const { mode, angles, busy, lastError, arm, disarm, nudge } = useGimbal({ pollMs: 1000 });

  // frontend-only UI state
  const [stepDeg, setStepDeg] = useState(15); // sensitivity for nudges (degrees per tap)
  const [zoom, setZoom] = useState(1.0);       // UI-only zoom level

  // map GimbalPad commands → hook functions, injecting stepDeg for movement
  const onCommand = useCallback(
    (cmd) => {
      if (cmd === "manual" || cmd === "arm") return arm();
      if (cmd === "auto"   || cmd === "disarm") return disarm();
      if (["up", "down", "left", "right"].includes(cmd)) {
        return nudge(cmd, stepDeg);
      }
    },
    [arm, disarm, nudge, stepDeg]
  );

  return (
    <BrowserRouter>
      <div className="app">
        <NavBar />
        <div className="container" style={{ width: "100%" }}>
          <Routes>
            <Route path="/controller" element={<ControllerPage useGimbalHook={useGimbalInline} />} />
            <Route path="/videos" element={<VideosPage />} />
            <Route path="*" element={<Navigate to="/controller" replace />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}
