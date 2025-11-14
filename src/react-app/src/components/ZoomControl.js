import React from "react";
import "./SliderMock.css";

export default function ZoomControl({ value, onChange }) {
  return (
    <div className="sliderBlock">
      <div className="sliderTitle">Zoom</div>
      <div className="sliderRow">
        <input
          type="range"
          min={1}
          max={10}
          step={1}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="slider"
        />
        <div className="sliderValue">{value}×</div>
      </div>
      <div className="sliderTicks">
        {[1,2,3,4,5,6,7,8,9,10].map((n) => (
          <span key={n}>{n}×</span>
        ))}
      </div>
    </div>
  );
}
