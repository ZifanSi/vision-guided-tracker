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
    <BrowserRouter>
      <div className="app">
        <NavBar />
        <div style={{ width: "100%", flex: 1 }}>
          <Routes>
            <Route path="/controller" element={<ControllerPage />} />
            <Route path="/videos" element={<VideosPage />} />
            <Route path="*" element={<Navigate to="/controller" replace />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}
