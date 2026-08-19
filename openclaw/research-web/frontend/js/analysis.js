/* ══════════════════════════════════
   分析模块 — 启动 + 轮询
   ══════════════════════════════════ */

const btnAnalyze = document.getElementById('btnAnalyze');
const progressSection = document.getElementById('progressSection');
const resultSection = document.getElementById('resultSection');

let pollTimer = null;

/* ── 启动分析 ── */
btnAnalyze.addEventListener('click', async () => {
  if (!window.currentTaskId) {
    showToast('请先上传文件', 'error');
    return;
  }

  const method = document.getElementById('methodSelect').value;
  const yVal = document.getElementById('yVar').value.trim();
  const xVal = document.getElementById('xVar').value.trim();

  const body = {
    y: yVal || null,
    x: xVal ? xVal.split(',').map(s => s.trim()).filter(Boolean) : null,
    method: method || null,
  };

  btnAnalyze.disabled = true;
  btnAnalyze.textContent = '分析中…';

  progressSection.classList.remove('hidden');
  progressSection.scrollIntoView({ behavior: 'smooth' });
  resultSection.classList.add('hidden');

  try {
    const res = await fetch(`${API_BASE}/analyze/${window.currentTaskId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '启动分析失败');

    // 开始轮询
    startPolling(window.currentTaskId);

  } catch (err) {
    showToast(err.message, 'error');
    btnAnalyze.disabled = false;
    btnAnalyze.textContent = '🚀 开始分析';
  }
});

/* ── 轮询任务状态 ── */
function startPolling(taskId) {
  if (pollTimer) clearInterval(pollTimer);

  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}`);
      const task = await res.json();
      if (!res.ok) throw new Error(task.detail);

      updateProgressUI(task);

      if (task.status === 'completed' || task.status === 'failed') {
        clearInterval(pollTimer);
        pollTimer = null;
        btnAnalyze.disabled = false;
        btnAnalyze.textContent = '🚀 开始分析';

        if (task.status === 'completed') {
          showToast('分析完成！', 'success');
          loadResults(taskId);
        } else {
          showToast('分析失败，请检查文件和参数', 'error');
        }
      }
    } catch (err) {
      console.error('Poll error:', err);
    }
  }, 1500);
}

/* ── 更新进度 UI ── */
function updateProgressUI(task) {
  const steps = document.querySelectorAll('.step');
  const currentStep = task.step || '';
  const stepOrder = ['uploaded', 'loading', 'cleaning', 'analyzing', 'figures', 'report', 'completed'];
  const currentIdx = stepOrder.indexOf(currentStep);

  steps.forEach((step, i) => {
    step.classList.remove('active', 'done', 'failed');
    const stepName = step.dataset.step;
    const si = stepOrder.indexOf(stepName);
    if (task.status === 'failed') {
      if (si === currentIdx) step.classList.add('failed');
      else if (si < currentIdx) step.classList.add('done');
    } else {
      if (si < currentIdx) step.classList.add('done');
      else if (si === currentIdx) step.classList.add('active');
    }
  });

  // 进度条
  document.getElementById('pipelineProgressFill').style.width = task.progress + '%';
  document.getElementById('progressStatus').textContent = task.message || '处理中…';
}

