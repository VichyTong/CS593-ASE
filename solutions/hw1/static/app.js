'use strict';
const $ = (s) => document.querySelector(s);
const state = {papers: [], results: [], paper: null, tab: 'overview', status: {}, searchVersion: 0, busy: false};
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let toastTimer;
function toast(message, error = false) {
  const node = $('#toast');
  const dialogs = [...document.querySelectorAll('dialog[open]')];
  (dialogs.at(-1) || document.body).append(node);
  node.textContent = message; node.classList.toggle('error', error); node.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => {node.hidden = true;}, error ? 10000 : 5000);
}
async function api(url, options = {}) {
  const response = await fetch(url, options);
  let data;
  try { data = await response.json(); } catch { throw new Error('The server returned an unreadable response. Please retry.'); }
  if (!response.ok) throw new Error(data.error || 'The request failed.');
  return data;
}
const jsonRequest = (method, data) => ({method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
function showView(view) {
  for (const el of document.querySelectorAll('.view')) el.hidden = el.id !== `${view}-view`;
  for (const el of document.querySelectorAll('[data-view]')) el.classList.toggle('active', el.dataset.view === view);
  if (view === 'library') renderLibrary();
}
function card(p, fromSearch = false) {
  const id = fromSearch ? p.saved_id : p.id;
  return `<article class="paper-card"><div class="paper-meta"><span class="tag">${p.source === 'arxiv' ? 'arXiv' : 'UPLOADED PDF'}</span><span>${esc(p.year || 'Year unknown')}</span>${p.has_full_text ? '<span>· Full text ready</span>' : ''}</div><h3 class="paper-title">${esc(p.title)}</h3><div class="authors">${esc(p.authors.join(', ') || 'Authors not identified')}</div><p class="abstract">${esc(p.abstract ? p.abstract.slice(0, 300) + (p.abstract.length > 300 ? '…' : '') : 'No abstract available. Open the paper to review its details.')}</p>${p.abstract.length > 300 ? `<details><summary>Read full abstract</summary><p class="abstract">${esc(p.abstract)}</p></details>` : ''}<div class="card-actions">${id ? `<button class="button" data-open="${id}">Open paper ↗</button><span class="hint">Saved in library</span>` : `<button class="button" data-save="${esc(p.source_id)}">+ Save to library</button>`}${p.url ? `<a class="source-link" href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">View on arXiv ↗</a>` : ''}</div></article>`;
}
async function refreshLibrary() {
  state.papers = (await api('/api/papers')).papers;
  $('#library-count').textContent = state.papers.length;
  for (const p of state.results) p.saved_id = state.papers.find(saved => saved.source_id === p.source_id)?.id;
  renderLibrary();
}
function renderLibrary() {
  const q = $('#library-filter').value.toLowerCase();
  const papers = state.papers.filter(p => `${p.title} ${p.authors.join(' ')}`.toLowerCase().includes(q));
  $('#library-results').innerHTML = papers.length ? papers.map(p => card(p)).join('') : `<div class="empty"><h3>${q ? 'No matching papers.' : 'No saved papers.'}</h3><p>${q ? 'Try a different title or author.' : 'Save a search result or upload a PDF.'}</p>${q ? '' : '<button class="button primary upload-trigger">↑ Upload your first paper</button>'}</div>`;
}
function renderResults() {
  $('#search-results').innerHTML = state.results.length ? state.results.map(p => card(p, true)).join('') : '<div class="empty"><h3>No papers found.</h3><p>Try broader keywords or paste an arXiv ID such as 1706.03762.</p></div>';
}
async function search(query) {
  const version = ++state.searchVersion;
  showView('discover'); $('#query').value = query; $('#search-button').disabled = true;
  $('#search-results').innerHTML = '<div class="loading">Looking through arXiv…</div>';
  $('#result-heading').textContent = 'Searching…';
  try {
    const data = await api(`/api/search?q=${encodeURIComponent(query)}`);
    if (version !== state.searchVersion) return;
    state.results = data.papers;
    $('#result-heading').textContent = `${state.results.length} ${state.results.length === 1 ? 'paper' : 'papers'} to explore`;
    renderResults();
  } catch (error) {
    if (version !== state.searchVersion) return;
    $('#result-heading').textContent = 'Search could not finish';
    $('#search-results').innerHTML = `<div class="empty"><h3>Search unavailable.</h3><p>${esc(error.message)}</p><button class="button" data-query="${esc(query)}">Try again</button></div>`;
  } finally { if (version === state.searchVersion) $('#search-button').disabled = false; }
}
let detailVersion = 0;
async function openPaper(id) {
  const version = ++detailVersion;
  const data = await api(`/api/papers/${id}`);
  if (version !== detailVersion) return;
  state.paper = data.paper; state.tab = 'overview';
  renderPaper(); if (!$('#paper-dialog').open) $('#paper-dialog').showModal();
}
function contentNotice() {
  return state.paper.has_full_text ? '' : `<div class="callout"><b>Full text required</b><p>Download the PDF to enable analysis.</p><button class="button primary" id="load-content" ${state.busy ? 'disabled' : ''}>${state.busy ? 'Loading paper…' : 'Load full paper ↓'}</button></div>`;
}
function renderPaper() {
  const p = state.paper;
  if (!p) return;
  $('#paper-head').innerHTML = `<div class="paper-meta"><span class="tag">${p.source === 'arxiv' ? 'arXiv' : 'UPLOADED PDF'}</span><span>${esc(p.year || 'Year unknown')}</span>${p.page_count ? `<span>· ${p.page_count} PDF pages</span>` : ''}</div><h2>${esc(p.title)}</h2><div class="authors">${esc(p.authors.join(', ') || 'Authors not identified')}</div>`;
  document.querySelectorAll('[data-tab]').forEach(b => {b.classList.toggle('active', b.dataset.tab === state.tab); b.setAttribute('aria-selected', b.dataset.tab === state.tab);});
  if (state.tab === 'overview') {
    $('#paper-body').innerHTML = `${contentNotice()}<div class="eyebrow">ABSTRACT</div><p class="detail-abstract">${esc(p.abstract || 'No abstract extracted. Review the source text and update the metadata.')}</p><div class="detail-actions"><button class="button" id="edit-metadata">Edit metadata</button>${p.has_pdf ? `<a class="button" href="/api/papers/${p.id}/pdf">Download PDF ↓</a>` : ''}${p.url ? `<a class="button" href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">Original paper ↗</a>` : ''}<button class="button subtle danger" id="delete-paper">Remove from library</button></div><p class="hint">Metadata: ${esc(p.metadata_method)}</p>`;
  } else if (state.tab === 'text') {
    $('#paper-body').innerHTML = contentNotice() + (p.pages.length ? `<p class="hint">PDF page numbers are preserved for checking AI citations. Extraction may imperfectly represent tables, equations, and columns.</p>` + p.pages.map(page => `<article class="text-page"><span class="eyebrow">PAGE ${page.page}</span><pre>${esc(page.text || '[No extractable text on this page]')}</pre></article>`).join('') : '');
  } else {
    const enabled = state.status.llm_configured && p.has_full_text && !state.busy;
    const analyses = p.analyses || [];
    $('#paper-body').innerHTML = `${contentNotice()}${state.status.llm_configured ? '' : '<div class="callout"><b>Model required</b><p>Configure an API key to enable summaries and questions.</p><button class="button" id="inline-setup">Model setup ↗</button></div>'}<div class="ai-toolbar"><button class="button primary" id="summarize" ${enabled ? '' : 'disabled'}>✳ Generate summary</button><small>Grounded in the paper · Page references included</small></div><div id="analyses">${analyses.length ? analyses.map(analysisCard).join('') : '<div class="empty"><h3>No analyses yet.</h3><p>Generate a summary or ask a question.</p></div>'}</div>${state.busy ? '<div class="loading">Reading the paper with your model…</div>' : ''}<form id="question-form" class="question-form"><label class="sr-only" for="question">Question about this paper</label><textarea id="question" required minlength="3" maxlength="2000" placeholder="What would you like to understand about this paper?" ${enabled ? '' : 'disabled'}></textarea><button class="button primary" ${enabled ? '' : 'disabled'}>Ask question ↑</button></form><div class="question-chips"><button data-question="What problem does this paper address?">Research problem</button><button data-question="What datasets and baselines are used?">Datasets & baselines</button><button data-question="What are the main limitations of this paper?">Limitations</button></div><p class="hint">Relevant paper text is sent to ${esc(state.status.provider_host || 'your model provider')}. Verify claims against the page excerpts; AI can make mistakes.</p>`;
  }
}
function analysisCard(a) {
  const formatted = esc(a.answer).replace(/^#{1,4}\s+(.+)$/gm, '<strong>$1</strong>').replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
  return `<article class="analysis-card"><div class="eyebrow">${a.kind === 'summary' ? 'PAPER SUMMARY' : 'YOUR QUESTION'}</div><h3>${a.kind === 'summary' ? 'Summary' : esc(a.question)}</h3><div class="answer">${formatted}</div><div class="analysis-meta">${esc(a.model)} · ${esc(a.coverage)}</div>${a.sources.map(s => `<details class="source"><summary>Evidence · PDF page ${s.page}</summary><p>${esc(s.text)}</p></details>`).join('')}</article>`;
}
function editMetadata() {
  const p = state.paper;
  $('#paper-body').innerHTML = `<form id="metadata-form" class="edit-form"><p class="hint">Review the extracted fields against the paper. Unknown fields can stay blank.</p><label>Title<input name="title" required maxlength="1000" value="${esc(p.title)}"></label><label>Authors (one per line)<textarea name="authors">${esc(p.authors.join('\n'))}</textarea></label><label>Publication year<input name="year" inputmode="numeric" maxlength="4" value="${esc(p.year || '')}"></label><label>Abstract<textarea name="abstract" maxlength="12000">${esc(p.abstract)}</textarea></label><div class="detail-actions"><button class="button primary" type="submit">Save corrections</button><button class="button" type="button" id="cancel-edit">Cancel</button></div></form>`;
}
async function analyze(kind, question = '') {
  if (state.busy) return;
  const id = state.paper.id;
  state.busy = true; renderPaper();
  try {
    const data = await api(`/api/papers/${id}/analyze`, jsonRequest('POST', {kind, question}));
    if (state.paper?.id === id && !state.paper.analyses.some(a => a.id === data.analysis.id)) state.paper.analyses.push(data.analysis);
    toast(data.cached ? 'Reused the saved result. No new model charge.' : 'Analysis saved.');
  } catch (error) {toast(error.message, true);}
  finally {state.busy = false; renderPaper(); if (question && $('#question')) $('#question').value = question;}
}
function modelSetup() {
  $('#setup-status').textContent = state.status.llm_configured ? `Configured: ${state.status.model} at ${state.status.provider_host}. AI budget: $${state.status.budget?.limit_usd ?? '—'}. Identical requests reuse saved results.` : 'No model is configured yet. Add your own OpenAI-compatible API or local Ollama model.';
  $('#setup-dialog').showModal();
}
document.addEventListener('click', async event => {
  const b = event.target.closest('button'); if (!b) return;
  try {
    if (b.dataset.close) {$('#toast').hidden = true; document.body.append($('#toast')); document.getElementById(b.dataset.close).close();}
    else if (b.dataset.view) showView(b.dataset.view);
    else if (b.dataset.query) await search(b.dataset.query);
    else if (b.classList.contains('upload-trigger')) $('#upload-dialog').showModal();
    else if (b.dataset.open) await openPaper(b.dataset.open);
    else if (b.dataset.save) {
      b.disabled = true;
      await api('/api/papers', jsonRequest('POST', state.results.find(p => p.source_id === b.dataset.save)));
      await refreshLibrary(); renderResults(); toast('Paper saved to your library.');
    } else if (b.dataset.tab) {state.tab = b.dataset.tab; renderPaper();}
    else if (b.dataset.question) {if ($('#question') && !$('#question').disabled) {$('#question').value = b.dataset.question; $('#question').focus();}}
    else if (b.id === 'model-setup' || b.id === 'inline-setup') modelSetup();
    else if (b.id === 'edit-metadata') editMetadata();
    else if (b.id === 'cancel-edit') renderPaper();
    else if (b.id === 'summarize') await analyze('summary');
    else if (b.id === 'load-content') {
      const id = state.paper.id; state.busy = true; renderPaper();
      try {
        const data = await api(`/api/papers/${id}/content`, {method: 'POST'});
        if (state.paper.id === id) Object.assign(state.paper, data.paper);
        await refreshLibrary(); toast('Full text loaded.');
      } finally {state.busy = false; renderPaper();}
    } else if (b.id === 'delete-paper') {
      if (!confirm('Remove this paper and its AI notebook from your library?')) return;
      await api(`/api/papers/${state.paper.id}`, {method: 'DELETE'});
      $('#paper-dialog').close(); state.paper = null;
      await refreshLibrary(); if (state.results.length) renderResults(); toast('Paper removed.');
    }
  } catch (error) {b.disabled = false; toast(error.message, true);}
});
document.addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.target;
  try {
    if (form.id === 'search-form') await search($('#query').value.trim());
    else if (form.id === 'upload-form') {
      const file = $('#pdf-file').files[0];
      if (!file) throw new Error('Choose a PDF file.');
      if (file.size > 20 * 1024 * 1024) throw new Error('PDF exceeds the 20 MB upload limit.');
      const body = new FormData(); body.append('file', file);
      $('#upload-button').disabled = true; $('#upload-button').textContent = 'Extracting your paper…';
      try {
        const data = await api('/api/upload', {method: 'POST', body});
        $('#upload-dialog').close(); form.reset(); $('#file-label').textContent = 'Choose a PDF paper';
        await refreshLibrary(); showView('library'); await openPaper(data.paper.id); editMetadata(); toast(data.notice);
      } finally {$('#upload-button').disabled = false; $('#upload-button').textContent = 'Add to library →';}
    } else if (form.id === 'metadata-form') {
      const fields = new FormData(form);
      const data = await api(`/api/papers/${state.paper.id}`, jsonRequest('PATCH', {
        title: fields.get('title'), authors: fields.get('authors').split('\n').filter(x => x.trim()),
        year: fields.get('year') || null, abstract: fields.get('abstract')}));
      Object.assign(state.paper, data.paper); await refreshLibrary(); renderPaper(); toast('Metadata updated.');
    } else if (form.id === 'question-form') await analyze('question', $('#question').value.trim());
  } catch (error) {toast(error.message, true);}
});
$('#library-filter').addEventListener('input', renderLibrary);
$('#pdf-file').addEventListener('change', () => {$('#file-label').textContent = $('#pdf-file').files[0]?.name || 'Choose a PDF paper';});
async function init() {
  try {
    const [status] = await Promise.all([api('/api/status'), refreshLibrary()]); state.status = status;
    if (!state.searchVersion) {$('#search-results').innerHTML = state.papers.length ? state.papers.slice(0,3).map(p => card(p)).join('') : '<div class="empty"><p>No saved papers.</p></div>';}
    $('#model-status').textContent = status.llm_configured ? 'Model configured' : 'Connect your model';
    $('#model-dot').classList.toggle('ready', status.llm_configured);
  } catch (error) {toast(error.message, true); $('#model-status').textContent = 'Server unavailable';}
}
init();
