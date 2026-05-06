package main

const indexHTML = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0b0d10">
<title>Screen Studio Recording Status</title>
<style>
  :root {
    color-scheme: dark;
    --bg: #0b0d10;
    --panel: #14181d;
    --panel-2: #1a1f26;
    --border: #232a33;
    --text: #e7ecf2;
    --muted: #8a96a3;
    --accent: #5cc8ff;
    --rec: #ff4d4f;
    --rec-bg: #2a0e10;
    --prep: #f0b429;
    --idle: #555f6b;
    --ok: #3ddc84;
    --err: #ff7676;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0;
    background: var(--bg); color: var(--text);
    font: 16px/1.45 -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif;
    min-height: 100vh;
  }
  body {
    padding: max(env(safe-area-inset-top), 16px) 16px max(env(safe-area-inset-bottom), 16px);
    max-width: 760px; margin: 0 auto;
  }
  header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 4px 0 14px; gap: 12px;
  }
  h1 { margin: 0; font-size: 18px; font-weight: 600; letter-spacing: 0.2px; }
  .conn { font-size: 12px; color: var(--muted); display: flex; align-items: center; gap: 6px; }
  .conn .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--ok); box-shadow: 0 0 8px rgba(61,220,132,0.6); }
  .conn.stale .dot { background: var(--err); box-shadow: none; }

  .card {
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 14px; padding: 18px; margin-bottom: 14px;
  }
  .phase-card {
    display: flex; flex-direction: column; gap: 10px;
    padding: 22px; border-radius: 18px;
  }
  .phase-row { display: flex; align-items: center; gap: 14px; }
  .badge {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 8px 14px; border-radius: 999px;
    font-weight: 600; font-size: 14px; letter-spacing: 0.3px;
    text-transform: uppercase;
    background: var(--panel-2); color: var(--text); border: 1px solid var(--border);
  }
  .badge .pulse {
    width: 10px; height: 10px; border-radius: 50%;
    background: currentColor;
  }
  body[data-phase="recording"] .phase-card {
    background: linear-gradient(180deg, var(--rec-bg), var(--panel));
    border-color: var(--rec);
  }
  body[data-phase="recording"] .badge { color: var(--rec); border-color: var(--rec); }
  body[data-phase="recording"] .badge .pulse { animation: pulse 1.1s ease-out infinite; }
  body[data-phase="preparing"] .badge { color: var(--prep); border-color: var(--prep); }
  body[data-phase="stopped"] .badge { color: var(--ok); border-color: var(--ok); }
  body[data-phase="error"] .badge { color: var(--err); border-color: var(--err); }
  body[data-phase="idle"] .badge { color: var(--idle); }

  @keyframes pulse {
    0%   { transform: scale(1);   opacity: 1; }
    70%  { transform: scale(2.2); opacity: 0; }
    100% { transform: scale(2.2); opacity: 0; }
  }

  .elapsed {
    font-variant-numeric: tabular-nums;
    font-size: 38px; font-weight: 700; letter-spacing: 0.5px;
    line-height: 1.1;
  }
  body[data-phase="recording"] .elapsed { color: var(--rec); }

  .meta { display: grid; grid-template-columns: auto 1fr; gap: 4px 14px; font-size: 14px; }
  .meta dt { color: var(--muted); }
  .meta dd { margin: 0; word-break: break-word; }

  .action {
    font-size: 17px; line-height: 1.4;
    padding: 14px 16px; background: var(--panel-2); border: 1px solid var(--border);
    border-radius: 10px; margin-top: 4px;
    min-height: 50px;
  }
  .action.empty { color: var(--muted); }

  h2 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.6px;
       color: var(--muted); margin: 0 0 8px; font-weight: 600; }

  ul.log { list-style: none; padding: 0; margin: 0; max-height: 360px; overflow: auto; }
  ul.log li {
    padding: 8px 0; border-top: 1px solid var(--border);
    display: grid; grid-template-columns: 76px 1fr; gap: 10px; font-size: 14px;
  }
  ul.log li:first-child { border-top: 0; }
  ul.log time { color: var(--muted); font-variant-numeric: tabular-nums; }

  .note-form { display: flex; flex-direction: column; gap: 10px; }
  .note-form textarea {
    width: 100%; min-height: 72px; resize: vertical;
    background: var(--panel-2); color: var(--text);
    border: 1px solid var(--border); border-radius: 10px;
    padding: 12px 14px; font: inherit; line-height: 1.4;
  }
  .note-form textarea:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
  .note-form .row { display: flex; gap: 10px; align-items: center; justify-content: space-between; }
  .note-form .hint { color: var(--muted); font-size: 12px; }
  .note-form button {
    padding: 10px 18px; font: inherit; font-weight: 600;
    background: var(--accent); color: var(--bg); border: 0; border-radius: 8px;
    cursor: pointer;
  }
  .note-form button[disabled] { opacity: 0.5; cursor: not-allowed; }
  .note-form button:hover:not([disabled]) { filter: brightness(1.1); }
  .note-form .status { font-size: 12px; color: var(--muted); min-height: 16px; }
  .note-form .status.ok { color: var(--ok); }
  .note-form .status.err { color: var(--err); }

  ul.notes { list-style: none; padding: 0; margin: 0; max-height: 280px; overflow: auto; }
  ul.notes li {
    padding: 10px 0; border-top: 1px solid var(--border);
    font-size: 14px;
  }
  ul.notes li:first-child { border-top: 0; }
  ul.notes .note-meta { color: var(--muted); font-size: 12px; margin-bottom: 4px; font-variant-numeric: tabular-nums; }
  ul.notes .note-text { white-space: pre-wrap; word-break: break-word; }

  .reachable { display: flex; flex-direction: column; gap: 14px; align-items: center; }
  .reachable .qr-wrap {
    background: #fff; padding: 10px; border-radius: 12px;
    line-height: 0;
  }
  .reachable .qr-wrap img { display: block; width: 200px; height: 200px; }
  .reachable dl {
    width: 100%;
    display: grid; grid-template-columns: auto 1fr; gap: 8px 14px;
    margin: 0; font-size: 14px; align-items: center;
  }
  .reachable dt { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.4px; }
  .reachable dd { margin: 0; word-break: break-all; }
  .reachable .pin {
    font: 700 22px/1 ui-monospace, "SF Mono", Menlo, monospace;
    letter-spacing: 6px; color: var(--accent);
    font-variant-numeric: tabular-nums;
  }
  .reachable code {
    color: var(--text); background: var(--panel-2);
    padding: 4px 8px; border-radius: 4px;
    font-size: 13px; word-break: break-all;
  }

  .hidden { display: none !important; }
