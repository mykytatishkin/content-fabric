// CFF toast — minimal, dependency-free.
// Exposes window.toast(msg, kind?). kinds: success | error | info | warning.
(function () {
  if (window.toast) return;
  var styled = false, container = null;
  var COLORS = {
    success: { bg: "#1a8f2d", fg: "#fff" },
    error:   { bg: "#c0392b", fg: "#fff" },
    warning: { bg: "#8a7a00", fg: "#fff" },
    info:    { bg: "#2b60a0", fg: "#fff" }
  };
  function inject() {
    if (styled) return; styled = true;
    var s = document.createElement("style");
    s.textContent =
      "#toast-container{position:fixed;bottom:16px;right:16px;display:flex;flex-direction:column;gap:8px;z-index:9999;pointer-events:none;max-width:90vw;}" +
      ".toast{pointer-events:auto;padding:10px 14px;border-radius:12px;font:500 13px/1.4 -apple-system,BlinkMacSystemFont,'SF Pro Text',Helvetica,sans-serif;color:#fff;background:#2b60a0;box-shadow:0 8px 24px rgba(0,0,0,0.18);min-width:240px;max-width:420px;opacity:0;transform:translateY(12px);transition:opacity 180ms ease,transform 180ms ease;cursor:pointer;word-wrap:break-word;}" +
      ".toast.show{opacity:1;transform:translateY(0);}" +
      ".toast-success{background:#1a8f2d;}.toast-error{background:#c0392b;}.toast-warning{background:#8a7a00;}.toast-info{background:#2b60a0;}";
    document.head.appendChild(s);
  }
  function ensureContainer() {
    if (container && document.body.contains(container)) return container;
    container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      document.body.appendChild(container);
    }
    return container;
  }
  function show(msg, kind) {
    inject();
    var k = COLORS[kind] ? kind : "info";
    var box = ensureContainer();
    var el = document.createElement("div");
    el.className = "toast toast-" + k;
    el.textContent = String(msg == null ? "" : msg);
    el.setAttribute("role", k === "error" ? "alert" : "status");
    box.appendChild(el);
    requestAnimationFrame(function () { el.classList.add("show"); });
    var timer = setTimeout(close, 4000);
    function close() {
      clearTimeout(timer);
      el.classList.remove("show");
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 220);
    }
    el.addEventListener("click", close);
    return { close: close };
  }
  window.toast = show;
})();
