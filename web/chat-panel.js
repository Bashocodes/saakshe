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
  /* the pane's chrome (founder, 2026-06-12): ONE ink tab at the top right —
     HISTORY + SETTINGS — just under the cockpit topbar. No close, no collapse,
     no live dot. The faculty pills float free above the ask box (no band), and
     a pill click drops an ENTITY CHIP into the ask, never plain text. */
  pane.innerHTML =
    '<div class="ch-head"><div class="ch-htab" role="group" aria-label="chat controls">' +
    '<button class="ch-hbtn" id="sa-ch-new" type="button" title="new chat — a fresh sitting">' +
    '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>new chat</button>' +
    '<button class="ch-hbtn" id="sa-ch-hist" type="button" title="chat history" aria-pressed="false">' +
    '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 12a8.5 8.5 0 1 1 2.5 6M3.5 12V7M3.5 12h5"/><path d="M12 7.5v5l3.2 2"/></svg>history</button>' +
    '<button class="ch-hbtn" id="sa-ch-gear" type="button" title="settings" aria-pressed="false">' +
    '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.2"/>' +
    '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>settings</button>' +
    '</div></div>' +
    '<div class="ch-feed" id="sa-ch-feed" aria-live="polite"></div>' +
    '<div id="sa-ch-settings" role="region" aria-label="settings"></div>' +
    '<div id="sa-ch-history" role="region" aria-label="chat history"></div>' +
    '<div class="ch-tabs" role="group" aria-label="mention an agent">' +
    '<button class="ch-tab" type="button" data-q="manas" title="drop manas into your ask"><span class="fdot"></span>manas</button>' +
    '<button class="ch-tab" type="button" data-q="arivu" title="drop arivu into your ask"><span class="fdot"></span>arivu</button>' +
    '<button class="ch-tab" type="button" data-q="kalai" title="drop kalai into your ask"><span class="fdot"></span>kalai</button>' +
    '<button class="ch-tab" type="button" data-q="kural" title="drop kural into your ask"><span class="fdot"></span>kural</button>' +
    '</div>' +
    '<div class="ch-input"><div class="ch-ed" id="sa-ch-inp" contenteditable="true" role="textbox" ' +
    'aria-multiline="false" aria-label="ask saakshe" data-ph="ask saakshe…"></div>' +
    '<button id="sa-ch-mic" type="button" title="voice — Gemini Live" aria-label="voice">' +
    '<svg class="ic" aria-hidden="true"><use href="#i-mic"/></svg><span class="recdot"></span></button>' +
    '<button id="sa-ch-send" type="button">SEND</button></div>';

  var feed = document.getElementById('sa-ch-feed');
  var input = document.getElementById('sa-ch-inp');
  var sendBtn = document.getElementById('sa-ch-send');
  var micBtn = document.getElementById('sa-ch-mic');
  var liveDot = null;   /* the green dot is retired — dot() keeps the contract as a no-op */
  var state = { budget: 1.0, seconds: 4, fx: 'sat_sort', image: null, job: null,
                poller: null, pollEnd: null, inflight: false, fac: 'saakshe' };
  var FX = ['sat_sort', 'dark_sort', 'vert_sort', 'hue_sort', 'ripple', 'wave',
            'light_sweep', 'charcoal', 'lith', 'sabattier', 'cinestill', 'ca_pulse'];
  var MEDIA_WORDS = ['hdr', 'video', 'reel', 'animate', 'motion'];   // mirrors presenter.media_intent

  function el(h) { var d = document.createElement('div'); d.innerHTML = h; return d.firstElementChild; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]; }); }
  function hdrs(extra) { return (window.SA_HEADERS || Object)(extra || {}); }
  function bot(fn) { if (window.SK_BOT && SK_BOT[fn]) SK_BOT[fn](); }
  function dot(cls) { if (liveDot) liveDot.className = 'live' + (cls ? ' ' + cls : ''); }

  /* ── the entity-chip ask box (contenteditable) ──
     A faculty pill drops a CHIP into the ask — the founder is pointing at the
     ENTITY, not typing its name. On send a chip serializes as @agent so the
     witness reads an unambiguous reference. */
  function entChip(q) {
    var s = document.createElement('span');
    s.className = 'ent'; s.dataset.q = q;
    s.setAttribute('contenteditable', 'false');
    s.innerHTML = '<span class="fdot"></span>' + esc(q);
    return s;
  }
  function insertEnt(q) {
    input.focus();
    var sel = window.getSelection(), range = null;
    if (sel && sel.rangeCount && input.contains(sel.anchorNode)) range = sel.getRangeAt(0);
    else { range = document.createRange(); range.selectNodeContents(input); range.collapse(false); }
    var chip = entChip(q);
    range.deleteContents(); range.insertNode(chip);
    var sp = document.createTextNode(' ');
    chip.after(sp);
    range.setStartAfter(sp); range.collapse(true);
    if (sel) { sel.removeAllRanges(); sel.addRange(range); }
    syncSend();
  }
  function readInput() {
    var out = '';
    for (var n = input.firstChild; n; n = n.nextSibling) {
      if (n.nodeType === 3) out += n.nodeValue;
      else if (n.classList && n.classList.contains('ent')) out += '@' + (n.dataset.q || '');
      else out += n.textContent;
    }
    return out.replace(/ /g, ' ').replace(/\s+/g, ' ').trim();
  }
  function clearInput() { input.innerHTML = ''; syncSend(); }

  /* honest wall-clock label: the render runs in a throttled background thread,
     so anything past 90s is shown as a MINUTES RANGE, never false precision */
  function fmtEta(sec) {
    sec = +sec || 0;
    if (sec <= 90) return '~' + sec + 's';
    var lo = Math.max(1, Math.round(sec / 60));
    return '~' + lo + '–' + (lo * 2) + ' min';
  }

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

  /* data/receipt rows render through ONE helper so a restored feed (session or
     server history) rebuilds them exactly like the live path did */
  function appendData(host, b) {
    var rows = b.rows.map(function (r) {
      return '<div class="row"><span>' + esc(r[0]) + '</span><b>' + esc(r[1]) + '</b></div>';
    }).join('');
    host.appendChild(el('<div class="data">' + rows + '</div>'));
    if (b.verify) host.appendChild(el(
      '<div class="data"><div class="row"><span>verify</span><b>' +
      (b.verify.ok ? '✓ ' + esc(b.verify.hdr_format) : '✗ FAILED') +
      '</b></div></div>'));
  }
  function appendActs(host, items) {
    var acts = el('<div class="acts"></div>');
    items.forEach(function (i) { acts.appendChild(actBtn(i)); });
    host.appendChild(acts);
  }

  function renderBlocks(blocks) {
    var last = null;
    blocks.forEach(function (b) {
      if (b.t === 'text') last = msg(b.who.toUpperCase(), fmt(b.md));
      else if ((b.t === 'data' || b.t === 'receipt') && last) {
        appendData(last, b);
        if (last._log) (last._log.rows = last._log.rows || []).push(
          { rows: b.rows, verify: b.verify || null });
      }
      else if (b.t === 'actions' && last) {
        appendActs(last, b.items);
        if (last._log) last._log.acts = b.items;
      }
      else if (b.t === 'slider' && last) {
        var sv = +b.value || 4, q = b.quote || { total_usd: 0, est_wall_sec: 0 };
        var s = el('<div class="sld"><div class="lab"><span>DURATION</span>' +
          '<span class="dv">' + sv + 's</span></div>' +
          '<input type="range" min="' + (+b.min || 1) + '" max="' + (+b.max || 8) + '" value="' + sv + '" aria-label="duration seconds">' +
          '<div class="quote"><span>est. cost</span><b class="qc">$' + (+q.total_usd || 0).toFixed(3) + '</b></div>' +
          '<div class="quote"><span>est. render</span><b class="qt">' + fmtEta(q.est_wall_sec) + '</b></div>' +
          '<div style="opacity:.72;font-size:.85em;margin-top:5px;">renders in the background — ' +
          'track it here or on the kalai card; it survives a closed tab.</div></div>');
        s.querySelector('input').oninput = function (e) {
          state.seconds = +e.target.value;
          s.querySelector('.dv').textContent = state.seconds + 's';
          api('/api/kalai/media/quote', { seconds: state.seconds, budget_usd: state.budget,
                                          has_source_image: true }).then(function (res) {
            if (!res.ok) return;
            s.querySelector('.qc').textContent = '$' + res.data.total_usd.toFixed(3);
            s.querySelector('.qt').textContent = fmtEta(res.data.est_wall_sec);
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

  /* A 401 can just mean the access token aged out (1h) while the tab sat
     backgrounded or the machine slept — refresh the session once and retry
     before telling a signed-in founder they are signed out. Always safe to
     retry: a 401'd request was rejected at auth and never executed. */
  function recoverAuth() {
    var A = window.SAAKSHE_AUTH;
    if (!A || !A.refresh || !A.signedIn()) return Promise.resolve(false);
    return Promise.resolve(A.refresh())
      .then(function () { return !!A.signedIn(); })
      .catch(function () { return false; });
  }

  /* api() reports status honestly — a 401/402 is an ANSWER, never '…' */
  function api(url, body, _retried) {
    dot('busy');
    return fetch(url, { method: 'POST', headers: hdrs({ 'content-type': 'application/json' }),
                        body: JSON.stringify(body) })
      .then(function (r) {
        return r.json().catch(function () { return null; }).then(function (d) {
          if (r.status === 401 && !_retried) {
            return recoverAuth().then(function (ok) {
              if (ok) return api(url, body, true);
              dot('err'); return { ok: false, status: 401, data: d };
            });
          }
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
    if (sg) { sendText(sg.dataset.ask || sg.textContent); return; }
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
    /* viewing and menus are repeatable — only acting/spending chips lock the
       row (VIEW HDR used to go permanently dead after one click) */
    if (action !== 'media.view' && action !== 'media.fxmenu') lockActs(b.closest('.acts'));
    if (action === 'media.render') startRender();
    else if (action === 'media.requote') { if (args.seconds) state.seconds = args.seconds; requote(); }
    else if (action === 'media.fxmenu') fxMenu();
    else if (action === 'media.fx') { state.fx = args.fx; startRender(); }
    else if (action === 'media.retrypoll' && args.job) pollJob(args.job);
    else if (action === 'media.view' && (args.job || state.job)) viewHdr(args.job || state.job);
  });

  function viewHdr(jid, _retried) {
    /* the cockpit canvas IS the screen — clear it to the player (founder,
       2026-06-12); the new-tab blob below survives only as a fallback */
    if (window.SK_VIEW_MEDIA) { SK_VIEW_MEDIA(jid); return; }
    /* the gated prod 401s a bare window.open (no Bearer on navigation) —
       fetch WITH the token and open the blob */
    dot('busy');
    fetch('/api/kalai/media/file/' + jid, { headers: hdrs({}) })
      .then(function (r) {
        if (r.status === 401 && _retried !== true) {
          return recoverAuth().then(function (ok) {
            if (ok) { viewHdr(jid, true); return null; }
            throw new Error('HTTP 401');
          });
        }
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.blob();
      })
      .then(function (bl) {
        if (bl == null) return;                     // handed off to the retry
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

  function startRender(_retried) {
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
      .then(function (r) { return r.json().catch(function () { return null; }).then(function (d) { return { ok: r.ok, status: r.status, data: d }; }); })
      .then(function (res) {
        if (res.status === 401 && _retried !== true) {
          return recoverAuth().then(function (ok) {
            if (ok) return startRender(true);
            dot('err'); httpBubble(res, 'render');
          });
        }
        dot(res.ok ? '' : 'err');
        if (res.data && res.data.job_id) { state.job = res.data.job_id; pollJob(res.data.job_id); }
        else if (!res.ok) httpBubble(res, 'render');
        else msg('▲ KALAI · ROUTER', fmt((res.data && res.data.error) || 'refused'));
      })
      .catch(function () { dot('err'); msg('▲ KALAI · ROUTER', 'render request failed — network?'); });
  }

  function pollJob(jid, mGiven) {
    if (state.pollEnd) state.pollEnd();        // a superseded poller must go fully dead
    if (state.poller) { clearInterval(state.poller); state.poller = null; }
    var m = mGiven || msg('▲ KALAI · RENDERER',
      'starting… — background render (takes minutes, not seconds). Watch it here or on the kalai card; safe to close this tab.');
    var p = m.querySelector('p');
    /* the log entry tracks the LIVE state (not the birth text) + the job id —
       that is what lets a refresh restore real progress and resume polling */
    if (m._log) { m._log.job = jid; }
    function note(t, terminal) {
      p.textContent = t;
      if (m._log) { m._log.html = fmt(t); if (terminal) m._log.job = null; }
    }
    /* `ended` makes every terminal branch fire ONCE. Without it, fetches that
       were already in flight when the backend stalled (the interval keeps
       issuing them) ALL land in .catch after the threshold and each appends
       its own RETRY — the observed wall of buttons. And the interval id is
       captured locally: clearing via state.poller could kill a NEWER poller
       while this one keeps ticking forever. */
    var fails = 0, every = 1500, ended = false, inflight = false, authTried = false, iv;
    function endPoll() {
      ended = true; clearInterval(iv);
      if (state.poller === iv) state.poller = null;
      if (state.pollEnd === endPoll) state.pollEnd = null;
    }
    state.pollEnd = endPoll;
    iv = setInterval(function () {
      if (ended || inflight) return;          // never stack requests on a slow backend
      inflight = true;
      fetch('/api/kalai/media/job/' + jid, { headers: hdrs({}) })
        .then(function (r) {
          if (!r.ok) {
            return r.json().catch(function () { return null; }).then(function (d) {
              if (ended) return null;
              if (r.status === 401 && !authTried) {
                /* the access token aged out mid-render — the render is still
                   running server-side. Refresh the session and keep polling;
                   only a 401 AFTER a refresh means really signed out. */
                authTried = true;
                return recoverAuth().then(function (ok) {
                  if (ok || ended) return null;   // next tick rides the fresh token
                  endPoll();
                  note('render check failed.', true);
                  httpBubble({ ok: false, status: 401, data: d }, 'check the render');
                  down(); persist();
                  return null;
                });
              }
              endPoll();
              if (r.status === 404) {
                /* the backend restarted mid-render and no persisted record
                   exists — say so honestly instead of a generic failure */
                note('this render did not survive a backend restart — start a new one.', true);
              } else {
                note('render check failed.', true);
                httpBubble({ ok: false, status: r.status, data: d }, 'check the render');
              }
              down(); persist();
              return null;
            });
          }
          return r.json();
        })
        .then(function (s) {
          inflight = false;
          if (s == null || ended) return;
          fails = 0; authTried = false;
          if (s.status === 'rendering') {
            note('frame ' + s.frame + '/' + s.frames + ' · rendering…');
          } else {
            endPoll();
            if (s.status === 'done') {
              p.innerHTML = '<b>done.</b>';
              if (m._log) { m._log.html = '<b>done.</b>'; m._log.job = null; }
              state.job = jid;
              renderBlocks(receiptBlocks(s, jid)); bot('joy');
            } else note('error: ' + (s.error || 'unknown'), true);
          }
          down(); persist();
        })
        .catch(function () {
          inflight = false;
          if (ended) return;
          if (++fails >= 4) {
            endPoll();
            note('lost the render — the backend stopped answering.');
            var acts = el('<div class="acts"></div>');
            acts.appendChild(actBtn({ label: 'RETRY', kind: 'primary', action: 'media.retrypoll', args: { job: jid } }));
            m.appendChild(acts); down(); persist();
          }
        });
    }, every);
    state.poller = iv;
  }

  function receiptBlocks(s, jid) {
    return [
      { t: 'text', who: 'kalai/verifier',
        md: s.verify.ok ? 'verified — ' + s.verify.hdr_format : 'HDR verify FAILED — not shipping.' },
      { t: 'receipt',
        rows: [['estimated', '$' + s.receipt.estimated_usd.toFixed(3)],
               ['cpu', s.receipt.measured_vcpu_sec + ' vCPU-s · $' + s.receipt.cpu_usd.toFixed(3)],
               ['total', '$' + s.receipt.total_usd.toFixed(3)]],
        verify: s.verify },
      { t: 'actions', items: s.verify.ok ?
        [{ label: 'VIEW HDR', kind: 'primary', action: 'media.view', args: { job: jid || '' } },
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

  function syncSend() { sendBtn.disabled = state.inflight || !readInput(); }
  input.addEventListener('input', syncSend);
  /* paste lands as plain text — markup must never enter the ask box */
  input.addEventListener('paste', function (e) {
    e.preventDefault();
    var t = (e.clipboardData || window.clipboardData).getData('text');
    if (t) document.execCommand('insertText', false, t);
  });

  /* sendText: the ONE ask path — typed sends and options chips both land here.
     Echoes the user bubble + POSTs /api/saakshe/ask. Returns true when the ask
     actually went out (false on empty / already inflight). */
  function sendText(text) {
    text = String(text == null ? '' : text).trim();
    if (!text || state.inflight) return false;
    setMode('chat');                              // an ask always surfaces the feed
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
    if (sendText(readInput())) { clearInput(); }
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
      var t = readInput();
      if (t) { msg('YOU', esc(t), true); voice.ws.send(JSON.stringify({ type: 'text', text: t })); clearInput(); }
      e.stopImmediatePropagation(); e.preventDefault();
    }
  }, true);

  sendBtn.onclick = send;
  input.addEventListener('keydown', function (e) {
    if (e.isComposing || e.keyCode === 229) return;
    /* the ask box is single-line — Enter always sends, never a newline */
    if (e.key === 'Enter') { e.preventDefault(); send(); }
  });

  /* ── faculty pills DROP the agent into the ask as an ENTITY CHIP (founder,
     2026-06-12): we are always talking to saakshe — the chip tells it WHO we
     mean, unambiguously (serialized @agent on send), never loose text.
     state.fac stays 'saakshe' forever, so the filter never hides anything. ── */
  function applyFacFilter(m) {
    var f = state.fac;
    var show = f === 'saakshe' || m.classList.contains('user') || m.dataset.fac === f;
    m.classList.toggle('hidden-fac', !show);
  }
  pane.querySelectorAll('.ch-tab').forEach(function (t) {
    t.onclick = function () {
      setMode('chat');                        // any faculty pill returns to chat
      insertEnt(t.dataset.q);
    };
  });

  /* ── pane MODES: chat ↔ settings ↔ history (the top-right ink tab drives
     them). The layout law — sidebar + canvas never move; the only thing that
     changes on the right is this pane's content. Display-only toggles: the
     feed DOM (and its scroll position) survives untouched. ── */
  var settingsEl = document.getElementById('sa-ch-settings');
  var historyEl = document.getElementById('sa-ch-history');
  var gearBtn = document.getElementById('sa-ch-gear');
  var histBtn = document.getElementById('sa-ch-hist');
  var paneMode = 'chat', feedScroll = 0;
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
    settingsEl.querySelector('.ch-setsback').onclick = function () { setMode('chat'); };
  }
  function tsMs(c) {
    var d = typeof c === 'number' ? new Date(c * 1000) : new Date(c || NaN);
    return isNaN(+d) ? 0 : +d;
  }
  /* the HISTORY view — the persisted transcript regrouped into sittings
     (a quiet gap over 45 min starts a new one); tapping a sitting opens it
     in the feed, exactly like the live path renders it. */
  function fillHistory() {
    historyEl.innerHTML =
      '<button class="ch-setsback" type="button">back to chat</button>' +
      '<div class="ch-setsnote">the witness transcript — every sitting, newest first</div>' +
      '<div class="ch-histlist"><div class="ch-setsnote">loading…</div></div>';
    historyEl.querySelector('.ch-setsback').onclick = function () { setMode('chat'); };
    var list = historyEl.querySelector('.ch-histlist');
    fetch('/api/saakshe/messages?limit=200', { headers: hdrs({}) })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        var rows = (d && Array.isArray(d.messages)) ? d.messages : [];
        if (!rows.length) {
          list.innerHTML = '<div class="ch-setsnote">no saved chats yet — ask saakshe something and the sitting lands here.</div>';
          return;
        }
        var secs = [], cur = null, last = 0;
        rows.forEach(function (r) {
          var t = tsMs(r.created_at);
          if (!cur || (t && last && (t - last) > 45 * 60000)) { cur = { at: t, rows: [] }; secs.push(cur); }
          cur.rows.push(r);
          if (t) last = t;
        });
        list.innerHTML = '';
        secs.slice().reverse().forEach(function (s) {
          var first = s.rows.filter(function (r) { return r.role === 'you'; })[0] || s.rows[0] || {};
          var when = s.at ? new Date(s.at) : null;
          var label = when
            ? when.toLocaleDateString(undefined, { day: 'numeric', month: 'short' }) +
              ' · ' + ('0' + when.getHours()).slice(-2) + ':' + ('0' + when.getMinutes()).slice(-2)
            : '—';
          var b = el('<button class="ch-histrow" type="button"><span class="hwhen">' + esc(label) +
            '</span><span class="htxt">' + esc(String(first.text || '…').slice(0, 90)) +
            '</span><span class="hct">' + s.rows.length + ' message' + (s.rows.length === 1 ? '' : 's') +
            '</span></button>');
          b.onclick = function () { renderHistory(s.rows); setMode('chat'); down(true); };
          list.appendChild(b);
        });
      })
      .catch(function () {
        list.innerHTML = '<div class="ch-setsnote">could not reach the transcript — signed in? backend up?</div>';
      });
  }
  function setMode(mode) {
    if (mode === paneMode) return;
    if (paneMode === 'chat') feedScroll = feed.scrollTop;
    if (mode === 'settings') fillSettings();
    if (mode === 'history') fillHistory();
    paneMode = mode;
    pane.classList.toggle('settings-on', mode === 'settings');
    pane.classList.toggle('history-on', mode === 'history');
    gearBtn.classList.toggle('on', mode === 'settings');
    gearBtn.setAttribute('aria-pressed', mode === 'settings' ? 'true' : 'false');
    histBtn.classList.toggle('on', mode === 'history');
    histBtn.setAttribute('aria-pressed', mode === 'history' ? 'true' : 'false');
    if (mode === 'chat') feed.scrollTop = feedScroll;     // exactly as it was
  }
  gearBtn.onclick = function () { setMode(paneMode === 'settings' ? 'chat' : 'settings'); };
  histBtn.onclick = function () { setMode(paneMode === 'history' ? 'chat' : 'history'); };
  /* NEW CHAT — a fresh sitting: the feed clears (the transcript keeps the old
     sitting; it stays reachable under HISTORY), the witness greets again. */
  document.getElementById('sa-ch-new').onclick = function () {
    setMode('chat');
    if (state.pollEnd) state.pollEnd();           // a live render poller must not write into the fresh feed
    feed.innerHTML = ''; log.length = 0;
    try { sessionStorage.removeItem('sk-chat-feed'); } catch (e) {}
    clearInput();
    greet();
  };

  /* ── the pane never closes on desktop (founder, 2026-06-12) — collapse is
     retired; the FAB stays for narrow screens only ── */
  var H = document.documentElement;
  H.classList.remove('sk-chat-collapsed');
  try { localStorage.removeItem('sk-chat-collapsed'); } catch (e) {}
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
      setMode('chat');
      if (window.innerWidth < 1100) { H.classList.add('sk-chat-open'); }
      down(true); input.focus();
    },
    ask: function (text) {
      if (!text) return;
      sendText(String(text));
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
     stored shape is {v:2, items:[{who, html, user, ts, rows, acts, opts, job}]}
     re-rendered through msg(); anything else (the old raw-innerHTML format,
     garbage) is discarded. A live job id on an entry RESUMES polling — the
     render survives the refresh, so the card must too. */
  function greet() {
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

  function restoreItems(items) {
    items.forEach(function (it) {
      if (!it || typeof it.html !== 'string') return;
      var rm = msg(String(it.who || 'SΛΛKSHE'), it.html, !!it.user, String(it.ts || ''));
      (Array.isArray(it.rows) ? it.rows : []).forEach(function (d) {
        if (d && Array.isArray(d.rows)) appendData(rm, d);
      });
      if (rm._log && Array.isArray(it.rows)) rm._log.rows = it.rows;
      if (Array.isArray(it.acts) && it.acts.length) {
        appendActs(rm, it.acts);
        if (rm._log) rm._log.acts = it.acts;
      }
      if (Array.isArray(it.opts) && it.opts.length) {
        /* restored options render SPENT — they reflect the moment they were
           offered; keep them on the fresh log entry so they survive again */
        if (rm._log) rm._log.opts = it.opts;
        renderOpts(rm, it.opts, true);
      }
      if (it.job) pollJob(String(it.job), rm);   // the render is still going — pick it back up
    });
    down(true);
  }

  function hhmm(c) {
    var d = typeof c === 'number' ? new Date(c * 1000) : new Date(c || NaN);
    if (isNaN(+d)) return '';
    return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
  }

  /* server history: the persisted transcript (closed tab / new device). Renders
     the stored reply blocks minus live-only kinds (slider/progress); a persisted
     render_done record rebuilds its receipt + a working VIEW HDR. */
  function renderHistory(rows) {
    feed.innerHTML = ''; log.length = 0;
    rows.forEach(function (r) {
      var who = String(r.role || 'saakshe'), when = hhmm(r.created_at);
      if (who === 'you') { msg('YOU', fmt(String(r.text || '')), true, when); return; }
      var meta = r.meta || {};
      var m = msg(who.toUpperCase(), fmt(String(r.text || '')), false, when);
      if (meta.kind === 'render_done' && meta.job_id && meta.receipt && meta.verify) {
        renderBlocks(receiptBlocks({ receipt: meta.receipt, verify: meta.verify }, meta.job_id));
        return;
      }
      (Array.isArray(meta.blocks) ? meta.blocks : []).forEach(function (b) {
        if (!b) return;
        if ((b.t === 'data' || b.t === 'receipt') && Array.isArray(b.rows)) {
          appendData(m, b);
          if (m._log) (m._log.rows = m._log.rows || []).push({ rows: b.rows, verify: b.verify || null });
        } else if (b.t === 'actions' && Array.isArray(b.items)) {
          appendActs(m, b.items);
          if (m._log) m._log.acts = b.items;
        } else if (b.t === 'options' && Array.isArray(b.items) && b.items.length) {
          var clean = b.items.map(function (i) {
            return { label: String(i.label || i.send || ''), send: String(i.send || i.label || '') };
          });
          if (m._log) m._log.opts = clean;
          renderOpts(m, clean, true);
        }
      });
    });
    down(true); persist();
  }

  function whenAuthSettled(cb) {
    var t0 = Date.now();
    (function tick() {
      var A = window.SAAKSHE_AUTH;
      if ((A && A._ready) || Date.now() - t0 > 7000) return cb();
      setTimeout(tick, 250);
    })();
  }

  var restored = null;
  try { restored = JSON.parse(sessionStorage.getItem('sk-chat-feed') || 'null'); }
  catch (e) { restored = null; }
  if (restored && restored.v === 2 && Array.isArray(restored.items) && restored.items.length) {
    restoreItems(restored.items);
  } else {
    greet();
    /* no session feed (closed tab) — once auth settles, swap in the persisted
       transcript from the backend; an empty or failed fetch keeps the greeting */
    whenAuthSettled(function () {
      fetch('/api/saakshe/messages', { headers: hdrs({}) })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) {
          if (d && Array.isArray(d.messages) && d.messages.length) renderHistory(d.messages);
        })
        .catch(function () {});
    });
  }
  syncSend();
})();
