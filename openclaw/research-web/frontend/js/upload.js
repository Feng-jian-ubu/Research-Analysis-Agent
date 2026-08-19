/* ══════════════════════════════════
   上传模块
   ══════════════════════════════════ */

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

/* ── 点击触发文件选择 ── */
dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => {
  if (e.target.files.length) selectFile(e.target.files[0]);
});

/* ── 拖拽 ── */
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  if (e.dataTransfer.files.length) selectFile(e.dataTransfer.files[0]);
});

/* ── 选中文件 ── */
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

/* ── 移除文件 ── */
removeBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  selectedFile = null;
  fileInput.value = '';
  dropContent.classList.remove('hidden');
  fileInfo.classList.add('hidden');
  btnUpload.disabled = true;
});

/* ── 上传 ── */
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

    // 显示配置区
    document.getElementById('configSection').classList.remove('hidden');
    document.getElementById('configSection').scrollIntoView({ behavior: 'smooth' });

  } catch (err) {
    showToast(err.message, 'error');
    uploadProgressFill.style.width = '0%';
    uploadProgress.classList.add('hidden');
  } finally {
    btnUpload.disabled = false;
    btnUpload.textContent = '开始上传';
  }
});

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}
