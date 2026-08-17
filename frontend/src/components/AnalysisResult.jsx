import { useEffect, useState } from "react";

import { getAnalysisResult } from "../api/client.js";
import AnalysisPlan from "./AnalysisPlan.jsx";
import ChartViewer from "./ChartViewer.jsx";
import ReportDownload from "./ReportDownload.jsx";
import ResultTable from "./ResultTable.jsx";

const skillLabels = {
  data_cleaner: "数据清洗",
  descriptive: "描述性统计",
  correlation: "相关分析",
  t_test: "独立样本 t 检验",
  regression: "回归分析",
  figure_generator: "生成分析图表",
  report_generator: "生成分析报告",
};

function formatValue(value) {
  if (value === null || value === undefined) {
    return "—";
  }

  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
}

function summaryToRows(summary = {}) {
  return Object.entries(summary).map(([name, value]) => ({
    name,
    value: formatValue(value),
  }));
}

function AnalysisResult({ taskId, resultUrl }) {
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    const loadResult = async () => {
      try {
        setIsLoading(true);
        setError("");

        const data = await getAnalysisResult(taskId, resultUrl);

        if (isMounted) {
          setResult(data);
        }
      } catch (requestError) {
        if (isMounted) {
          setError(
            requestError.response?.data?.detail ??
              requestError.message ??
              "分析结果加载失败，请稍后重试。"
          );
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    loadResult();

    return () => {
      isMounted = false;
    };
  }, [taskId, resultUrl]);

  if (isLoading) {
    return <p className="status-message">正在加载完整分析结果...</p>;
  }

  if (error) {
    return (
      <section className="error-panel">
        <h2>分析结果加载失败</h2>
        <p>{error}</p>
      </section>
    );
  }

  if (!result) {
    return null;
  }

  const plan = (result.analysis_plan?.steps ?? []).map((step, index) => ({
    id: `${step.skill_name}-${index}`,
    title: skillLabels[step.skill_name] ?? step.skill_name,
  }));

  return (
    <section className="result-content">
      <article className="result-summary">
        <h2>分析问题</h2>
        <p>{result.question}</p>
      </article>

      <AnalysisPlan plan={plan} />

      {(result.statistical_results ?? []).map((statisticalResult, index) => {
        const skillName = statisticalResult.skill_name;
        const sectionTitle = skillLabels[skillName] ?? skillName;
        const summaryRows = summaryToRows(statisticalResult.summary);

        return (
          <div key={`${skillName}-${index}`}>
            {summaryRows.length > 0 && (
              <ResultTable
                title={`${sectionTitle}摘要`}
                columns={[
                  { key: "name", label: "指标" },
                  { key: "value", label: "结果" },
                ]}
                rows={summaryRows}
              />
            )}

            {(statisticalResult.tables ?? []).map((table, tableIndex) => (
              <ResultTable
                key={table.table_id ?? table.name ?? `table-${tableIndex}`}
                title={table.title ?? sectionTitle}
                columns={table.columns}
                rows={table.rows}
              />
            ))}
          </div>
        );
      })}

      {(result.figures ?? []).length > 0 && (
        <ChartViewer charts={result.figures} />
      )}

      <ReportDownload
        taskId={taskId}
        reportUrl={result.report_download_url}
      />
    </section>
  );
}

export default AnalysisResult;
