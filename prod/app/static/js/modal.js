// CFF reusable modal — vanilla, dependency-free.
// window.openModal({title, bodyHtml, footerButtons:[{label, kind, onClick}]})
// returns {close}. Backdrop, Esc, click-outside, body-scroll lock.
(function () {
  if (window.openModal) return;
  var styled = false;
  function inject() {
    if (styled) return; styled = true;
    var s = document.createElement("style");
    s.textContent =
      ".cff-modal-backdrop{position:fixed;inset:0;background:rgba(0,0,0,0.4);z-index:1000;display:flex;align-items:center;justify-content:center;opacity:0;transition:opacity 160ms ease;}" +
      ".cff-modal-backdrop.show{opacity:1;}" +
      ".cff-modal-card{background:#fff;border-radius:16px;max-width:1100px;width:92%;max-height:85vh;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 24px 48px rgba(0,0,0,0.25);transform:translateY(8px) scale(0.99);transition:transform 160ms ease;}" +
      ".cff-modal-backdrop.show .cff-modal-card{transform:translateY(0) scale(1);}" +
      ".cff-modal-head{display:flex;align-items:center;justify-content:space-between;padding:1rem 1.25rem;border-bottom:1px solid rgba(0,0,0,0.075);}" +
      ".cff-modal-head h3{margin:0;font:600 15px/1.3 -apple-system,BlinkMacSystemFont,'SF Pro Text',Helvetica,sans-serif;color:#000;}" +
      ".cff-modal-close{background:none;border:none;cursor:pointer;font-size:22px;line-height:1;color:#858587;padding:4px 8px;}" +
      ".cff-modal-close:hover{color:#000;}" +
      ".cff-modal-body{padding:1rem 1.25rem;overflow:auto;flex:1;font:400 13px/1.5 -apple-system,BlinkMacSystemFont,'SF Pro Text',Helvetica,sans-serif;color:#000;}" +
      ".cff-modal-body pre{background:#1d1d1f;color:#f5f5f7;padding:0.85rem;border-radius:12px;font:11px/1.4 ui-monospace,Menlo,monospace;white-space:pre-wrap;max-height:60vh;overflow:auto;margin:0;}" +
      ".cff-modal-foot{padding:0.75rem 1.25rem;border-top:1px solid rgba(0,0,0,0.075);display:flex;gap:0.5rem;justify-content:flex-end;}" +
      ".cff-modal-btn{display:inline-block;padding:0.4rem 0.9rem;border-radius:100vh;font:500 13px/1.2 inherit;border:1px solid rgba(0,0,0,0.075);cursor:pointer;background:#fff;color:#000;}" +
      ".cff-modal-btn:hover{filter:brightness(0.97);}" +
      ".cff-modal-btn-primary{background:#E08A3C;color:#fff;border-color:rgba(0,0,0,0.1);}" +
      ".cff-modal-btn-danger{background:rgb(254,112,112);color:#fff;border-color:rgba(0,0,0,0.1);}";
    document.head.appendChild(s);
  }
  function open(opts) {
    inject();
    opts = opts || {};
    var prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    var bd = document.createElement("div");
    bd.className = "cff-modal-backdrop";
    var card = document.createElement("div"); card.className = "cff-modal-card";
    var head = document.createElement("div"); head.className = "cff-modal-head";
    var h3 = document.createElement("h3"); h3.textContent = opts.title || "";
    var x = document.createElement("button"); x.className = "cff-modal-close"; x.type = "button"; x.innerHTML = "&times;"; x.setAttribute("aria-label", "Close");
    head.appendChild(h3); head.appendChild(x);
    var body = document.createElement("div"); body.className = "cff-modal-body";
    if (opts.bodyHtml != null) body.innerHTML = opts.bodyHtml;
    card.appendChild(head); card.appendChild(body);
    var handle = { close: closeNow };
    if (Array.isArray(opts.footerButtons) && opts.footerButtons.length) {
      var foot = document.createElement("div"); foot.className = "cff-modal-foot";
      opts.footerButtons.forEach(function (b) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "cff-modal-btn" + (b.kind === "primary" ? " cff-modal-btn-primary" : b.kind === "danger" ? " cff-modal-btn-danger" : "");
        btn.textContent = b.label || "";
        btn.addEventListener("click", function () { if (typeof b.onClick === "function") b.onClick(handle); });
        foot.appendChild(btn);
      });
      card.appendChild(foot);
    }
    bd.appendChild(card); document.body.appendChild(bd);
    requestAnimationFrame(function () { bd.classList.add("show"); });
    function closeNow() {
      if (!bd.parentNode) return;
      bd.classList.remove("show");
      document.removeEventListener("keydown", onKey);
      setTimeout(function () {
        if (bd.parentNode) bd.parentNode.removeChild(bd);
        document.body.style.overflow = prevOverflow;
      }, 180);
    }
    function onKey(e) { if (e.key === "Escape") closeNow(); }
    bd.addEventListener("click", function (e) { if (e.target === bd) closeNow(); });
    x.addEventListener("click", closeNow);
    document.addEventListener("keydown", onKey);
    return handle;
  }
  window.openModal = open;
})();
