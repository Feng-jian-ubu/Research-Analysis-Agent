import { useRef, useState } from "react";

import { uploadDataset } from "../api/client.js";

const allowedExtensions = [".csv", ".xlsx", ".xls"];
const maxFileSize = 20 * 1024 * 1024;

function FileUploader({ onUploadSuccess }) {
  const inputRef = useRef(null);

  const [selectedFile, setSelectedFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState("");

  const validateFile = (file) => {
    if (!file) {
      return "请选择文件。";
    }

    const fileName = file.name.toLowerCase();
    const isAllowed = allowedExtensions.some((extension) =>
      fileName.endsWith(extension)
    );

    if (!isAllowed) {
      return "仅支持 CSV、XLSX 和 XLS 文件。";
    }

    if (file.size > maxFileSize) {
      return "文件大小不能超过 20 MB。";
    }

    return "";
  };

  const handleFile = (file) => {
    const validationError = validateFile(file);

    if (validationError) {
      setSelectedFile(null);
      setError(validationError);
      return;
    }

    setSelectedFile(file);
    setError("");
  };

  const handleInputChange = (event) => {
    handleFile(event.target.files?.[0]);
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (event) => {
    event.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);

    handleFile(event.dataTransfer.files?.[0]);
  };

  const handleUpload = async () => {
    const validationError = validateFile(selectedFile);

    if (validationError) {
      setError(validationError);
      return;
    }

    try {
      setIsUploading(true);
      setError("");

      const data = await uploadDataset(selectedFile);
      const fileId = data.file_id ?? data.id;

      if (!fileId) {
        throw new Error("后端未返回 file_id。");
      }

      onUploadSuccess(fileId);
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ??
          requestError.message ??
          "文件上传失败，请稍后重试。"
      );
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <section className="upload-card">
      <div
        className={`drop-zone ${isDragging ? "drop-zone--active" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            inputRef.current?.click();
          }
        }}
      >
        <input
          ref={inputRef}
          className="file-input"
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={handleInputChange}
          disabled={isUploading}
        />

        <div className="upload-icon" aria-hidden="true">
          ↑
        </div>

        <h2>拖拽数据文件到此处</h2>
        <p>或者点击选择本地文件</p>
        <span>支持 CSV、XLSX、XLS，最大 20 MB</span>
      </div>

      {selectedFile && (
        <div className="selected-file">
          <div>
            <strong>{selectedFile.name}</strong>
            <span>{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</span>
          </div>

          <button
            type="button"
            className="text-button"
            onClick={() => {
              setSelectedFile(null);
              setError("");

              if (inputRef.current) {
                inputRef.current.value = "";
              }
            }}
            disabled={isUploading}
          >
            移除
          </button>
        </div>
      )}

      {error && <p className="form-error">{error}</p>}

      <button
        className="primary-button upload-button"
        type="button"
        onClick={handleUpload}
        disabled={!selectedFile || isUploading}
      >
        {isUploading ? "正在上传..." : "上传并继续"}
      </button>
    </section>
  );
}

export default FileUploader;