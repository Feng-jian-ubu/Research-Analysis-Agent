import { useNavigate } from "react-router-dom";

import Header from "../components/layout/Header.jsx";
import StepIndicator from "../components/layout/StepIndicator.jsx";
import FileUploader from "../components/FileUploader.jsx";

function UploadPage() {
  const navigate = useNavigate();

  const handleUploadSuccess = (fileId) => {
    navigate(`/analysis/${fileId}`);
  };

  return (
    <div className="app">
      <Header />

      <main className="page-container">
        <StepIndicator currentStep={1} />

        <section className="page-heading">
          <p className="page-eyebrow">STEP 01</p>
          <h1>上传数据集</h1>
          <p>
            上传 CSV 或 Excel 文件，系统将自动读取数据并生成基础数据画像。
          </p>
        </section>

        <FileUploader onUploadSuccess={handleUploadSuccess} />
      </main>
    </div>
  );
}

export default UploadPage;