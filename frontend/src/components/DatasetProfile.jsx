import { useEffect, useState } from "react";

import { getDatasetProfile } from "../api/client.js";

function DatasetProfile({ fileId }) {
  const [profile, setProfile] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    const loadProfile = async () => {
      try {
        setIsLoading(true);
        setError("");

        const data = await getDatasetProfile(fileId);

        if (isMounted) {
          setProfile(data);
        }
      } catch (requestError) {
        if (isMounted) {
          setError(
            requestError.response?.data?.detail ??
              "数据画像加载失败，请稍后重试。"
          );
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    loadProfile();

    return () => {
      isMounted = false;
    };
  }, [fileId]);

  if (isLoading) {
    return (
      <section className="profile-card">
        <p className="status-message">正在读取数据画像...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="profile-card">
        <p className="form-error">{error}</p>
      </section>
    );
  }

  const columns = profile?.columns ?? [];
  const previewRows = profile?.preview ?? profile?.preview_rows ?? [];

  return (
    <section className="profile-card">
      <div className="section-heading">
        <div>
          <p className="section-eyebrow">DATASET PROFILE</p>
          <h2>数据集概览</h2>
        </div>

        <span className="file-name">
          {profile?.filename ?? profile?.file_name ?? "已上传数据集"}
        </span>
      </div>

      <div className="profile-stats">
        <div className="stat-card">
          <span>数据行数</span>
          <strong>{profile?.row_count ?? profile?.rows ?? 0}</strong>
        </div>

        <div className="stat-card">
          <span>变量数量</span>
          <strong>{profile?.column_count ?? columns.length}</strong>
        </div>

        <div className="stat-card">
          <span>缺失值</span>
          <strong>{profile?.missing_count ?? profile?.missing_values ?? 0}</strong>
        </div>

        <div className="stat-card">
          <span>文件类型</span>
          <strong>{profile?.file_type ?? "—"}</strong>
        </div>
      </div>

      {columns.length > 0 && (
        <div className="profile-section">
          <h3>变量信息</h3>

          <div className="table-wrapper">
            <table className="result-table">
              <thead>
                <tr>
                  <th>变量名称</th>
                  <th>数据类型</th>
                  <th>缺失值</th>
                  <th>唯一值数量</th>
                </tr>
              </thead>

              <tbody>
                {columns.map((column, index) => (
                  <tr key={column.name ?? `column-${index}`}>
                    <td>{column.name ?? "—"}</td>
                    <td>{column.dtype ?? column.type ?? "—"}</td>
                    <td>{column.missing_count ?? column.missing ?? 0}</td>
                    <td>{column.unique_count ?? column.unique ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {previewRows.length > 0 && (
        <div className="profile-section">
          <h3>数据预览</h3>

          <div className="table-wrapper">
            <table className="result-table">
              <thead>
                <tr>
                  {Object.keys(previewRows[0]).map((columnName) => (
                    <th key={columnName}>{columnName}</th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {previewRows.map((row, rowIndex) => (
                  <tr key={`preview-row-${rowIndex}`}>
                    {Object.keys(previewRows[0]).map((columnName) => (
                      <td key={`${rowIndex}-${columnName}`}>
                        {row[columnName] === null ||
                        row[columnName] === undefined
                          ? "—"
                          : String(row[columnName])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

export default DatasetProfile;