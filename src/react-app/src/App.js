import React from "react";
import TwoByTwoGrid from "./layouts/TwoByTwoGrid";

const Box = ({ children }) => (
  <div className="blank" style={{ display: "grid", placeItems: "center", minHeight: 80 }}>
    {children}
  </div>
);

export default function App() {
  return (
    <div className="app">
      <TwoByTwoGrid
        topLeft={<Box>TOP LEFT</Box>}
        topRight={<Box>TOP RIGHT</Box>}
        bottomLeft={<Box>BOTTOM LEFT</Box>}
        bottomRight={<Box>BOTTOM RIGHT</Box>}
      />
    </div>
  );
}