</style>
</head>
<body data-phase="idle">

<header>
  <h1>Screen Studio</h1>
  <div class="conn" id="conn"><span class="dot"></span><span id="conn-text">live</span></div>
</header>

<section class="card phase-card">
  <div class="phase-row">
    <span class="badge"><span class="pulse"></span><span id="phase-label">idle</span></span>
    <div class="elapsed" id="elapsed">--:--</div>
  </div>
  <div class="action empty" id="action">Waiting for status&hellip;</div>
  <dl class="meta" id="meta">
    <dt>Project</dt><dd id="project">&mdash;</dd>
    <dt>Updated</dt><dd id="updated">&mdash;</dd>
    <dt class="note-dt hidden">Note</dt><dd class="note-dd hidden" id="note"></dd>
  </dl>
</section>

<section class="card">
  <h2>Send a note to {{AGENT}}</h2>
  <form class="note-form" id="note-form">
    <textarea id="note-text" maxlength="1000" placeholder="Type a note for {{AGENT}}&hellip;"></textarea>
    <div class="row">
      <span class="hint">Notes are seen between scripted actions, but answered after the take stops to avoid disrupting the recording.</span>
      <button type="submit" id="note-send">Send</button>
    </div>
    <div class="status" id="note-status"></div>
  </form>
</section>

<section class="card">
  <h2>Your sent notes</h2>
  <ul class="notes" id="notes-list"><li class="empty" style="color:var(--muted)">none yet</li></ul>
</section>

<section class="card">
  <h2>Recent actions</h2>
  <ul class="log" id="log"><li class="empty"><time></time><span style="color:var(--muted)">none yet</span></li></ul>
</section>

<section class="card">
  <h2>Open on your phone</h2>
  <div class="reachable">
    <div class="qr-wrap"><img src="/api/qr.png" alt="QR code linking to this page"></div>
    <dl>
      <dt>PIN</dt>
      <dd class="pin">{{PIN}}</dd>
      <dt class="bonjour-dt hidden">Bonjour</dt>
      <dd class="bonjour-dd hidden"><code id="bonjour-url"></code></dd>
      <dt class="lan-dt hidden">LAN IP</dt>
      <dd class="lan-dd hidden"><code id="lan-url"></code></dd>
    </dl>
  </div>
</section>

