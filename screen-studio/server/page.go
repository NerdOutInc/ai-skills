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

  .lan { font-size: 12px; color: var(--muted); margin-top: 18px; text-align: center; }
  .lan code { color: var(--text); background: var(--panel-2); padding: 2px 6px; border-radius: 4px; }

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
  <h2>Recent actions</h2>
  <ul class="log" id="log"><li class="empty"><time></time><span style="color:var(--muted)">none yet</span></li></ul>
</section>

<div class="lan" id="lan"></div>

<script>
(function() {
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

  let lastStartedAt = null;
  let lastPhase = "idle";
  let stale = false;
  let consecutiveFails = 0;

  async function fetchStatus() {
    try {
      const res = await fetch("/api/status", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const s = await res.json();
      consecutiveFails = 0;
      setConn(true);
      render(s);
    } catch (e) {
      consecutiveFails++;
      if (consecutiveFails >= 2) setConn(false);
    }
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
        const txt = (e.action || "").replace(/[<>&]/g, (c) => ({"<":"&lt;",">":"&gt;","&":"&amp;"}[c]));
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
      const res = await fetch("/api/lan", { cache: "no-store" });
      if (!res.ok) return;
      const j = await res.json();
      const ips = j.ips || [];
      const port = j.port;
      const bonjour = j.bonjour || "";
      const urls = [];
      if (bonjour) urls.push('<code>http://' + bonjour + ':' + port + '</code>');
      ips.forEach((ip) => urls.push('<code>http://' + ip + ':' + port + '</code>'));
      if (!urls.length) {
        $("lan").innerHTML = "Server reachable on this machine only.";
        return;
      }
      $("lan").innerHTML = "Reachable from another device: " + urls.join(" &nbsp; ");
    } catch (_) { /* ignore */ }
  }

  fetchStatus();
  loadLan();
  setInterval(fetchStatus, 1500);
  setInterval(updateElapsed, 250);
})();
</script>

</body>
</html>
`
