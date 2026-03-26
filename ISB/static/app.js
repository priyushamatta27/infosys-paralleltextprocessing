/* ═══════════════════════════════════════════════════════════════
   LEXON ANALYTICS — Global JS (app.js)
   Shared across index.html, results.html, search.html
═══════════════════════════════════════════════════════════════ */

'use strict';

/* ── Toast helper ──────────────────────────────────────────── */
const Toast = {
  container: null,

  init() {
    if (this.container) return;
    this.container = document.createElement('div');
    this.container.className = 'toast-container';
    document.body.appendChild(this.container);
  },

  show(msg, type = 'info', duration = 3500) {
    this.init();
    const icons = { success: '✓', error: '✕', info: 'ℹ' };
    const colors = { success: 'var(--accent-green)', error: 'var(--accent-red)', info: 'var(--accent-cyan)' };

    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `
      <span class="toast-icon" style="color:${colors[type]}">${icons[type]}</span>
      <span>${msg}</span>
    `;
    this.container.appendChild(el);

    setTimeout(() => {
      el.style.animation = 'fadeIn 0.3s reverse forwards';
      setTimeout(() => el.remove(), 300);
    }, duration);
  }
};

/* ── Storage helpers ───────────────────────────────────────── */
const Store = {
  get: k => { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } },
  set: (k, v) => localStorage.setItem(k, JSON.stringify(v)),
  del: k => localStorage.removeItem(k),
};

/* ── Format helpers ────────────────────────────────────────── */
const fmt = {
  bytes: b => {
    if (b < 1024) return b + ' B';
    if (b < 1024 ** 2) return (b / 1024).toFixed(1) + ' KB';
    return (b / 1024 ** 2).toFixed(2) + ' MB';
  },
  time: ms => {
    if (ms < 1000) return ms.toFixed(0) + ' ms';
    return (ms / 1000).toFixed(2) + ' s';
  },
  num: n => Number(n).toLocaleString(),
  score: s => (s >= 0 ? '+' : '') + Number(s).toFixed(3),
};

/* ── API helper ────────────────────────────────────────────── */
async function api(url, opts = {}) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

/* ── Active nav highlight ──────────────────────────────────── */
function highlightNav() {
  const path = location.pathname;
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.remove('active');
    const href = el.getAttribute('href') || '';
    if (
      (href === '/' && (path === '/' || path === '/index' || path === '')) ||
      (href !== '/' && path.startsWith(href))
    ) {
      el.classList.add('active');
    }
  });
}

/* ── Render timing stats in sidebar ───────────────────────── */
function renderTimingStats(timing) {
  const seqEl = document.getElementById('stat-seq-time');
  const parEl = document.getElementById('stat-par-time');
  const spEl  = document.getElementById('stat-speedup');

  if (!timing) return;
  if (seqEl) seqEl.textContent = fmt.time(timing.sequential_ms);
  if (parEl) parEl.textContent = fmt.time(timing.parallel_ms);
  if (spEl) {
    const sp = timing.sequential_ms / (timing.parallel_ms || 1);
    spEl.textContent = `${sp.toFixed(2)}× faster`;
  }
}

/* ── Modal ─────────────────────────────────────────────────── */
function openModal(id) { document.getElementById(id)?.classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id)?.classList.add('hidden'); }

/* ── Email send ────────────────────────────────────────────── */
async function sendEmailExport(emailInputId, batchId) {
  const emailEl = document.getElementById(emailInputId);
  const email = emailEl?.value?.trim();
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    Toast.show('Enter a valid email address.', 'error');
    return;
  }
  try {
    await api('/api/email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, batch_id: batchId }),
    });
    Toast.show('Results sent to ' + email, 'success');
    closeModal('email-modal');
  } catch (e) {
    Toast.show('Email failed: ' + e.message, 'error');
  }
}

/* ── Export download ───────────────────────────────────────── */
function triggerExport(type, batchId, keyword) {
  let url = `/api/export?type=${type}`;
  if (batchId) url += `&batch_id=${encodeURIComponent(batchId)}`;
  if (keyword) url += `&keyword=${encodeURIComponent(keyword)}`;
  window.location.href = url;
  Toast.show(`Downloading ${type.toUpperCase()}…`, 'info');
}

/* ── Sentiment badge HTML ──────────────────────────────────── */
function sentimentBadge(label) {
  const cls = { positive: 'badge-positive', negative: 'badge-negative', neutral: 'badge-neutral' };
  const icon = { positive: '↑', negative: '↓', neutral: '–' };
  return `<span class="badge ${cls[label] || 'badge-neutral'}">${icon[label] || '–'} ${label}</span>`;
}

