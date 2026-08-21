const btnAnalyze = document.getElementById('btnAnalyze');
const progressSection = document.getElementById('progressSection');
const resultSection = document.getElementById('resultSection');

let eventSource = null;
let stepStartTime = Date.now();
let lastStep = "";
let stepTimings = {};

btnAnalyze.addEventListener('click', async () => {
  if (!window.currentTaskId) { showToast('请先上传文件', 'error'); return; }

  const body = {
    y: document.getElementById('yVar').value.trim() || null,
    x: (document.getElementById('xVar').value.trim() || '').split(',').map(s => s.trim()).filter(Boolean) || null,
    method: document.getElementById('methodSelect').value || null,
  };

  btnAnalyze.disabled = true;
  btnAnalyze.textContent = '分析中…';

  progressSection.classList.remove('hidden');
  window._analysisStartTime = Date.now();
  stepStartTime = Date.now();
  stepTimings = {};
  lastStep = "";
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
    connectSSE(window.currentTaskId);
  } catch (err) {
    showToast(err.message, 'error');
    btnAnalyze.disabled = false;
    btnAnalyze.textContent = '\u{1F680} 开始分析';
  }
});

/* ── SSE 连接 ── */
function connectSSE(taskId) {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }

  const es = new EventSource(`${API_BASE}/events/${taskId}`);
  eventSource = es;

  // 常规进度更新
  es.addEventListener('message', (e) => {
    try {
      const data = JSON.parse(e.data);
      updateProgressUI(data);
    } catch (err) {
      console.error('SSE parse error:', err);
    }
  });

  // 完成事件
  es.addEventListener('completed', (e) => {
    try {
      const data = JSON.parse(e.data);
      updateProgressUI(data);
      finishAnalysis(taskId);
    } catch (err) {
      console.error('SSE completed error:', err);
    }
  });

  // 失败事件
  es.addEventListener('error', (e) => {
    try {
      const data = JSON.parse(e.data);
      updateProgressUI(data);
      failAnalysis(data);
    } catch (err) {
      console.error('SSE error event:', err);
    }
    es.close();
    eventSource = null;
  });

  // done 事件（连接自然结束）
  es.addEventListener('done', () => {
    es.close();
    eventSource = null;
  });

  // 连接错误 — 回退到轮询
  es.onerror = () => {
    console.warn('SSE 连接失败，回退到轮询模式');
    es.close();
    eventSource = null;
    if (window.currentTaskId) {
      startPollingFallback(window.currentTaskId);
    }
  };
}

/* ── 轮询备用（SSE 失败时回退）── */
let pollTimer = null;

