function ResultTable({ title = "分析结果", columns = [], rows = [] }) {
  if (columns.length === 0 || rows.length === 0) {
    return null;
  }

  const getColumnKey = (column) =>
    typeof column === "string" ? column : column.key ?? column.field;

  const getColumnLabel = (column) =>
    typeof column === "string"
      ? column
      : column.label ?? column.title ?? column.key ?? column.field;

  return (
    <section className="result-section">
      <h2>{title}</h2>

      <div className="table-wrapper">
        <table className="result-table">
          <thead>
            <tr>
              {columns.map((column, index) => (
                <th key={getColumnKey(column) ?? `heading-${index}`}>
                  {getColumnLabel(column)}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={row.id ?? `row-${rowIndex}`}>
                {columns.map((column, columnIndex) => {
                  const key = getColumnKey(column);
                  const value = Array.isArray(row)
                    ? row[columnIndex]
                    : row[key];

                  return (
                    <td key={`${rowIndex}-${key ?? columnIndex}`}>
                      {value === null || value === undefined
                        ? "—"
                        : typeof value === "object"
                          ? JSON.stringify(value)
                          : String(value)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default ResultTable;