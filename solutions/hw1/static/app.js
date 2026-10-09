'use strict';

const $ = (selector, parent = document) => parent.querySelector(selector);
const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
const icon = name => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const state = {library: [], status: null, paper: null, route: 'discover', tab: 'overview', search: null,
  searchQuery: '', searchPage: 1, searchSort: 'relevance', libraryQuery: '', libraryFilter: 'all', librarySort: 'newest',
  routeVersion: 0, searchVersion: 0, searchBusy: false, analysisBusy: new Set(), sourceBusy: new Set()};
let toastTimer;

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {...options, headers: {
      ...(options.body && !(options.body instanceof FormData) ? {'Content-Type': 'application/json'} : {}), ...options.headers}});
  } catch {
    throw new Error('Cannot reach Papertrail. Check that the local server is running, then retry.');
  }
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || 'The request failed. Please try again.');
  return result;
}
function notify(message, error = false) {
  const toast = $('#toast');
  toast.textContent = message;
  toast.className = 'toast' + (error ? ' error' : '');
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, error ? 9000 : 4500);
}
function loading(message) { return `<div class="loading" role="status"><span class="spinner"></span>${escapeHTML(message)}</div>`; }
function errorBox(message) { return `<div class="error-box" role="alert">${escapeHTML(message)}</div>`; }
function setError(id, message = '') { const node = $(id); node.textContent = message; node.hidden = !message; }
function buttonBusy(button, busy, label = 'Working…') {
  if (!button) return;
  if (busy) { button.dataset.original = button.innerHTML; button.innerHTML = `<span class="spinner"></span>${escapeHTML(label)}`; }
  else if (button.dataset.original) button.innerHTML = button.dataset.original;
  button.disabled = busy;
}
function openDialog(id) { const dialog = $(id); if (!dialog.open) dialog.showModal(); }
function navigate(hash) { if (location.hash === hash) route(); else location.hash = hash; }
function sourceLabel(paper) { return paper.source === 'upload' ? 'UPLOADED PDF' : 'arXiv'; }
function authorsText(paper) { return paper.authors?.length ? paper.authors.join(', ') : 'Authors not available'; }

const heroArt = `<div class="hero-art" aria-hidden="true"><svg viewBox="0 0 220 180" fill="none">
  <ellipse cx="110" cy="159" rx="73" ry="9" fill="#e9eee2"/>
  <circle cx="123" cy="78" r="64" fill="#f0f3e8"/>
  <path d="M46 47 118 36l22 97-72 11z" fill="#e2eacb" stroke="#a7bc8a" stroke-width="1.2"/>
  <path d="m47 48 12 9 72-10" stroke="#a7bc8a" stroke-width="1.2"/>
  <path d="M77 41h73v106H77z" fill="#fffdf7" stroke="#a5b88e" stroke-width="1.2"/>
  <path d="M85 41v106" stroke="#becdad" stroke-width="1.2"/>
  <path d="M97 62h39M97 69h30M97 97h37M97 105h31M97 113h36M97 121h24" stroke="#d0d9bf" stroke-width="2" stroke-linecap="round"/>
  <path d="M131 40v27l6-4 6 4V40" fill="#bacb9c"/>
  <circle cx="159" cy="119" r="23" fill="#eff4e5" stroke="#809d67" stroke-width="1.5"/>
  <circle cx="159" cy="119" r="17" stroke="#a3b98c" stroke-width="1.2"/>
  <path d="m176 137 16 18" stroke="#809d67" stroke-width="7" stroke-linecap="round"/>
  <path d="m174 135 17 19" stroke="#c1d0ad" stroke-width="3" stroke-linecap="round"/>
  <path d="M41 95v10m-5-5h10M176 43v10m-5-5h10M62 24v6m-3-3h6" stroke="#a5bb8b" stroke-width="1.2"/>
  <circle cx="182" cy="80" r="2" fill="#b5c79e"/><circle cx="38" cy="128" r="2" fill="#b5c79e"/>
  </svg></div>`;

