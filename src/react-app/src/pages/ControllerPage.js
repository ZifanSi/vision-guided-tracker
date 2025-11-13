// src/react-app/src/pages/ControllerPage.js
import React, { useState, useCallback } from "react";
import TwoByTwoGrid from "../layouts/TwoByTwoGrid";
import VideoPane from "../components/VideoPane";
import GimbalPad from "../components/GimbalPad";
import GimbalStatus from "../components/GimbalStatus";
import SensitivityControl from "../components/SensitivityControl";
import ZoomControl from "../components/ZoomControl";
import { useGimbal } from "../lib/gimbalClient";

export default function ControllerPage() {
  const { mode, angles, busy, lastError, arm, disarm, nudge } =
    useGimbal({ pollMs: 1000 });

  const [stepDeg, setStepDeg] = useState(15);
  const [zoom, setZoom] = useState(1.0);

  const onCommand = useCallback(
    (cmd) => {
      if (cmd === "manual" || cmd === "arm") return arm();
      if (cmd === "auto" || cmd === "disarm") return disarm();
      if (["up", "down", "left", "right"].includes(cmd)) {
        return nudge(cmd, stepDeg);
      }
    },
    [arm, disarm, nudge, stepDeg]
  );

  return (
    <div className="grid-col-12">   {/* 👈 full-width content cell inside .container */}
      <TwoByTwoGrid
        topLeft={<VideoPane /* zoom={zoom} */ />}
        topRight={<GimbalStatus angles={angles} lastError={lastError} />}
        bottomLeft={
          <div style={{ display: "grid", gap: 12 }}>
            <SensitivityControl value={stepDeg} onChange={setStepDeg} />
            <ZoomControl value={zoom} onChange={setZoom} />
          </div>
        }
        bottomRight={
          <GimbalPad busy={busy} mode={mode} onCommand={onCommand} />
        }
      />
    </div>
  );
}
