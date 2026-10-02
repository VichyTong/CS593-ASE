"""Extract text and best-effort metadata without assuming PDF metadata is correct."""
import io
import re
from datetime import date
from pypdf import PdfReader


class PaperError(ValueError):
    pass


def cited_page_numbers(answer):
    """Accept common model citations: [p. 2], [p. 2, p. 6], [pp. 7-9]."""
    pages = set()
    for citation in re.findall(r'\[(?:pp?\.)\s*([^\]]+)\]', answer, re.I):
        for start, end in re.findall(r'(\d+)(?:\s*[-–—]\s*(\d+))?', citation):
            first, last = int(start), int(end or start)
            if 0 <= last - first <= 150:
                pages.update(range(first, last + 1))
    return pages


def extract_pdf(data):
    if not data.startswith(b'%PDF-'):
        raise PaperError('Please upload a valid PDF file.')
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(''):
            raise PaperError('This PDF is password protected. Upload an unlocked copy.')
        if len(reader.pages) > 150:
            raise PaperError('Please use a paper with at most 150 pages.')
        pages = [{'page': i + 1, 'text': p.extract_text() or ''}
                 for i, p in enumerate(reader.pages)]
        if sum(len(p['text'].strip()) for p in pages) < 200:
            raise PaperError('No readable text found. Scanned PDFs need OCR before upload.')
        if sum(len(p['text']) for p in pages) > 1_000_000:
            raise PaperError('This PDF contains too much text (limit: 1 million characters).')
        meta = reader.metadata or {}
        return pages, heuristic_metadata(pages, meta)
    except PaperError:
        raise
    except Exception as exc:
        raise PaperError('Could not read this PDF. Try an unencrypted, text-based PDF.') from exc


def heuristic_metadata(pages, meta):
    first = pages[0]['text']
    lines = [re.sub(r'\s+', ' ', x).strip() for x in first.splitlines() if x.strip()]
    title = str(meta.get('/Title') or '').strip()
    if not title or title.lower() in {'untitled', 'unknown', 'microsoft word'} or title.endswith(('.tex', '.dvi')):
        candidates = [x for x in lines[:16] if len(x) > 12 and not re.match(
            r'(arxiv:|https?://|preprint|published|proceedings|copyright|©)', x, re.I)]
        title = candidates[0] if candidates else 'Untitled paper'
    authors_raw = str(meta.get('/Author') or '').strip()
    authors = [x.strip() for x in re.split(r';|\band\b', authors_raw) if x.strip()]
    if not authors:
        # Conservative fallback. The editable review form makes uncertainty explicit.
        title_index = next((i for i,x in enumerate(lines) if title in x), -1)
        for line in lines[title_index + 1:title_index + 5] if title_index >= 0 else []:
            if re.search(r'(university|institute|abstract|@|department|laboratory|research|\d{4})', line, re.I):
                break
            names = [re.sub(r'[\d*†‡]+', '', x).strip() for x in re.split(r',|\band\b|\s{2,}', line)]
            if all(2 <= len(x.split()) <= 5 for x in names) and all(len(x) < 65 for x in names):
                authors.extend(names)
            else:
                break
    match = re.search(r'\babstract\b\s*[:.\-—]?\s*(.*?)(?=\n\s*(?:\d+[.\s]+)?(?:introduction|keywords|index terms|1\s+introduction)\b|\Z)',
                      '\n'.join(p['text'] for p in pages[:2]), re.I | re.S)
    abstract = re.sub(r'\s+', ' ', match.group(1)).strip()[:6000] if match else ''
    years = [int(y) for y in re.findall(r'\b((?:19|20)\d{2})\b', first[:6000])]
    years = [y for y in years if 1900 <= y <= date.today().year + 1]
    return {'title': title[:1000], 'authors': authors[:50],
            'year': years[0] if years else None, 'abstract': abstract,
            'metadata_method': 'PDF metadata and text heuristics; review recommended'}


def chunks(pages, size=2600):
    """Preserve PDF page numbers, including pages with no text."""
    result = []
    for p in pages:
        text = p['text'].strip()
        for start in range(0, len(text), size):
            result.append({'page': p['page'], 'text': text[start:start + size]})
    return result


def select_context(pages, question=None, budget=42000):
    pieces = chunks(pages)
    total = sum(len(p['text']) for p in pieces)
    if total <= budget:
        selected = pieces
        coverage = 'Full extracted text'
    elif question:
        tokens = set(re.findall(r'\w{3,}', question.lower()))
        # The first chunk gives context; lexical retrieval selects evidence elsewhere.
        ranked = sorted(enumerate(pieces), key=lambda item: sum(
            min(item[1]['text'].lower().count(t), 8) for t in tokens), reverse=True)
        indexes, used = {0}, len(pieces[0]['text'])
        for i,p in ranked:
            if i not in indexes and used + len(p['text']) <= budget:
                indexes.add(i)
                used += len(p['text'])
        selected = [pieces[i] for i in sorted(indexes)]
        coverage = 'Selected excerpts ranked by question keywords; not the entire paper'
    else:
        # Even sampling includes the ending, avoiding first-N-character summaries.
        count = max(1, budget // 2600)
        indexes = sorted({round(i * (len(pieces)-1) / (count-1)) for i in range(count)})
        selected = [pieces[i] for i in indexes]
        coverage = 'Excerpts sampled across the paper; not the entire paper'
    context = '\n\n'.join(f"[p. {p['page']}]\n{p['text']}" for p in selected)
    return context, selected, coverage
