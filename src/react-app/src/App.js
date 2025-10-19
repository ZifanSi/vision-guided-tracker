import React from "react";
import TwoByTwoGrid from "./layouts/TwoByTwoGrid";
import VideoPane from "./components/VideoPane";
import GimbalPad from "./components/GimbalPad";

const Box = ({ children }) => (
  <div className="blank" style={{ display: "grid", placeItems: "center", minHeight: 80 }}>
    {children}
  </div>
);

export default function App() {
  return (
    <div className="app">
      <TwoByTwoGrid
        topLeft={<VideoPane />}
        topRight={<Box>TOP RIGHT</Box>}
        bottomLeft={<Box>BOTTOM LEFT</Box>}
        bottomRight={<GimbalPad />}
      />
    </div>
  );
}
