import React from "react";
import "../styles/TwoByTwoGrid.css";

export default function TwoByTwoGrid({ topLeft, topRight, bottomLeft, bottomRight }) {
  return (
    <div className="twoByTwoGrid">
      <div className="cell">{topLeft}</div>
      <div className="cell">{topRight}</div>
      <div className="cell">{bottomLeft}</div>
      <div className="cell">{bottomRight}</div>
    </div>
  );
}
