const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const dropContent = document.getElementById('dropContent');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const removeBtn = document.getElementById('removeFile');
const btnUpload = document.getElementById('btnUpload');
const uploadProgress = document.getElementById('uploadProgress');
const uploadProgressFill = document.getElementById('uploadProgressFill');

let selectedFile = null;

dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => { if (e.target.files.length) selectFile(e.target.files[0]); });

dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault(); dropZone.classList.remove('dragover');
  if (e.dataTransfer.files.length) selectFile(e.dataTransfer.files[0]);
});

function selectFile(file) {
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!['.csv', '.xlsx', '.xls'].includes(ext)) {
    showToast('不支持的文件格式，请上传 CSV 或 Excel 文件', 'error');
    return;
  }
  selectedFile = file;
  dropContent.classList.add('hidden');
  fileInfo.classList.remove('hidden');
  fileName.textContent = file.name;
  fileSize.textContent = formatSize(file.size);
  btnUpload.disabled = false;
}

removeBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  selectedFile = null;
  fileInput.value = '';
  dropContent.classList.remove('hidden');
  fileInfo.classList.add('hidden');
  btnUpload.disabled = true;
});

btnUpload.addEventListener('click', async () => {
  if (!selectedFile) return;
  btnUpload.disabled = true;
  btnUpload.textContent = '上传中…';
  uploadProgress.classList.remove('hidden');
  uploadProgressFill.style.width = '30%';

  const formData = new FormData();
  formData.append('file', selectedFile);

  try {
    const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '上传失败');

    uploadProgressFill.style.width = '100%';
    showToast('上传成功！', 'success');
    window.currentTaskId = data.task_id;

    // 显示配置区并加载数据预览
    document.getElementById('configSection').classList.remove('hidden');
    document.getElementById('configSection').scrollIntoView({ behavior: 'smooth' });
    loadDataPreview(data.task_id);

  } catch (err) {
    showToast(err.message, 'error');
    uploadProgressFill.style.width = '0%';
    uploadProgress.classList.add('hidden');
  } finally {
    btnUpload.disabled = false;
    btnUpload.textContent = '开始上传';
  }
});

