/* Static starter: choose the scene and requested functions before adding motion. */
(function () {
  'use strict';
  var root = document.documentElement;
  var zh = Orbit.lang === 'zh';
  root.lang = zh ? 'zh-CN' : 'en';
  if (!zh) {
    document.querySelectorAll('[data-en]').forEach(function (el) { el.textContent = el.getAttribute('data-en'); });
    document.querySelectorAll('[data-en-clock]').forEach(function (el) { el.setAttribute('data-orbit-clock', el.getAttribute('data-en-clock')); });
    document.querySelectorAll('[data-en-label]').forEach(function (el) { el.setAttribute('aria-label', el.getAttribute('data-en-label')); });
  }

  // Review fixtures affect presentation only. Do not run actions to create a screenshot state.
  // Add state cases for actual features and list them in theme.json review.states.
  function applyReviewState() {
    var state = new URLSearchParams(location.search).get('review-state');
    if (!Orbit.demo || !state) return;
    var status = document.querySelector('[data-orbit-status]');
    if (state === 'empty') {
      document.querySelectorAll('[data-orbit-weather]').forEach(function (el) {
        el.textContent = '';
        el.setAttribute('data-orbit-empty', '');
      });
      status.textContent = Orbit.t('暂无天气数据（预览）', 'No weather data (preview)');
    } else if (state === 'offline') {
      root.setAttribute('data-orbit-connection', 'offline');
      status.textContent = Orbit.t('桌面服务离线 · 此处保留示例数据（预览）', 'Desktop service offline · sample data retained (preview)');
    } else {
      console.error('Unsupported review-state: ' + state);
      return;
    }
    // The review records this declaration; also inspect the actual image and expected content.
    root.setAttribute('data-review-state', state);
  }
  Orbit.ready.then(applyReviewState);
})();
