import React from "react";
import VideoPane from "../components/VideoPane";

export default function VideosPage() {
  return (
    <div className="container" style={{ padding:16 }}>
      <h2 style={{ marginTop:0 }}>Videos</h2>
      <VideoPane />
      {/* Add more VideoPane instances or a gallery later */}
    </div>
  );
}