function startPollingFallback(taskId) {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}`);
      const task = await res.json();
      if (!res.ok) throw new Error(task.detail);
      updateProgressUI(task);
      if (task.status === 'completed') {
        clearInterval(pollTimer);
        pollTimer = null;
        finishAnalysis(taskId);
      } else if (task.status === 'failed') {
        clearInterval(pollTimer);
        pollTimer = null;
        failAnalysis(task);
      }
    } catch (err) { console.error('Poll error:', err); }
  }, 1500);
}

/* ── 分析完成 ── */
function finishAnalysis(taskId) {
  btnAnalyze.disabled = false;
  btnAnalyze.textContent = '\u{1F680} 开始分析';
  showToast('\u2705 分析完成！', 'success');
  loadResults(taskId);
}

/* ── 分析失败 ── */
function failAnalysis(task) {
  btnAnalyze.disabled = false;
  btnAnalyze.textContent = '\u{1F680} 开始分析';
  showToast('\u274C 分析失败', 'error');
}

/* ── 更新进度 UI（含泳道日志）── */
function updateProgressUI(task) {
  const steps = document.querySelectorAll('.step');
  const stepOrder = ['uploaded', 'loading', 'cleaning', 'analyzing', 'figures', 'report', 'completed'];
  const currentIdx = stepOrder.indexOf(task.step || '');
  steps.forEach((step, i) => {
    step.classList.remove('active', 'done', 'failed');
    const si = stepOrder.indexOf(step.dataset.step);
    if (task.status === 'failed') {
      if (si === currentIdx) step.classList.add('failed');
      else if (si < currentIdx) step.classList.add('done');
    } else {
      if (si < currentIdx) step.classList.add('done');
      else if (si === currentIdx) step.classList.add('active');
    }
  });

  // 更新泳道日志
  updatePipelineLogs(task);

  // 进度条
  document.getElementById('pipelineProgressFill').style.width = task.progress + '%';
  document.getElementById('progressStatus').textContent = task.message || '处理中…';

  // 追踪每步耗时
  if (task.step && task.step !== lastStep) {
    const elapsed = ((Date.now() - stepStartTime) / 1000).toFixed(1);
    if (lastStep) {
      stepTimings[lastStep] = elapsed + 's';
    }
    lastStep = task.step;
    stepStartTime = Date.now();
  }

  // 在已完成步骤后显示耗时
  document.querySelectorAll('.step.done, .step.failed').forEach(s => {
    const stepName = s.dataset.step;
    if (stepTimings[stepName]) {
      let timeEl = s.querySelector('.step-time');
      if (!timeEl) {
        timeEl = document.createElement('span');
        timeEl.className = 'step-time';
        s.appendChild(timeEl);
      }
      timeEl.textContent = ' (' + stepTimings[stepName] + ')';
    }
  });

  // 全部完成时显示总耗时
  if (task.status === 'completed') {
    const statusEl = document.getElementById('progressStatus');
    if (!statusEl.querySelector('.total-time')) {
      const totalEl = document.createElement('div');
      totalEl.className = 'total-time';
      totalEl.textContent = '⏱️ 总耗时: ' + ((Date.now() - window._analysisStartTime) / 1000).toFixed(1) + 's';
      statusEl.appendChild(totalEl);
    }
  }

  if (task.status === 'failed' && task.message) {
    document.getElementById('progressStatus').innerHTML =
      `<span style="color:var(--danger);">\u274C ${escapeHtml(task.message)}</span>`;
  }
}

/* ── 更新泳道日志 ── */
function updatePipelineLogs(task) {
  const step = task.step || '';
  const status = task.status || '';
  const logEntries = document.querySelectorAll('.log-entry');
  const stepOrder = ['loading', 'cleaning', 'analyzing', 'figures', 'report'];
  const currentIdx = stepOrder.indexOf(step);

  logEntries.forEach(entry => {
    entry.classList.remove('running', 'done', 'failed');
    const entryStep = entry.dataset.step;
    const entryIdx = stepOrder.indexOf(entryStep);

    if (status === 'failed') {
      if (entryIdx === currentIdx) entry.classList.add('failed');
      else if (entryIdx < currentIdx) entry.classList.add('done');
    } else if (status === 'completed') {
      entry.classList.add('done');
    } else if (currentIdx >= 0) {
      if (entryIdx < currentIdx) entry.classList.add('done');
      else if (entryIdx === currentIdx) entry.classList.add('running');
    }

    // 更新状态文本
    const statusEl = entry.querySelector('.log-step-status');
    if (!statusEl) return;
    if (entry.classList.contains('failed')) {
      statusEl.textContent = '❌ 失败';
    } else if (entry.classList.contains('running')) {
      statusEl.textContent = '⏳ 进行中…';
    } else if (entry.classList.contains('done')) {
      statusEl.textContent = '✓ 完成';
      // 显示耗时
      const stepName = entryStep;
      if (stepTimings[stepName]) {
        statusEl.textContent += ' (' + stepTimings[stepName] + ')';
      }
    } else {
      statusEl.textContent = '⏳ 等待中';
    }

    // 点击展开/收起日志
    const header = entry.querySelector('.log-header');
    const body = entry.querySelector('.log-body');
    if (header && body) {
      header.onclick = () => {
        body.classList.toggle('hidden');
      };
    }

    // 正在运行的步骤自动展开
    if (entry.classList.contains('running')) {
      if (body) body.classList.remove('hidden');
    }
  });
}

/* ── 失败重试按钮 ── */
function showRetry(task) {
  const container = document.getElementById('progressStatus');
  if (container.querySelector('.btn')) return; // 避免重复
  const retryBtn = document.createElement('button');
  retryBtn.className = 'btn btn-primary';
  retryBtn.style.marginTop = '16px';
  retryBtn.textContent = '\u{1F504} 修改参数重试';
  retryBtn.addEventListener('click', () => {
    document.getElementById('progressSection').classList.add('hidden');
    document.getElementById('configSection').classList.remove('hidden');
    document.getElementById('configSection').scrollIntoView({ behavior: 'smooth' });
  });
  container.appendChild(retryBtn);
}

/* ── 加载结果 ── */
async function loadResults(taskId) {
  resultSection.classList.remove('hidden');
  resultSection.scrollIntoView({ behavior: 'smooth' });

  const reportSection = document.getElementById('reportPreview');
  reportSection.innerHTML = '<div class="placeholder">\u23F3 正在加载报告…</div>';

  let found = false;
  const candidates = ['report.md', 'summary.md'];
  for (const fileType of candidates) {
    try {
      const res = await fetch(`${API_BASE}/download/${taskId}/${fileType}`);
      if (res.ok) {
        const text = await res.text();
        if (window.marked) {
          reportSection.innerHTML = '<div class="markdown-body">' + marked.parse(text) + '</div>';
        } else {
          reportSection.innerHTML = `<pre style="white-space:pre-wrap;font-family:inherit;line-height:1.8;">${escapeHtml(text)}</pre>`;
        }
        found = true;
        break;
      }
    } catch (e) {}
  }

  if (!found) {
    try {
      const res = await fetch(`${API_BASE}/download/${taskId}/result.json`);
      if (res.ok) {
        const data = await res.json();
        reportSection.innerHTML = `<pre style="white-space:pre-wrap;font-family:inherit;line-height:1.8;">${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
      } else {
        reportSection.innerHTML = '<div class="placeholder">暂无报告</div>';
      }
    } catch (e) {
      reportSection.innerHTML = '<div class="placeholder">暂无报告</div>';
    }
  }

  loadFigures(taskId);
  loadDownloads(taskId);
}