/* ── 加载数据预览（增强版：类型徽标 + 列统计 hover + 排序）── */
async function loadDataPreview(taskId) {
  const previewContainer = document.getElementById('dataPreview');
  previewContainer.classList.remove('hidden');
  previewContainer.innerHTML = '<div class="placeholder">⏳ 加载数据预览…</div>';

  try {
    const res = await fetch(`${API_BASE}/tasks/${taskId}/preview?rows=100`);
    if (!res.ok) throw new Error('预览加载失败');
    const data = await res.json();

    if (!data.columns || !data.columns.length) {
      previewContainer.innerHTML = '<div class="placeholder">⚠️ 未能识别列名</div>';
      return;
    }

    // 自动推断列类型
    const colTypes = inferColumnTypes(data.preview, data.columns);

    // 渲染
    let html = '<div class="preview-header">';
    html += `<span><strong>列名：</strong>${data.columns.join('、')}</span>`;
    html += `<span class="preview-stats">${data.total_rows} 行 × ${data.columns.length} 列</span>`;
    html += '</div>';
    html += '<div class="preview-table-wrap"><table class="preview-table" id="previewTable"><thead><tr>';

    // 生成列统计信息
    const colStats = computeColumnStats(data.preview, data.columns, colTypes);

    data.columns.forEach((c, idx) => {
      const typeLabel = { numeric: '🔢', categorical: '🏷️', datetime: '📅' }[colTypes[idx] || 'categorical'] || '🏷️';
      const typeClass = colTypes[idx] || 'categorical';
      const stat = colStats[idx] || {};
      let tipHtml = '';
      if (stat.unique !== undefined) {
        tipHtml = `<div class="col-stat-tip">
          <strong>${escapeHtml(c)}</strong><br>
          类型: ${typeLabel} <span class="col-type-badge ${typeClass}">${typeClass}</span><br>
          唯一值: ${stat.unique}<br>
          ${stat.min !== undefined ? `最小值: ${stat.min}<br>` : ''}
          ${stat.max !== undefined ? `最大值: ${stat.max}<br>` : ''}
          ${stat.mean !== undefined ? `均值: ${stat.mean}<br>` : ''}
          ${stat.null !== undefined ? `缺失: ${stat.null}` : ''}
        </div>`;
      }
      html += `<th data-col-idx="${idx}" class="sortable-col">
        <div class="col-header-inner">
          <span>${escapeHtml(c)}</span>
          <span class="col-type-badge ${typeClass}">${typeClass}</span>
          <span class="sort-indicator">⇅</span>
        </div>
        ${tipHtml}
      </th>`;
    });
    html += '</tr></thead><tbody>';
    data.preview.slice(0, 10).forEach(row => {
      html += '<tr>';
      row.forEach((cell, i) => {
        html += `<td>${escapeHtml(cell)}</td>`;
      });
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    html += `<div class="preview-footer">显示前 ${Math.min(data.preview.length, 10)} 行 · 悬停表头查看列统计 · 点击排序</div>`;
    previewContainer.innerHTML = html;

    // 绑定排序
    setupSorting();

    // 填充下拉选择框
    populateColumnSelects(data.columns);

  } catch (err) {
    previewContainer.innerHTML = `<div class="placeholder">⚠️ ${err.message}</div>`;
  }
}

/* ── 推断列类型 ── */
function inferColumnTypes(rows, columns) {
  const types = [];
  columns.forEach((_, idx) => {
    const values = rows.map(r => r[idx]).filter(v => v !== '' && v !== null && v !== undefined);
    if (values.length === 0) { types.push('categorical'); return; }

    // 日期检测
    const datePattern = /^\d{4}[-/]\d{1,2}[-/]\d{1,2}/;
    const dateCount = values.filter(v => datePattern.test(String(v).trim())).length;
    if (dateCount / values.length > 0.7) { types.push('datetime'); return; }

    // 数值检测
    const numValues = values.map(v => parseFloat(String(v).replace(/,/g, '').trim()));
    const numericCount = numValues.filter(v => !isNaN(v)).length;
    if (numericCount / values.length > 0.8) {
      const unique = new Set(values.map(v => String(v).trim()));
      if (unique.size <= 10) { types.push('categorical'); }
      else { types.push('numeric'); }
      return;
    }

    types.push('categorical');
  });
  return types;
}

/* ── 计算列统计 ── */
function computeColumnStats(rows, columns, colTypes) {
  const stats = [];
  columns.forEach((_, idx) => {
    const values = rows.map(r => r[idx]).filter(v => v !== '' && v !== null && v !== undefined);
    const unique = new Set(values.map(v => String(v).trim()));
    const nullCount = rows.length - values.length;
    const stat = { unique: unique.size, null: nullCount };

    if (colTypes[idx] === 'numeric') {
      const nums = values.map(v => parseFloat(String(v).replace(/,/g, '').trim())).filter(v => !isNaN(v));
      if (nums.length > 0) {
        stat.min = Math.min(...nums).toFixed(2);
        stat.max = Math.max(...nums).toFixed(2);
        stat.mean = (nums.reduce((a, b) => a + b, 0) / nums.length).toFixed(2);
      }
    }
    stats.push(stat);
  });
  return stats;
}

/* ── 表头排序 ── */
let sortState = { colIdx: -1, asc: true };

function setupSorting() {
  const table = document.getElementById('previewTable');
  if (!table) return;
  const headers = table.querySelectorAll('th.sortable-col');
  headers.forEach(th => {
    th.style.cursor = 'pointer';
    th.addEventListener('click', () => {
      const idx = parseInt(th.dataset.colIdx);
      const tbody = table.querySelector('tbody');
      const rows = Array.from(tbody.querySelectorAll('tr'));

      if (sortState.colIdx === idx) {
        sortState.asc = !sortState.asc;
      } else {
        sortState.colIdx = idx;
        sortState.asc = true;
        headers.forEach(h => { h.classList.remove('sort-asc', 'sort-desc'); });
      }
      th.classList.add(sortState.asc ? 'sort-asc' : 'sort-desc');

      rows.sort((a, b) => {
        const va = a.cells[idx]?.textContent || '';
        const vb = b.cells[idx]?.textContent || '';
        const na = parseFloat(va), nb = parseFloat(vb);
        if (!isNaN(na) && !isNaN(nb)) {
          return sortState.asc ? na - nb : nb - na;
        }
        return sortState.asc ? va.localeCompare(vb) : vb.localeCompare(va);
      });

      rows.forEach(r => tbody.appendChild(r));
    });
  });
}

/* ── 填充列名下选择框 ── */
function populateColumnSelects(columns) {
  const ySelect = document.getElementById('yVar');
  const currentY = ySelect.dataset.prevValue || '';
  ySelect.innerHTML = '<option value="">— 自动检测 —</option>';
  columns.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c;
    opt.textContent = c;
    if (c === currentY) opt.selected = true;
    ySelect.appendChild(opt);
  });

  const xContainer = document.getElementById('xVarContainer');
  xContainer.innerHTML = '';
  columns.forEach(c => {
    const label = document.createElement('label');
    label.className = 'x-checkbox-label';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.value = c;
    cb.className = 'x-checkbox';
    label.appendChild(cb);
    label.appendChild(document.createTextNode(' ' + c));
    xContainer.appendChild(label);
  });

  updateXValue();
  xContainer.querySelectorAll('.x-checkbox').forEach(cb => {
    cb.addEventListener('change', updateXValue);
  });
}

function updateXValue() {
  const checked = document.querySelectorAll('.x-checkbox:checked');
  const values = Array.from(checked).map(cb => cb.value);
  document.getElementById('xVar').value = values.join(', ');
}

function escapeHtml(text) {
  if (text === null || text === undefined) return '';
  const d = document.createElement('div');
  d.textContent = String(text);
  return d.innerHTML;
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}
