import { useState } from "react";

function ChartViewer({ charts = [] }) {
  const [activeIndex, setActiveIndex] = useState(0);

  if (charts.length === 0) {
    return null;
  }

  const activeChart = charts[activeIndex];
  const imageUrl =
    activeChart.image_url ??
    activeChart.url ??
    activeChart.chart_url ??
    activeChart.src;

  return (
    <section className="result-section chart-section">
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">VISUALIZATION</p>
          <h2>分析图表</h2>
        </div>

        {charts.length > 1 && (
          <span className="chart-count">
            {activeIndex + 1} / {charts.length}
          </span>
        )}
      </div>

      {charts.length > 1 && (
        <div className="chart-tabs" role="tablist">
          {charts.map((chart, index) => (
            <button
              key={chart.id ?? `chart-tab-${index}`}
              type="button"
              className={`chart-tab ${
                index === activeIndex ? "chart-tab--active" : ""
              }`}
              onClick={() => setActiveIndex(index)}
              role="tab"
              aria-selected={index === activeIndex}
            >
              {chart.title ?? `图表 ${index + 1}`}
            </button>
          ))}
        </div>
      )}

      <figure className="chart-viewer">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={activeChart.alt ?? activeChart.title ?? "数据分析图表"}
          />
        ) : (
          <div className="chart-placeholder">图表暂时无法显示</div>
        )}

        {(activeChart.title || activeChart.description) && (
          <figcaption>
            {activeChart.title && <h3>{activeChart.title}</h3>}
            {activeChart.description && <p>{activeChart.description}</p>}
          </figcaption>
        )}
      </figure>
    </section>
  );
}

export default ChartViewer;