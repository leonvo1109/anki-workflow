(function () {
  function htmlToPlain(html) {
    var normalized = html
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/(div|p|li|tr|h[1-6]|blockquote)>/gi, "\n")
      .replace(/<(div|p|li|tr|h[1-6]|blockquote)[^>]*>/gi, "");

    var tmp = document.createElement("div");
    tmp.innerHTML = normalized;
    return (tmp.textContent || "").replace(/\u00a0/g, " ");
  }

  function normalizeMermaid(text) {
    return text
      .replace(/\u2014/g, " --- ")
      .replace(/\u2013/g, " -- ")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n[ \t]+/g, "\n")
      .replace(/[ \t]{2,}/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function clozePlaceholder(index) {
    return "C" + index + '[" "]';
  }

  function clozeInsideLabel(node, root) {
    var html = root.innerHTML;
    var nodeHtml = node.outerHTML;
    var pos = html.indexOf(nodeHtml);
    if (pos < 0) return false;
    var before = html.slice(0, pos);
    var quotes = (before.match(/"/g) || []).length;
    return quotes % 2 === 1;
  }

  function clozeHtmlToMermaid(el) {
    var root = el.cloneNode(true);
    var clozeIndex = 0;

    root.querySelectorAll(".cloze-inactive").forEach(function (node) {
      node.replaceWith(document.createTextNode(node.textContent || ""));
    });

    root.querySelectorAll(".cloze").forEach(function (node) {
      if (clozeInsideLabel(node, root)) {
        node.replaceWith(document.createTextNode("…"));
      } else {
        clozeIndex += 1;
        node.replaceWith(document.createTextNode(clozePlaceholder(clozeIndex)));
      }
    });

    var text = normalizeMermaid(htmlToPlain(root.innerHTML));
    text = text.replace(/\[...\]/g, function () {
      clozeIndex += 1;
      return clozePlaceholder(clozeIndex);
    });
    return text;
  }

  function hasContent(el) {
    return !!normalizeMermaid(htmlToPlain(el.innerHTML));
  }

  function readSource() {
    var clozeEl = document.getElementById("mermaid-src-cloze");
    var rawEl =
      document.getElementById("mermaid-src-raw") ||
      document.getElementById("mermaid-src-fallback") ||
      document.getElementById("mermaid-src");

    if (clozeEl && hasContent(clozeEl)) {
      return clozeHtmlToMermaid(clozeEl);
    }
    if (rawEl && hasContent(rawEl)) {
      return normalizeMermaid(htmlToPlain(rawEl.innerHTML));
    }
    return "";
  }

  function hidePlainFallback() {
    var plain = document.querySelector(".mermaid-plain");
    if (plain) plain.style.display = "none";
  }

  function showPlainFallback() {
    var plain = document.querySelector(".mermaid-plain");
    if (plain) plain.style.display = "block";
  }

  async function mermaidToSvg(renderId, source) {
    if (typeof mermaid.renderAsync === "function") {
      return await mermaid.renderAsync(renderId, source);
    }
    return mermaid.render(renderId, source);
  }

  function svgFromResult(result) {
    if (typeof result === "string") return result;
    if (result && typeof result.svg === "string") return result.svg;
    return "";
  }

  async function renderDiagram() {
    var outEl = document.getElementById("mermaid-out");
    if (!outEl) return;

    outEl.innerHTML = "";
    var source = readSource();

    if (!source) {
      outEl.textContent = "(Kein Mermaid-Code im Feld Text)";
      showPlainFallback();
      return;
    }

    if (typeof mermaid === "undefined") {
      outEl.textContent = "Mermaid-Bibliothek (_mermaid.min.js) nicht geladen.";
      showPlainFallback();
      return;
    }

    var isDark =
      document.body.classList.contains("nightMode") ||
      window.matchMedia("(prefers-color-scheme: dark)").matches;

    mermaid.initialize({
      startOnLoad: false,
      theme: isDark ? "dark" : "default",
      securityLevel: "loose",
    });

    var renderId = "mmd-" + Math.random().toString(36).slice(2);
    try {
      var result = await mermaidToSvg(renderId, source);
      var svg = svgFromResult(result);
      if (!svg) {
        outEl.textContent = "Mermaid hat kein SVG zurückgegeben.";
        showPlainFallback();
        return;
      }
      outEl.innerHTML = svg;
      hidePlainFallback();
      if (result && typeof result.bindFunctions === "function") {
        result.bindFunctions(outEl);
      }
    } catch (err) {
      outEl.innerHTML =
        '<pre class="mermaid-err">' +
        source.replace(/</g, "&lt;") +
        "\n\n— " +
        String(err.message || err).replace(/</g, "&lt;") +
        "</pre>";
      showPlainFallback();
    }
  }

  function waitForMermaid(retries, cb) {
    if (typeof mermaid !== "undefined") {
      cb();
      return;
    }
    if (retries >= 30) {
      cb();
      return;
    }
    setTimeout(function () {
      waitForMermaid(retries + 1, cb);
    }, 100);
  }

  function boot() {
    waitForMermaid(0, function () {
      renderDiagram().catch(function (err) {
        var out = document.getElementById("mermaid-out");
        if (out) out.textContent = "Mermaid-Fehler: " + String(err.message || err);
        showPlainFallback();
      });
    });
  }

  if (typeof onUpdateHook !== "undefined") {
    onUpdateHook.push(boot);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    setTimeout(boot, 50);
  }
})();
