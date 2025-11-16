import { Route, Routes } from "react-router-dom";


import RecordingsPage from "@/pages/recordings";
import ControlPage from "./pages/control";

function App() {
  return (
    <Routes>
      <Route element={<ControlPage />} path="/" />
      <Route element={<RecordingsPage />} path="/recordings" />
    </Routes>
  );
}

export default App;
