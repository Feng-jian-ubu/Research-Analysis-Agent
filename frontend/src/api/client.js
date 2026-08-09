// Unified FastAPI client.
import axios from "axios";

/*
 * 后端基础地址：
 *
 * 1. 如果 .env 中配置了 VITE_API_BASE_URL，则使用配置值。
 * 2. 如果没有配置，则默认连接本机 FastAPI：
 *    http://localhost:8000/api
 */
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000,
  headers: {
    Accept: "application/json",
  },
});

/*
 * 统一处理后端请求错误。
 */
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // 后端已经响应，但状态码为 4xx 或 5xx。
      return Promise.reject(error);
    }

    if (error.request) {
      // 请求已经发出，但没有收到后端响应。
      error.message = "无法连接后端服务，请确认 FastAPI 服务是否已经启动。";
      return Promise.reject(error);
    }

    error.message = error.message || "请求发送失败。";
    return Promise.reject(error);
  }
);

/*
 * 上传 CSV 或 Excel 数据文件。
 *
 * POST /api/files
 *
 * 返回示例：
 * {
 *   "file_id": "file-123",
 *   "filename": "data.csv"
 * }
 */
export async function uploadDataset(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiClient.post("/files", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },

    // 上传文件时允许更长的等待时间。
    timeout: 60_000,
  });

  return response.data;
}

/*
 * 获取数据集画像。
 *
 * GET /api/files/{file_id}/profile
 *
 * 返回内容包括：
 * - 文件名称
 * - 行数和列数
 * - 缺失值数量
 * - 字段信息
 * - 数据预览
 */
export async function getDatasetProfile(fileId) {
  const response = await apiClient.get(
    `/files/${encodeURIComponent(fileId)}/profile`
  );

  return response.data;
}

/*
 * 创建分析任务。
 *
 * POST /api/analysis
 *
 * 请求体示例：
 * {
 *   "file_id": "file-123",
 *   "question": "不同肥料组的产量是否存在显著差异？"
 * }
 *
 * 返回示例：
 * {
 *   "task_id": "task-123",
 *   "status": "pending",
 *   "plan": [...]
 * }
 */
export async function createAnalysisTask(fileId, question) {
  const response = await apiClient.post("/analysis", {
    file_id: fileId,
    question: question.trim(),
  });

  return response.data;
}

/*
 * 查询分析任务的执行状态。
 *
 * GET /api/tasks/{task_id}
 *
 * 返回内容可以包括：
 * - status
 * - progress
 * - current_step
 * - steps
 * - result
 * - error
 */
export async function getTaskStatus(taskId) {
  const response = await apiClient.get(
    `/tasks/${encodeURIComponent(taskId)}`
  );

  return response.data;
}

/*
 * 获取分析任务的最终结果。
 *
 * GET /api/tasks/{task_id}/result
 *
 * 当前 ResultPage 可以直接从任务状态响应中的 result 读取结果；
 * 此函数保留给后端将“状态接口”和“结果接口”分离时使用。
 */
export async function getAnalysisResult(taskId) {
  const response = await apiClient.get(
    `/tasks/${encodeURIComponent(taskId)}/result`
  );

  return response.data;
}

/*
 * 下载 Markdown 分析报告。
 *
 * 优先使用后端返回的 reportUrl；
 * 如果没有，则使用默认报告接口。
 */
export async function downloadReport(taskId, reportUrl) {
  const defaultUrl = `/tasks/${encodeURIComponent(taskId)}/report`;
  const requestUrl = reportUrl || defaultUrl;

  const response = await apiClient.get(requestUrl, {
    responseType: "blob",
    timeout: 60_000,
  });

  return response.data;
}

export default apiClient;