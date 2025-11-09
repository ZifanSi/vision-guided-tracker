import React from "react";
import TwoByTwoGrid from "../layouts/TwoByTwoGrid";
import GimbalPad from "../components/GimbalPad";
import GimbalStatus from "../components/GimbalStatus";
import VideoPane from "../components/VideoPane";

export default function ControllerPage({ useGimbalHook }) {
  const { mode, busy, angles, lastError, onCommand } = useGimbalHook();
  return (
    <TwoByTwoGrid
      a={<VideoPane />}
      b={<GimbalPad mode={mode} busy={busy} onCommand={onCommand} />}
      c={<GimbalStatus mode={mode} angles={angles} lastError={lastError} busy={busy} />}
      d={<div style={{ padding:12, opacity:.85 }}>Logs/telemetry here</div>}
    />
  );
}