async function loadFigures(taskId) {
  try {
    const res = await fetch(`${API_BASE}/files/${taskId}`);
    const data = await res.json();
    if (!data.files) return;

    const figFiles = data.files.filter(f => f.name.startsWith('figures/') && f.name.endsWith('.png'));
    if (!figFiles.length) {
      document.getElementById('figuresGrid').innerHTML = '<div class="placeholder">暂无图表</div>';
      return;
    }

    const grid = document.getElementById('figuresGrid');
    grid.innerHTML = '';

    figFiles.forEach(f => {
      const url = `${API_BASE}/download/${taskId}/${encodeURIComponent(f.name)}`;
      const label = f.name.split('/').pop().replace(/_figure|_/g, ' ').trim();
      const card = document.createElement('div');
      card.className = 'figure-card';
      card.innerHTML = `
        <div class="figure-thumb">
          <img src="${url}" alt="${label}" loading="lazy" style="object-fit:contain;width:100%;height:100%;padding:0;">
        </div>
        <div class="figure-label">📈 ${label} (${formatSize(f.size)})</div>`;
      grid.appendChild(card);
    });

  } catch (e) { console.error('Load figures error:', e); }
}

async function loadDownloads(taskId) {
  try {
    const res = await fetch(`${API_BASE}/files/${taskId}`);
    const data = await res.json();
    if (!data.files) return;

    const list = document.getElementById('downloadList');
    list.innerHTML = '';

    const items = [
      { key: 'report.md', icon: '\u{1F4C4}', label: '分析报告 (Markdown)' },
      { key: 'summary.md', icon: '\u{1F4DD}', label: '分析摘要' },
      { key: 'result.json', icon: '\u{1F4CA}', label: '统计结果 (JSON)' },
      { key: 'data.csv', icon: '\u{1F4CB}', label: '清洗后数据 (CSV)' },
    ];

    items.forEach(item => {
      const div = document.createElement('div');
      div.className = 'download-item';
      div.innerHTML = `<div class="item-left"><span class="item-icon">${item.icon}</span>
        <div><div class="item-name">${item.label}</div><div class="item-size">${item.key}</div></div></div>
        <a href="${API_BASE}/download/${taskId}/${item.key}" download class="btn btn-secondary" style="font-size:13px;padding:6px 14px;">下载</a>`;
      list.appendChild(div);
    });

    if (data.files.some(f => f.name.startsWith('figures/'))) {
      const div = document.createElement('div');
      div.className = 'download-item';
      div.innerHTML = `<div class="item-left"><span class="item-icon">\u{1F5BC}\uFE0F</span>
        <div><div class="item-name">所有图表 (ZIP)</div><div class="item-size">figures.zip</div></div></div>
        <a href="${API_BASE}/download/${taskId}/figures.zip" download class="btn btn-secondary" style="font-size:13px;padding:6px 14px;">下载</a>`;
      list.appendChild(div);
    }
  } catch (e) { console.error('Load downloads error:', e); }
}

function escapeHtml(text) {
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}
