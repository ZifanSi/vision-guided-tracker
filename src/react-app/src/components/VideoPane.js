import React from "react";

export default function VideoPane({ className = "" }) {
  return (
    <div className={`live ${className}`}>
      {/* Simple placeholder frame (16:9) matching theme */}
      <div className="video" />
    </div>
  );
}