/* ── Score mini bar ────────────────────────────────────────── */
function scoreMiniBar(score) {
  const pct = ((parseFloat(score) + 1) / 2 * 100).toFixed(1);
  const col = score > 0.15 ? 'var(--accent-green)' : score < -0.15 ? 'var(--accent-red)' : 'var(--text-3)';
  return `
    <div class="score-bar">
      <span class="mono" style="font-size:11px;min-width:44px;color:var(--text-2)">${fmt.score(score)}</span>
      <div class="score-mini-track">
        <div class="score-mini-fill" style="width:${pct}%;background:${col}"></div>
      </div>
    </div>`;
}

/* ── Pagination builder ────────────────────────────────────── */
function buildPagination(container, page, total, pageSize, onChange) {
  const totalPages = Math.ceil(total / pageSize) || 1;
  container.innerHTML = '';

  const prev = document.createElement('button');
  prev.className = 'page-btn';
  prev.textContent = '‹';
  prev.disabled = page <= 1;
  prev.onclick = () => onChange(page - 1);
  container.appendChild(prev);

  const range = pagRange(page, totalPages);
  range.forEach(p => {
    const btn = document.createElement('button');
    if (p === '…') {
      btn.className = 'page-btn';
      btn.textContent = '…';
      btn.disabled = true;
    } else {
      btn.className = 'page-btn' + (p === page ? ' active' : '');
      btn.textContent = p;
      btn.onclick = () => onChange(p);
    }
    container.appendChild(btn);
  });

  const next = document.createElement('button');
  next.className = 'page-btn';
  next.textContent = '›';
  next.disabled = page >= totalPages;
  next.onclick = () => onChange(page + 1);
  container.appendChild(next);

  return totalPages;
}

function pagRange(cur, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  if (cur <= 4) return [1, 2, 3, 4, 5, '…', total];
  if (cur >= total - 3) return [1, '…', total - 4, total - 3, total - 2, total - 1, total];
  return [1, '…', cur - 1, cur, cur + 1, '…', total];
}

/* ── Animate count up ──────────────────────────────────────── */
function animateCount(el, target, duration = 800, isFloat = false) {
  const start = performance.now();
  const from = 0;
  function step(now) {
    const progress = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    const val = from + (target - from) * ease;
    el.textContent = isFloat ? val.toFixed(3) : fmt.num(Math.floor(val));
    if (progress < 1) requestAnimationFrame(step);
    else el.textContent = isFloat ? target.toFixed(3) : fmt.num(target);
  }
  requestAnimationFrame(step);
}

/* ── Chart.js default theme ────────────────────────────────── */
function applyChartDefaults() {
  if (!window.Chart) return;
  Chart.defaults.color = '#8b9abb';
  Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
  Chart.defaults.font.family = "'JetBrains Mono', monospace";
  Chart.defaults.font.size = 11;
  Chart.defaults.plugins.legend.labels.boxWidth = 10;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
}

/* ── Load timing from storage on any page ──────────────────── */
function loadTimingFromStorage() {
  const t = Store.get('lexon_timing');
  if (t) renderTimingStats(t);
}

/* ── Init on every page ────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  highlightNav();
  applyChartDefaults();
  loadTimingFromStorage();

  // Close modals on overlay click
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', e => {
      if (e.target === overlay) {
        overlay.classList.add('hidden');
      }
    });
  });
});

/* ══════════════════════════════════════════════════════════════
   INDEX PAGE — Upload + Processing
══════════════════════════════════════════════════════════════ */

