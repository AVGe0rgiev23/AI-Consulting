(function () {
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function easeOut(t) { return 1 - Math.pow(1 - t, 3); }

  function countUp(el) {
    var node = el.firstChild;
    if (!node || node.nodeType !== 3) return;
    var raw = node.textContent.trim();
    var target = parseFloat(raw);
    if (isNaN(target)) return;
    if (reduced || target === 0) return;
    var decimals = (raw.split(".")[1] || "").length;
    var dur = 900, start = null;
    function frame(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      node.textContent = (target * easeOut(p)).toFixed(decimals);
      if (p < 1) requestAnimationFrame(frame);
      else node.textContent = raw;
    }
    node.textContent = (0).toFixed(decimals);
    requestAnimationFrame(frame);
  }

  function sweepGauges() {
    if (reduced) return;
    document.querySelectorAll(".gauge").forEach(function (g) {
      var final = g.style.getPropertyValue("--score");
      if (!final) return;
      g.style.setProperty("--score", 0);
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { g.style.setProperty("--score", final); });
      });
    });
  }

  function loadingButtons() {
    document.querySelectorAll("form[method=post]").forEach(function (f) {
      f.addEventListener("submit", function () {
        var btn = f.querySelector("button:not(.ghost)") || f.querySelector("button");
        if (!btn) return;
        btn.classList.add("loading");
        setTimeout(function () { btn.disabled = true; }, 0);
      });
    });
  }

  var PALETTE = [
    { label: "Overview", hint: "Dashboard & activity", href: "/" },
    { label: "Lead Lists", hint: "Upload & manage lists", href: "/lists" },
    { label: "Exports", hint: "Download or push campaigns", href: "/exports" },
    { label: "Analytics", hint: "Funnel & hypothesis leaderboard", href: "/analytics" },
    { label: "Audit Reports", hint: "White-label opportunity audits", href: "/audit" },
    { label: "Offer Profile", hint: "What you sell & proof point", href: "/onboarding" },
    { label: "Prompt Library", hint: "Edit every AI prompt", href: "/prompts" },
    { label: "Team", hint: "Seats, roles & invites", href: "/team" },
    { label: "Billing", hint: "Plan, credits & history", href: "/billing" },
    { label: "Settings", hint: "White-label & API keys", href: "/settings" },
    { label: "Toggle theme", hint: "Switch dark / light", action: "theme" },
    { label: "Log out", hint: "End this session", href: "/logout" }
  ];

  var cmdk, cmdkInput, cmdkList, cmdkItems = [], cmdkIndex = 0;

  function buildPalette() {
    cmdk = document.createElement("div");
    cmdk.className = "cmdk";
    cmdk.innerHTML =
      '<div class="cmdk-backdrop"></div>' +
      '<div class="cmdk-panel" role="dialog" aria-label="Command palette">' +
      '<input class="cmdk-input" type="text" placeholder="Where to?" spellcheck="false">' +
      '<div class="cmdk-list"></div>' +
      '<div class="cmdk-foot"><span><b class="kbd">&uarr;&darr;</b> navigate</span>' +
      '<span><b class="kbd">&crarr;</b> open</span><span><b class="kbd">esc</b> close</span></div>' +
      "</div>";
    document.body.appendChild(cmdk);
    cmdkInput = cmdk.querySelector(".cmdk-input");
    cmdkList = cmdk.querySelector(".cmdk-list");
    cmdk.querySelector(".cmdk-backdrop").addEventListener("click", closePalette);
    cmdkInput.addEventListener("input", function () { renderPalette(cmdkInput.value); });
    cmdkInput.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); movePalette(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); movePalette(-1); }
      else if (e.key === "Enter") { e.preventDefault(); runPalette(); }
    });
    renderPalette("");
  }

  function renderPalette(q) {
    q = q.toLowerCase().trim();
    cmdkItems = PALETTE.filter(function (it) {
      return !q || it.label.toLowerCase().indexOf(q) > -1 || it.hint.toLowerCase().indexOf(q) > -1;
    });
    cmdkIndex = 0;
    if (!cmdkItems.length) {
      cmdkList.innerHTML = '<div class="cmdk-empty">Nothing matches.</div>';
      return;
    }
    cmdkList.innerHTML = cmdkItems.map(function (it, i) {
      return '<div class="cmdk-item' + (i === 0 ? " active" : "") + '" data-i="' + i + '">' +
        "<b>" + it.label + "</b><span>" + it.hint + "</span></div>";
    }).join("");
    Array.prototype.forEach.call(cmdkList.children, function (el) {
      el.addEventListener("mouseenter", function () { setActive(parseInt(el.dataset.i, 10)); });
      el.addEventListener("click", runPalette);
    });
  }

  function setActive(i) {
    cmdkIndex = i;
    Array.prototype.forEach.call(cmdkList.children, function (el, j) {
      el.classList.toggle("active", j === i);
    });
  }

  function movePalette(d) {
    if (!cmdkItems.length) return;
    var i = (cmdkIndex + d + cmdkItems.length) % cmdkItems.length;
    setActive(i);
    var el = cmdkList.children[i];
    if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest" });
  }

  function runPalette() {
    var it = cmdkItems[cmdkIndex];
    if (!it) return;
    closePalette();
    if (it.action === "theme" && window.toggleTheme) window.toggleTheme();
    else if (it.href) window.location.href = it.href;
  }

  function openPalette() {
    if (!cmdk) buildPalette();
    cmdk.classList.add("open");
    cmdkInput.value = "";
    renderPalette("");
    cmdkInput.focus();
  }

  function closePalette() {
    if (cmdk) cmdk.classList.remove("open");
  }

  function isTyping(e) {
    var t = e.target;
    return t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
  }

  function hotkeys() {
    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (cmdk && cmdk.classList.contains("open")) closePalette(); else openPalette();
        return;
      }
      if (e.key === "Escape") { closePalette(); return; }
      if (isTyping(e) || e.ctrlKey || e.metaKey || e.altKey) return;
      if (cmdk && cmdk.classList.contains("open")) return;

      var k = e.key.toLowerCase();
      if (k === "a") submitIf("#hk-approve");
      else if (k === "r") submitIf("#hk-regen");
      else if (k === "e") focusIf("#hk-editor");
      else if (e.key === "ArrowRight") clickIf("#hk-next");
      else if (e.key === "ArrowLeft") clickIf("#hk-prev");
    });
  }

  function submitIf(sel) {
    var el = document.querySelector(sel);
    if (el) { e_flash(el); el.submit ? el.submit() : el.closest("form").submit(); }
  }
  function clickIf(sel) {
    var el = document.querySelector(sel);
    if (el) el.click();
  }
  function focusIf(sel) {
    var el = document.querySelector(sel);
    if (el) { el.focus(); el.setSelectionRange && el.setSelectionRange(el.value.length, el.value.length); }
  }
  function e_flash(el) {
    var btn = el.querySelector ? el.querySelector("button") : null;
    if (btn) btn.classList.add("loading");
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-count]").forEach(countUp);
    sweepGauges();
    loadingButtons();
    hotkeys();
    var trigger = document.getElementById("cmdk-trigger");
    if (trigger) trigger.addEventListener("click", openPalette);
  });
})();
