/* =============================================================
   n8n Management Suite — User Manual
   manual.js — theme toggle, copy buttons, sidebar toggle
   ============================================================= */

(function () {
  'use strict';

  const THEME_KEY = 'n8n-manual-theme';

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch (e) {
      // localStorage may be unavailable (private mode); silently continue.
    }
    const btn = document.getElementById('themeToggle');
    if (btn) btn.textContent = theme === 'dark' ? '☀️ Light' : '🌙 Dark';
  }

  function initTheme() {
    let stored = null;
    try {
      stored = localStorage.getItem(THEME_KEY);
    } catch (e) {
      // ignore
    }
    if (stored === 'light' || stored === 'dark') {
      applyTheme(stored);
      return;
    }
    const prefersDark = window.matchMedia &&
      window.matchMedia('(prefers-color-scheme: dark)').matches;
    applyTheme(prefersDark ? 'dark' : 'light');
  }

  function toggleTheme() {
    const current = document.documentElement.dataset.theme || 'light';
    applyTheme(current === 'dark' ? 'light' : 'dark');
  }

  function attachCopyButtons() {
    const blocks = document.querySelectorAll('pre');
    blocks.forEach(function (pre) {
      if (pre.querySelector('.copy-btn')) return;
      const btn = document.createElement('button');
      btn.className = 'copy-btn';
      btn.type = 'button';
      btn.textContent = 'Copy';
      btn.setAttribute('aria-label', 'Copy code to clipboard');
      btn.addEventListener('click', function () {
        const code = pre.querySelector('code') || pre;
        const text = code.innerText;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(
            function () { showCopied(btn); },
            function () { fallbackCopy(text, btn); }
          );
        } else {
          fallbackCopy(text, btn);
        }
      });
      pre.appendChild(btn);
    });
  }

  function fallbackCopy(text, btn) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand('copy');
      showCopied(btn);
    } catch (e) {
      btn.textContent = 'Failed';
      setTimeout(function () { btn.textContent = 'Copy'; }, 1500);
    }
    document.body.removeChild(ta);
  }

  function showCopied(btn) {
    btn.textContent = 'Copied!';
    setTimeout(function () { btn.textContent = 'Copy'; }, 1500);
  }

  function initSidebarToggle() {
    const btn = document.getElementById('sidebarToggle');
    const sidebar = document.querySelector('.sidebar');
    if (!btn || !sidebar) return;
    btn.addEventListener('click', function () {
      sidebar.classList.toggle('open');
    });
    // Close sidebar when clicking a link inside it (mobile).
    sidebar.addEventListener('click', function (e) {
      const link = e.target.closest('a');
      if (link && window.matchMedia('(max-width: 900px)').matches) {
        sidebar.classList.remove('open');
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initTheme();
    attachCopyButtons();
    initSidebarToggle();
    const tt = document.getElementById('themeToggle');
    if (tt) tt.addEventListener('click', toggleTheme);
  });
})();
