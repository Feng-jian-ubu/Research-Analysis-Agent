
/* ══════════════════════════════════
   Tab 切换 + Toast + 历史记录
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

/* ── Toast 通知 ── */
function showToast(message, type) {
  if (!type) type = 'info';
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();
  const toast = document.createElement('div');
  toast.className = 'toast ' + type;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

/* ── 格式化文件大小（全局）── */
function formatSize(bytes) {
  if (!bytes) return '0 B';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/* ── 状态标签文本 ── */
function statusLabel(status) {
  const map = {
    completed: '已完成',
    failed: '失败',
    running: '运行中',
    ready: '等待分析',
    pending: '等待中',
    uploading: '上传中'
  };
  return map[status] || status;
}

/* ── 历史记录加载 ── */
async function loadHistory() {
  const list = document.getElementById('historyList');
  list.innerHTML = '<div class="placeholder">\u23f3\u52a0\u8f7d\u4e2d\u2026</div>';

  try {
    const res = await fetch(API_BASE + '/tasks');
    const tasks = await res.json();
    if (!tasks.length) {
      list.innerHTML = '<div class="placeholder">\u6682\u65e0\u5386\u53f2\u8bb0\u5f55</div>';
      return;
    }

    list.innerHTML = '';
    tasks.forEach(function(t) {
      const div = document.createElement('div');
      div.className = 'history-item';

      const date = new Date(t.created_at * 1000);
      const sd = t.step_data || {};
      const method = sd.recommended_method || '';

      // 生成元信息摘要
      let meta = '';
      if (t.status === 'completed') {
        meta = '\u2705 ';
        if (method) meta += '\ud83e\uddea ' + method;
        else meta += '\u5206\u6790\u5b8c\u6210';
      } else if (t.status === 'failed') {
        meta = '\u274c ' + (t.message || '').substring(0, 50);
      } else if (t.status === 'running') {
        meta = '\u23f3 ' + (t.message || '\u8fd0\u884c\u4e2d');
      }

      // 重跑按钮（仅已完成）
      let actionsHtml = '<span class="hi-status ' + t.status + '">' + statusLabel(t.status) + '</span>';
      if (t.status === 'completed') {
        actionsHtml += '<button class="btn btn-small" onclick="event.stopPropagation();reAnalyze(\'' + t.task_id + '\')">\ud83d\udd04 \u91cd\u8dd1</button>';
      }

      div.innerHTML = '<div class="hi-left"><span style="font-size:20px;">\ud83d\udcc4</span>' +
        '<div>' +
          '<div class="hi-name">' + escapeHtml(t.original_filename || '\u672a\u547d\u540d') + '</div>' +
          '<div style="font-size:12px;color:var(--gray-400);">' + date.toLocaleString('zh-CN', { hour12: false }) + '</div>' +
          '<div style="font-size:12px;color:var(--gray-500);margin-top:2px;">' + escapeHtml(meta) + '</div>' +
        '</div></div>' +
        '<div style="display:flex;gap:6px;align-items:center;">' + actionsHtml + '</div>';

      div.addEventListener('click', function() { loadHistoryTask(t.task_id); });
      list.appendChild(div);
    });

  } catch (e) {
    list.innerHTML = '<div class="placeholder">\u52a0\u8f7d\u5931\u8d25</div>';
  }
}

/* ── 从历史重新分析 ── */
function reAnalyze(taskId) {
  loadHistoryTask(taskId).then(function() {
    document.getElementById('configSection').classList.remove('hidden');
    document.getElementById('configSection').scrollIntoView({ behavior: 'smooth' });
    showToast('\u2705 \u5df2\u52a0\u8f7d\u5386\u53f2\u4efb\u52a1\uff0c\u53ef\u4fee\u6539\u53c2\u6570\u540e\u91cd\u65b0\u5206\u6790', 'info');
  });
}

/* ── 加载历史任务 ── */
async function loadHistoryTask(taskId) {
  window.currentTaskId = taskId;
  document.getElementById('historySection').classList.add('hidden');

  const res = await fetch(API_BASE + '/tasks/' + taskId);
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

/* ── URL 参数初始检查 ── */
(function() {
  const params = new URLSearchParams(window.location.search);
  const taskId = params.get('task');
  if (taskId) {
    window.currentTaskId = taskId;
    loadHistoryTask(taskId);
  }
})();

/* ── escapeHtml 别名（供 history 用，与 analysis.js 共享）── */
function escapeHtml(text) {
  if (text === null || text === undefined) return '';
  var d = document.createElement('div');
  d.textContent = String(text);
  return d.innerHTML;
}