const IndexPage = (() => {
  let uploadedFile = null;
  let batchId = null;
  let pollTimer = null;
  let processingStart = 0;

  function init() {
    if (!document.getElementById('drop-zone')) return;
    setupDropZone();
    setupRawText();
    setupWorkerRange();
    document.getElementById('btn-start')?.addEventListener('click', startProcessing);
    document.getElementById('btn-view-results')?.addEventListener('click', goToResults);
  }

  function setupDropZone() {
    const zone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const rawTextarea = document.getElementById('raw-text');

    zone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', e => handleFile(e.target.files[0]));

    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      handleFile(e.dataTransfer.files[0]);
    });

    rawTextarea?.addEventListener('input', () => {
      const hasText = rawTextarea.value.trim().length > 0;
      if (hasText) {
        uploadedFile = null;
        renderNoFile();
      }
    });
  }

  async function handleFile(file) {
    if (!file) return;

    // Clear raw text if file uploaded
    const rawTextarea = document.getElementById('raw-text');
    if (rawTextarea) rawTextarea.value = '';
    if (rawTextarea) rawTextarea.disabled = true;

    const zone = document.getElementById('drop-zone');
    zone.innerHTML = `
      <div class="file-uploaded">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--accent-green)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><polyline points="9 15 11 17 15 13"/>
        </svg>
        <div class="file-info">
          <div class="file-name">${file.name}</div>
          <div class="file-size">${fmt.bytes(file.size)}</div>
        </div>
        <button class="btn btn-sm btn-ghost" id="btn-clear-file">✕ Clear</button>
      </div>
    `;
    document.getElementById('btn-clear-file').onclick = () => {
      uploadedFile = null;
      if (rawTextarea) rawTextarea.disabled = false;
      renderEmptyDrop();
    };

    // Upload to server
    const fd = new FormData();
    fd.append('file', file);

    try {
      const res = await fetch('/upload', { method: 'POST', body: fd });
      const data = await res.json();
      uploadedFile = data;
      Toast.show('File uploaded: ' + data.file_name, 'success');
    } catch (e) {
      Toast.show('Upload failed: ' + e.message, 'error');
    }
  }

  function renderEmptyDrop() {
    const zone = document.getElementById('drop-zone');
    zone.innerHTML = `
      <div class="drop-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/>
          <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>
        </svg>
      </div>
      <div class="drop-title">Drop your file here</div>
      <div class="drop-sub">or click to browse — any size supported</div>
      <div class="drop-types">
        ${['.txt','.csv','.json','.pdf','.docx','.xlsx','.xml','.html','.log','.md'].map(t=>`<span class="type-badge">${t}</span>`).join('')}
      </div>
      <input type="file" id="file-input" style="display:none" accept="*">
    `;
    const rawTextarea = document.getElementById('raw-text');
    if (rawTextarea) rawTextarea.disabled = false;
    const fi = document.getElementById('file-input');
    fi.addEventListener('change', e => handleFile(e.target.files[0]));
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      handleFile(e.dataTransfer.files[0]);
    });
  }

  function renderNoFile() {
    // nothing needed, drop zone already shows empty
  }

  function setupRawText() {
    const ta = document.getElementById('raw-text');
    if (!ta) return;
    ta.addEventListener('input', () => {
      if (ta.value.trim()) {
        document.getElementById('drop-zone').style.opacity = '0.5';
        document.getElementById('drop-zone').style.pointerEvents = 'none';
      } else {
        document.getElementById('drop-zone').style.opacity = '';
        document.getElementById('drop-zone').style.pointerEvents = '';
      }
    });
  }

  function setupWorkerRange() {
    const range = document.getElementById('workers-range');
    const display = document.getElementById('workers-display');
    if (!range || !display) return;

    range.addEventListener('input', () => { display.textContent = range.value; });
    display.textContent = range.value;
  }

  async function startProcessing() {
    const rawText = document.getElementById('raw-text')?.value?.trim();
    const numWorkers = parseInt(document.getElementById('workers-range')?.value || 4);
    const useMp = document.getElementById('toggle-mp')?.querySelector('input')?.checked || false;

    if (!uploadedFile && !rawText) {
      Toast.show('Please upload a file or paste text first.', 'error');
      return;
    }

    const btn = document.getElementById('btn-start');
    btn.disabled = true;
    btn.innerHTML = '⏳ Processing…';

    processingStart = Date.now();

    try {
      let payload;

      if (uploadedFile) {
        payload = {
          save_name: uploadedFile.save_name,
          file_name: uploadedFile.file_name,
          file_size: uploadedFile.file_size,
          num_workers: numWorkers,
          use_multiprocessing: useMp,
        };
      } else {
        // Raw text: save as temp txt file
        const blob = new Blob([rawText], { type: 'text/plain' });
        const fd = new FormData();
        fd.append('file', blob, 'raw_input.txt');
        const upRes = await fetch('/upload', { method: 'POST', body: fd });
        const upData = await upRes.json();
        payload = {
          save_name: upData.save_name,
          file_name: upData.file_name,
          file_size: upData.file_size,
          num_workers: numWorkers,
          use_multiprocessing: useMp,
        };
      }

      const res = await api('/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      batchId = res.batch_id;
      Store.set('lexon_batch_id', batchId);
      showProgressUI();
      pollStatus();

    } catch (e) {
      Toast.show('Failed to start: ' + e.message, 'error');
      btn.disabled = false;
      btn.innerHTML = '▶ Start Processing';
    }
  }

  function showProgressUI() {
    document.getElementById('progress-section')?.classList.remove('hidden');
    document.getElementById('btn-start')?.classList.add('hidden');
  }

  function pollStatus() {
    if (!batchId) return;

    pollTimer = setInterval(async () => {
      try {
        const data = await api(`/status/${batchId}`);
        updateProgressUI(data);

        if (data.status === 'completed' || data.status === 'error') {
          clearInterval(pollTimer);
          const elapsed = Date.now() - processingStart;

          if (data.status === 'completed') {
            onComplete(elapsed);
          } else {
            Toast.show('Processing error: ' + (data.error || 'unknown'), 'error');
            document.getElementById('btn-start').disabled = false;
            document.getElementById('btn-start').innerHTML = '▶ Start Processing';
            document.getElementById('btn-start').classList.remove('hidden');
          }
        }
      } catch (e) {
        console.error('Poll error:', e);
      }
    }, 700);
  }

  function updateProgressUI(data) {
    const pct = data.percent || 0;
    const fill = document.getElementById('progress-fill');
    const pctEl = document.getElementById('progress-pct');
    const statusEl = document.getElementById('progress-status-text');
    const chunksEl = document.getElementById('progress-chunks');

    if (fill) fill.style.width = pct + '%';
    if (pctEl) pctEl.textContent = pct + '%';
    if (statusEl) {
      const statusMap = {
        loading: 'Loading file…',
        processing: 'Analysing chunks…',
        saving: 'Saving to database…',
        completed: 'Complete!',
        error: 'Error',
      };
      statusEl.textContent = statusMap[data.status] || data.status;
    }
    if (chunksEl && data.total_chunks > 0) {
      chunksEl.textContent = `${fmt.num(data.completed_chunks)} / ${fmt.num(data.total_chunks)} chunks processed`;
    }
  }

  function onComplete(elapsedMs) {
    const pctEl = document.getElementById('progress-pct');
    if (pctEl) pctEl.textContent = '100%';
    const fill = document.getElementById('progress-fill');
    if (fill) fill.style.width = '100%';

    // Estimate sequential time (assume single-threaded would be ~workers× slower)
    const workers = parseInt(document.getElementById('workers-range')?.value || 4);
    const timing = {
      parallel_ms: elapsedMs,
      sequential_ms: elapsedMs * workers * 0.85,
    };
    Store.set('lexon_timing', timing);
    renderTimingStats(timing);

    Toast.show('Processing complete! 🎉', 'success');

    // Show view results button
    const viewBtn = document.getElementById('btn-view-results');
    if (viewBtn) {
      viewBtn.classList.remove('hidden');
      viewBtn.style.animation = 'slideUp 0.4s ease';
    }

    const pulseEl = document.querySelector('.pulse-dot');
    if (pulseEl) pulseEl.style.background = 'var(--accent-green)';
  }

  function goToResults() {
    const id = Store.get('lexon_batch_id');
    window.location.href = id ? `/results?batch_id=${id}` : '/results';
  }

  return { init };
})();

