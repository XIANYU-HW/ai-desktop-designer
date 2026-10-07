/* Bilingual public showcase. English HTML remains readable without JavaScript. */
(function () {
  'use strict';
  var chinese = {
  "nav-worlds": "探索主题",
  "nav-method": "设计方法",
  "hero-title": "把你想象的世界，<br>做成每天使用的桌面。",
  "hero-subtitle": "Turn a world you love into a desktop you can live in.",
  "hero-intro": "早晨，在须弥记一行灵感。深夜，在三日凌空的观测站归档最后一份文件。<br><br><strong>你给出想象，AI 把画面、动效和日常工具一起写成桌面。</strong>",
  "custom-tools": "可自定义功能",
  "cosmos-title": "三体 · 文明观测站",
  "cosmos-subtitle": "Civilization Observatory",
  "cosmos-thesis": "在不可预测的世界，留下秩序。<br>让“观测与文明延续”成为桌面的行为逻辑。",
  "screenshot-label": "Running theme / 实际运行截图",
  "cosmos-enter": "进入观测站 ",
  "cosmos-eras": "从恒纪元，到乱纪元",
  "cosmos-eras-body": "切换纪元，三日轨迹改变。指针化作观测探针，点击留下局部扰动。星空对你的介入作出回应。",
  "cosmos-stable": "恒纪元",
  "cosmos-compare": "观测对照",
  "cosmos-focus": "为注意力留一段确定时间",
  "cosmos-focus-body": "用 25 分钟专注计时建立工作节奏。钟表、天气与工具在同一座观测台上各安其位。",
  "cosmos-tools": "日常，也有文明的尺度",
  "cosmos-tools-body": "归档文件、打开资料、结束工作，化为文明归档、文明资料库与静默值守。命名有意境，功能有说明。",
  "garden-title": "原神 · 须弥知识之庭",
  "garden-thesis": "让知识生长，让日常融入风景。<br>在树城、瀑布与元素之间，设计另一种生活节奏。",
  "garden-enter": "漫步知识之庭 ",
  "garden-elements": "触碰庭院，让元素相遇",
  "garden-elements-body": "草木生长、水色绽放、雷光沿枝脉游走。不同选择带来不同回应，水光与流叶为静候时的庭院保留生机。",
  "garden-mode": "庭院",
  "garden-bloom": "绽放",
  "garden-note": "把灵感，留在林间",
  "garden-note-body": "打开金色叶印，写下便笺。卷宗、时钟与天气采用不同形态，在繁复的风景中仍然清晰可用。",
  "garden-tools": "同样的工具，全新的形态",
  "garden-tools-body": "以植物纹样、书卷与金色边饰承载归档、资料入口和收工。布局随主题重新组织。",
  "demo-note": "在线演示使用示例天气、文件与应用数据，系统按钮不操作你的电脑。计时可用；便笺仅保存在当前浏览器本地。建议在电脑浏览器体验。",
  "method-title": "主题有内核，<br>每个细节有来处。",
  "method-story": "起点是一次桌面大扫除。后来，想让按钮融入风景，让河流流动，让星空回应鼠标。一次次迭代留下的设计与交付方法，被写成了这个 Skill。<br><br>下一套世界可以完全不同：静态、摄影、像素或实用工作台，都成立。",
  "step-one": "理解世界，也理解你的工作",
  "step-one-body": "明确主题的意义、必需功能、屏幕与性能偏好。",
  "step-two": "一起设计画面、动作和工具",
  "step-two-body": "用合适的构图、素材和反馈建立联系，保留清楚的操作路径。",
  "step-three": "亲眼看，亲手试，再交付",
  "step-three-body": "实际截图、交互与临时数据测试，分别验证浏览器和桌面宿主。",
  "step-four": "保留旧主题，继续生长",
  "step-four-body": "独立主题目录、可扩展功能与可回退的操作，支持下一次灵感。",
  "start-title": "下一次，从你的想法开始。",
  "start-prompt": "“做一个深海研究站桌面。探索与记录是主题，要有待办、资料入口和专注计时，让声呐与鼠标互动。”",
  "start-body": "将 Skill 安装到 Codex 或 Claude Code，直接描述你的需求。也可以下载示例，在启动菜单中预览与换主题。",
  "start-link": "安装与使用 ↗",
  "download-link": "下载 ZIP ↓",
  "details-title": "运行方式、基础示例与创作说明",
  "details-runtime": "桌面宿主：Windows 使用 Lively，macOS 使用 Plash；Linux 可在浏览器预览。本机功能由独立 Python 助手提供。两套主展示的整理与收工会先显示确认，文件整理保留撤销记录；收工只请求正常退出，未保存文档与网页会话由应用处理。复杂输入与性能需在实际宿主验证。",
  "details-credits": "基础示例仍可体验：<a href=\"themes/ink-study/?demo=1\">墨痕书房</a> · <a href=\"themes/deep-orbit/?demo=1\">深空轨道</a> · <a href=\"themes/defrag-95/?demo=1\">磁盘整理 95</a>。主展示是原创同人演绎，与三体或原神官方无关联；轨迹与元素互动不是科学或游戏规则模拟。<a href=\"https://github.com/XIANYU-HW/ai-desktop-designer/blob/main/docs/showcase-art.md\">素材来源与生成提示</a> · <a href=\"https://github.com/XIANYU-HW/ai-desktop-designer/blob/main/docs/showcase-verification.md\">实际验证记录</a>。"
};

  var storageKey = 'ai-desktop-designer-showcase-language';
  var root = document.documentElement;
  var content = Array.from(document.querySelectorAll('[data-i18n]')).map(function (node) {
    return { node: node, key: node.dataset.i18n, english: node.innerHTML };
  });
  var attributes = [];
  ['aria', 'alt'].forEach(function (kind) {
    document.querySelectorAll('[data-zh-' + kind + ']').forEach(function (node) {
      var name = kind === 'aria' ? 'aria-label' : 'alt';
      attributes.push({node: node, name: name, english: node.getAttribute(name), chinese: node.getAttribute('data-zh-' + kind)});
    });
  });
  var englishMeta = {
    title: document.title,
    description: document.querySelector('meta[name="description"]').content,
    social: document.querySelector('meta[property="og:description"]').content
  };
  function normalize(value) {
    if (/^zh(?:-|$)/i.test(value || '')) return 'zh-CN';
    if (/^en(?:-|$)/i.test(value || '')) return 'en';
    return null;
  }
  function preference() {
    var query = normalize(new URLSearchParams(location.search).get('lang'));
    var saved = null;
    try { saved = normalize(localStorage.getItem(storageKey)); } catch (error) { /* A session-only switch still works. */ }
    var browser = (navigator.languages && navigator.languages[0]) || navigator.language;
    return query || saved || normalize(browser) || 'en';
  }
  function apply(language) {
    var zh = language === 'zh-CN';
    root.lang = language;
    content.forEach(function (entry) {
      entry.node.innerHTML = zh ? chinese[entry.key] : entry.english;
    });
    attributes.forEach(function (entry) { entry.node.setAttribute(entry.name, zh ? entry.chinese : entry.english); });
    document.title = zh ? 'AI Desktop Designer · 让桌面成为一个世界' : englishMeta.title;
    document.querySelector('meta[property="og:title"]').content = document.title;
    document.querySelector('meta[name="description"]').content = zh
      ? 'AI Desktop Designer：把你想象的世界，做成每天使用的桌面。探索三体文明观测站与原神须弥知识之庭，体验融合场景、动效和实用功能的 AI 桌面设计 Skill。'
      : englishMeta.description;
    document.querySelector('meta[property="og:description"]').content = zh
      ? '三体的观测与秩序，须弥的知识与生长。两套可以亲手操作的桌面世界。' : englishMeta.social;
    document.querySelector('meta[property="og:image"]').content = 'https://xianyu-hw.github.io/ai-desktop-designer/' + (zh ? 'themes/genshin-sumeru/preview.png' : 'docs/showcase/genshin-en.png');
    document.querySelectorAll('[data-set-lang]').forEach(function (button) {
      button.setAttribute('aria-pressed', String(button.dataset.setLang === language));
    });
    document.querySelectorAll('a[href^="themes/"]').forEach(function (link) {
      var url = new URL(link.getAttribute('href'), location.href);
      url.searchParams.set('lang', language);
      link.href = url.href;
      // Keep the paths relative so repeat switches can update them again.
      link.setAttribute('href', 'themes/' + url.pathname.split('/themes/')[1] + url.search + url.hash);
    });
    document.querySelector('[data-install-link]').href = zh
      ? 'https://github.com/XIANYU-HW/ai-desktop-designer/blob/main/README.zh-CN.md#开始使用'
      : 'https://github.com/XIANYU-HW/ai-desktop-designer#get-started';
    document.querySelectorAll('[data-image]').forEach(function (button) {
      button.dataset.src = zh ? button.dataset.srcZh : button.dataset.srcEn;
      if (button.getAttribute('aria-pressed') === 'true') {
        document.getElementById(button.dataset.image).src = button.dataset.src;
      }
    });
  }
  document.querySelectorAll('[data-set-lang]').forEach(function (button) {
    button.addEventListener('click', function () {
      var language = button.dataset.setLang;
      try { localStorage.setItem(storageKey, language); } catch (error) { /* Storage may be disabled. */ }
      // The URL preserves an explicit choice on refresh and when shared, even without storage.
      try {
        var url = new URL(location.href);
        url.searchParams.set('lang', language);
        history.replaceState(null, '', url.href);
      } catch (error) { /* Language controls also work in a local-file preview. */ }
      apply(language);
    });
  });
  document.querySelectorAll('[data-image]').forEach(function (button) {
    button.addEventListener('click', function () {
      document.getElementById(button.dataset.image).src = button.dataset.src;
      button.parentElement.querySelectorAll('button').forEach(function (peer) {
        peer.setAttribute('aria-pressed', String(peer === button));
      });
    });
  });
  apply(preference());
})();
