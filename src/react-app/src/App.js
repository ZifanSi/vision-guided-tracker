import React, { useState } from "react";
import VideoPane from "./components/VideoPane";
import GimbalPad from "./components/GimbalPad";
import { sendCommand } from "./lib/api";

export default function App() {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handle(cmd) {
    if (busy) return;
    setBusy(true);
    setStatus(`Sending: ${cmd.toUpperCase()}…`);
    try {
      const { ok } = await sendCommand(cmd);
      if (!ok) throw new Error("Command failed");
      setStatus(`OK: ${cmd.toUpperCase()}`);
    } catch (e) {
      setStatus(`Error: ${e.message}`);
    } finally {
      setBusy(false);
      setTimeout(() => setStatus(null), 1200);
    }
  }

  return (
    <div className="app">
      <div className="container">
        {/* TOP-LEFT: Main camera only */}
        <VideoPane className="grid-col-8" />

        {/* TOP-RIGHT: Blank */}
        <div className="blank grid-col-4"><div className="spacer" /></div>

        {/* BOTTOM-LEFT: Blank */}
        <div className="blank grid-col-8"><div className="spacer" /></div>

        {/* BOTTOM-RIGHT: Gimbal/control pad */}
        <div className="card grid-col-4 padWrap">
          <GimbalPad busy={busy} onCommand={handle} />
        </div>
      </div>

      {status && <div className="status">{status}</div>}
    </div>
  );
}
