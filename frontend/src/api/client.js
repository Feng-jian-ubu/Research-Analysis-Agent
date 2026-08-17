// Unified FastAPI client.
import axios from "axios";

/*
 * 后端基础地址：
 *
 * 1. 如果 .env 中配置了 VITE_API_BASE_URL，则使用配置值。
 * 2. 如果没有配置，则默认连接本机 FastAPI：
 *    /api/v1（开发环境由 Vite 代理到 FastAPI）
 */
const API_PREFIX = "/api/v1";
const configuredApiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL ?? API_PREFIX
).replace(/\/+$/, "");

// 兼容旧版示例中的 /api 配置，避免请求落到不存在的 /api/datasets。
const API_BASE_URL = configuredApiBaseUrl.endsWith("/api")
  ? `${configuredApiBaseUrl}/v1`
  : configuredApiBaseUrl;

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000,
  headers: {
    Accept: "application/json",
  },
});

function normalizeRequestUrl(url, fallbackUrl) {
  if (!url) {
    return fallbackUrl;
  }

  if (/^https?:\/\//i.test(url)) {
    return url;
  }

  if (url.startsWith(API_PREFIX)) {
    return url.slice(API_PREFIX.length) || "/";
  }

  return url;
}

export function resolveApiUrl(url) {
  if (!url || /^https?:\/\//i.test(url)) {
    return url;
  }

  if (/^https?:\/\//i.test(API_BASE_URL)) {
    const apiOrigin = new URL(API_BASE_URL).origin;
    return url.startsWith("/")
      ? `${apiOrigin}${url}`
      : `${API_BASE_URL}/${url}`;
  }

  return url.startsWith("/")
    ? url
    : `${API_BASE_URL}/${url}`;
}

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
 * POST /api/v1/datasets
 *
 * 返回示例：
 * {
 *   "dataset_id": "ds_123",
 *   "file_name": "data.csv"
 * }
 */
export async function uploadDataset(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiClient.post("/datasets", formData, {
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
 * GET /api/v1/datasets/{dataset_id}/profile
 *
 * 返回内容包括：
 * - 文件名称
 * - 行数和列数
 * - 缺失值数量
 * - 字段信息
 * - 数据预览
 */
export async function getDatasetProfile(datasetId) {
  const response = await apiClient.get(
    `/datasets/${encodeURIComponent(datasetId)}/profile`
  );

  return response.data;
}

/*
 * 创建分析任务。
 *
 * POST /api/v1/analyses
 *
 * 请求体示例：
 * {
 *   "dataset_id": "ds_123",
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
export async function createAnalysisTask(datasetId, question) {
  const response = await apiClient.post("/analyses", {
    dataset_id: datasetId,
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
 * GET /api/v1/analyses/{task_id}/result
 */
export async function getAnalysisResult(taskId, resultUrl) {
  const fallbackUrl = `/analyses/${encodeURIComponent(taskId)}/result`;
  const requestUrl = normalizeRequestUrl(resultUrl, fallbackUrl);
  const response = await apiClient.get(requestUrl);

  const result = response.data;
  result.figures = (result.figures ?? []).map((figure) => ({
    ...figure,
    url: resolveApiUrl(figure.url),
  }));

  return result;
}

/*
 * 下载 Markdown 分析报告。
 *
 * 优先使用后端返回的 reportUrl；
 * 如果没有，则使用默认报告接口。
 */
export async function downloadReport(taskId, reportUrl) {
  const defaultUrl = `/reports/${encodeURIComponent(taskId)}/download`;
  const requestUrl = normalizeRequestUrl(reportUrl, defaultUrl);

  const response = await apiClient.get(requestUrl, {
    responseType: "blob",
    timeout: 60_000,
  });

  return response.data;
}

export default apiClient;
