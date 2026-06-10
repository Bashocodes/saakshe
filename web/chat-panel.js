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
