import React from "react";
import "./SliderMock.css";

export default function SensitivityControl({ value, onChange }) {
  return (
    <div className="sliderBlock">
      <div className="sliderTitle">Sensitivity</div>
      <div className="sliderRow">
        <input
          type="range"
          min={1}
          max={30}
          step={1}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="slider"
        />
        <div className="sliderValue">{value.toFixed(0)}°</div>
      </div>
      <div className="sliderTicks">
        {[1,5,10,15,20,25,30].map((n) => (
          <span key={n}>{n}°</span>
        ))}
      </div>
    </div>
  );
}