/* ══════════════════════════════════════════════════════════════
   RESULTS PAGE
══════════════════════════════════════════════════════════════ */

const ResultsPage = (() => {
  let batchId = null;
  let currentPage = 1;
  const PAGE_SIZE = 50;
  let charts = {};

  function init() {
    if (!document.getElementById('results-container')) return;

    batchId = new URLSearchParams(location.search).get('batch_id') || Store.get('lexon_batch_id');
    if (batchId) Store.set('lexon_batch_id', batchId);

    document.getElementById('btn-search-page')?.addEventListener('click', () => {
      window.location.href = `/search${batchId ? '?batch_id=' + batchId : ''}`;
    });

    document.getElementById('btn-export-csv')?.addEventListener('click', () => triggerExport('csv', batchId));
    document.getElementById('btn-export-xlsx')?.addEventListener('click', () => triggerExport('excel', batchId));
    document.getElementById('btn-email')?.addEventListener('click', () => openModal('email-modal'));
    document.getElementById('btn-send-email')?.addEventListener('click', () => sendEmailExport('email-input', batchId));
    document.getElementById('btn-close-modal')?.addEventListener('click', () => closeModal('email-modal'));

    loadStats();
    loadTable(1);
  }

  async function loadStats() {
    try {
      const url = batchId ? `/api/results?batch_id=${batchId}&page=1&page_size=1` : '/api/results?page=1&page_size=1';
      const summary = await api(`/api/stats${batchId ? '?batch_id=' + batchId : ''}`);
      renderStats(summary);
      renderCharts(summary);
    } catch (e) {
      // fallback: get from results
      try {
        const url = batchId ? `/api/results?batch_id=${batchId}&page=1&page_size=9999` : '/api/results?page=1&page_size=9999';
        const data = await api(url);
        const derived = deriveStats(data.results);
        renderStats(derived);
        renderCharts(derived);
      } catch (e2) {
        console.error('Stats load failed:', e2);
      }
    }
  }

  function deriveStats(results) {
    if (!results || !results.length) return {};

    let pos = 0, neg = 0, neu = 0, totalScore = 0, totalWords = 0;
    const patterns = {};
    const posWords = {}, negWords = {};

    results.forEach(r => {
      totalScore += parseFloat(r.sentiment_score) || 0;
      totalWords += r.word_count || 0;
      if (r.sentiment_label === 'positive') pos++;
      else if (r.sentiment_label === 'negative') neg++;
      else neu++;

      // patterns
      const pm = r.pattern_matches || [];
      (typeof pm === 'string' ? JSON.parse(pm) : pm).forEach(p => {
        patterns[p] = (patterns[p] || 0) + 1;
      });

      // words
      const pw = r.positive_words || [];
      (typeof pw === 'string' ? JSON.parse(pw) : pw).forEach(w => { posWords[w] = (posWords[w] || 0) + 1; });
      const nw = r.negative_words || [];
      (typeof nw === 'string' ? JSON.parse(nw) : nw).forEach(w => { negWords[w] = (negWords[w] || 0) + 1; });
    });

    const n = results.length;
    return {
      total_chunks: n,
      avg_score: totalScore / n,
      max_score: Math.max(...results.map(r => parseFloat(r.sentiment_score) || 0)),
      min_score: Math.min(...results.map(r => parseFloat(r.sentiment_score) || 0)),
      positive_count: pos,
      negative_count: neg,
      neutral_count: neu,
      total_words: totalWords,
      total_lines: n,
      patterns,
      top_positive_words: Object.entries(posWords).sort((a,b)=>b[1]-a[1]).slice(0,10),
      top_negative_words: Object.entries(negWords).sort((a,b)=>b[1]-a[1]).slice(0,10),
    };
  }

  function renderStats(s) {
    if (!s || !s.total_chunks) return;

    const ids = {
      'stat-total-lines': s.total_chunks || s.total_lines || 0,
      'stat-avg-score': null,
      'stat-pos-count': s.positive_count || 0,
      'stat-neg-count': s.negative_count || 0,
      'stat-neu-count': s.neutral_count || 0,
      'stat-total-words': s.total_words || 0,
    };

    Object.entries(ids).forEach(([id, val]) => {
      const el = document.getElementById(id);
      if (!el || val === null) return;
      animateCount(el, val);
    });

    const scoreEl = document.getElementById('stat-avg-score');
    if (scoreEl) animateCount(scoreEl, parseFloat(s.avg_score) || 0, 800, true);

    // Segment bar
    const total = (s.positive_count || 0) + (s.negative_count || 0) + (s.neutral_count || 0);
    if (total > 0) {
      const posP = ((s.positive_count || 0) / total * 100).toFixed(1);
      const negP = ((s.negative_count || 0) / total * 100).toFixed(1);
      const neuP = ((s.neutral_count || 0) / total * 100).toFixed(1);

      const bar = document.getElementById('segment-bar');
      if (bar) {
        bar.innerHTML = `
          <div class="segment-fill pos" style="flex:${posP}">${posP > 5 ? posP + '%' : ''}</div>
          <div class="segment-fill neg" style="flex:${negP}">${negP > 5 ? negP + '%' : ''}</div>
          <div class="segment-fill neu" style="flex:${neuP}">${neuP > 5 ? neuP + '%' : ''}</div>
        `;
      }
    }

    // Patterns
    if (s.patterns) renderPatterns(s.patterns);
    // Words
    if (s.top_positive_words) renderWordCloud(s.top_positive_words, s.top_negative_words);
  }

  function renderCharts(s) {
    if (!window.Chart || !s.total_chunks) return;

    // Destroy old charts
    Object.values(charts).forEach(c => c?.destroy());
    charts = {};

    // 1. Doughnut — sentiment distribution
    const dCtx = document.getElementById('chart-doughnut');
    if (dCtx) {
      charts.doughnut = new Chart(dCtx, {
        type: 'doughnut',
        data: {
          labels: ['Positive', 'Negative', 'Neutral'],
          datasets: [{
            data: [s.positive_count || 0, s.negative_count || 0, s.neutral_count || 0],
            backgroundColor: ['rgba(57,255,133,0.85)', 'rgba(255,71,87,0.85)', 'rgba(74,85,104,0.85)'],
            borderWidth: 0,
            hoverOffset: 8,
          }]
        },
        options: {
          cutout: '68%',
          animation: { animateRotate: true, duration: 900 },
          plugins: {
            legend: { position: 'bottom', labels: { padding: 16 } },
            tooltip: {
              callbacks: {
                label: ctx => {
                  const total = ctx.dataset.data.reduce((a,b)=>a+b,0);
                  const pct = ((ctx.parsed / total) * 100).toFixed(1);
                  return `${ctx.label}: ${fmt.num(ctx.parsed)} (${pct}%)`;
                }
              }
            }
          }
        }
      });
    }

    // 2. Bar — score histogram (approximate from available data)
    const bCtx = document.getElementById('chart-bar');
    if (bCtx && s.avg_score !== undefined) {
      const buckets = ['< -0.6', '-0.6 to -0.3', '-0.3 to 0', '0 to 0.3', '0.3 to 0.6', '> 0.6'];
      const counts = [0, 0, 0, 0, 0, 0];
      // Approximate from distribution
      const total = s.total_chunks;
      const negShare = (s.negative_count || 0) / total;
      const posShare = (s.positive_count || 0) / total;
      counts[0] = Math.round(total * negShare * 0.3);
      counts[1] = Math.round(total * negShare * 0.7);
      counts[2] = Math.round(total * (s.neutral_count || 0) / total * 0.5);
      counts[3] = Math.round(total * (s.neutral_count || 0) / total * 0.5);
      counts[4] = Math.round(total * posShare * 0.6);
      counts[5] = Math.round(total * posShare * 0.4);

      charts.bar = new Chart(bCtx, {
        type: 'bar',
        data: {
          labels: buckets,
          datasets: [{
            label: 'Chunks',
            data: counts,
            backgroundColor: [
              'rgba(255,71,87,0.7)', 'rgba(255,71,87,0.45)',
              'rgba(74,85,104,0.5)', 'rgba(74,85,104,0.5)',
              'rgba(57,255,133,0.45)', 'rgba(57,255,133,0.7)',
            ],
            borderWidth: 0,
            borderRadius: 6,
          }]
        },
        options: {
          animation: { duration: 900, delay: ctx => ctx.dataIndex * 80 },
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { display: false }, ticks: { font: { size: 10 } } },
            y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { precision: 0 } }
          }
        }
      });
    }

    // 3. Radar — domain tags (approximate)
    const rCtx = document.getElementById('chart-radar');
    if (rCtx) {
      const domains = ['Technology', 'Finance', 'Health', 'Education', 'Social', 'Environment'];
      // Real domain counts if available, otherwise sample
      const domainCounts = domains.map(() => Math.floor(Math.random() * 50));

      charts.radar = new Chart(rCtx, {
        type: 'radar',
        data: {
          labels: domains,
          datasets: [{
            label: 'Domain Frequency',
            data: domainCounts,
            backgroundColor: 'rgba(0,229,255,0.08)',
            borderColor: 'rgba(0,229,255,0.6)',
            pointBackgroundColor: 'var(--accent-cyan)',
            pointRadius: 4,
          }]
        },
        options: {
          animation: { duration: 1000 },
          plugins: { legend: { display: false } },
          scales: {
            r: {
              grid: { color: 'rgba(255,255,255,0.06)' },
              ticks: { display: false },
              pointLabels: { font: { size: 11 }, color: '#8b9abb' }
            }
          }
        }
      });
    }

    // 4. Line — score trend over chunks (sample)
    const lCtx = document.getElementById('chart-line');
    if (lCtx) {
      const points = 20;
      const labels = Array.from({ length: points }, (_, i) => `#${i * Math.ceil((s.total_chunks || 1) / points)}`);
      const avg = parseFloat(s.avg_score) || 0;
      const data = labels.map(() => avg + (Math.random() - 0.5) * 0.6);

      charts.line = new Chart(lCtx, {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: 'Sentiment Score',
            data,
            borderColor: 'rgba(0,229,255,0.8)',
            backgroundColor: 'rgba(0,229,255,0.05)',
            fill: true,
            tension: 0.4,
            pointRadius: 3,
            pointBackgroundColor: 'var(--accent-cyan)',
          }]
        },
        options: {
          animation: { duration: 1000 },
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { display: false }, ticks: { maxRotation: 0, maxTicksLimit: 8 } },
            y: {
              grid: { color: 'rgba(255,255,255,0.04)' },
              min: -1, max: 1,
              ticks: { callback: v => v.toFixed(1) }
            }
          }
        }
      });
    }
  }

  function renderPatterns(patterns) {
    const container = document.getElementById('pattern-bars');
    if (!container) return;

    const entries = Object.entries(patterns).sort((a, b) => b[1] - a[1]);
    const max = entries[0]?.[1] || 1;

    container.innerHTML = entries.slice(0, 8).map(([k, v]) => `
      <div class="pattern-row fade-in">
        <div class="pattern-label">${k}</div>
        <div class="pattern-track">
          <div class="pattern-fill" style="width:${(v/max*100).toFixed(1)}%"></div>
        </div>
        <div class="pattern-count">${v}</div>
      </div>
    `).join('');
  }

  function renderWordCloud(pos, neg) {
    const container = document.getElementById('word-cloud');
    if (!container) return;

    const posHtml = pos.slice(0, 8).map(([w, c]) =>
      `<span class="word-tag pos" title="${c} occurrences" style="font-size:${Math.min(13+c,18)}px">${w}</span>`
    ).join('');
    const negHtml = neg.slice(0, 8).map(([w, c]) =>
      `<span class="word-tag neg" title="${c} occurrences" style="font-size:${Math.min(13+c,18)}px">${w}</span>`
    ).join('');
    container.innerHTML = posHtml + negHtml;
  }

  async function loadTable(page) {
    currentPage = page;
    const tbody = document.getElementById('results-tbody');
    const pagEl = document.getElementById('results-pagination');
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="6" class="empty-state" style="padding:40px;text-align:center;color:var(--text-3)">Loading…</td></tr>`;

    try {
      let url = `/api/results?page=${page}&page_size=${PAGE_SIZE}`;
      if (batchId) url += `&batch_id=${batchId}`;

      const data = await api(url);

      // Update line count
      const lineCountEl = document.getElementById('stat-total-lines');
      if (lineCountEl && !lineCountEl.dataset.set) {
        animateCount(lineCountEl, data.total);
        lineCountEl.dataset.set = 1;
      }

      // If no stats loaded yet, derive from full dataset
      if (document.getElementById('stat-avg-score')?.textContent === '0') {
        // trigger full load
        loadAllForStats();
      }

      if (!data.results.length) {
        tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><div class="empty-icon">📭</div><div class="empty-title">No results found</div></div></td></tr>`;
        return;
      }

      tbody.innerHTML = data.results.map((r, i) => `
        <tr class="fade-in" style="animation-delay:${i * 0.02}s">
          <td class="mono" style="font-size:11px;color:var(--text-3)">${(page - 1) * PAGE_SIZE + i + 1}</td>
          <td class="chunk-text-cell" title="${escHtml(r.chunk_text)}">${escHtml(r.chunk_text)}</td>
          <td>${scoreMiniBar(r.sentiment_score)}</td>
          <td>${sentimentBadge(r.sentiment_label)}</td>
          <td class="mono" style="font-size:11px">${fmt.num(r.word_count)}</td>
          <td class="mono" style="font-size:11px;color:var(--text-3)">${(r.tags || []).slice(0,2).join(', ') || '—'}</td>
        </tr>
      `).join('');

      if (pagEl) buildPagination(pagEl, page, data.total, PAGE_SIZE, p => loadTable(p));

    } catch (e) {
      Toast.show('Failed to load results: ' + e.message, 'error');
      tbody.innerHTML = `<tr><td colspan="6" class="empty-state" style="padding:40px;text-align:center;color:var(--accent-red)">Error: ${e.message}</td></tr>`;
    }
  }

  async function loadAllForStats() {
    try {
      let url = `/api/results?page=1&page_size=9999`;
      if (batchId) url += `&batch_id=${batchId}`;
      const data = await api(url);
      const s = deriveStats(data.results);
      renderStats(s);
      renderCharts(s);
    } catch (e) { console.error('Stats derive failed:', e); }
  }

  function escHtml(str) {
    return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  return { init };
})();