function discover() {
  $('#view').innerHTML = `<section class="hero"><div class="hero-copy"><span class="eyebrow">THE RESEARCH DESK</span><h1>Follow your curiosity.</h1><p>Find papers. Keep what matters. Understand more.</p></div>${heroArt}</section>
    <form id="search-form" class="search-form" role="search">${icon('search')}<input id="search-input" type="search" aria-label="Research topic or arXiv ID" placeholder="A topic, a question, a new idea…" maxlength="200" minlength="2" value="${escapeHTML(state.searchQuery)}" required><button class="button primary" type="submit" aria-label="Search papers">Search papers${icon('arrow')}</button></form>
    <div class="topic-row"><span>Try exploring</span><button class="topic-chip" data-topic="large language models">Large language models</button><button class="topic-chip" data-topic="software testing">Software testing</button><button class="topic-chip" data-topic="retrieval augmented generation">Retrieval-augmented generation</button></div>
    <div id="discovery-content">${state.searchBusy ? loading('Searching arXiv…') : state.search ? searchResults() : discoveryHome()}</div>`;
  $('#search-form').addEventListener('submit', event => { event.preventDefault(); search($('#search-input').value); });
}

function discoveryHome() {
  return `<section><div class="section-heading"><h2>Where will you begin?</h2><p>A few paths worth following</p></div><div class="topic-grid">
    <button class="topic-card" data-topic="large language models"><span class="topic-icon">${icon('spark')}</span><h3>Language & intelligence</h3><p>Explore how machines learn to think.</p><span class="topic-bottom">LARGE LANGUAGE MODELS${icon('arrow')}</span></button>
    <button class="topic-card" data-topic="software engineering"><span class="topic-icon">${icon('library')}</span><h3>Better software</h3><p>The ideas behind reliable systems.</p><span class="topic-bottom">SOFTWARE ENGINEERING${icon('arrow')}</span></button>
    <button class="topic-card" data-topic="computer vision"><span class="topic-icon">${icon('search')}</span><h3>A different perspective</h3><p>Making sense of the visual world.</p><span class="topic-bottom">COMPUTER VISION${icon('arrow')}</span></button>
    </div></section><section class="workflow-note">${icon('file')}<div><h3>Already have a paper in mind?</h3><p>Bring a PDF, get the key ideas, and ask the questions that matter.</p></div><button class="button ghost" data-action="upload">Upload a paper${icon('arrow')}</button></section>
    ${state.library.length ? `<section class="recent-section"><div class="section-heading"><h2>Pick up where you left off</h2><a href="#library" class="text-link">View library${icon('arrow')}</a></div><div class="recent-list">${state.library.slice(0, 3).map(p => `<a class="recent-item" href="#paper/${p.id}">${icon('file')}<div><h3>${escapeHTML(p.title)}</h3><p>${p.year || 'Year unknown'} · ${escapeHTML(sourceLabel(p))}</p></div>${icon('arrow')}</a>`).join('')}</div></section>` : ''}`;
}

function paperCard(paper, inLibrary = false) {
  const saved = inLibrary ? paper.id : state.library.find(p => p.source_id === paper.source_id)?.id;
  const identifier = inLibrary ? `data-id="${paper.id}"` : `data-source="${escapeHTML(paper.source_id)}"`;
  return `<article class="paper-card"><div class="paper-card-top"><div class="paper-labels"><span class="tag ${paper.source === 'upload' ? 'upload' : ''}">${sourceLabel(paper)}</span><span>${paper.year || 'Year unknown'}</span>${paper.category ? `<span>· ${escapeHTML(paper.category)}</span>` : ''}</div>${saved ? `<span class="paper-labels">${icon('check')}In your library</span>` : ''}</div>
    <h3>${escapeHTML(paper.title)}</h3><p class="authors">${escapeHTML(authorsText(paper))}</p>
    <p class="abstract clamped">${escapeHTML(paper.abstract || 'No abstract available. Open the paper to explore its content.')}</p>${paper.abstract?.length > 300 ? '<button class="abstract-toggle" data-action="abstract" aria-expanded="false">Read abstract</button>' : ''}
    <div class="paper-card-bottom"><span>${paper.has_full_text ? `${paper.page_count} pages · Ready to read` : paper.source === 'upload' ? 'Your PDF, saved locally' : 'Research from arXiv'}</span><div class="card-actions">${paper.url ? `<a class="button ghost" href="${escapeHTML(paper.url)}" target="_blank" rel="noopener noreferrer">Original paper${icon('link')}</a>` : ''}${saved ? `<a class="button secondary" href="#paper/${saved}">Open paper${icon('arrow')}</a>` : `<button class="button secondary" data-action="save" ${identifier}>${icon('plus')}Save to library</button>`}</div></div></article>`;
}

