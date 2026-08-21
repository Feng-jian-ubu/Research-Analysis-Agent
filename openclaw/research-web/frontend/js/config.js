// API 地址 — 使用相对路径，跟随当前页面地址
// 这样无论通过哪种端口映射或域名访问都能正常工作
const API_BASE = '/api';

/* ══════════════════════════════════
   深色模式（在 DOM 加载前生效，防闪烁）
   ══════════════════════════════════ */
(function() {
  const saved = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = saved || (prefersDark ? 'dark' : 'light');
  if (theme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();

/* ── 初始化主题切换（在 DOM 就绪后绑定事件）── */
document.addEventListener('DOMContentLoaded', function initTheme() {
  const btn = document.getElementById('themeToggle');
  if (!btn) return;
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  btn.textContent = isDark ? '☀️' : '🌙';
  btn.addEventListener('click', function() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    btn.textContent = next === 'dark' ? '☀️' : '🌙';
    localStorage.setItem('theme', next);
  });
});
