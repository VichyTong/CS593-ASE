"""Bounded PDF extraction and page-preserving context selection."""
import io
import re
from datetime import date
from pypdf import PdfReader

MAX_PDF_BYTES = 20 * 1024 * 1024


class PaperError(ValueError):
    """An actionable error that can safely be displayed to the user."""


def extract_pdf(raw):
    if not raw.startswith(b'%PDF-'):
        raise PaperError('This file is not a valid PDF. Please choose a PDF paper.')
    if len(raw) > MAX_PDF_BYTES:
        raise PaperError('Please choose a PDF smaller than 20 MB.')
    try:
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted and not reader.decrypt(''):
            raise PaperError('This PDF is password protected. Upload an unlocked copy.')
        if not 1 <= len(reader.pages) <= 150:
            raise PaperError('Please choose a PDF with 1 to 150 pages.')
        pages, total = [], 0
        for i, page in enumerate(reader.pages):
            content = page.get_contents()
            if content and len(content.get_data()) > 15_000_000:
                raise PaperError('This PDF page is too complex to process. Try a smaller copy.')
            text = (page.extract_text() or '').replace('\x00', '')
            total += len(text)
            if total > 1_000_000:
                raise PaperError('This PDF exceeds the one-million-character text limit.')
            pages.append({'page': i + 1, 'text': text})
        if sum(len(p['text'].strip()) for p in pages) < 200:
            raise PaperError('No readable text found. Scanned PDFs need OCR before uploading.')
        metadata = extract_metadata(pages, reader.metadata or {})
        # A legal notice or running header can precede the title in reading order.
        # Prefer prominent text above the abstract when document metadata is empty.
        if not (reader.metadata or {}).get('/Title'):
            prominent = []
            def visit(text, cm, tm, font, size):
                clean = ' '.join(text.split())
                if len(clean) > 10 and not re.match(r'(arxiv|https?://|abstract)', clean, re.I):
                    prominent.append((size, clean))
            reader.pages[0].extract_text(visitor_text=visit)
            if prominent:
                largest = max(size for size, _ in prominent)
                title_parts = [text for size, text in prominent if size >= largest - .1]
                title = ' '.join(title_parts)
                if 12 <= len(title) <= 500:
                    metadata['title'] = title
        return pages, metadata
    except PaperError:
        raise
    except Exception as exc:
        raise PaperError('This PDF could not be read. Try an unlocked, text-based copy.') from exc


def extract_metadata(pages, metadata):
    first = pages[0]['text']
    lines = [re.sub(r'\s+', ' ', line).strip() for line in first.splitlines() if line.strip()]
    title = str(metadata.get('/Title') or '').strip()
    if not title or title.lower() in {'untitled', 'unknown', 'microsoft word'} or re.search(r'\.(tex|dvi|pdf)$', title):
        candidates = [line for line in lines[:20] if len(line) > 12 and not re.match(
            r'(arxiv:|https?://|preprint|published|proceedings|copyright|©|under review)', line, re.I)]
        title = candidates[0] if candidates else 'Untitled paper'
    authors_raw = str(metadata.get('/Author') or '').strip()
    authors = [s.strip() for s in re.split(r';|,|\band\b', authors_raw) if s.strip()]
    if not authors:
        index = next((i for i, line in enumerate(lines) if title in line), -1)
        for line in lines[index + 1:index + 7] if index >= 0 else []:
            if re.search(r'(university|institute|abstract|@|department|laboratory|\d{4})', line, re.I):
                break
            names = [re.sub(r'[\d*†‡]+', '', s).strip() for s in re.split(r',|;|\band\b', line)]
            if names and all(2 <= len(s.split()) <= 5 and len(s) < 65 for s in names):
                authors.extend(names)
            else:
                break
    leading = '\n'.join(p['text'] for p in pages[:2])
    match = re.search(r'\babstract\b\s*[:.\-—]?\s*(.*?)(?=\n\s*(?:(?:\d+[.\s]+)?(?:introduction|keywords|index terms)\b|[∗*†‡]\s*(?:Equal contribution|Work performed))|\Z)', leading, re.I | re.S)
    abstract = re.sub(r'\s+', ' ', match.group(1)).strip()[:10000] if match else ''
    arxiv = re.search(r'arXiv\s*:\s*(\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?', first, re.I)
    publication_lines = '\n'.join(line for line in lines if re.search(r'(copyright|©|conference|proceedings|published|accepted|journal|preprint)', line, re.I))
    years = [int(y) for y in re.findall(r'\b((?:19|20)\d{2})\b', publication_lines)]
    years = [y for y in years if 1900 <= y <= date.today().year + 1]
    if not years:
        standalone = [int(line) for line in lines if re.fullmatch(r'(?:19|20)\d{2}', line)]
        years = [y for y in standalone if y <= date.today().year + 1]
    return {'title': title[:1000], 'authors': authors[:100], 'year': years[0] if years else None,
            'abstract': abstract, 'arxiv_id': arxiv.group(1) if arxiv else None,
            'metadata_method': 'PDF text and document metadata; review recommended'}


def select_context(pages, question='', budget=48000):
    """Include all text when possible, else distribute/rank bounded excerpts."""
    size = min(2400, max(100, budget // 3))
    pieces = [{'page': p['page'], 'text': p['text'][i:i + size].strip()}
              for p in pages for i in range(0, len(p['text']), size) if p['text'][i:i + size].strip()]
    if not pieces:
        raise PaperError('This paper has no readable text to analyze.')
    cost = lambda p: len(p['text']) + len(str(p['page'])) + 9
    if sum(map(cost, pieces)) <= budget:
        selected = pieces
        coverage = 'Full extracted text'
    else:
        if question:
            stop = {'what', 'which', 'does', 'this', 'paper', 'about', 'are', 'the', 'and', 'how', 'with'}
            terms = set(re.findall(r'\w{3,}', question.lower())) - stop
            ranked = sorted(range(1, len(pieces)), key=lambda i: sum(min(pieces[i]['text'].lower().count(t), 10) for t in terms), reverse=True)
            order = [0] + ranked
            coverage = 'Relevant excerpts selected by question keywords'
        else:
            count = max(1, min(len(pieces), budget // (size + 20)))
            order = [round(i * (len(pieces) - 1) / max(1, count - 1)) for i in range(count)]
            coverage = 'Excerpts sampled across the paper'
        indexes, used = [], 0
        for i in dict.fromkeys(order):
            if used + cost(pieces[i]) <= budget:
                indexes.append(i)
                used += cost(pieces[i])
        selected = [pieces[i] for i in sorted(indexes)]
    context = '\n\n'.join(f"[p. {p['page']}]\n{p['text']}" for p in selected)
    return context, selected, coverage


def cited_pages(answer):
    numbers = set()
    for group in re.findall(r'\[pp?\.\s*([^\]]+)\]', answer, re.I):
        for a, b in re.findall(r'(\d+)(?:\s*[-–—]\s*(\d+))?', group):
            start, end = int(a), int(b or a)
            if 0 <= end - start <= 150:
                numbers.update(range(start, end + 1))
    return numbers
