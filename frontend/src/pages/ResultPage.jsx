import { useParams } from "react-router-dom";

import Header from "../components/layout/Header.jsx";
import StepIndicator from "../components/layout/StepIndicator.jsx";
import AnalysisProgress from "../components/AnalysisProgress.jsx";
import ResultTable from "../components/ResultTable.jsx";
import ChartViewer from "../components/ChartViewer.jsx";
import ReportDownload from "../components/ReportDownload.jsx";
import useTaskPolling from "../hooks/useTaskPolling.js";

function ResultPage() {
  const { taskId } = useParams();
  const { task, isLoading, error } = useTaskPolling(taskId);

  if (isLoading && !task) {
    return (
      <div className="app">
        <Header />

        <main className="page-container">
          <StepIndicator currentStep={3} />
          <p className="status-message">正在获取分析任务...</p>
        </main>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app">
        <Header />

        <main className="page-container">
          <StepIndicator currentStep={3} />

          <section className="error-panel">
            <h1>任务获取失败</h1>
            <p>{error}</p>
          </section>
        </main>
      </div>
    );
  }

  const status = task?.status ?? "pending";
  const isCompleted = status === "completed";
  const isFailed = status === "failed";
  const result = task?.result ?? {};

  return (
    <div className="app">
      <Header />

      <main className="page-container">
        <StepIndicator currentStep={3} />

        <section className="page-heading">
          <p className="page-eyebrow">STEP 03</p>
          <h1>{isCompleted ? "分析结果" : "任务执行进度"}</h1>
          <p>
            {isCompleted
              ? "分析任务已完成，你可以查看结果并下载完整报告。"
              : "智能分析 Agent 正在执行任务，请稍候。"}
          </p>
        </section>

        <AnalysisProgress
          status={status}
          progress={task?.progress ?? 0}
          currentStep={task?.current_step ?? ""}
          steps={task?.steps ?? []}
        />

        {isFailed && (
          <section className="error-panel">
            <h2>分析任务执行失败</h2>
            <p>{task?.error ?? "任务执行过程中出现错误，请重新创建任务。"}</p>
          </section>
        )}

        {isCompleted && (
          <section className="result-content">
            {result.summary && (
              <article className="result-summary">
                <h2>分析结论</h2>
                <p>{result.summary}</p>
              </article>
            )}

            {result.tables?.map((table, index) => (
              <ResultTable
                key={table.id ?? `table-${index}`}
                title={table.title}
                columns={table.columns}
                rows={table.rows}
              />
            ))}

            {result.charts?.length > 0 && (
              <ChartViewer charts={result.charts} />
            )}

            {result.report_url && (
              <ReportDownload
                taskId={taskId}
                reportUrl={result.report_url}
              />
            )}
          </section>
        )}
      </main>
    </div>
  );
}

export default ResultPage;