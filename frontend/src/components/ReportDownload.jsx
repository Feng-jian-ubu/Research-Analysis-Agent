import { useState } from "react";

import { downloadReport } from "../api/client.js";

function ReportDownload({ taskId, reportUrl }) {
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState("");

  const handleDownload = async () => {
    try {
      setIsDownloading(true);
      setError("");

      const reportBlob = await downloadReport(taskId, reportUrl);
      const objectUrl = URL.createObjectURL(reportBlob);
      const link = document.createElement("a");

      link.href = objectUrl;
      link.download = `analysis-report-${taskId}.md`;
      document.body.appendChild(link);
      link.click();
      link.remove();

      URL.revokeObjectURL(objectUrl);
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ??
          "报告下载失败，请稍后重试。"
      );
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <section className="report-download">
      <div>
        <p className="section-eyebrow">ANALYSIS REPORT</p>
        <h2>下载完整分析报告</h2>
        <p>报告包含数据概览、分析过程、统计结果、图表和分析结论。</p>
      </div>

      <button
        className="primary-button"
        type="button"
        onClick={handleDownload}
        disabled={isDownloading}
      >
        {isDownloading ? "正在下载..." : "下载 Markdown 报告"}
      </button>

      {error && <p className="form-error">{error}</p>}
    </section>
  );
}

export default ReportDownload;