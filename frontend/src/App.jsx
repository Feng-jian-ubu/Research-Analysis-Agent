import { Navigate, Route, Routes } from "react-router-dom";

import UploadPage from "./pages/UploadPage.jsx";
import AnalysisPage from "./pages/AnalysisPage.jsx";
import ResultPage from "./pages/ResultPage.jsx";

function App() {
  return (
    <Routes>
      <Route path="/" element={<UploadPage />} />
      <Route path="/analysis/:fileId" element={<AnalysisPage />} />
      <Route path="/result/:taskId" element={<ResultPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;