<script>
(function() {
  // --- PIN handoff: if ?pin=... is in the URL, the server sets a cookie
  // for us. Once that's done, strip it from the URL so it doesn't leak
  // via screenshots, referrers, or "share this page".
  (function stripPinFromUrl() {
    const u = new URL(window.location.href);
    if (u.searchParams.has("pin")) {
      u.searchParams.delete("pin");
      window.history.replaceState({}, "", u.pathname + (u.search || "") + (u.hash || ""));
    }
  })();

  // --- Demo notes: ?demo=1 pre-populates sessionStorage with sample notes
  // for documentation screenshots. No-op once the user actually sends a real
  // note (sessionStorage is keyed by browser session). Strips ?demo from URL.
  (function maybeSeedDemo() {
    const u = new URL(window.location.href);
    if (!u.searchParams.has("demo")) return;
    u.searchParams.delete("demo");
    window.history.replaceState({}, "", u.pathname + (u.search || "") + (u.hash || ""));
    if (sessionStorage.getItem("ss_notes")) return;
    const t1 = new Date(Date.now() - 60000).toISOString();
    const t2 = new Date(Date.now() - 18000).toISOString();
    sessionStorage.setItem("ss_notes", JSON.stringify([
      { id: 1, at: t1, offset_ms: 27000, text: "The cursor moved too fast across the search box — could we slow it down for a retake?" },
      { id: 2, at: t2, offset_ms: 72000, text: "Did the email confirmation toast render before I clicked Next?" }
    ]));
  })();

  const $  = (id) => document.getElementById(id);
  const fmtClock = (ms) => {
    if (ms < 0 || !isFinite(ms)) return "--:--";
    const s = Math.floor(ms / 1000);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    const pad = (n) => String(n).padStart(2, "0");
    return h > 0 ? h + ":" + pad(m) + ":" + pad(sec) : pad(m) + ":" + pad(sec);
  };
  const fmtTime = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d)) return "—";
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  };
  const fmtOffset = (ms) => {
    if (ms == null || ms < 0) return "before take";
    const s = Math.floor(ms / 1000);
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return "+" + m + ":" + String(sec).padStart(2, "0") + " into take";
  };
  const escapeHTML = (s) => String(s).replace(/[<>&"']/g, (c) => ({
    "<":"&lt;", ">":"&gt;", "&":"&amp;", '"':"&quot;", "'":"&#39;"
  }[c]));

  let lastStartedAt = null;
  let lastPhase = "idle";
  let consecutiveFails = 0;
  let myNotes = []; // notes sent from THIS browser session
  let consumedById = {}; // id -> consumed_at (ISO string), populated from server polls

  async function fetchStatus() {
    try {
      const res = await fetch("/api/status", { cache: "no-store", credentials: "same-origin" });
      if (!res.ok) {
        if (res.status === 401) { redirectForPin(); return; }
        throw new Error("HTTP " + res.status);
      }
      const s = await res.json();
      consecutiveFails = 0;
      setConn(true);
      render(s);
    } catch (e) {
      consecutiveFails++;
      if (consecutiveFails >= 2) setConn(false);
    }
  }

  function redirectForPin() {
    // Cookie missing/expired. Bounce to the PIN entry page; the server's
    // 401 already returned that page, but if we got here via a stale
    // cookie, just reload so the server can render its PIN form.
    window.location.reload();
  }

  function setConn(ok) {
    const el = $("conn");
    if (ok) {
      el.classList.remove("stale");
      $("conn-text").textContent = "live";
    } else {
      el.classList.add("stale");
      $("conn-text").textContent = "disconnected";
    }
  }

  function render(s) {
    const phase = (s.phase || "idle").toLowerCase();
    document.body.dataset.phase = phase;
    $("phase-label").textContent = phase;
    lastPhase = phase;

    lastStartedAt = s.started_at ? new Date(s.started_at).getTime() : null;
    updateElapsed();

    const action = (s.action || "").trim();
    const actionEl = $("action");
    if (action) {
      actionEl.textContent = action;
      actionEl.classList.remove("empty");
    } else {
      actionEl.textContent = "No action yet";
      actionEl.classList.add("empty");
    }

    $("project").textContent = s.project ? s.project : "—";
    $("updated").textContent = fmtTime(s.updated_at);

    const noteDt = document.querySelector(".note-dt");
    const noteDd = document.querySelector(".note-dd");
    if (s.note && s.note.trim()) {
      noteDt.classList.remove("hidden");
      noteDd.classList.remove("hidden");
      noteDd.textContent = s.note;
    } else {
      noteDt.classList.add("hidden");
      noteDd.classList.add("hidden");
    }

    const log = (s.log || []).slice().reverse();
    const ul = $("log");
    if (!log.length) {
      ul.innerHTML = '<li class="empty"><time></time><span style="color:var(--muted)">none yet</span></li>';
    } else {
      ul.innerHTML = log.map((e) => {
        const t = fmtTime(e.at);
        const txt = escapeHTML(e.action || "");
        return '<li><time>' + t + '</time><span>' + txt + '</span></li>';
      }).join("");
    }
  }

  function updateElapsed() {
    if (!lastStartedAt || (lastPhase !== "recording" && lastPhase !== "preparing")) {
      $("elapsed").textContent = "--:--";
      return;
    }
    const ms = Date.now() - lastStartedAt;
    $("elapsed").textContent = fmtClock(ms);
  }

  async function loadLan() {
    try {
      const res = await fetch("/api/lan", { cache: "no-store", credentials: "same-origin" });
      if (!res.ok) return;
      const j = await res.json();
      const port = j.port;
      const bonjour = j.bonjour || "";
      const preferred = j.preferred || "";
      if (bonjour) {
        $("bonjour-url").textContent = "http://" + bonjour + ":" + port;
        document.querySelector(".bonjour-dt").classList.remove("hidden");
        document.querySelector(".bonjour-dd").classList.remove("hidden");
      }
      if (preferred) {
        $("lan-url").textContent = "http://" + preferred + ":" + port;
        document.querySelector(".lan-dt").classList.remove("hidden");
        document.querySelector(".lan-dd").classList.remove("hidden");
      }
    } catch (_) { /* ignore */ }
  }

  function renderMyNotes() {
    const ul = $("notes-list");
    if (!myNotes.length) {
      ul.innerHTML = '<li class="empty" style="color:var(--muted)">none yet</li>';
      return;
    }
    ul.innerHTML = myNotes.slice().reverse().map((n) => {
      const t = fmtTime(n.at);
      const off = fmtOffset(n.offset_ms);
      const txt = escapeHTML(n.text);
      const consumedAt = consumedById[n.id];
      let badge;
      if (consumedAt) {
        badge = '<span style="color:var(--accent)">&check; seen by {{AGENT}} at ' + fmtTime(consumedAt) + '</span>';
      } else {
        badge = '<span style="color:var(--ok)">queued for {{AGENT}}</span>';
      }
      return '<li><div class="note-meta">' + t + ' &middot; ' + off + ' &middot; ' + badge + '</div><div class="note-text">' + txt + '</div></li>';
    }).join("");
  }

  // Poll the server for the consumed status of all notes we've sent.
  async function refreshNoteStatus() {
    if (!myNotes.length) return;
    try {
      const res = await fetch("/api/notes?status=all", { cache: "no-store", credentials: "same-origin" });
      if (!res.ok) return;
      const j = await res.json();
      let changed = false;
      (j.notes || []).forEach((sn) => {
        const prev = consumedById[sn.id];
        const next = sn.consumed_at || null;
        if (prev !== next) {
          consumedById[sn.id] = next;
          changed = true;
        }
      });
      if (changed) renderMyNotes();
    } catch (_) { /* ignore */ }
  }

  // Hold a per-tab list in sessionStorage so a reload keeps the
  // "queued" history visible during the take.
  function loadMyNotes() {
    try {
      const raw = sessionStorage.getItem("ss_notes");
      if (raw) myNotes = JSON.parse(raw) || [];
    } catch (_) { myNotes = []; }
    renderMyNotes();
  }
  function saveMyNotes() {
    try { sessionStorage.setItem("ss_notes", JSON.stringify(myNotes)); } catch (_) {}
  }

  $("note-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const ta = $("note-text");
    const btn = $("note-send");
    const status = $("note-status");
    const text = ta.value.trim();
    if (!text) return;

    btn.disabled = true;
    status.className = "status";
    status.textContent = "Sending…";

    try {
      const res = await fetch("/api/note", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ text }),
      });
      if (!res.ok) {
        if (res.status === 401) { redirectForPin(); return; }
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || ("HTTP " + res.status));
      }
      const note = await res.json();
      myNotes.push(note);
      saveMyNotes();
      renderMyNotes();
      ta.value = "";
      status.className = "status ok";
      status.textContent = "📨 Queued for {{AGENT}}.";
    } catch (e) {
      status.className = "status err";
      status.textContent = "Failed: " + e.message;
    } finally {
      btn.disabled = false;
      setTimeout(() => { if (status.classList.contains("ok")) status.textContent = ""; }, 4000);
    }
  });

  loadMyNotes();
  fetchStatus();
  loadLan();
  refreshNoteStatus();
  setInterval(fetchStatus, 1500);
  setInterval(updateElapsed, 250);
  setInterval(refreshNoteStatus, 3000);
})();
</script>

</body>
</html>
`
