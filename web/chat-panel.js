/* saakshe chat panel — always-on right pane. Renders presenter blocks.
   Block kinds (contract in service/presenter.py): text · data · actions ·
   slider · progress · receipt. The panel formats; it never authors. */
(function () {
  var pane = document.getElementById('sa-chatpane');
  if (!pane) return;
  pane.innerHTML =
    '<div class="ch-head"><span class="brand">SΛΛKSHE</span>' +
    '<span class="t">· COMPANY CHAT</span><span class="live"></span></div>' +
    '<div class="ch-tabs">' +
    '<span class="ch-tab on" data-q="saakshe">saakshe</span>' +
    '<span class="ch-tab" data-q="manas" style="color:#e3a200">● manas</span>' +
    '<span class="ch-tab" data-q="arivu" style="color:#0a39ff">◆ arivu</span>' +
    '<span class="ch-tab" data-q="kalai" style="color:#ff2d2d">▲ kalai</span>' +
    '<span class="ch-tab" data-q="kural" style="color:#00a86b">■ kural</span></div>' +
    '<div class="ch-feed" id="sa-ch-feed"></div>' +
    '<div class="ch-input"><input id="sa-ch-inp" placeholder="ask saakshe…">' +
    '<button id="sa-ch-mic" title="voice — Gemini Live">🎙</button>' +
    '<button id="sa-ch-send">→</button></div>';

  var feed = document.getElementById('sa-ch-feed');
  var state = { budget: 1.0, seconds: 4, fx: 'sat_sort', image: null, job: null };
  var FX = ['sat_sort', 'dark_sort', 'vert_sort', 'hue_sort', 'ripple', 'wave',
            'light_sweep', 'charcoal', 'lith', 'sabattier', 'cinestill', 'ca_pulse'];

  function el(h) { var d = document.createElement('div'); d.innerHTML = h; return d.firstElementChild; }
  function down() { feed.scrollTop = feed.scrollHeight; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]; }); }
  function hdrs(extra) { return (window.SA_HEADERS || Object)(extra || {}); }

  function msg(who, text, user) {
    var m = el('<div class="msg' + (user ? ' user' : '') + '"><div class="who">' +
               esc(who) + '</div><p>' + text + '</p></div>');
    feed.appendChild(m); down(); return m;
  }

  function typing(cb, ms) {
    var t = el('<div class="typing"><span></span><span></span><span></span></div>');
    feed.appendChild(t); down();
    setTimeout(function () { t.remove(); cb(); down(); }, ms || 600);
  }

  function lockActs(scope) {
    scope.querySelectorAll('.act').forEach(function (b) { b.classList.add('done'); });
  }

  function renderBlocks(blocks) {
    var last = null;
    blocks.forEach(function (b) {
      if (b.t === 'text') last = msg(b.who.toUpperCase(), esc(b.md));
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
        var btns = b.items.map(function (i) {
          return '<button class="act ' + (i.kind || 'plain') + '" data-action="' + i.action +
                 "\" data-args='" + JSON.stringify(i.args || {}) + "'>" + esc(i.label) + '</button>';
        }).join('');
        last.appendChild(el('<div class="acts">' + btns + '</div>'));
      }
      else if (b.t === 'slider' && last) {
        var s = el('<div class="sld"><div class="lab"><span>DURATION</span>' +
          '<span class="dv">' + b.value + 's</span></div>' +
          '<input type="range" min="' + b.min + '" max="' + b.max + '" value="' + b.value + '">' +
          '<div class="quote"><span>est. cost</span><b class="qc">$' + b.quote.total_usd.toFixed(3) + '</b></div>' +
          '<div class="quote"><span>est. render</span><b class="qt">~' + b.quote.est_wall_sec + 's</b></div></div>');
        s.querySelector('input').oninput = function (e) {
          state.seconds = +e.target.value;
          s.querySelector('.dv').textContent = state.seconds + 's';
          api('/api/kalai/media/quote', { seconds: state.seconds, budget_usd: state.budget,
                                          has_source_image: true }).then(function (q) {
            s.querySelector('.qc').textContent = '$' + q.total_usd.toFixed(3);
            s.querySelector('.qt').textContent = '~' + q.est_wall_sec + 's';
          });
        };
        last.appendChild(s);
      }
      else if (b.t === 'progress') pollJob(b.job_id);
    });
    down();
  }

  function api(url, body) {
    return fetch(url, { method: 'POST', headers: hdrs({ 'content-type': 'application/json' }),
                        body: JSON.stringify(body) }).then(function (r) { return r.json(); });
  }

  feed.addEventListener('click', function (e) {
    var b = e.target.closest('.act');
    if (!b || b.classList.contains('done')) return;
    lockActs(b.closest('.acts'));
    var action = b.dataset.action, args = JSON.parse(b.dataset.args || '{}');
    if (action === 'media.render') startRender();
    else if (action === 'media.requote') { if (args.seconds) state.seconds = args.seconds; requote(); }
    else if (action === 'media.fxmenu') fxMenu();
    else if (action === 'media.fx') { state.fx = args.fx; startRender(); }
    else if (action === 'media.view' && state.job) window.open('/api/kalai/media/file/' + state.job);
  });

  function fxMenu() {
    typing(function () {
      var m = msg('▲ KALAI · FX-PICKER', 'pick the effect:');
      m.appendChild(el('<div class="acts">' + FX.map(function (f) {
        return '<button class="act ' + (f === state.fx ? 'ok' : 'plain') +
               '" data-action="media.fx" data-args=\'{"fx":"' + f + '"}\'>' +
               f.replace(/_/g, ' ').toUpperCase() + '</button>';
      }).join('') + '</div>'));
    });
  }

  function startRender() {
    if (!state.image) {
      var m = msg('▲ KALAI · PRODUCER', 'drop the source image:');
      var inp = el('<input type="file" accept="image/*" style="margin-top:8px;font-size:11px">');
      inp.onchange = function () { state.image = inp.files[0]; startRender(); };
      m.appendChild(inp); down(); return;
    }
    var fd = new FormData();
    fd.append('image', state.image);
    fd.append('fx', state.fx);
    fd.append('seconds', state.seconds);
    fd.append('budget_usd', state.budget);
    fetch('/api/kalai/media/render', { method: 'POST', headers: hdrs({}), body: fd })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.job_id) { state.job = d.job_id; pollJob(d.job_id); }
        else msg('▲ KALAI · ROUTER', esc(d.error || 'refused'));
      });
  }

  function pollJob(jid) {
    var m = msg('▲ KALAI · RENDERER', 'starting…');
    var p = m.querySelector('p');
    var iv = setInterval(function () {
      fetch('/api/kalai/media/job/' + jid, { headers: hdrs({}) })
        .then(function (r) { return r.json(); })
        .then(function (s) {
          if (s.status === 'rendering') {
            p.textContent = 'frame ' + s.frame + '/' + s.frames + ' · rendering…';
          } else {
            clearInterval(iv);
            if (s.status === 'done') {
              p.innerHTML = '<b>done.</b>';
              renderBlocks(receiptBlocks(s));
            } else p.textContent = 'error: ' + (s.error || 'unknown');
          }
          down();
        });
    }, 1500);
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
                                    has_source_image: true }).then(function (q) {
      typing(function () {
        renderBlocks([
          { t: 'text', who: 'kalai/pricer', md: 'requoted.' },
          { t: 'slider', action: 'media.requote', min: 1, max: 8, value: q.seconds,
            quote: { total_usd: q.total_usd, est_wall_sec: q.est_wall_sec } },
          { t: 'actions', items: [
            { label: 'RENDER', kind: 'primary', action: 'media.render', args: {} },
            { label: 'PICK FX (12)', kind: 'plain', action: 'media.fxmenu', args: {} }] }]);
      });
    });
  }

  function send() {
    var i = document.getElementById('sa-ch-inp');
    var text = i.value.trim();
    if (!text) return;
    msg('YOU', esc(text), true);
    i.value = '';
    var m = text.match(/\$\s*(\d+(?:\.\d+)?)/);
    if (m) state.budget = +m[1];
    typing(function () {
      api('/api/saakshe/ask', { text: text }).then(function (d) {
        renderBlocks(d.blocks && d.blocks.length ? d.blocks :
          [{ t: 'text', who: 'saakshe', md: d.text || '…' }]);
      });
    });
  }
  /* ── voice: /ws/voice — Gemini Live native-audio bridge ──
     demo mode: text frames through the same witness tools.
     live mode: mic PCM16@16k up (hex), PCM16@24k down, replies as messages. */
  var voice = { ws: null, on: false, ctx: null, src: null, proc: null,
                playCtx: null, playAt: 0 };

  function voiceStop() {
    voice.on = false;
    if (voice.proc) { voice.proc.disconnect(); voice.proc = null; }
    if (voice.src) { voice.src.disconnect(); voice.src = null; }
    if (voice.ctx) { voice.ctx.close(); voice.ctx = null; }
    if (voice.ws) { try { voice.ws.close(); } catch (e) {} voice.ws = null; }
    micBtn.style.background = '';
    micBtn.textContent = '🎙';
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
    var ws = new WebSocket(proto + location.host + '/ws/voice');
    voice.ws = ws; voice.on = true;
    micBtn.textContent = '…';
    ws.onmessage = function (ev) {
      var m = JSON.parse(ev.data);
      if (m.type === 'hello') {
        msg('SΛΛKSHE · VOICE', esc(m.mode === 'live'
          ? 'voice live — Gemini native audio. speak.'
          : 'voice in demo mode — type below, same tools answer.'));
        if (m.mode === 'live') micUp(ws); else micBtn.textContent = '⌨';
        micBtn.style.background = '#d8f7e8';
      }
      else if (m.type === 'audio') playPcm(m.data);
      else if (m.type === 'reply') msg('SΛΛKSHE · VOICE', esc(m.text || ''));
      else if (m.type === 'notice') msg('SΛΛKSHE · VOICE', esc(m.text || ''));
    };
    ws.onclose = voiceStop;
    ws.onerror = voiceStop;
  }

  function micUp(ws) {
    navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 16000, channelCount: 1 } })
      .then(function (stream) {
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
        micBtn.textContent = '⏺';
      })
      .catch(function () { msg('SΛΛKSHE · VOICE', 'mic permission denied — voice off.'); voiceStop(); });
  }

  var micBtn = document.getElementById('sa-ch-mic');
  micBtn.onclick = function () { voice.on ? voiceStop() : voiceStart(); };
  // demo-mode keyboard frames also go over the voice socket when it's open in ⌨ mode
  document.getElementById('sa-ch-inp').addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && voice.on && voice.ws && voice.ws.readyState === 1 &&
        micBtn.textContent === '⌨') {
      var i = document.getElementById('sa-ch-inp');
      var t = i.value.trim();
      if (t) { msg('YOU', esc(t), true); voice.ws.send(JSON.stringify({ type: 'text', text: t })); i.value = ''; }
      e.stopImmediatePropagation(); e.preventDefault();
    }
  }, true);

  document.getElementById('sa-ch-send').onclick = send;
  document.getElementById('sa-ch-inp').addEventListener('keydown', function (e) {
    if (e.key === 'Enter') send();
  });
  pane.querySelectorAll('.ch-tab').forEach(function (t) {
    t.onclick = function () {
      pane.querySelectorAll('.ch-tab').forEach(function (x) { x.classList.remove('on'); });
      t.classList.add('on');
    };
  });
})();