function searchResults() {
  const result = state.search;
  if (result.error) return errorBox(result.error);
  const hasNext = result.page * result.page_size < result.total && result.page < 100;
  return `<div class="list-toolbar"><div><h2>Ideas worth a closer look.</h2><p>${Number(result.total).toLocaleString()} ${result.total === 1 ? 'result' : 'results'} for “${escapeHTML(state.searchQuery)}” · via arXiv</p></div><label class="select-wrap"><span>Sort by</span><select id="search-sort" aria-label="Sort search results"><option value="relevance" ${state.searchSort === 'relevance' ? 'selected' : ''}>Most relevant</option><option value="submittedDate" ${state.searchSort === 'submittedDate' ? 'selected' : ''}>Newest first</option></select></label></div>
    ${result.papers.length ? `<div class="paper-list">${result.papers.map(p => paperCard(p)).join('')}</div><div class="pagination"><button class="button secondary" data-action="previous-search" ${result.page <= 1 ? 'disabled' : ''}>${icon('back')}Previous</button><span>Page ${result.page}</span><button class="button secondary" data-action="next-search" ${!hasNext ? 'disabled' : ''}>Next${icon('arrow')}</button></div>` : `<div class="empty-state">${icon('search')}<h2>A different path, perhaps?</h2><p>No papers matched this search. Try fewer keywords, a broader topic, or an exact arXiv ID.</p><button class="button secondary" data-topic="software testing">Explore software testing${icon('arrow')}</button></div>`}`;
}

async function search(query, page = 1) {
  query = query.trim();
  if (query.length < 2) { notify('Enter at least two characters to search.', true); return; }
  state.searchQuery = query; state.searchPage = page; state.searchBusy = true;
  const version = ++state.searchVersion;
  if (state.route !== 'discover') navigate('#discover');
  else discover();
  try {
    const result = await api(`/api/search?q=${encodeURIComponent(query)}&page=${page}&sort=${state.searchSort}`);
    if (version !== state.searchVersion) return;
    state.search = result;
  } catch (error) { if (version === state.searchVersion) state.search = {error: error.message}; }
  finally {
    if (version === state.searchVersion) {
      state.searchBusy = false;
      if (state.route === 'discover') { $('#discovery-content').innerHTML = searchResults(); }
    }
  }
}

function library() {
  $('#view').innerHTML = `<section class="page-header"><div><span class="eyebrow">YOUR PERSONAL COLLECTION</span><h1>Your reading, collected.</h1><p>${state.library.length} ${state.library.length === 1 ? 'paper' : 'papers'} saved. A little more perspective with every one.</p></div><button class="button primary" data-action="upload">${icon('plus')}Upload a PDF</button></section>
    <div class="library-tools"><label class="library-search">${icon('search')}<input id="library-search" type="search" placeholder="Find in your library…" aria-label="Filter your library" value="${escapeHTML(state.libraryQuery)}"></label><div class="filter-pills" role="group" aria-label="Paper source"><button data-filter="all" class="${state.libraryFilter === 'all' ? 'active' : ''}" aria-pressed="${state.libraryFilter === 'all'}">All papers</button><button data-filter="upload" class="${state.libraryFilter === 'upload' ? 'active' : ''}" aria-pressed="${state.libraryFilter === 'upload'}">PDF uploads</button></div><label class="select-wrap"><select id="library-sort" aria-label="Sort library"><option value="newest" ${state.librarySort === 'newest' ? 'selected' : ''}>Recently saved</option><option value="year" ${state.librarySort === 'year' ? 'selected' : ''}>Publication year</option><option value="title" ${state.librarySort === 'title' ? 'selected' : ''}>Title A–Z</option></select></label></div><div id="library-results">${libraryResults()}</div>`;
  $('#library-search').addEventListener('input', event => { state.libraryQuery = event.target.value; $('#library-results').innerHTML = libraryResults(); });
}
function libraryResults() {
  let papers = state.library.filter(p => (state.libraryFilter === 'all' || p.source === 'upload') &&
    [p.title, ...p.authors, p.abstract].join(' ').toLowerCase().includes(state.libraryQuery.toLowerCase()));
  if (state.librarySort === 'year') papers.sort((a, b) => (b.year || 0) - (a.year || 0));
  if (state.librarySort === 'title') papers.sort((a, b) => a.title.localeCompare(b.title));
  if (!papers.length) return `<div class="empty-state">${icon('library')}<h2>${state.library.length ? 'Nothing here just yet.' : 'Every library starts with one paper.'}</h2><p>${state.library.length ? 'Try a different filter or a broader search.' : 'Save something that sparks your curiosity, or bring a PDF of your own.'}</p>${!state.library.length ? '<a href="#discover" class="button primary">Discover papers</a><button class="button secondary" data-action="upload">Upload a PDF</button>' : '<button class="button secondary" data-action="clear-filters">Clear filters</button>'}</div>`;
  return `<div class="paper-list">${papers.map(p => paperCard(p, true)).join('')}</div>`;
}
async function refreshLibrary() { state.library = (await api('/api/papers')).papers; $('#library-count').textContent = state.library.length; }

