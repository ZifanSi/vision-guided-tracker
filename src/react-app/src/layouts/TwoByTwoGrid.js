import React from "react";

export default function TwoByTwoGrid({ topLeft, topRight, bottomLeft, bottomRight }) {
  return (
    <div className="container">{/* 12-col grid from your CSS */}
      <div className="grid-col-8">{topLeft}</div>
      <div className="grid-col-4">{topRight}</div>
      <div className="grid-col-8">{bottomLeft}</div>
      <div className="grid-col-4">{bottomRight}</div>
    </div>
  );
}
