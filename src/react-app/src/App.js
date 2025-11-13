// src/react-app/src/App.js

import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import "./styles/theme.css";
import "./styles/layout.css";

import NavBar from "./components/NavBar";
import ControllerPage from "./pages/ControllerPage";
import VideosPage from "./pages/VideosPage";

export default function App() {
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