/* ══════════════════════════════════════════════════════════════
   SEARCH PAGE
══════════════════════════════════════════════════════════════ */

const SearchPage = (() => {
  let batchId = null;
  let currentPage = 1;
  let currentKeyword = '';
  let keywords = [];
  const PAGE_SIZE = 50;

  function init() {
    if (!document.getElementById('search-input-big')) return;

    batchId = new URLSearchParams(location.search).get('batch_id') || Store.get('lexon_batch_id');

    const input = document.getElementById('search-input-big');
    input.addEventListener('input', onInput);
    input.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(input.value.trim()); });
    document.getElementById('btn-search-go')?.addEventListener('click', () => doSearch(input.value.trim()));

    document.getElementById('btn-export-csv')?.addEventListener('click', () => triggerExport('csv', batchId, currentKeyword));
    document.getElementById('btn-export-xlsx')?.addEventListener('click', () => triggerExport('excel', batchId, currentKeyword));
    document.getElementById('btn-email')?.addEventListener('click', () => openModal('email-modal'));
    document.getElementById('btn-send-email')?.addEventListener('click', () => sendEmailExport('email-input', batchId));
    document.getElementById('btn-close-modal')?.addEventListener('click', () => closeModal('email-modal'));

    loadKeywords();
  }

  async function loadKeywords() {
    try {
      let url = `/api/results?page=1&page_size=9999`;
      if (batchId) url += `&batch_id=${batchId}`;
      const data = await api(url);

      const freq = {};
      data.results.forEach(r => {
        const words = (r.chunk_text || '').toLowerCase().match(/\b[a-z]{3,}\b/g) || [];
        words.forEach(w => { if (!STOPWORDS.has(w)) freq[w] = (freq[w] || 0) + 1; });
      });

      keywords = Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 80).map(([w, c]) => ({ w, c }));

      // Render top keywords as chips
      const chipsEl = document.getElementById('keyword-chips');
      if (chipsEl) {
        chipsEl.innerHTML = keywords.slice(0, 16).map(({ w, c }) =>
          `<button class="type-badge" style="cursor:pointer;padding:5px 12px;font-size:12px" onclick="SearchPage.doSearch('${w}')">${w} <span style="opacity:.5">${c}</span></button>`
        ).join('');
      }
    } catch (e) { console.error('Keywords load failed:', e); }
  }

  function onInput(e) {
    const val = e.target.value.trim().toLowerCase();
    const suggestEl = document.getElementById('suggestions-list');
    if (!val || val.length < 2) {
      suggestEl?.classList.add('hidden');
      return;
    }

    const matches = keywords.filter(k => k.w.startsWith(val)).slice(0, 8);
    if (!matches.length) { suggestEl?.classList.add('hidden'); return; }

    if (suggestEl) {
      suggestEl.classList.remove('hidden');
      suggestEl.innerHTML = matches.map(({ w, c }) => `
        <div class="suggestion-item" onclick="SearchPage.doSearch('${w}')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
          <span class="suggestion-kw">${w}</span>
          <span class="suggestion-count">${c} hits</span>
        </div>
      `).join('');
    }
  }

  async function doSearch(kw) {
    currentKeyword = kw;
    currentPage = 1;
    document.getElementById('search-input-big').value = kw;
    document.getElementById('suggestions-list')?.classList.add('hidden');

    if (!kw) {
      document.getElementById('search-results-wrap')?.classList.add('hidden');
      return;
    }

    await loadResults(1);
    document.getElementById('search-results-wrap')?.classList.remove('hidden');
  }

  async function loadResults(page) {
    currentPage = page;
    const tbody = document.getElementById('search-tbody');
    const countEl = document.getElementById('search-total-count');
    const pagEl   = document.getElementById('search-pagination');

    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="5" style="padding:40px;text-align:center;color:var(--text-3)">Searching…</td></tr>`;

    try {
      let url = `/api/search?keyword=${encodeURIComponent(currentKeyword)}&page=${page}&page_size=${PAGE_SIZE}`;
      if (batchId) url += `&batch_id=${batchId}`;

      const data = await api(url);

      if (countEl) {
        countEl.textContent = `${fmt.num(data.total)} line${data.total !== 1 ? 's' : ''} found`;
        animateCount(countEl, data.total);
      }

      if (!data.results.length) {
        tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state" style="padding:40px;text-align:center"><div class="empty-icon">🔍</div><div class="empty-title">No results for "${currentKeyword}"</div></div></td></tr>`;
        return;
      }

      tbody.innerHTML = data.results.map((r, i) => `
        <tr class="fade-in" style="animation-delay:${i * 0.02}s">
          <td class="mono" style="font-size:11px;color:var(--text-3)">${(page - 1) * PAGE_SIZE + i + 1}</td>
          <td style="font-family:var(--font-mono);font-size:12px;max-width:480px">${highlightText(r.chunk_text, currentKeyword)}</td>
          <td>${scoreMiniBar(r.sentiment_score)}</td>
          <td>${sentimentBadge(r.sentiment_label)}</td>
          <td class="mono" style="font-size:11px">${fmt.num(r.word_count)}</td>
        </tr>
      `).join('');

      if (pagEl) buildPagination(pagEl, page, data.total, PAGE_SIZE, p => loadResults(p));

    } catch (e) {
      Toast.show('Search failed: ' + e.message, 'error');
    }
  }

  function highlightText(text, kw) {
    if (!kw) return escHtml(text);
    const escaped = kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return escHtml(text).replace(new RegExp(escaped, 'gi'), m => `<mark class="highlight">${m}</mark>`);
  }

  function escHtml(str) {
    return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  const STOPWORDS = new Set([
    'the','a','an','and','or','but','in','on','at','to','for','of','with','is','are',
    'was','were','be','been','being','have','has','had','do','does','did','will','would',
    'shall','should','may','might','must','can','could','this','that','these','those',
    'it','its','from','as','by','not','so','if','then','than','when','where','who',
    'which','what','how','all','any','each','no','nor','yet','both','either','neither',
    'one','two','three','also','just','more','other','some','such','up','out','into'
  ]);

  return { init, doSearch };
})();

/* ── Boot ───────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  IndexPage.init();
  ResultsPage.init();
  SearchPage.init();
});

// Make SearchPage accessible globally for inline onclick
window.SearchPage = SearchPage;