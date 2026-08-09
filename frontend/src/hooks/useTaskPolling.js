import { useEffect, useState } from "react";

import { getTaskStatus } from "../api/client.js";

const POLLING_INTERVAL = 2000;
const FINISHED_STATUSES = ["completed", "failed"];

function useTaskPolling(taskId) {
  const [task, setTask] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!taskId) {
      setError("缺少任务 ID。");
      setIsLoading(false);
      return undefined;
    }

    let isMounted = true;
    let timerId = null;

    const stopPolling = () => {
      if (timerId) {
        clearTimeout(timerId);
        timerId = null;
      }
    };

    const pollTask = async () => {
      try {
        const data = await getTaskStatus(taskId);

        if (!isMounted) {
          return;
        }

        setTask(data);
        setError("");
        setIsLoading(false);

        if (!FINISHED_STATUSES.includes(data.status)) {
          timerId = setTimeout(pollTask, POLLING_INTERVAL);
        }
      } catch (requestError) {
        if (!isMounted) {
          return;
        }

        setError(
          requestError.response?.data?.detail ??
            "获取任务状态失败，请稍后重试。"
        );
        setIsLoading(false);
        stopPolling();
      }
    };

    setTask(null);
    setError("");
    setIsLoading(true);
    pollTask();

    return () => {
      isMounted = false;
      stopPolling();
    };
  }, [taskId]);

  return {
    task,
    isLoading,
    error,
  };
}

export default useTaskPolling;