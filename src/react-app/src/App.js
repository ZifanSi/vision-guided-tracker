import React from "react";
import TwoByTwoGrid from "./layouts/TwoByTwoGrid";
import VideoPane from "./components/VideoPane";
import GimbalPad from "./components/GimbalPad";
import GimbalStatus from "./components/GimbalStatus";
import { useGimbal } from "./lib/gimbalClient";

const Box = ({ children }) => (
  <div className="blank" style={{ display: "grid", placeItems: "center", minHeight: 80 }}>
    {children}
  </div>
);

export default function App() {
  const { mode, angles, busy, lastError, onCommand } = useGimbal({ pollMs: 1000 });

  return (
    <div className="app">
      <TwoByTwoGrid
        topLeft={<VideoPane />}
        topRight={<GimbalStatus angles={angles} lastError={lastError} />}
        bottomLeft={<Box>BOTTOM LEFT</Box>}
        bottomRight={<GimbalPad busy={busy} mode={mode} onCommand={onCommand} />}
      />
    </div>
  );
}
