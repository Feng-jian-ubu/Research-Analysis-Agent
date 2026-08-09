const steps = [
  {
    number: 1,
    title: "上传数据",
    description: "选择 CSV 或 Excel 文件",
  },
  {
    number: 2,
    title: "设置分析",
    description: "输入自然语言分析需求",
  },
  {
    number: 3,
    title: "查看结果",
    description: "查看结果并下载报告",
  },
];

function StepIndicator({ currentStep }) {
  return (
    <nav className="step-indicator" aria-label="分析流程">
      {steps.map((step, index) => {
        const isCompleted = step.number < currentStep;
        const isActive = step.number === currentStep;

        const statusClass = isCompleted
          ? "step-item--completed"
          : isActive
            ? "step-item--active"
            : "step-item--pending";

        return (
          <div className="step-wrapper" key={step.number}>
            <div
              className={`step-item ${statusClass}`}
              aria-current={isActive ? "step" : undefined}
            >
              <div className="step-number">
                {isCompleted ? "✓" : step.number}
              </div>

              <div className="step-content">
                <span className="step-title">{step.title}</span>
                <span className="step-description">
                  {step.description}
                </span>
              </div>
            </div>

            {index < steps.length - 1 && (
              <div
                className={`step-line ${
                  isCompleted ? "step-line--completed" : ""
                }`}
                aria-hidden="true"
              />
            )}
          </div>
        );
      })}
    </nav>
  );
}

export default StepIndicator;