/* ── 加载结果 ── */
async function loadResults(taskId) {
  resultSection.classList.remove('hidden');
  resultSection.scrollIntoView({ behavior: 'smooth' });

  // 加载报告预览
  try {
    const reportRes = await fetch(`${API_BASE}/download/${taskId}/report.md`);
    if (reportRes.ok) {
      const text = await reportRes.text();
      const preview = document.getElementById('reportPreview');
      // 简单渲染为纯文本，后续可加 Markdown 渲染
      preview.innerHTML = `<pre style="white-space:pre-wrap;font-family:inherit;line-height:1.8;">${escapeHtml(text)}</pre>`;
    }
  } catch (e) { /* ignore */ }

  // 加载摘要
  try {
    const sumRes = await fetch(`${API_BASE}/download/${taskId}/summary.md`);
    if (sumRes.ok && document.getElementById('reportPreview').querySelector('pre') === null) {
      const text = await sumRes.text();
      document.getElementById('reportPreview').innerHTML = `<pre style="white-space:pre-wrap;font-family:inherit;line-height:1.8;">${escapeHtml(text)}</pre>`;
    }
  } catch (e) { /* ignore */ }

  // 加载图表
  loadFigures(taskId);

  // 加载下载列表
  loadDownloads(taskId);
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/* ── 加载图表列表 ── */
async function loadFigures(taskId) {
  try {
    const res = await fetch(`${API_BASE}/files/${taskId}`);
    const data = await res.json();
    if (!data.files) return;

    // 查找 HTML 图表文件
    const htmlFigs = data.files.filter(f => f.name.startsWith('figures/') && f.name.endsWith('.html'));
    if (!htmlFigs.length) return;

    const grid = document.getElementById('figuresGrid');
    grid.innerHTML = '';

    htmlFigs.forEach(f => {
      const url = `${API_BASE}/download/${taskId}/` + encodeURIComponent(f.name);
      const card = document.createElement('div');
      card.className = 'figure-card';
      card.innerHTML = `
        <a href="${url}" target="_blank">
          <img src="${url.replace('.html', '.png')}" alt="${f.name}" style="width:100%;height:260px;object-fit:contain;background:#f8fafc;padding:8px;"
               onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22160%22><rect fill=%22%23e2e8f0%22 width=%22200%22 height=%22160%22/><text x=%2250%%22 y=%2250%%22 text-anchor=%22middle%22 fill=%22%2394a3b8%22 font-size=%2214%22>点此打开交互图表</text></svg>'">
        </a>
        <div class="figure-label">📈 ${f.name.split('/').pop()} (${formatSize(f.size)})</div>
      `;
      grid.appendChild(card);
    });
  } catch (e) { console.error('Load figures error:', e); }
}

/* ── 加载下载列表 ── */
async function loadDownloads(taskId) {
  try {
    const res = await fetch(`${API_BASE}/files/${taskId}`);
    const data = await res.json();
    if (!data.files) return;

    const list = document.getElementById('downloadList');
    list.innerHTML = '';

    const downloadable = [
      { key: 'report.md', icon: '📄', label: '分析报告 (Markdown)' },
      { key: 'summary.md', icon: '📝', label: '分析摘要' },
      { key: 'result.json', icon: '📊', label: '统计结果 (JSON)' },
    ];

    downloadable.forEach(item => {
      const div = document.createElement('div');
      div.className = 'download-item';
      div.innerHTML = `
        <div class="item-left">
          <span class="item-icon">${item.icon}</span>
          <div>
            <div class="item-name">${item.label}</div>
            <div class="item-size">${item.key}</div>
          </div>
        </div>
        <a href="${API_BASE}/download/${taskId}/${item.key}" download class="btn btn-secondary" style="font-size:13px;padding:6px 14px;">
          下载
        </a>
      `;
      list.appendChild(div);
    });

    // 图表 ZIP
    const hasFigs = data.files.some(f => f.name.startsWith('figures/'));
    if (hasFigs) {
      const div = document.createElement('div');
      div.className = 'download-item';
      div.innerHTML = `
        <div class="item-left">
          <span class="item-icon">🖼️</span>
          <div>
            <div class="item-name">所有图表 (ZIP)</div>
            <div class="item-size">figures.zip</div>
          </div>
        </div>
        <a href="${API_BASE}/download/${taskId}/figures.zip" download class="btn btn-secondary" style="font-size:13px;padding:6px 14px;">
          下载
        </a>
      `;
      list.appendChild(div);
    }

  } catch (e) { console.error('Load downloads error:', e); }
}
