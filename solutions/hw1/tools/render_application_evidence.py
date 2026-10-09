"""Render the app's metadata HTML/CSS as vector PDF, without desktop automation.

Uses an isolated headless Chromium process to print local, script-free HTML.
The historical failure is explicitly a transcription, not a new screenshot.
Run: python tools/render_application_evidence.py --paper-id 2
"""
import argparse
import html
import json
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs' / 'evidence'


def render(paper_id, database, chromium):
    from pypdf import PdfReader

    with sqlite3.connect(f'file:{database.resolve()}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT title, authors, year, abstract FROM papers WHERE id=?', (paper_id,)).fetchone()
    if row is None:
        raise SystemExit(f'Paper {paper_id} is not in the local library.')
    paper = dict(row)
    paper['authors'] = json.loads(paper['authors'])
    template = (ROOT / 'templates' / 'index.html').read_text()
    css = (ROOT / 'static' / 'style.css').read_text()
    dialog = re.search(r'<dialog id="metadata-dialog".*?</dialog>', template, re.S).group()
    dialog = dialog.replace('<dialog id="metadata-dialog"', '<dialog open id="metadata-dialog"', 1)
    for name, value in [('title', paper['title']), ('authors', '\n'.join(paper['authors'])), ('abstract', paper['abstract'])]:
        pattern = rf'(<textarea id="edit-{name}"[^>]*>).*?(</textarea>)'
        dialog = re.sub(pattern, lambda m: m[1] + html.escape(value) + m[2], dialog, flags=re.S)
    dialog = dialog.replace('<input id="edit-year"', f'<input value="{paper["year"] or ""}" id="edit-year"', 1)

    # Print-only overrides expose full field contents while retaining the app's
    # actual labels, HTML structure, colors, typography, and field styling.
    print_css = '''
    @page { size: 508pt 540pt; margin: 0; }
    body { background: white; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .capture { width: 100%; padding: 0; break-after: page; }
    .capture:last-child { break-after: auto; }
    #metadata-dialog[open] { display: block; position: static; margin: 0;
      width: 100%; max-width: none; max-height: none; padding: 16px 24px;
      overflow: visible; box-shadow: none; border-radius: 12px; }
    #metadata-dialog .icon-button, #metadata-dialog .dialog-actions,
    #metadata-dialog .form-error { display: none; }
    #metadata-dialog .dialog-heading { margin-bottom: 10px; }
    #metadata-dialog .dialog-heading h2 { font-size: 28px; margin-top: 5px; }
    #metadata-dialog .dialog-heading + .muted { margin-bottom: 12px; }
    #metadata-form > label { margin: 8px 0 4px; font-size: 13px; color: #385846; }
    #metadata-form textarea, #metadata-form input:not([type=hidden]) {
      font-size: 13px; line-height: 1.3; padding: 8px 10px; }
    #metadata-form textarea { field-sizing: content; resize: none;
      height: auto; min-height: 0; max-height: none; overflow: visible; }
    .transcript { padding: 26px; background: #fafbf8; border: 1px solid #dde7d3;
      border-radius: 12px; font-size: 15px; line-height: 1.55; }
    .transcript h1 { font: 29px Georgia, serif; color: #285e50; margin: 8px 0 18px; }
    .transcript h2 { font-size: 14px; margin: 22px 0 6px; color: #385846; }
    .transcript p { margin: 6px 0; }
    .transcript .value { padding: 12px; background: white; border: 1px solid #dce5d4; border-radius: 6px; }
    .transcript .label { font-size: 11px; letter-spacing: 1.4px; color: #526b5b; }
    .transcript .note { font-size: 13px; color: #526b5b; margin-top: 24px; }
    '''
    before = '''<section class="capture"><article class="transcript">
    <div class="label">HISTORICAL EVIDENCE / TEXT TRANSCRIPTION</div>
    <h1>What the first upload showed</h1>
    <p>The following values are transcribed from the original failure screenshot.
    This is a readable evidence record, not a recreation of the application screen.</p>
    <h2>Title field - visible text</h2>
    <p class="value">Provided proper attribution is provided, Google hereby grants permission to</p>
    <h2>Authors</h2><p class="value">The field was empty.</p>
    <h2>Publication year</h2><p class="value">2014</p>
    <h2>Why the result was incorrect</h2>
    <p>The title came from a reproduction notice, and the year came from a dataset.
    The expected paper was <em>Attention Is All You Need</em>, with eight authors and a 2017 publication year.</p>
    <p class="note">Original evidence is retained in docs/evidence/metadata-before.jpg.
    Only the clearly visible title, author-field state, and year are transcribed here.</p>
    </article></section>'''
    document = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<title>Papertrail application evidence</title><style>' + css + '\n' + print_css +
        '</style></head><body>' + before + '<section class="capture">' + dialog + '</section></body></html>')
    html_path = EVIDENCE / 'application-evidence.html'
    pdf_path = EVIDENCE / 'application-evidence.pdf'
    html_path.write_text(document)
    # No user browser profile, remote-debugging session, or GUI is used.
    with tempfile.TemporaryDirectory(prefix='papertrail-pdf-') as profile:
        rendered_pdf = Path(profile) / 'rendered.pdf'
        command = [str(chromium), '--headless=new', '--disable-gpu', '--disable-extensions',
            '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
            f'--user-data-dir={profile}', '--no-pdf-header-footer',
            f'--print-to-pdf={rendered_pdf}', html_path.as_uri()]
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 30
            last_size = None
            while time.monotonic() < deadline:
                if rendered_pdf.exists():
                    data = rendered_pdf.read_bytes()
                    if data.rstrip().endswith(b'%%EOF') and len(data) == last_size:
                        PdfReader(rendered_pdf)  # Validate the completed output before copying it.
                        shutil.copyfile(rendered_pdf, pdf_path)
                        break
                    last_size = len(data)
                if process.poll() not in (None, 0):
                    raise RuntimeError('The headless HTML renderer failed.')
                time.sleep(0.25)
            else:
                raise TimeoutError('The headless HTML renderer did not produce a complete PDF.')
        finally:
            # Some desktop Chromium builds remain alive after writing print output.
            # Stop only this task's isolated renderer, never the user's browser.
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    reader = PdfReader(pdf_path)
    if len(reader.pages) != 2:
        raise SystemExit(f'Expected two evidence pages, got {len(reader.pages)}; inspect the layout.')
    assert all(not page.images for page in reader.pages), 'Application evidence must remain vector.'
    text = reader.pages[1].extract_text()
    for expected in [paper['title'], str(paper['year']), *paper['authors']]:
        assert expected in text, f'Missing text in PDF: {expected}'
    print('Created application-evidence.pdf: 2 vector pages, no embedded raster images.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--paper-id', type=int, default=2)
    parser.add_argument('--database', type=Path, default=ROOT / 'data' / 'library.sqlite3')
    parser.add_argument('--chromium', type=Path, default=Path(shutil.which('chromium') or
        shutil.which('google-chrome') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'))
    args = parser.parse_args()
    render(args.paper_id, args.database, args.chromium)