async function openPaper(id, version = state.routeVersion) {
  $('#view').innerHTML = loading('Opening your paper…');
  try {
    const result = await api(`/api/papers/${id}`);
    if (version !== state.routeVersion) return;
    state.paper = result.paper;
    state.tab = 'overview';
    renderPaper();
  } catch (error) { if (version === state.routeVersion) $('#view').innerHTML = `<a class="back-link" href="#library">${icon('back')}Back to library</a>${errorBox(error.message)}`; }
}
function renderPaper() {
  const p = state.paper;
  if (!p || state.route !== 'paper') return;
  $('#view').innerHTML = `<a class="back-link" href="#library">${icon('back')}Back to my library</a><header class="paper-header"><div class="paper-labels"><span class="tag ${p.source === 'upload' ? 'upload' : ''}">${sourceLabel(p)}</span><span>${p.year || 'Year unknown'}</span>${p.category ? `<span>· ${escapeHTML(p.category)}</span>` : ''}</div><h1>${escapeHTML(p.title)}</h1><p class="authors">${escapeHTML(authorsText(p))}</p></header>
    <div class="paper-actions">${p.url ? `<a class="button secondary" href="${escapeHTML(p.url)}" target="_blank" rel="noopener noreferrer">Original paper${icon('link')}</a>` : ''}${p.has_pdf ? `<a class="button secondary" href="/api/papers/${p.id}/pdf">${icon('download')}Download PDF</a>` : `<button class="button secondary" data-action="load-content" ${state.sourceBusy.has(p.id) ? 'disabled' : ''}>${icon('file')}${state.sourceBusy.has(p.id) ? 'Loading text…' : 'Load full text'}</button>`}<button class="button ghost" data-action="edit">${icon('edit')}Edit details</button><button class="button ghost remove-button" data-action="delete">${icon('trash')}Remove</button></div>
    <div class="reading-grid"><section class="reader-panel"><div class="tabs" role="tablist" aria-label="Paper workspace"><button id="tab-overview" class="tab ${state.tab === 'overview' ? 'active' : ''}" role="tab" data-tab="overview" aria-selected="${state.tab === 'overview'}" aria-controls="reader-content" tabindex="${state.tab === 'overview' ? 0 : -1}">Overview</button><button id="tab-summary" class="tab ${state.tab === 'summary' ? 'active' : ''}" role="tab" data-tab="summary" aria-selected="${state.tab === 'summary'}" aria-controls="reader-content" tabindex="${state.tab === 'summary' ? 0 : -1}">AI summary</button><button id="tab-source" class="tab ${state.tab === 'source' ? 'active' : ''}" role="tab" data-tab="source" aria-selected="${state.tab === 'source'}" aria-controls="reader-content" tabindex="${state.tab === 'source' ? 0 : -1}">Source text</button></div><div id="reader-content" class="content-panel" role="tabpanel" aria-labelledby="tab-${state.tab}">${readerContent()}</div></section>
    <aside class="chat-panel" aria-label="Ask this paper"><div class="chat-heading">${icon('spark')}<div><h2>Ask this paper</h2><p>A conversation grounded in the text</p></div></div><div class="chat-body" id="chat-body">${chatContent()}</div><form id="question-form" class="chat-form"><div class="chat-input-wrap"><textarea id="question-input" aria-label="Your question about this paper" placeholder="What would you like to understand?" maxlength="2000" rows="2" required ${state.analysisBusy.has(p.id) ? 'disabled' : ''}></textarea><div class="chat-send-row"><span>Grounded in your paper</span><button class="button primary" type="submit" ${state.analysisBusy.has(p.id) ? 'disabled' : ''}>Ask${icon('arrow')}</button></div></div><p class="chat-disclaimer">AI can make mistakes. Follow the page references.</p><p class="form-error" id="question-error" role="alert" hidden></p></form></aside></div>`;
  $('#question-form').addEventListener('submit', event => { event.preventDefault(); analyze('question', $('#question-input').value); });
  const chatBody = $('#chat-body'); if (chatBody) chatBody.scrollTop = chatBody.scrollHeight;
}
function readerContent() {
  const p = state.paper;
  if (state.tab === 'overview') return `<h2>At a glance</h2><p class="abstract-full">${escapeHTML(p.abstract || 'No abstract was found. You can add one in Edit details, or read the extracted source text.')}</p><dl class="paper-facts"><div><dt>Source</dt><dd>${p.source === 'upload' ? 'Uploaded PDF' : 'arXiv research archive'}</dd></div><div><dt>Full text</dt><dd>${p.has_full_text ? `${p.page_count} pages available` : 'Loads when you analyze'}</dd></div><div><dt>Publication year</dt><dd>${p.year || 'Unknown'}</dd></div><div><dt>Saved</dt><dd>${escapeHTML(p.created_at.slice(0, 10))}</dd></div></dl><div class="workflow-note">${icon('spark')}<div><h3>Find the thread.</h3><p>Get the question, approach, findings, and limitations in one summary.</p></div><button class="button ghost" data-tab="summary">Read summary${icon('arrow')}</button></div>`;
  if (state.tab === 'summary') {
    const summary = [...p.analyses].reverse().find(a => a.kind === 'summary');
    if (summary) return `<h2>The paper, in perspective.</h2>${analysisHTML(summary)}`;
    if (state.analysisBusy.has(p.id)) return loading('Reading the paper and finding the key ideas…');
    return `<div class="analysis-invite">${icon('spark')}<h2>The essentials, thoughtfully distilled.</h2><p>Understand the research question, approach, findings, and limitations — with references to the actual paper.</p><button class="button primary" data-action="summarize">${icon('spark')}Generate summary</button><p class="small muted" id="summary-note">${!p.has_full_text ? 'We’ll load the full PDF before summarizing.' : `${p.page_count} pages ready to explore.`}</p></div><div id="summary-error"></div>`;
  }
  if (!p.has_full_text) return state.sourceBusy.has(p.id) ? loading('Downloading and reading the PDF…') : `<div class="analysis-invite">${icon('file')}<h2>Go straight to the source.</h2><p>Load the PDF to inspect the text behind every summary and answer.</p><button class="button primary" data-action="load-content">Load full text${icon('arrow')}</button></div>`;
  return `<div class="section-heading"><h2>In the author’s words</h2><p>${p.page_count} PDF pages</p></div><p class="small muted">Text extracted from the PDF. Complex tables and equations may lose formatting.</p>${p.pages.map(page => `<details class="source-page" id="source-page-${page.page}"><summary>Page ${page.page}</summary><pre>${escapeHTML(page.text || 'No text extracted from this page.')}</pre></details>`).join('')}`;
}
function inlineMarkdown(text) {
  return escapeHTML(text).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[pp?\.\s*([\d\s,–—-]+)\]/gi, (reference, group) => {
      const pages = new Set();
      for (const match of group.matchAll(/(\d+)(?:\s*[-–—]\s*(\d+))?/g)) {
        const start = Number(match[1]), end = Number(match[2] || match[1]);
        if (end < start || end - start > 150) return reference;
        for (let page = start; page <= end; page++) pages.add(page);
      }
      return [...pages].map(n => `<button class="citation" data-action="cite" data-page="${n}" aria-label="Read PDF page ${n}">p. ${n}</button>`).join(' ') || reference;
    });
}
function markdown(text) {
  let html = '', list = '';
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    const item = trimmed.match(/^(?:[-*]|\d+\.)\s+(.+)$/);
    if (item) { if (!list) { html += '<ul>'; list = 'ul'; } html += `<li>${inlineMarkdown(item[1])}</li>`; continue; }
    if (list) { html += '</ul>'; list = ''; }
    if (/^#{1,6}\s/.test(trimmed)) html += `<h3>${inlineMarkdown(trimmed.replace(/^#{1,6}\s+/, ''))}</h3>`;
    else if (trimmed) html += `<p>${inlineMarkdown(trimmed)}</p>`;
  }
  return html + (list ? '</ul>' : '');
}
function analysisHTML(analysis) {
  return `<div class="analysis-meta"><span>${escapeHTML(analysis.model)}</span><span>${escapeHTML(analysis.coverage)}</span></div><div class="prose">${markdown(analysis.answer)}</div>${analysis.warning ? `<p class="inline-warning">${escapeHTML(analysis.warning)}</p>` : ''}<details class="source-details"><summary>Explore the source excerpts</summary>${analysis.sources.map(s => `<div class="source-excerpt"><strong><button class="citation" data-action="cite" data-page="${s.page}">PDF page ${s.page}</button></strong><p>${escapeHTML(s.text)}</p></div>`).join('')}</details>`;
}
function chatContent() {
  const questions = state.paper.analyses.filter(a => a.kind === 'question');
  const busy = state.analysisBusy.has(state.paper.id);
  return (questions.length ? questions.map(q => `<div class="chat-message"><div class="chat-question">${escapeHTML(q.question)}</div>${analysisHTML(q)}</div>`).join('') : `<div class="chat-empty">${icon('chat')}<h3>What’s on your mind?</h3><p>Go beyond the abstract. Ask about the ideas, evidence, or things left unsaid.</p><div class="question-suggestions">${['What problem does this paper address?', 'What datasets are used?', 'What are the main limitations?'].map(q => `<button data-question="${escapeHTML(q)}" ${busy ? 'disabled' : ''}>${escapeHTML(q)}${icon('arrow')}</button>`).join('')}</div></div>`) + (busy ? loading('Reading the paper…') : '');
}
function setTab(tab) {
  if (!state.paper) return;
  state.tab = tab;
  $$('.tab').forEach(b => { const active = b.dataset.tab === tab; b.classList.toggle('active', active); b.setAttribute('aria-selected', active); b.tabIndex = active ? 0 : -1; });
  $('#reader-content').innerHTML = readerContent();
  $('#reader-content').setAttribute('aria-labelledby', 'tab-' + tab);
}
async function loadContent() {
  const id = state.paper.id;
  if (state.sourceBusy.has(id)) return;
  state.sourceBusy.add(id); renderPaper();
  try {
    await api(`/api/papers/${id}/content`, {method: 'POST'});
    await updatePaper(id); await refreshLibrary();
    if (state.paper?.id === id && state.route === 'paper') { state.tab = 'source'; renderPaper(); }
    notify('Full text is ready to read.');
  } catch (error) { notify(error.message, true); }
  finally { state.sourceBusy.delete(id); if (state.paper?.id === id && state.route === 'paper') renderPaper(); }
}
async function updatePaper(id) {
  const result = await api(`/api/papers/${id}`);
  if (state.route === 'paper' && state.paper?.id === id) state.paper = result.paper;
}
async function analyze(kind, question = '') {
  if (!state.status?.llm_configured) { settings(); return; }
  const id = state.paper.id;
  if (state.analysisBusy.has(id)) return;
  question = question.trim();
  if (kind === 'question' && !question) return;
  state.analysisBusy.add(id);
  if (kind === 'summary') state.tab = 'summary';
  renderPaper();
  try {
    await api(`/api/papers/${id}/analyze`, {method: 'POST', body: JSON.stringify({kind, question})});
    await updatePaper(id); await refreshLibrary();
    notify(kind === 'summary' ? 'Summary saved with your paper.' : 'Answer saved with your paper.');
  } catch (error) {
    notify(error.message, true);
    state.analysisBusy.delete(id);
    if (state.route === 'paper' && state.paper?.id === id) {
      renderPaper();
      if (kind === 'question') { $('#question-input').value = question; setError('#question-error', error.message); }
      else if ($('#summary-error')) $('#summary-error').innerHTML = errorBox(error.message);
    }
    return;
  } finally { state.analysisBusy.delete(id); }
  if (state.route === 'paper' && state.paper?.id === id) renderPaper();
}

