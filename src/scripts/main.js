/**
 * 全站脚本：主题切换、滚动入场、代码复制、阅读进度、目录高亮、
 * 回到顶部、搜索弹窗。
 * 所有节点查询先判空——同一份脚本会在没有对应元素的页面上执行。
 */
import { loadIndex, runSearch } from './search-core.js';

(function () {
  'use strict';

  var root = document.documentElement;
  var STORAGE_KEY = 'theme';
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- 明暗切换 ---------- */
  var toggle = document.querySelector('[data-theme-toggle]');
  var sun = document.querySelector('.theme-icon--sun');
  var moon = document.querySelector('.theme-icon--moon');

  function stored() {
    try { return localStorage.getItem(STORAGE_KEY); } catch (e) { return null; }
  }

  function setHidden(el, hidden) {
    if (!el) return;
    if (hidden) el.setAttribute('hidden', '');
    else el.removeAttribute('hidden');
  }

  function syncThemeUI() {
    var dark = root.dataset.theme === 'dark';
    if (toggle) toggle.setAttribute('aria-label', dark ? '切换到浅色模式' : '切换到深色模式');
    setHidden(sun, !dark);
    setHidden(moon, dark);
  }

  if (toggle) {
    toggle.addEventListener('click', function () {
      var next = root.dataset.theme === 'dark' ? 'light' : 'dark';
      root.dataset.theme = next;
      try { localStorage.setItem(STORAGE_KEY, next); } catch (e) { /* 隐私模式 */ }
      syncThemeUI();
    });
  }

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
    if (stored()) return;
    root.dataset.theme = e.matches ? 'dark' : 'light';
    syncThemeUI();
  });

  syncThemeUI();

  /* ---------- 滚动入场 ---------- */
  var revealTargets = document.querySelectorAll('.reveal');

  if (reduceMotion || !('IntersectionObserver' in window)) {
    revealTargets.forEach(function (el) { el.classList.add('is-in'); });
  } else {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-in');
        observer.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -6% 0px', threshold: 0.05 });
    revealTargets.forEach(function (el) { observer.observe(el); });
  }

  /* ---------- 代码块复制 ---------- */
  document.querySelectorAll('.prose pre').forEach(function (pre) {
    var code = pre.querySelector('code');
    if (!code) return;

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'code-copy';
    btn.textContent = '复制';
    btn.setAttribute('aria-label', '复制代码');

    btn.addEventListener('click', function () {
      navigator.clipboard.writeText(code.innerText).then(function () {
        btn.textContent = '已复制';
        btn.classList.add('is-done');
      }).catch(function () {
        btn.textContent = '复制失败';
      });
      window.setTimeout(function () {
        btn.textContent = '复制';
        btn.classList.remove('is-done');
      }, 1800);
    });

    pre.appendChild(btn);
  });

  /* ---------- 进度条 / 回到顶部 / 目录高亮 ---------- */
  var progress = document.querySelector('[data-progress], .progress');
  var toTop = document.querySelector('[data-to-top]');
  var tocLinks = Array.prototype.slice.call(
    document.querySelectorAll('[data-toc] a[href^="#"]')
  );

  var tocTargets = tocLinks.map(function (link) {
    var id = decodeURIComponent(link.hash.slice(1));
    var el = document.getElementById(id);
    return el ? { link: link, el: el } : null;
  }).filter(Boolean);

  var activeId = '';

  function setActive(id) {
    if (id === activeId) return;
    activeId = id;
    tocTargets.forEach(function (item) {
      var on = decodeURIComponent(item.link.hash.slice(1)) === id;
      item.link.classList.toggle('is-active', on);
      if (on) item.link.setAttribute('aria-current', 'true');
      else item.link.removeAttribute('aria-current');
    });
  }

  var ticking = false;

  function onScroll() {
    if (ticking) return;
    ticking = true;

    window.requestAnimationFrame(function () {
      ticking = false;

      if (progress) {
        var max = document.documentElement.scrollHeight - window.innerHeight;
        var ratio = max > 0 ? Math.min(1, window.scrollY / max) : 0;
        progress.style.transform = 'scaleX(' + ratio + ')';
      }

      if (toTop) toTop.classList.toggle('is-visible', window.scrollY > 640);

      if (tocTargets.length > 0) {
        var current = '';
        for (var i = 0; i < tocTargets.length; i++) {
          if (tocTargets[i].el.getBoundingClientRect().top <= 120) current = tocTargets[i].el.id;
          else break;
        }
        if (!current) current = tocTargets[0].el.id;
        setActive(current);
      }
    });
  }

  if (progress || toTop || tocTargets.length > 0) {
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    onScroll();
  }

  if (toTop) {
    toTop.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' });
    });
  }

  /* ---------- 搜索弹窗 ---------- */
  var dialog = document.querySelector('[data-search-dialog]');
  var openBtn = document.querySelector('[data-search-open]');
  var input = document.querySelector('[data-search-input]');
  var results = document.querySelector('[data-search-results]');

  if (!dialog || !input || !results) return;

  var timer = null;
  var items = [];
  var cursor = -1;

  function openDialog() {
    if (typeof dialog.showModal === 'function') dialog.showModal();
    else dialog.setAttribute('open', '');
    window.setTimeout(function () { input.focus(); }, 30);
  }

  function closeDialog() {
    if (typeof dialog.close === 'function') dialog.close();
    else dialog.removeAttribute('open');
  }

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function renderEmpty(text) {
    results.innerHTML = '<li class="search-empty">' + esc(text) + '</li>';
    items = [];
    cursor = -1;
  }

  function render(list) {
    if (!list.length) { renderEmpty('没有找到匹配的内容'); return; }
    items = list;
    cursor = -1;
    results.innerHTML = list.map(function (item, i) {
      return '<li>'
        + '<a class="search-result" href="' + esc(item.url) + '" data-i="' + i + '">'
        + '<span class="search-result__title">' + esc(item.title) + '</span>'
        + (item.excerpt ? '<span class="search-result__excerpt">' + esc(item.excerpt) + '</span>' : '')
        + '</a></li>';
    }).join('');
  }

  function highlight() {
    Array.prototype.forEach.call(results.querySelectorAll('.search-result'), function (el, i) {
      el.classList.toggle('is-selected', i === cursor);
      if (i === cursor) el.scrollIntoView({ block: 'nearest' });
    });
  }

  // 服务端搜索是否可用：null=未知，true=可用，false=不可用（已降级）
  var apiMode = null;

  function search(q) {
    if (!q) { renderEmpty('输入关键词开始搜索'); return; }
    renderEmpty('搜索中…');

    var local = function () {
      loadIndex()
        .then(function (index) { render(runSearch(index, q)); })
        .catch(function () { renderEmpty('搜索出错了，稍后再试'); });
    };

    // 纯静态托管（拖拽上传）没有 Functions，首次探测失败后永久走本地索引
    if (apiMode === false) { local(); return; }

    fetch('/api/search?q=' + encodeURIComponent(q))
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        apiMode = true;
        return r.json();
      })
      .then(function (data) {
        render(data && Array.isArray(data.results) ? data.results : []);
      })
      .catch(function () {
        apiMode = false;
        local();
      });
  }

  input.addEventListener('input', function () {
    window.clearTimeout(timer);
    var q = input.value.trim();
    timer = window.setTimeout(function () { search(q); }, 220);
  });

  input.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!items.length) return;
      cursor = (cursor + 1) % items.length;
      highlight();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (!items.length) return;
      cursor = (cursor - 1 + items.length) % items.length;
      highlight();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      // 有选中项就直接进结果；否则去搜索页，与原站「未选中走搜索归档」的行为一致
      var pick = cursor >= 0 ? items[cursor] : null;
      if (pick) {
        window.location.href = pick.url;
        return;
      }
      var kw = input.value.trim();
      if (kw) window.location.href = '/search/?q=' + encodeURIComponent(kw);
    }
  });

  dialog.addEventListener('click', function (e) {
    if (e.target === dialog) closeDialog();
  });

  if (openBtn) openBtn.addEventListener('click', openDialog);

  document.addEventListener('keydown', function (e) {
    var isK = (e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey);
    if (isK) {
      e.preventDefault();
      if (dialog.open) closeDialog();
      else openDialog();
    }
    if (e.key === 'Escape' && dialog.open) closeDialog();
  });
})();
