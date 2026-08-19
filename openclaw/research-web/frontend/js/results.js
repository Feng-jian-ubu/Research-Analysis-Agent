/* ══════════════════════════════════
   结果展示 + 历史记录
   ══════════════════════════════════ */

/* ── Tab 切换 ── */
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
    tab.classList.add('active');
    const targetId = 'tab' + tab.dataset.tab.charAt(0).toUpperCase() + tab.dataset.tab.slice(1);
    document.getElementById(targetId).classList.remove('hidden');
  });
});

/* ── 导航切换 ── */
document.querySelectorAll('.nav-links a').forEach(link => {
  link.addEventListener('click', (e) => {
    e.preventDefault();
    const href = link.getAttribute('href');
    if (href === '#history') {
      document.getElementById('historySection').classList.remove('hidden');
      document.getElementById('historySection').scrollIntoView({ behavior: 'smooth' });
      document.getElementById('nav-history').classList.add('active');
      document.querySelector('.nav-links a[href="#upload"]').classList.remove('active');
      loadHistory();
    } else {
      document.getElementById('historySection').classList.add('hidden');
      document.querySelector('.nav-links a[href="#upload"]').classList.add('active');
      document.getElementById('nav-history').classList.remove('active');
      document.getElementById('upload').scrollIntoView({ behavior: 'smooth' });
    }
  });
});

/* ── Toast ── */
function showToast(message, type = 'info') {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

/* ── 格式大小（全局）── */
function formatSize(bytes) {
  if (!bytes) return '0 B';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/* ── 加载历史 ── */
async function loadHistory() {
  const list = document.getElementById('historyList');
  list.innerHTML = '<div class="placeholder">加载中…</div>';

  try {
    const res = await fetch(`${API_BASE}/tasks`);
    const tasks = await res.json();
    if (!tasks.length) {
      list.innerHTML = '<div class="placeholder">暂无历史记录</div>';
      return;
    }

    list.innerHTML = '';
    tasks.forEach(t => {
      const div = document.createElement('div');
      div.className = 'history-item';
      const date = new Date(t.created_at * 1000);
      const timeStr = date.toLocaleString('zh-CN', { hour12: false });
      div.innerHTML = `
        <div class="hi-left">
          <span style="font-size:20px;">📄</span>
          <div>
            <div class="hi-name">${t.original_filename || '未命名'}</div>
            <div style="font-size:12px;color:var(--gray-400);">${timeStr}</div>
          </div>
        </div>
        <span class="hi-status ${t.status}">${statusLabel(t.status)}</span>
      `;
      div.addEventListener('click', () => loadHistoryTask(t.task_id));
      list.appendChild(div);
    });
  } catch (e) {
    list.innerHTML = '<div class="placeholder">加载失败</div>';
  }
}

function statusLabel(status) {
  const map = { completed: '已完成', failed: '失败', running: '运行中', ready: '等待分析', pending: '等待中', uploading: '上传中' };
  return map[status] || status;
}

async function loadHistoryTask(taskId) {
  window.currentTaskId = taskId;
  document.getElementById('historySection').classList.add('hidden');

  // 查看状态
  const res = await fetch(`${API_BASE}/tasks/${taskId}`);
  const task = await res.json();

  if (task.status === 'completed') {
    progressSection.classList.remove('hidden');
    resultSection.classList.remove('hidden');
    updateProgressUI(task);
    loadResults(taskId);
    resultSection.scrollIntoView({ behavior: 'smooth' });
  } else if (task.status === 'running') {
    progressSection.classList.remove('hidden');
    resultSection.classList.add('hidden');
    updateProgressUI(task);
    startPolling(taskId);
    progressSection.scrollIntoView({ behavior: 'smooth' });
  } else if (task.status === 'ready') {
    document.getElementById('configSection').classList.remove('hidden');
    document.getElementById('configSection').scrollIntoView({ behavior: 'smooth' });
  }
}

/* ── 初始检查 URL 参数 ── */
(function() {
  const params = new URLSearchParams(window.location.search);
  const taskId = params.get('task');
  if (taskId) {
    window.currentTaskId = taskId;
    loadHistoryTask(taskId);
  }
})();
