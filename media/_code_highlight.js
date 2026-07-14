(function () {
  "use strict";

  var HLJS_LIGHT = "_hljs_github.min.css";
  var HLJS_DARK = "_hljs_github-dark.min.css";

  function isDark() {
    return (
      document.body.classList.contains("nightMode") ||
      document.documentElement.classList.contains("nightMode") ||
      !!document.querySelector(".nightMode.card") ||
      window.matchMedia("(prefers-color-scheme: dark)").matches
    );
  }

  function loadTheme() {
    var href = isDark() ? HLJS_DARK : HLJS_LIGHT;
    if (document.querySelector('link[data-hljs-theme="' + href + '"]')) {
      return;
    }
    document.querySelectorAll("link[data-hljs-theme]").forEach(function (el) {
      el.remove();
    });
    var link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = href;
    link.setAttribute("data-hljs-theme", href);
    document.head.appendChild(link);
  }

  function pickLanguage(codeEl, preEl) {
    var from = [codeEl, preEl];
    for (var i = 0; i < from.length; i++) {
      var el = from[i];
      if (!el || !el.classList) continue;
      for (var j = 0; j < el.classList.length; j++) {
        var cls = el.classList[j];
        if (cls.indexOf("language-") === 0) {
          return cls.slice(9);
        }
      }
    }
    return null;
  }

  function normalizeBlocks(root) {
    root.querySelectorAll("pre").forEach(function (pre) {
      var code = pre.querySelector("code");
      if (!code) {
        code = document.createElement("code");
        code.textContent = pre.textContent;
        pre.textContent = "";
        pre.appendChild(code);
      }
      if (!pickLanguage(code, pre) && pre.className && !code.className) {
        code.className = pre.className;
      }
    });
  }

  function setLangLabel(pre, lang) {
    if (!lang || !pre) return;
    pre.setAttribute("data-lang", lang);
    pre.classList.add("language-" + lang);
  }

  function highlight(root) {
    if (typeof hljs === "undefined") return;
    normalizeBlocks(root);
    root.querySelectorAll("pre code").forEach(function (code) {
      if (code.classList.contains("hljs")) return;
      var pre = code.parentElement;
      var lang = pickLanguage(code, pre);
      if (lang && hljs.getLanguage(lang)) {
        code.classList.add("language-" + lang);
        hljs.highlightElement(code);
        setLangLabel(pre, lang);
        return;
      }
      var result = hljs.highlightAuto(code.textContent);
      code.innerHTML = result.value;
      code.classList.add("hljs");
      if (result.language) {
        code.classList.add("language-" + result.language);
        setLangLabel(pre, result.language);
      } else if (lang) {
        setLangLabel(pre, lang);
      }
    });
  }

  function run() {
    loadTheme();
    var roots = document.querySelectorAll(".card-box");
    if (!roots.length) {
      highlight(document.body);
      return;
    }
    roots.forEach(highlight);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
