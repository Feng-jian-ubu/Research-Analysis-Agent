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

/* ── 加载数据预览 ── */
async function loadDataPreview(taskId) {
  const previewContainer = document.getElementById('dataPreview');
  previewContainer.classList.remove('hidden');
  previewContainer.innerHTML = '<div class="placeholder">⏳ 加载数据预览…</div>';

  try {
    const res = await fetch(`${API_BASE}/tasks/${taskId}/preview?rows=10`);
    if (!res.ok) throw new Error('预览加载失败');
    const data = await res.json();

    if (!data.columns || !data.columns.length) {
      previewContainer.innerHTML = '<div class="placeholder">⚠️ 未能识别列名</div>';
      return;
    }

    // 渲染数据预览表格
    let html = '<div class="preview-header">';
    html += `<span><strong>列名：</strong>${data.columns.join('、')}</span>`;
    html += `<span class="preview-stats">${data.total_rows} 行 × ${data.columns.length} 列</span>`;
    html += '</div>';
    html += '<div class="preview-table-wrap"><table class="preview-table"><thead><tr>';
    data.columns.forEach(c => { html += `<th>${escapeHtml(c)}</th>`; });
    html += '</tr></thead><tbody>';
    data.preview.slice(0, 10).forEach(row => {
      html += '<tr>';
      row.forEach((cell, i) => {
        html += `<td>${escapeHtml(cell)}</td>`;
      });
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    html += `<div class="preview-footer">显示前 ${Math.min(data.preview.length, 10)} 行</div>`;
    previewContainer.innerHTML = html;

    // 填充下拉选择框
    populateColumnSelects(data.columns);

  } catch (err) {
    previewContainer.innerHTML = `<div class="placeholder">⚠️ ${err.message}</div>`;
  }
}

/* ── 填充列名下选择框 ── */
function populateColumnSelects(columns) {
  // Y 变量下拉
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

  // X 下拉改为一个 selection area with checkboxes
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

  // 更新 X 值
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
