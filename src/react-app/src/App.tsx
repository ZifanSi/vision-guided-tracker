import { Route, Routes } from "react-router-dom";

import ControlPage from "./pages/control";

import RecordingsPage from "@/pages/recordings";

function App() {
  return (
    <Routes>
      <Route element={<ControlPage />} path="/" />
      <Route element={<RecordingsPage />} path="/recordings" />
    </Routes>
  );
}

export default App;
