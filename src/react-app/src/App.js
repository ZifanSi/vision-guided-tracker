import React, { useState, useCallback } from "react";
import TwoByTwoGrid from "./layouts/TwoByTwoGrid";
import VideoPane from "./components/VideoPane";
import GimbalPad from "./components/GimbalPad";
import GimbalStatus from "./components/GimbalStatus";
import SensitivityControl from "./components/SensitivityControl";
import ZoomControl from "./components/ZoomControl";
import { useGimbal } from "./lib/gimbalClient";

const Box = ({ children }) => (
  <div className="blank" style={{ display: "grid", placeItems: "center", minHeight: 80 }}>
    {children}
  </div>
);

export default function App() {
  // use the hook, but grab arm/disarm/nudge so we can apply custom step
  const { mode, angles, busy, lastError, arm, disarm, nudge } = useGimbal({ pollMs: 1000 });

  // frontend-only UI state
  const [stepDeg, setStepDeg] = useState(0.5); // sensitivity for nudges (degrees per tap)
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
    <div className="app">
      <TwoByTwoGrid
        topLeft={<VideoPane /* zoom={zoom} // pass to VideoPane when implemented */ />}
        topRight={<GimbalStatus angles={angles} lastError={lastError} />}
        bottomLeft={
          <div style={{ display: "grid", gap: 12 }}>
            <SensitivityControl value={stepDeg} onChange={setStepDeg} />
            <ZoomControl value={zoom} onChange={setZoom} />
          </div>
        }
        bottomRight={<GimbalPad busy={busy} mode={mode} onCommand={onCommand} />}
      />
    </div>
  );
}
