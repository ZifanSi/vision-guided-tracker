// src/react-app/src/components/VideoPane.js
import React from "react";
import redImage from "../components/red.png"; // adjust path if needed
import "../styles/VideoPane.css";

export default function VideoPane() {
  return (
    <div className="videoPane">
        Preview video here
      {/* <img src={redImage} alt="Camera preview" className="videoPaneImg" /> */}
    </div>
  );
}
