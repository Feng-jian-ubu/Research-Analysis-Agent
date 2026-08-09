const statusLabels = {
  pending: "等待执行",
  queued: "等待执行",
  running: "正在分析",
  completed: "分析完成",
  failed: "执行失败",
};

function AnalysisProgress({
  status = "pending",
  progress = 0,
  currentStep = "",
  steps = [],
}) {
  const normalizedProgress = Math.min(
    100,
    Math.max(0, Number(progress) || 0)
  );

  return (
    <section className={`progress-card progress-card--${status}`}>
      <div className="progress-header">
        <div>
          <p className="section-eyebrow">TASK STATUS</p>
          <h2>{statusLabels[status] ?? status}</h2>
        </div>

        <strong className="progress-percentage">
          {Math.round(normalizedProgress)}%
        </strong>
      </div>

      <div
        className="progress-track"
        role="progressbar"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={normalizedProgress}
      >
        <div
          className="progress-bar"
          style={{ width: `${normalizedProgress}%` }}
        />
      </div>

      {currentStep && <p className="current-step">{currentStep}</p>}

      {steps.length > 0 && (
        <ul className="execution-steps">
          {steps.map((step, index) => {
            const stepStatus =
              typeof step === "string" ? "pending" : step.status ?? "pending";

            const stepTitle =
              typeof step === "string"
                ? step
                : step.title ?? step.name ?? `步骤 ${index + 1}`;

            return (
              <li
                className={`execution-step execution-step--${stepStatus}`}
                key={step.id ?? `execution-step-${index}`}
              >
                <span className="execution-step-icon" aria-hidden="true">
                  {stepStatus === "completed"
                    ? "✓"
                    : stepStatus === "running"
                      ? "●"
                      : stepStatus === "failed"
                        ? "×"
                        : index + 1}
                </span>

                <span>{stepTitle}</span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export default AnalysisProgress;