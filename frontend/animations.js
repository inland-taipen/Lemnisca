(function () {
  'use strict';

  function initPageEntrance() {
    const els = [
      ...document.querySelectorAll('.panel-section'),
      document.querySelector('.bar'),
      document.querySelector('.composer'),
    ].filter(Boolean);

    els.forEach((el, i) => {
      el.classList.add('anim-load');
      el.style.animationDelay = `${80 + i * 50}ms`;
    });

    const welcome = document.getElementById('welcome-state');
    if (welcome) {
      welcome.classList.add('anim-load');
      welcome.style.animationDelay = `${80 + els.length * 50}ms`;
    }
  }

  function initOnlineDot() {
    const dot = document.querySelector('.dot-online');
    if (dot) dot.classList.add('dot-pulse');
  }

  function initSidebarAnim() {
    const openBtn = document.getElementById('sidebar-open-btn');
    const closeBtn = document.getElementById('sidebar-close-btn');
    const panel = document.getElementById('sidebar');
    if (!openBtn || !panel) return;

    function afterToggle() {
      openBtn.classList.toggle('icon-rotated', !panel.classList.contains('hidden'));
    }
    openBtn.addEventListener('click', () => setTimeout(afterToggle, 10));
    if (closeBtn) closeBtn.addEventListener('click', () => setTimeout(afterToggle, 10));
    afterToggle();
  }

  function initMessageObserver() {
    const chat = document.getElementById('messages');
    if (!chat) return;

    new MutationObserver((muts) => {
      for (const m of muts) {
        m.addedNodes.forEach((n) => {
          if (n.nodeType !== 1 || !n.classList.contains('message')) return;

          n.classList.add('msg-enter');
          requestAnimationFrame(() =>
            requestAnimationFrame(() => n.classList.add('msg-enter-active'))
          );
          setTimeout(() => n.classList.remove('msg-enter', 'msg-enter-active'), 400);

          const av = n.querySelector('.msg-avatar');
          if (av) {
            av.classList.add('avatar-pop');
            setTimeout(() => av.classList.remove('avatar-pop'), 350);
          }

          if (n.classList.contains('assistant') && !n.id) {
            setTimeout(() => {
              n.classList.add('msg-highlight');
              setTimeout(() => n.classList.remove('msg-highlight'), 1400);
            }, 100);
          }

          if (n.classList.contains('user')) {
            const bubble = n.querySelector('.msg-bubble');
            if (bubble) {
              bubble.classList.add('bubble-pop');
              setTimeout(() => bubble.classList.remove('bubble-pop'), 300);
            }
          }
        });
      }
    }).observe(chat, { childList: true });
  }

  function initTypingObserver() {
    const chat = document.getElementById('messages');
    if (!chat) return;

    new MutationObserver((muts) => {
      for (const m of muts) {
        m.addedNodes.forEach((n) => {
          if (n.nodeType !== 1 || n.id !== 'typing-indicator') return;
          n.classList.add('typing-enter');
          requestAnimationFrame(() =>
            requestAnimationFrame(() => n.classList.add('typing-enter-active'))
          );
        });
      }
    }).observe(chat, { childList: true });
  }

  function initSourceObserver() {
    const list = document.getElementById('sources-list');
    if (!list) return;

    new MutationObserver((muts) => {
      for (const m of muts) {
        let i = 0;
        m.addedNodes.forEach((n) => {
          if (n.nodeType !== 1 || !n.classList.contains('source-item')) return;
          n.classList.add('source-enter');
          n.style.transitionDelay = `${i * 60}ms`;
          requestAnimationFrame(() =>
            requestAnimationFrame(() => n.classList.add('source-enter-active'))
          );
          const delay = 350 + i * 60;
          setTimeout(() => {
            n.classList.remove('source-enter', 'source-enter-active');
            n.style.transitionDelay = '';
          }, delay);
          i++;
        });
      }
    }).observe(list, { childList: true, subtree: true });
  }

  function initDebugObserver() {
    const debug = document.getElementById('debug-panel');
    if (!debug) return;

    new MutationObserver(() => {
      const rows = debug.querySelectorAll('.debug-row');
      rows.forEach((row, i) => {
        row.classList.add('debug-row-enter');
        row.style.animationDelay = `${i * 30}ms`;
        setTimeout(() => {
          row.classList.remove('debug-row-enter');
          row.style.animationDelay = '';
        }, 300 + i * 30);
      });
    }).observe(debug, { childList: true });
  }

  function initStatObserver() {
    ['stat-queries', 'stat-tokens', 'stat-simple', 'stat-complex'].forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      const card = el.closest('.stat-card');
      if (!card) return;
      new MutationObserver(() => {
        card.classList.add('stat-bump');
        el.classList.add('num-flash');
        setTimeout(() => { card.classList.remove('stat-bump'); el.classList.remove('num-flash'); }, 450);
      }).observe(el, { characterData: true, childList: true, subtree: true });
    });
  }

  function initSendBurst() {
    const btn = document.getElementById('send-btn');
    if (!btn) return;
    btn.addEventListener('click', function () {
      if (this.disabled) return;
      this.classList.add('send-burst');
      setTimeout(() => this.classList.remove('send-burst'), 350);
    });
  }

  function initChipTilt() {
    document.querySelectorAll('.chip').forEach((chip) => {
      chip.addEventListener('mouseenter', function (e) {
        const rect = this.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const half = rect.width / 2;
        const tilt = ((x - half) / half) * 2;
        this.style.transform = `translateY(-1px) rotate(${tilt}deg)`;
      });
      chip.addEventListener('mouseleave', function () {
        this.style.transform = '';
      });
      chip.addEventListener('click', function () {
        this.classList.add('chip-click');
        setTimeout(() => this.classList.remove('chip-click'), 250);
      });
    });
  }

  function initClearAnim() {
    const btn = document.getElementById('clear-btn');
    if (!btn) return;
    btn.addEventListener('click', function () {
      const svg = this.querySelector('svg');
      if (svg) {
        svg.classList.add('icon-spin-once');
        setTimeout(() => svg.classList.remove('icon-spin-once'), 400);
      }
    });
  }

  function initComposerGlow() {
    const box = document.querySelector('.composer-box');
    const input = document.getElementById('query-input');
    if (!box || !input) return;
    input.addEventListener('focus', () => box.classList.add('composer-glow'));
    input.addEventListener('blur', () => box.classList.remove('composer-glow'));
  }

  function init() {
    initPageEntrance();
    initOnlineDot();
    initSidebarAnim();
    initMessageObserver();
    initTypingObserver();
    initSourceObserver();
    initDebugObserver();
    initStatObserver();
    initSendBurst();
    initChipTilt();
    initClearAnim();
    initComposerGlow();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