function editMetadata(paper, note = '') {
  $('#edit-id').value = paper.id;
  $('#edit-title').value = paper.title;
  $('#edit-authors').value = paper.authors.join('\n');
  $('#edit-year').value = paper.year || '';
  $('#edit-year').max = new Date().getFullYear() + 1;
  $('#edit-abstract').value = paper.abstract;
  $('#metadata-note').textContent = note || 'Check the title, authors, year, and abstract. Unknown fields can stay blank.';
  setError('#metadata-error'); openDialog('#metadata-dialog');
}
async function refreshStatus() {
  state.status = await api('/api/status');
  $('#model-status').textContent = state.status.llm_configured ? state.status.model : 'Connect a model';
  $('#status-dot').classList.toggle('ready', state.status.llm_configured);
}
function settings() {
  const s = state.status;
  $('#settings-content').innerHTML = `<div class="connection-card"><strong>${s?.llm_configured ? 'Model configured' : 'Ready when you are.'}</strong><p>${s?.llm_configured ? `${escapeHTML(s.model)} · ${escapeHTML(s.provider_host)}<br>Configuration is present. A successful summary verifies the connection.` : 'Connect a model to summarize papers and ask questions. Search, saving, and PDF uploads already work.'}</p></div><p>On the computer running Papertrail, open <strong>solutions/hw1/.env</strong> and set:</p><pre>LLM_BASE_URL=https://api.openai.com/v1\nLLM_API_KEY=your-key\nLLM_MODEL=gpt-6-luna\nLLM_REASONING_EFFORT=none</pre><p>Restart the app after editing. You can use another OpenAI-compatible service or a local Ollama model.</p><p class="small">The key stays on the server. Paper text is sent to your configured model for summaries, questions, and optional metadata extraction. Your library is stored in the local database.</p>`;
  openDialog('#settings-dialog');
}

