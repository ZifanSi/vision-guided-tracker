import React from "react";
import { NavLink } from "react-router-dom";
import redImage from "../components/red.png";

export default function NavBar() {
  const link = ({ isActive }) =>
    "nav__link" + (isActive ? " nav__link--active" : "");
  return (
    <nav className="nav">
      <div className="nav__brand"><img src={redImage} alt="Camera preview" className="nav__brandImg" /></div>
      <div className="nav__links">
        <NavLink to="/controller" className={link}>Controller</NavLink>
        <NavLink to="/videos" className={link}>Videos</NavLink>
      </div>
    </nav>
  );
}
