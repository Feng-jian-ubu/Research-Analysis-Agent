import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import Header from "../components/layout/Header.jsx";
import StepIndicator from "../components/layout/StepIndicator.jsx";
import DatasetProfile from "../components/DatasetProfile.jsx";
import AnalysisPlan from "../components/AnalysisPlan.jsx";
import { createAnalysisTask } from "../api/client.js";

function AnalysisPage() {
  const { fileId } = useParams();
  const navigate = useNavigate();

  const [question, setQuestion] = useState("");
  const [plan, setPlan] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();

    const trimmedQuestion = question.trim();

    if (!trimmedQuestion) {
      setError("请输入分析需求。");
      return;
    }

    try {
      setIsSubmitting(true);
      setError("");

      const data = await createAnalysisTask(fileId, trimmedQuestion);

      setPlan(data.plan ?? []);

      if (data.task_id) {
        navigate(`/result/${data.task_id}`);
      }
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ??
          requestError.message ??
          "创建分析任务失败，请稍后重试。"
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="app">
      <Header />

      <main className="page-container">
        <StepIndicator currentStep={2} />

        <section className="page-heading">
          <p className="page-eyebrow">STEP 02</p>
          <h1>设置分析任务</h1>
          <p>查看数据基本信息，并用自然语言描述你希望完成的分析。</p>
        </section>

        <DatasetProfile fileId={fileId} />

        <form className="analysis-form" onSubmit={handleSubmit}>
          <label htmlFor="analysis-question">分析需求</label>

          <textarea
            id="analysis-question"
            rows="6"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="例如：分析各变量之间的相关关系，并建立回归模型解释销售额的主要影响因素。"
            disabled={isSubmitting}
          />

          {error && <p className="form-error">{error}</p>}

          <button
            className="primary-button"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "正在创建任务..." : "开始分析"}
          </button>
        </form>

        {plan.length > 0 && <AnalysisPlan plan={plan} />}
      </main>
    </div>
  );
}

export default AnalysisPage;