async function route() {
  const version = ++state.routeVersion;
  const hash = location.hash.slice(1) || 'discover';
  const match = hash.match(/^paper\/(\d+)$/);
  state.route = match ? 'paper' : hash === 'library' ? 'library' : 'discover';
  $$('.nav-link').forEach(a => { const active = a.dataset.nav === (state.route === 'paper' ? 'library' : state.route); a.classList.toggle('active', active); if (active) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  $('#breadcrumb-current').textContent = state.route === 'paper' ? 'Reading room' : state.route === 'library' ? 'My library' : 'Discover';
  document.title = `${state.route === 'paper' ? 'Reading room' : state.route === 'library' ? 'My library' : 'Discover'} — Papertrail`;
  if (match) { state.paper = null; await openPaper(Number(match[1]), version); }
  else if (state.route === 'library') library();
  else discover();
  window.scrollTo(0, 0);
}

document.addEventListener('click', async event => {
  const button = event.target.closest('button, [data-action]');
  if (!button || button.disabled) return;
  if (button.dataset.close) { $('#' + button.dataset.close).close(); return; }
  if (button.dataset.topic) { search(button.dataset.topic); return; }
  if (button.dataset.tab) { setTab(button.dataset.tab); return; }
  if (button.dataset.filter) { state.libraryFilter = button.dataset.filter; library(); return; }
  if (button.dataset.question) { $('#question-input').value = button.dataset.question; $('#question-input').focus(); return; }
  const action = button.dataset.action;
  if (action === 'upload') { setError('#upload-error'); openDialog('#upload-dialog'); }
  if (action === 'settings') settings();
  if (action === 'refresh-status') {
    try { await refreshStatus(); settings(); notify('Configuration checked.'); } catch (e) { notify(e.message, true); }
  }
  if (action === 'abstract') { const expanded = button.getAttribute('aria-expanded') === 'true'; button.previousElementSibling.classList.toggle('clamped', expanded); button.setAttribute('aria-expanded', !expanded); button.textContent = expanded ? 'Read abstract' : 'Show less'; }
  if (action === 'save') {
    const paper = state.search?.papers?.find(p => p.source_id === button.dataset.source);
    if (!paper) return;
    buttonBusy(button, true, 'Saving…');
    try { await api('/api/papers', {method: 'POST', body: JSON.stringify(paper)}); await refreshLibrary(); if (state.route === 'discover') $('#discovery-content').innerHTML = searchResults(); notify('Saved to your library.'); }
    catch (e) { notify(e.message, true); buttonBusy(button, false); }
  }
  if (action === 'next-search') search(state.searchQuery, state.searchPage + 1);
  if (action === 'previous-search') search(state.searchQuery, state.searchPage - 1);
  if (action === 'clear-filters') { state.libraryQuery = ''; state.libraryFilter = 'all'; library(); }
  if (action === 'load-content') await loadContent();
  if (action === 'summarize') await analyze('summary');
  if (action === 'edit') editMetadata(state.paper);
  if (action === 'delete') { $('#confirm-delete').dataset.id = state.paper.id; setError('#delete-error'); openDialog('#delete-dialog'); }
  if (action === 'cite') {
    setTab('source'); const source = $(`#source-page-${button.dataset.page}`);
    if (source) { source.open = true; source.scrollIntoView({behavior: 'smooth', block: 'start'}); $('summary', source).focus({preventScroll: true}); }
    else notify('That page is not in the extracted text. Please check the original PDF.', true);
  }
});
document.addEventListener('change', event => {
  if (event.target.id === 'search-sort') { state.searchSort = event.target.value; search(state.searchQuery); }
  if (event.target.id === 'library-sort') { state.librarySort = event.target.value; $('#library-results').innerHTML = libraryResults(); }
});
document.addEventListener('keydown', event => {
  if (event.target.matches('.tab') && ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
    event.preventDefault(); const tabs = $$('.tab'); const index = tabs.indexOf(event.target);
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    setTab(tabs[next].dataset.tab); tabs[next].focus();
  }
});
$('#pdf-input').addEventListener('change', event => { $('#file-label').textContent = event.target.files[0]?.name || 'Choose a PDF or drop it here'; });
const dropZone = $('#drop-zone');
['dragenter', 'dragover'].forEach(type => dropZone.addEventListener(type, event => { event.preventDefault(); dropZone.classList.add('dragging'); }));
['dragleave', 'drop'].forEach(type => dropZone.addEventListener(type, () => dropZone.classList.remove('dragging')));
dropZone.addEventListener('drop', event => {
  event.preventDefault();
  if (!event.dataTransfer.files.length) return;
  const transfer = new DataTransfer(); transfer.items.add(event.dataTransfer.files[0]);
  $('#pdf-input').files = transfer.files; $('#file-label').textContent = transfer.files[0].name;
});
$('#upload-form').addEventListener('submit', async event => {
  event.preventDefault(); const file = $('#pdf-input').files[0]; if (!file) return;
  if (!file.name.toLowerCase().endsWith('.pdf') || file.size > 20 * 1024 * 1024) { setError('#upload-error', 'Choose a PDF smaller than 20 MB.'); return; }
  const form = new FormData(); form.append('file', file); const button = $('#upload-submit');
  setError('#upload-error'); buttonBusy(button, true, 'Reading your PDF…');
  try {
    const result = await api('/api/upload', {method: 'POST', body: form});
    await refreshLibrary(); $('#upload-dialog').close(); $('#upload-form').reset(); $('#file-label').textContent = 'Choose a PDF or drop it here';
    navigate(`#paper/${result.paper.id}`); editMetadata(result.paper, result.notice); notify(result.created ? 'Your paper is in the library.' : 'This PDF is already saved.');
  } catch (error) { setError('#upload-error', error.message); }
  finally { buttonBusy(button, false); }
});
$('#metadata-form').addEventListener('submit', async event => {
  event.preventDefault(); const button = $('button[type="submit"]', event.target); const id = Number($('#edit-id').value);
  const body = {title: $('#edit-title').value, authors: $('#edit-authors').value.split('\n').map(s => s.trim()).filter(Boolean), year: $('#edit-year').value || null, abstract: $('#edit-abstract').value};
  setError('#metadata-error'); buttonBusy(button, true, 'Saving…');
  try { await api(`/api/papers/${id}`, {method: 'PATCH', body: JSON.stringify(body)}); await refreshLibrary(); await updatePaper(id); $('#metadata-dialog').close(); if (state.route === 'paper') renderPaper(); else if (state.route === 'library') library(); notify('Paper details updated.'); }
  catch (error) { setError('#metadata-error', error.message); }
  finally { buttonBusy(button, false); }
});
$('#confirm-delete').addEventListener('click', async event => {
  const button = event.currentTarget; const id = Number(button.dataset.id); buttonBusy(button, true, 'Removing…');
  try { await api(`/api/papers/${id}`, {method: 'DELETE'}); await refreshLibrary(); $('#delete-dialog').close(); navigate('#library'); notify('Paper removed from your library.'); }
  catch (error) { setError('#delete-error', error.message); }
  finally { buttonBusy(button, false); }
});
// The mobile header keeps settings reachable after the desktop sidebar collapses.
$('.topbar-note').setAttribute('data-action', 'settings');
$('.topbar-note').setAttribute('role', 'button');
$('.topbar-note').setAttribute('tabindex', '0');
$('.topbar-note').setAttribute('aria-label', 'AI settings');
$('.topbar-note').addEventListener('keydown', event => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); settings(); } });
window.addEventListener('hashchange', route);
$('.skip-link').addEventListener('click', event => { event.preventDefault(); $('#main').focus(); });
async function init() {
  const results = await Promise.allSettled([refreshLibrary(), refreshStatus()]);
  for (const result of results) if (result.status === 'rejected') notify(result.reason.message, true);
  await route();
}
init();
