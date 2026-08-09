function AnalysisPlan({ plan = [] }) {
  if (plan.length === 0) {
    return null;
  }

  return (
    <section className="analysis-plan">
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">ANALYSIS PLAN</p>
          <h2>分析计划</h2>
        </div>
      </div>

      <ol className="plan-list">
        {plan.map((item, index) => {
          const title =
            typeof item === "string"
              ? item
              : item.title ?? item.name ?? `步骤 ${index + 1}`;

          const description =
            typeof item === "string" ? "" : item.description ?? "";

          return (
            <li className="plan-item" key={item.id ?? `plan-${index}`}>
              <span className="plan-number">{index + 1}</span>

              <div>
                <h3>{title}</h3>
                {description && <p>{description}</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export default AnalysisPlan;