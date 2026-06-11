/* saakshe chat panel — always-on right pane. Renders presenter blocks.
   Block kinds (contract in service/presenter.py): text · data · actions ·
   slider · progress · receipt · options. The panel formats; it never authors.
   Brut skin rides the cockpit tokens (chat-panel.css); the skbot mascot,
   honest error states, voice auth and the collapse rail live here. */
(function () {
  'use strict';
  var pane = document.getElementById('sa-chatpane');
  if (!pane) return;

  var BOT = '<span class="skbot sm" aria-hidden="true"><span class="skface">' +
            '<span class="skeye L"></span><span class="skeye R"></span>' +
            '<span class="skmouth"></span></span></span>';
  /* the chat has NO top chrome at all — messages flow from under the cockpit's
     single topbar. The bot mark rides every witness reply (and the typing row),
     black bezel always; collapse + live dot sit at the far right of the
     faculty-tabs row, just above the ask box. Collapsed = just the bot, big. */
  pane.innerHTML =
    '<div class="ch-feed" id="sa-ch-feed" aria-live="polite"></div>' +
    '<div id="sa-ch-settings" role="region" aria-label="settings"></div>' +
    '<div class="ch-tabs" role="group" aria-label="filter by faculty">' +
    '<button class="ch-tab on" type="button" data-q="saakshe" aria-pressed="true">saakshe</button>' +
    '<button class="ch-tab" type="button" data-q="manas" aria-pressed="false"><span class="fdot"></span>manas</button>' +
    '<button class="ch-tab" type="button" data-q="arivu" aria-pressed="false"><span class="fdot"></span>arivu</button>' +
    '<button class="ch-tab" type="button" data-q="kalai" aria-pressed="false"><span class="fdot"></span>kalai</button>' +
    '<button class="ch-tab" type="button" data-q="kural" aria-pressed="false"><span class="fdot"></span>kural</button>' +
    '<span class="live" id="sa-ch-live"></span>' +
    '<button class="ch-gear" id="sa-ch-gear" type="button" title="settings" aria-label="settings" aria-pressed="false">' +
    '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.2"/>' +
    '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg></button>' +
    '<button class="ch-collapse" id="sa-ch-clps" type="button" title="collapse the chat pane" aria-label="collapse chat">' +
    '<svg class="ic" aria-hidden="true"><use href="#i-handoff"/></svg></button></div>' +
    '<div class="ch-input"><input id="sa-ch-inp" placeholder="ask saakshe…" aria-label="ask saakshe">' +
    '<button id="sa-ch-mic" type="button" title="voice — Gemini Live" aria-label="voice">' +
    '<svg class="ic" aria-hidden="true"><use href="#i-mic"/></svg><span class="recdot"></span></button>' +
    '<button id="sa-ch-send" type="button">SEND</button></div>' +
    '<button class="ch-rail" id="sa-ch-rail" type="button" title="open the chat pane" aria-label="open chat">' +
    BOT + '</button>';

  var feed = document.getElementById('sa-ch-feed');
  var input = document.getElementById('sa-ch-inp');
  var sendBtn = document.getElementById('sa-ch-send');
  var micBtn = document.getElementById('sa-ch-mic');
  var liveDot = document.getElementById('sa-ch-live');
  var state = { budget: 1.0, seconds: 4, fx: 'sat_sort', image: null, job: null,
                poller: null, inflight: false, fac: 'saakshe' };
  var FX = ['sat_sort', 'dark_sort', 'vert_sort', 'hue_sort', 'ripple', 'wave',
            'light_sweep', 'charcoal', 'lith', 'sabattier', 'cinestill', 'ca_pulse'];
  var MEDIA_WORDS = ['hdr', 'video', 'reel', 'animate', 'motion'];   // mirrors presenter.media_intent

  function el(h) { var d = document.createElement('div'); d.innerHTML = h; return d.firstElementChild; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]; }); }
  function hdrs(extra) { return (window.SA_HEADERS || Object)(extra || {}); }
  function bot(fn) { if (window.SK_BOT && SK_BOT[fn]) SK_BOT[fn](); }
  function dot(cls) { liveDot.className = 'live' + (cls ? ' ' + cls : ''); }

  /* escape FIRST, then a tiny safe formatter: **bold**, `code`, bare links */
  function fmt(s) {
    return esc(s)
      .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
  }
  function ts() {
    var d = new Date();
    return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
  }
  function facOf(who) {
    var w = String(who).toLowerCase();
    var f = ['manas', 'arivu', 'kalai', 'kural'].filter(function (q) { return w.indexOf(q) !== -1; });
    return f[0] || 'saakshe';
  }

  /* ── stick-to-bottom only when the founder IS at the bottom ── */
  var newBtn = null;
  function nearBottom() { return feed.scrollHeight - feed.scrollTop - feed.clientHeight < 60; }
  function down(force) {
    if (force || nearBottom()) {
      feed.scrollTop = feed.scrollHeight;
      if (newBtn) { newBtn.remove(); newBtn = null; }
    } else if (!newBtn) {
      newBtn = el('<button class="newmsgs" type="button">new messages ↓</button>');
      newBtn.onclick = function () { down(true); };
      feed.appendChild(newBtn);
    }
  }
  feed.addEventListener('scroll', function () { if (nearBottom() && newBtn) { newBtn.remove(); newBtn = null; } });

  /* ── feed persistence: a refresh must not amnesia the conversation ──
     structured JSON (v2) re-rendered through msg() on restore — never raw
     innerHTML re-injection. persist() is debounced (~1s trailing) because it
     fires on every message AND every 1.5s poll tick. */
  var log = [];
  var persistTimer = null;
  function persistNow() {
    persistTimer = null;
    try {
      var keep = JSON.stringify({ v: 2, items: log.slice(-200) });
      if (keep.length < 200000) sessionStorage.setItem('sk-chat-feed', keep);
    } catch (e) {}
  }
  function persist() {
    if (persistTimer) clearTimeout(persistTimer);
    persistTimer = setTimeout(persistNow, 1000);
  }
  window.addEventListener('pagehide', persistNow);
  function msg(who, html, user, stamp) {
    /* every non-user message wears the bot mark — the witness is the one talking */
    var when = stamp || ts();
    var entry = { who: String(who), html: String(html), user: !!user, ts: when };
    log.push(entry);
    var m = el('<div class="msg' + (user ? ' user' : '') + '" data-fac="' + esc(facOf(who)) + '"><div class="who">' +
               (user ? '' : BOT) + esc(who) + '<span class="ts">' + esc(when) + '</span></div><p>' + html + '</p></div>');
    m._log = entry;                 // options blocks ride the entry into sessionStorage
    applyFacFilter(m);
    feed.appendChild(m); down(); persist(); return m;
  }

  var typingEl = null;
  function showTyping() {
    if (typingEl) return;
    typingEl = el('<div class="typing" aria-label="saakshe is thinking">' + BOT +
                  '<span class="td"></span><span class="td"></span><span class="td"></span></div>');
    feed.appendChild(typingEl); down(); bot('think'); dot('busy');
  }
  function hideTyping(ok) {
    if (typingEl) { typingEl.remove(); typingEl = null; }
    bot(ok ? 'joy' : 'idle'); dot(ok ? '' : 'err');
  }

  function lockActs(scope) {
    if (!scope) return;
    scope.querySelectorAll('.act').forEach(function (b) { b.classList.add('done'); });
  }

  /* options chips — the founder's core chat principle: EVERY answer offers
     tappable next steps, while typing stays always available. A chip click ==
     typing item.send and pressing send. Once one chip in a row fires, the row
     is spent — options reflect the moment they were offered. Built via DOM +
     dataset (same no-attribute-injection rule as actBtn). */
  function renderOpts(host, items, spent) {
    var row = el('<div class="ch-opts' + (spent ? ' spent' : '') + '"></div>');
    items.forEach(function (i) {
      var b = document.createElement('button');
      b.className = 'ch-opt';
      b.type = 'button';
      b.dataset.send = String(i.send || i.label || '');
      b.textContent = String(i.label || i.send || '');
      if (spent) b.disabled = true;
      row.appendChild(b);
    });
    host.appendChild(row);
    return row;
  }

  /* actions render via DOM + dataset — never string-built attributes (an args
     value with a quote must not become an attribute-injection sink) */
  function actBtn(i) {
    var b = document.createElement('button');
    b.className = 'act ' + (i.kind || 'plain');
    b.type = 'button';
    b.dataset.action = i.action || '';
    b.dataset.args = JSON.stringify(i.args || {});
    b.textContent = i.label;
    return b;
  }

  function renderBlocks(blocks) {
    var last = null;
    blocks.forEach(function (b) {
      if (b.t === 'text') last = msg(b.who.toUpperCase(), fmt(b.md));
      else if ((b.t === 'data' || b.t === 'receipt') && last) {
        var rows = b.rows.map(function (r) {
          return '<div class="row"><span>' + esc(r[0]) + '</span><b>' + esc(r[1]) + '</b></div>';
        }).join('');
        last.appendChild(el('<div class="data">' + rows + '</div>'));
        if (b.verify) last.appendChild(el(
          '<div class="data"><div class="row"><span>verify</span><b>' +
          (b.verify.ok ? '✓ ' + esc(b.verify.hdr_format) : '✗ FAILED') +
          '</b></div></div>'));
      }
      else if (b.t === 'actions' && last) {
        var acts = el('<div class="acts"></div>');
        b.items.forEach(function (i) { acts.appendChild(actBtn(i)); });
        last.appendChild(acts);
      }
      else if (b.t === 'slider' && last) {
        var sv = +b.value || 4, q = b.quote || { total_usd: 0, est_wall_sec: 0 };
        var s = el('<div class="sld"><div class="lab"><span>DURATION</span>' +
          '<span class="dv">' + sv + 's</span></div>' +
          '<input type="range" min="' + (+b.min || 1) + '" max="' + (+b.max || 8) + '" value="' + sv + '" aria-label="duration seconds">' +
          '<div class="quote"><span>est. cost</span><b class="qc">$' + (+q.total_usd || 0).toFixed(3) + '</b></div>' +
          '<div class="quote"><span>est. render</span><b class="qt">~' + q.est_wall_sec + 's</b></div></div>');
        s.querySelector('input').oninput = function (e) {
          state.seconds = +e.target.value;
          s.querySelector('.dv').textContent = state.seconds + 's';
          api('/api/kalai/media/quote', { seconds: state.seconds, budget_usd: state.budget,
                                          has_source_image: true }).then(function (res) {
            if (!res.ok) return;
            s.querySelector('.qc').textContent = '$' + res.data.total_usd.toFixed(3);
            s.querySelector('.qt').textContent = '~' + res.data.est_wall_sec + 's';
          });
        };
        last.appendChild(s);
      }
      else if (b.t === 'options' && Array.isArray(b.items) && b.items.length) {
        var clean = b.items.map(function (i) {
          return { label: String(i.label || i.send || ''), send: String(i.send || i.label || '') };
        });
        renderOpts(last || feed, clean, false);
        if (last && last._log) last._log.opts = clean;   // refresh restores the row (spent)
      }
      else if (b.t === 'progress') pollJob(b.job_id);
    });
    down(); persist();
  }

  /* api() reports status honestly — a 401/402 is an ANSWER, never '…' */
  function api(url, body) {
    dot('busy');
    return fetch(url, { method: 'POST', headers: hdrs({ 'content-type': 'application/json' }),
                        body: JSON.stringify(body) })
      .then(function (r) {
        return r.json().catch(function () { return null; }).then(function (d) {
          dot(r.ok ? '' : 'err');
          return { ok: r.ok, status: r.status, data: d };
        });
      })
      .catch(function (e) { dot('err'); return { ok: false, status: 0, data: null, error: String(e) }; });
  }
  function httpBubble(res, what) {
    if (res.status === 401) {
      var m = msg('SΛΛKSHE', 'You are signed out — sign in to ' + esc(what) + '.');
      var acts = el('<div class="acts"></div>');
      acts.appendChild(actBtn({ label: 'SIGN IN', kind: 'primary', action: 'auth.signin', args: {} }));
      m.appendChild(acts); down(); persist(); return;
    }
    if (res.status === 402) {
      var bal = (res.data && res.data.balance != null) ? ' Balance: ' + res.data.balance + '.' : '';
      var m2 = msg('SΛΛKSHE', 'Out of credits — this needs more.' + esc(bal));
      var a2 = el('<div class="acts"></div>');
      a2.appendChild(actBtn({ label: 'SEE PRICING', kind: 'primary', action: 'open.pricing', args: {} }));
      m2.appendChild(a2); down(); persist(); return;
    }
    if (res.status === 429) { msg('SΛΛKSHE', 'Rate limited — give it a few seconds, then try again.'); return; }
    if (res.status === 0) { msg('SΛΛKSHE', 'The backend is not answering — is it running?'); return; }
    msg('SΛΛKSHE', 'That failed — ' + fmt((res.data && (res.data.detail || res.data.error)) || ('HTTP ' + res.status)));
  }

  feed.addEventListener('click', function (e) {
    var sg = e.target.closest('.sug');
    if (sg) { input.value = sg.dataset.ask || sg.textContent; send(); return; }
    var op = e.target.closest('.ch-opt');
    if (op) {
      /* a chip == the founder typed it; spend the row only if the send took
         (inflight asks bounce, and the row must stay live for a retry) */
      var row = op.closest('.ch-opts');
      if (row && !row.classList.contains('spent') &&
          sendText(op.dataset.send || op.textContent)) {
        row.classList.add('spent');
        row.querySelectorAll('.ch-opt').forEach(function (x) { x.disabled = true; });
      }
      return;
    }
    var b = e.target.closest('.act');
    if (!b || b.classList.contains('done')) return;
    var action = b.dataset.action, args = {};
    try { args = JSON.parse(b.dataset.args || '{}'); } catch (er) {}
    if (action === 'noop') return;                    // a blocked chip must not kill its siblings
    if (action === 'auth.signin') { if (window.SAAKSHE_AUTH) SAAKSHE_AUTH.signIn(); return; }
    if (action === 'open.pricing') { window.open('/pricing.html', '_blank', 'noopener'); return; }
    if (action === 'nav.questions') { if (window.cockpitGo) window.cockpitGo('questions', null); return; }
    if (action === 'nav.connections') { if (window.cockpitGo) window.cockpitGo('manas', 'connections'); return; }
    lockActs(b.closest('.acts'));
    if (action === 'media.render') startRender();
    else if (action === 'media.requote') { if (args.seconds) state.seconds = args.seconds; requote(); }
    else if (action === 'media.fxmenu') fxMenu();
    else if (action === 'media.fx') { state.fx = args.fx; startRender(); }
    else if (action === 'media.retrypoll' && args.job) pollJob(args.job);
    else if (action === 'media.view' && state.job) viewHdr();
  });

  function viewHdr() {
    /* the gated prod 401s a bare window.open (no Bearer on navigation) —
       fetch WITH the token and open the blob */
    dot('busy');
    fetch('/api/kalai/media/file/' + state.job, { headers: hdrs({}) })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.blob(); })
      .then(function (bl) {
        dot('');
        var u = URL.createObjectURL(bl);
        window.open(u, '_blank', 'noopener');
        setTimeout(function () { URL.revokeObjectURL(u); }, 60000);
      })
      .catch(function () { dot('err'); msg('▲ KALAI', 'could not fetch the file — are you signed in?'); });
  }

  function fxMenu() {
    var m = msg('▲ KALAI · FX-PICKER', 'pick the effect:');
    var acts = el('<div class="acts"></div>');
    FX.forEach(function (f) {
      acts.appendChild(actBtn({ label: f.replace(/_/g, ' ').toUpperCase(),
                                kind: (f === state.fx ? 'ok' : 'plain'),
                                action: 'media.fx', args: { fx: f } }));
    });
    m.appendChild(acts); down(); persist();
  }

  function dropPlate(m) {
    var d = el('<label class="drop">drop / choose image<input type="file" accept="image/*"></label>');
    var inp = d.querySelector('input');
    function take(file) {
      if (!file || file.type.indexOf('image/') !== 0) return;
      state.image = file;
      var chip = el('<span class="filechip">' + esc(file.name) +
                    '<button type="button" aria-label="remove">✕</button></span>');
      chip.querySelector('button').onclick = function () { state.image = null; chip.remove(); m.appendChild(dropPlate(m)); };
      d.replaceWith(chip);
      startRender();
    }
    inp.onchange = function () { take(inp.files[0]); };
    d.addEventListener('dragover', function (e) { e.preventDefault(); d.classList.add('over'); });
    d.addEventListener('dragleave', function () { d.classList.remove('over'); });
    d.addEventListener('drop', function (e) {
      e.preventDefault(); d.classList.remove('over');
      take(e.dataTransfer.files && e.dataTransfer.files[0]);
    });
    return d;
  }

  function startRender() {
    if (!state.image) {
      var m = msg('▲ KALAI · PRODUCER', 'drop the source image — or click to choose:');
      m.appendChild(dropPlate(m)); down(); persist(); return;
    }
    var fd = new FormData();
    fd.append('image', state.image);
    fd.append('fx', state.fx);
    fd.append('seconds', state.seconds);
    fd.append('budget_usd', state.budget);
    dot('busy');
    fetch('/api/kalai/media/render', { method: 'POST', headers: hdrs({}), body: fd })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, status: r.status, data: d }; }); })
      .then(function (res) {
        dot(res.ok ? '' : 'err');
        if (res.data && res.data.job_id) { state.job = res.data.job_id; pollJob(res.data.job_id); }
        else if (!res.ok) httpBubble(res, 'render');
        else msg('▲ KALAI · ROUTER', fmt((res.data && res.data.error) || 'refused'));
      })
      .catch(function () { dot('err'); msg('▲ KALAI · ROUTER', 'render request failed — network?'); });
  }

  function pollJob(jid) {
    if (state.poller) { clearInterval(state.poller); state.poller = null; }
    var m = msg('▲ KALAI · RENDERER', 'starting…');
    var p = m.querySelector('p');
    var fails = 0, every = 1500;
    state.poller = setInterval(function () {
      fetch('/api/kalai/media/job/' + jid, { headers: hdrs({}) })
        .then(function (r) {
          if (!r.ok) {
            return r.json().catch(function () { return null; }).then(function (d) {
              clearInterval(state.poller); state.poller = null;
              p.textContent = 'render check failed.';
              httpBubble({ ok: false, status: r.status, data: d }, 'check the render');
              down(); persist();
              return null;
            });
          }
          return r.json();
        })
        .then(function (s) {
          if (s == null) return;
          fails = 0;
          if (s.status === 'rendering') {
            p.textContent = 'frame ' + s.frame + '/' + s.frames + ' · rendering…';
          } else {
            clearInterval(state.poller); state.poller = null;
            if (s.status === 'done') { p.innerHTML = '<b>done.</b>'; renderBlocks(receiptBlocks(s)); bot('joy'); }
            else p.textContent = 'error: ' + (s.error || 'unknown');
          }
          down(); persist();
        })
        .catch(function () {
          if (++fails >= 4) {
            clearInterval(state.poller); state.poller = null;
            p.textContent = 'lost the render — the backend stopped answering.';
            var acts = el('<div class="acts"></div>');
            acts.appendChild(actBtn({ label: 'RETRY', kind: 'primary', action: 'media.retrypoll', args: { job: jid } }));
            m.appendChild(acts); down(); persist();
          }
        });
    }, every);
  }

  function receiptBlocks(s) {
    return [
      { t: 'text', who: 'kalai/verifier',
        md: s.verify.ok ? 'verified — ' + s.verify.hdr_format : 'HDR verify FAILED — not shipping.' },
      { t: 'receipt',
        rows: [['estimated', '$' + s.receipt.estimated_usd.toFixed(3)],
               ['cpu', s.receipt.measured_vcpu_sec + ' vCPU-s · $' + s.receipt.cpu_usd.toFixed(3)],
               ['total', '$' + s.receipt.total_usd.toFixed(3)]],
        verify: s.verify },
      { t: 'actions', items: s.verify.ok ?
        [{ label: 'VIEW HDR', kind: 'primary', action: 'media.view', args: {} },
         { label: 'NEW RENDER', kind: 'plain', action: 'media.fxmenu', args: {} }] :
        [{ label: 'RETRY', kind: 'primary', action: 'media.render', args: {} }] }
    ];
  }

  function requote() {
    api('/api/kalai/media/quote', { seconds: state.seconds, budget_usd: state.budget,
                                    has_source_image: true }).then(function (res) {
      if (!res.ok) return httpBubble(res, 'quote');
      var q = res.data;
      renderBlocks([
        { t: 'text', who: 'kalai/pricer', md: 'requoted.' },
        { t: 'slider', action: 'media.requote', min: 1, max: 8, value: q.seconds,
          quote: { total_usd: q.total_usd, est_wall_sec: q.est_wall_sec } },
        { t: 'actions', items: [
          { label: 'RENDER', kind: 'primary', action: 'media.render', args: {} },
          { label: 'PICK FX (12)', kind: 'plain', action: 'media.fxmenu', args: {} }] }]);
    });
  }

  function syncSend() { sendBtn.disabled = state.inflight || !input.value.trim(); }
  input.addEventListener('input', syncSend);

  /* sendText: the ONE ask path — typed sends and options chips both land here.
     Echoes the user bubble + POSTs /api/saakshe/ask. Returns true when the ask
     actually went out (false on empty / already inflight). */
  function sendText(text) {
    text = String(text == null ? '' : text).trim();
    if (!text || state.inflight) return false;
    setSettings(false);                           // an ask always surfaces the feed
    msg('YOU', esc(text), true);
    var low = text.toLowerCase();
    var m = low.match(/\$\s*(\d+(?:\.\d+)?)/);
    if (m && MEDIA_WORDS.some(function (w) { return low.indexOf(w) !== -1; })) {
      state.budget = +m[1];                       // only a media-shaped ask moves the budget
    }
    state.inflight = true; syncSend(); showTyping();
    var ik = 'ask:' + Date.now() + ':' + Math.random().toString(36).slice(2);
    api('/api/saakshe/ask', { text: text, idem_key: ik }).then(function (res) {
      state.inflight = false; syncSend();
      hideTyping(res.ok);
      if (!res.ok) return httpBubble(res, 'keep asking');
      var d = res.data || {};
      renderBlocks(d.blocks && d.blocks.length ? d.blocks :
        [{ t: 'text', who: 'saakshe', md: d.text || '…' }]);
    });
    return true;
  }
  function send() {
    if (sendText(input.value)) { input.value = ''; syncSend(); }
  }

  /* ── voice: /ws/voice — Gemini Live native-audio bridge ──
     demo mode: text frames through the same witness tools.
     live mode: mic PCM16@16k up (hex), PCM16@24k down, replies as messages.
     The gated prod REQUIRES auth — the JWT rides the FIRST FRAME
     ({type:'auth', token}) so it never lands in access logs via the query
     string; the server answers 4401 when it's missing or bad. */
  var voice = { ws: null, on: false, mode: null, ctx: null, src: null, proc: null,
                stream: null, playCtx: null, playAt: 0, sawHello: false };

  function flushPlayback() {
    /* kill EVERYTHING already scheduled — chunks are queued seconds ahead, so
       without this the bot keeps talking long after stop */
    if (voice.playCtx) { try { voice.playCtx.close(); } catch (e) {} }
    voice.playCtx = null; voice.playAt = 0;
  }
  function voiceStop() {
    voice.on = false; voice.mode = null;
    if (voice.proc) { voice.proc.disconnect(); voice.proc = null; }
    if (voice.src) { voice.src.disconnect(); voice.src = null; }
    if (voice.stream) { voice.stream.getTracks().forEach(function (t) { t.stop(); }); voice.stream = null; }
    if (voice.ctx) { voice.ctx.close(); voice.ctx = null; }
    if (voice.ws) { try { voice.ws.close(); } catch (e) {} voice.ws = null; }
    flushPlayback();
    micBtn.classList.remove('rec', 'kbd', 'loading');
  }

  function playPcm(hex) {
    if (!voice.playCtx) { voice.playCtx = new AudioContext({ sampleRate: 24000 }); voice.playAt = 0; }
    var bytes = new Uint8Array(hex.length / 2);
    for (var i = 0; i < bytes.length; i++) bytes[i] = parseInt(hex.substr(i * 2, 2), 16);
    var i16 = new Int16Array(bytes.buffer);
    var f32 = new Float32Array(i16.length);
    for (var j = 0; j < i16.length; j++) f32[j] = i16[j] / 32768;
    var buf = voice.playCtx.createBuffer(1, f32.length, 24000);
    buf.getChannelData(0).set(f32);
    var s = voice.playCtx.createBufferSource();
    s.buffer = buf; s.connect(voice.playCtx.destination);
    voice.playAt = Math.max(voice.playAt, voice.playCtx.currentTime);
    s.start(voice.playAt);
    voice.playAt += buf.duration;
  }

  function voiceStart() {
    var proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
    var A = window.SAAKSHE_AUTH;
    var tok = (A && A.token && A.token()) || '';
    var ws = new WebSocket(proto + location.host + '/ws/voice');
    voice.ws = ws; voice.on = true; voice.sawHello = false;
    micBtn.classList.add('loading');
    ws.onopen = function () {
      /* first-frame auth — the gated server awaits this before its hello;
         the open demo just ignores it */
      ws.send(JSON.stringify({ type: 'auth', token: tok }));
    };
    ws.onmessage = function (ev) {
      var m = JSON.parse(ev.data);
      if (m.type === 'hello') {
        voice.sawHello = true;
        micBtn.classList.remove('loading');
        msg('SΛΛKSHE · VOICE', esc(m.mode === 'live'
          ? 'voice live — Gemini native audio. speak.'
          : 'voice in demo mode — type below, same tools answer.'));
        if (m.mode === 'live') { voice.mode = 'live'; micUp(ws); }
        else { voice.mode = 'kbd'; micBtn.classList.add('kbd'); }
      }
      else if (m.type === 'audio') playPcm(m.data);
      else if (m.type === 'interrupted') flushPlayback();   // barge-in: drop queued speech NOW
      else if (m.type === 'reply') msg('SΛΛKSHE · VOICE', fmt(m.text || ''));
      else if (m.type === 'notice') msg('SΛΛKSHE · VOICE', fmt(m.text || ''));
    };
    ws.onclose = function (ev) {
      var auth401 = (ev && ev.code === 4401) || (!voice.sawHello && voice.on);
      voiceStop();
      if (ev && ev.code === 4401) {
        var mm = msg('SΛΛKSHE · VOICE', 'voice needs you signed in.');
        var acts = el('<div class="acts"></div>');
        acts.appendChild(actBtn({ label: 'SIGN IN', kind: 'primary', action: 'auth.signin', args: {} }));
        mm.appendChild(acts); down(); persist();
      } else if (auth401) {
        msg('SΛΛKSHE · VOICE', 'voice could not connect — signed in? backend up?');
      }
    };
    ws.onerror = function () { /* onclose follows and reports */ };
  }

  function micUp(ws) {
    /* echo cancellation is load-bearing: without it the mic hears the bot's own
       speech and the conversation feeds back into a self-talking loop */
    navigator.mediaDevices.getUserMedia({ audio: {
      sampleRate: 16000, channelCount: 1,
      echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
      .then(function (stream) {
        voice.stream = stream;                       // hold it so stop() can RELEASE the mic
        voice.ctx = new AudioContext({ sampleRate: 16000 });
        voice.src = voice.ctx.createMediaStreamSource(stream);
        voice.proc = voice.ctx.createScriptProcessor(4096, 1, 1);
        voice.proc.onaudioprocess = function (e) {
          if (!voice.on || ws.readyState !== 1) return;
          var f32 = e.inputBuffer.getChannelData(0);
          var i16 = new Int16Array(f32.length);
          for (var i = 0; i < f32.length; i++) {
            var v = Math.max(-1, Math.min(1, f32[i]));
            i16[i] = v < 0 ? v * 32768 : v * 32767;
          }
          var bytes = new Uint8Array(i16.buffer), hex = '';
          for (var j = 0; j < bytes.length; j++) hex += bytes[j].toString(16).padStart(2, '0');
          ws.send(JSON.stringify({ type: 'audio', data: hex }));
        };
        voice.src.connect(voice.proc);
        voice.proc.connect(voice.ctx.destination);
        micBtn.classList.add('rec');
      })
      .catch(function () { msg('SΛΛKSHE · VOICE', 'mic permission denied — voice off.'); voiceStop(); });
  }

  micBtn.onclick = function () { voice.on ? voiceStop() : voiceStart(); };
  // demo-mode keyboard frames also go over the voice socket when it's open in ⌨ mode
  input.addEventListener('keydown', function (e) {
    if (e.isComposing || e.keyCode === 229) return;       // never swallow IME composition
    if (e.key === 'Enter' && voice.on && voice.ws && voice.ws.readyState === 1 &&
        voice.mode === 'kbd') {
      var t = input.value.trim();
      if (t) { msg('YOU', esc(t), true); voice.ws.send(JSON.stringify({ type: 'text', text: t })); input.value = ''; syncSend(); }
      e.stopImmediatePropagation(); e.preventDefault();
    }
  }, true);

  sendBtn.onclick = send;
  input.addEventListener('keydown', function (e) {
    if (e.isComposing || e.keyCode === 229) return;
    if (e.key === 'Enter') send();
  });

  /* ── faculty tabs FILTER the feed (your bubbles always stay) ── */
  function applyFacFilter(m) {
    var f = state.fac;
    var show = f === 'saakshe' || m.classList.contains('user') || m.dataset.fac === f;
    m.classList.toggle('hidden-fac', !show);
  }
  pane.querySelectorAll('.ch-tab').forEach(function (t) {
    t.onclick = function () {
      setSettings(false);                     // any faculty tab returns to chat
      pane.querySelectorAll('.ch-tab').forEach(function (x) {
        x.classList.remove('on'); x.setAttribute('aria-pressed', 'false');
      });
      t.classList.add('on'); t.setAttribute('aria-pressed', 'true');
      state.fac = t.dataset.q;
      feed.querySelectorAll('.msg').forEach(applyFacFilter);
      down(true);
    };
  });

  /* ── settings INSIDE the pane: the layout law — sidebar + canvas never move;
     the only thing that changes on the right is this pane's content,
     chat ↔ settings. Toggling is display-only: the feed DOM (and its scroll
     position) survives untouched. ── */
  var settingsEl = document.getElementById('sa-ch-settings');
  var gearBtn = document.getElementById('sa-ch-gear');
  var settingsOn = false, feedScroll = 0;
  function fillSettings() {
    /* filled lazily on every open — the cockpit owns the markup (and the
       document-level delegation for its controls); we own the back row */
    var back = '<button class="ch-setsback" type="button">back to chat</button>';
    if (typeof window.SK_SETTINGS_HTML === 'function') {
      settingsEl.innerHTML = back + window.SK_SETTINGS_HTML();
    } else {
      settingsEl.innerHTML = back +
        '<div class="ch-setsnote">settings live on the stage for now.</div>' +
        '<button class="act plain ch-setsgo" type="button">OPEN SETTINGS</button>';
      settingsEl.querySelector('.ch-setsgo').onclick = function () {
        if (window.cockpitGo) window.cockpitGo('settings');
      };
    }
    settingsEl.querySelector('.ch-setsback').onclick = function () { setSettings(false); };
  }
  function setSettings(on) {
    on = !!on;
    if (on === settingsOn) return;
    if (on) { feedScroll = feed.scrollTop; fillSettings(); }
    settingsOn = on;
    pane.classList.toggle('settings-on', on);
    gearBtn.classList.toggle('on', on);
    gearBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
    if (!on) feed.scrollTop = feedScroll;     // exactly as it was
  }
  gearBtn.onclick = function () { setSettings(!settingsOn); };

  /* ── collapse rail (desktop) + FAB (narrow) ── */
  var H = document.documentElement;
  function setCollapsed(c) {
    H.classList.toggle('sk-chat-collapsed', c);
    try { localStorage.setItem('sk-chat-collapsed', c ? '1' : ''); } catch (e) {}
  }
  document.getElementById('sa-ch-clps').onclick = function () { setCollapsed(true); };
  document.getElementById('sa-ch-rail').onclick = function () { setCollapsed(false); };
  try {
    var stored = localStorage.getItem('sk-chat-collapsed');
    if (stored === '1') setCollapsed(true);
    /* no stored choice: on tighter desktops the stage needs the room more —
       start collapsed; the witness rail stays one click away */
    else if (stored === null && window.innerWidth >= 1100 && window.innerWidth < 1500) {
      H.classList.add('sk-chat-collapsed');
    }
  } catch (e) {}
  var fab = el('<button id="sa-chatfab" type="button" title="company chat" aria-label="open chat">' + BOT + '</button>');
  fab.onclick = function () { H.classList.add('sk-chat-open'); down(true); };
  document.body.appendChild(fab);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && H.classList.contains('sk-chat-open')) H.classList.remove('sk-chat-open');
  });

  /* ── the ONE chat: the cockpit (rail chips, taps, the reveal seed) routes
     every ask here instead of keeping a second chat surface ── */
  window.SK_CHAT = {
    open: function () {
      setSettings(false);
      if (window.innerWidth < 1100) { H.classList.add('sk-chat-open'); }
      else { setCollapsed(false); }
      down(true); input.focus();
    },
    ask: function (text) {
      if (!text) return;
      input.value = String(text); syncSend(); send();
    },
    note: function (who, text) { msg(String(who || 'SΛΛKSHE').toUpperCase(), fmt(String(text || ''))); },
    /* the reveal seed: each clarifying question is its OWN row plus a chip
       that jumps to the Questions view — never one concatenated paragraph */
    questions: function (p) {
      p = p || {};
      var m = msg('WITNESS', fmt(String(p.lead || '')));
      (p.items || []).forEach(function (q, i) {
        m.appendChild(el('<div class="qseed"><span class="qn">' + (i + 1) + '</span><span class="qt">' +
          fmt(String(q.text || '')) +
          (q.why ? '<i class="qw">' + fmt(String(q.why)) + '</i>' : '') + '</span></div>'));
      });
      var acts = el('<div class="acts"></div>');
      acts.appendChild(actBtn({ label: p.cta || 'OPEN THE QUESTIONS PAGE', kind: 'primary',
                                action: 'nav.questions', args: {} }));
      m.appendChild(acts); down(); persist();
    }
  };

  /* ── first paint: restore the session's feed, or seed the witness greeting ──
     stored shape is {v:2, items:[{who, html, user, ts}]} re-rendered through
     msg(); anything else (the old raw-innerHTML format, garbage) is discarded */
  var restored = null;
  try { restored = JSON.parse(sessionStorage.getItem('sk-chat-feed') || 'null'); }
  catch (e) { restored = null; }
  if (restored && restored.v === 2 && Array.isArray(restored.items) && restored.items.length) {
    restored.items.forEach(function (it) {
      if (it && typeof it.html === 'string') {
        var rm = msg(String(it.who || 'SΛΛKSHE'), it.html, !!it.user, String(it.ts || ''));
        if (Array.isArray(it.opts) && it.opts.length) {
          /* restored options render SPENT — they reflect the moment they were
             offered; keep them on the fresh log entry so they survive again */
          if (rm._log) rm._log.opts = it.opts;
          renderOpts(rm, it.opts, true);
        }
      }
    });
    down(true);
  } else {
    var g = msg('SΛΛKSHE · WITNESS',
      'I see everything the three agents and the arivu chamber do — and answer only from it. Ask me anything about your company.');
    var sugs = el('<div class="sugs"></div>');
    [['what is waiting on me?', "what's waiting on me?"],
     ['status', 'status'],
     ['render an HDR reel under $1', 'render an HDR reel under $1']].forEach(function (s) {
      var b = el('<button class="sug" type="button">' + esc(s[0]) + '</button>');
      b.dataset.ask = s[1];
      sugs.appendChild(b);
    });
    g.appendChild(sugs); down(true);
  }
  syncSend();
})();
