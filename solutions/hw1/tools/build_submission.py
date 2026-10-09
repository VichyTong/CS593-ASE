"""Build a review PDF and captioned walkthrough from actual browser evidence.

Optional tooling only: pip install reportlab imageio-ffmpeg pillow
Run from any directory: python tools/build_submission.py
Use --complete-demo only after capturing live summary and Q&A evidence.
"""
import argparse
import re
import subprocess
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
EVIDENCE = DOCS / 'evidence'
TEMP = ROOT / 'data' / 'submission-build'


def plain(text):
    for old, new in [('—', '-'), ('–', '-'), ('‑', '-'), ('“', '"'), ('”', '"'), ('’', "'"), ('‘', "'")]:
        text = text.replace(old, new)
    return text


def paragraph_markup(text):
    text = escape(plain(text))
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\*', r'<i>\1</i>', text)
    return re.sub(r'`([^`]+)`', r'<font name="Courier" size="9">\1</font>', text)


def build_pdf():
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, Flowable, Image
    from PIL import Image as PILImage
    text_color = colors.black
    styles = {
        'title': ParagraphStyle('title', fontName='Times-Roman', fontSize=30, leading=35, textColor=text_color, spaceAfter=20),
        'h2': ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=14, leading=19, textColor=text_color, spaceBefore=20, spaceAfter=10, keepWithNext=True),
        'h3': ParagraphStyle('h3', fontName='Helvetica-Bold', fontSize=11, leading=16, textColor=text_color, spaceBefore=14, spaceAfter=7, keepWithNext=True),
        'body': ParagraphStyle('body', fontName='Helvetica', fontSize=10, leading=15.5, textColor=colors.black, spaceAfter=9, alignment=TA_LEFT),
        'prompt': ParagraphStyle('prompt', fontName='Helvetica', fontSize=9.5, leading=15, backColor=colors.HexColor('#edf3e8'), borderPadding=10, spaceBefore=9, spaceAfter=18),
        'caption': ParagraphStyle('caption', fontName='Helvetica', fontSize=9, leading=13, textColor=colors.black, spaceAfter=15),
    }
    output = DOCS / 'reflection-draft.pdf'
    story = []
    for block in (DOCS / 'REFLECTION.md').read_text().split('\n\n'):
        block = block.strip()
        if not block:
            continue
        picture = re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)', block)
        if block == '<!-- pagebreak -->':
            story.append(PageBreak())
        elif picture:
            caption, relative_path = picture.groups()
            path = DOCS / relative_path
            with PILImage.open(path) as source:
                width, height = source.size
            scale = min(508 / width, 540 / height)
            screenshot = Image(str(path), width=width * scale, height=height * scale)
            screenshot.hAlign = 'LEFT'
            screenshot.spaceAfter = 9
            screenshot.keepWithNext = True
            story.extend([screenshot, Paragraph(paragraph_markup(caption), styles['caption'])])
        elif block.startswith('# '):
            story.append(Paragraph(paragraph_markup(block[2:]), styles['title']))
        elif block.startswith('## '):
            story.append(Paragraph(paragraph_markup(block[3:]), styles['h2']))
        elif block.startswith('### '):
            story.append(Paragraph(paragraph_markup(block[4:]), styles['h3']))
        elif block.startswith('- '):
            for line in block.splitlines():
                story.append(Paragraph('- ' + paragraph_markup(line[2:]), styles['body']))
        else:
            style = 'prompt' if block.startswith(('**Personal', '**Insert genuine')) else 'body'
            story.append(Paragraph(paragraph_markup(block.replace('\n', ' ')), styles[style]))
    overlays = []
    class VectorEvidence(Flowable):
        """Reserve space, then merge the original PDF operators without rasterizing."""
        def __init__(self, path, page_index):
            super().__init__()
            self.path = path
            self.page_index = page_index
            self.width, self.height = 508, 540
        def draw(self):
            x, y = self.canv.absolutePosition(0, 0)
            overlays.append((self.canv.getPageNumber() - 1, self.path, self.page_index, x, y))
    evidence_pdf = EVIDENCE / 'application-evidence.pdf'
    if not evidence_pdf.exists():
        raise FileNotFoundError('Render vector evidence first: python tools/render_application_evidence.py')
    for index, heading, caption in [
        (0, 'Evidence A: the observed metadata failure',
         'Readable transcription of the original failure: a notice became the title, authors were missing, and the dataset year 2014 was used. The original screenshot remains in the evidence folder.'),
        (1, 'Evidence B: corrected application details',
         'Direct rendering of the application metadata HTML and CSS with the saved paper record. The print layout exposes all eight authors and the complete abstract; text remains selectable when enlarged.')]:
        story.extend([PageBreak(), Paragraph(heading, styles['h2']), Paragraph(caption, styles['caption']),
                      VectorEvidence(evidence_pdf, index)])
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#dce5d5')); canvas.line(52, 44, 560, 44)
        canvas.setFillColor(colors.black); canvas.setFont('Helvetica', 8)
        canvas.drawString(52, 29, 'PAPERTRAIL  /  Reflection draft - student review required')
        canvas.drawRightString(560, 29, str(doc.page)); canvas.restoreState()
    SimpleDocTemplate(str(output), pagesize=(612, 792), leftMargin=52, rightMargin=52, topMargin=48,
                      bottomMargin=62, title='Papertrail - Reflection draft', author='Agent-assisted draft for student review').build(story, onFirstPage=footer, onLaterPages=footer)
    from pypdf import PdfReader, PdfWriter, Transformation
    reader = PdfReader(output)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    for target, source_path, source_index, x, y in overlays:
        source = PdfReader(source_path).pages[source_index]
        writer.pages[target].merge_transformed_page(source, Transformation().translate(x, y))
    with output.open('wb') as file:
        writer.write(file)
    print('Created', output.name)


def build_video(complete):
    import imageio_ffmpeg
    from PIL import Image, ImageDraw, ImageFont
    TEMP.mkdir(parents=True, exist_ok=True)
    scenes = [
        ('01-home.jpg', 'Papertrail', 'A quiet workspace for discovering, collecting, and understanding research.', 7),
        ('02-search.jpg', '01  Search for a paper', 'Live arXiv results include the title, authors, year, abstract, and original link.', 10),
        ('03-library.jpg', '02  Keep what matters', 'Save a result to SQLite. The library survives refreshes and server restarts.', 9),
        ('04-upload.jpg', '03  Bring your own PDF', 'Upload a readable PDF of up to 20 MB. The application extracts its pages.', 9),
        ('05-metadata.jpg', 'Review the details', 'The PDF identifier matches the title, eight authors, 2017, and abstract. Details stay editable.', 10),
    ]
    if complete:
        for required in ['06-summary.jpg', '07-question.jpg']:
            if not (EVIDENCE / required).exists():
                raise SystemExit('Capture actual live AI evidence before building a complete demo: ' + required)
        scenes += [('06-summary.jpg', '04  Understand the essentials', 'A real LLM summary uses extracted paper content and includes page references.', 14),
                   ('07-question.jpg', '05  Ask a question', 'A real answer is saved with the paper and can be checked against source excerpts.', 14)]
    scenes += [('08-evidence.jpg', 'Follow the evidence', 'Inspect the extracted text, organized by the physical PDF page number.', 8),
               ('09-mobile.jpg', 'Research, at your own pace', 'A responsive reading workspace on desktop and smaller screens.', 7)]
    if not complete:
        scenes.append(('ai-setup-pending.jpg', 'PREVIEW - AI verification still pending', 'Connect a model, then record a real summary and answer to complete the required five-flow demo.', 10))
    font_path = '/System/Library/Fonts/Supplemental/Arial.ttf'
    if not Path(font_path).exists():
        font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    title_font = ImageFont.truetype(font_path, 29)
    body_font = ImageFont.truetype(font_path, 18)
    label_font = ImageFont.truetype(font_path, 12)
    rendered = []
    for i, (filename, title, caption, seconds) in enumerate(scenes):
        frame = Image.new('RGB', (1440, 1080), '#f8faf5')
        source = Image.open(EVIDENCE / filename).convert('RGB')
        source.thumbnail((1408, 894), Image.Resampling.LANCZOS)
        frame.paste(source, ((1440 - source.width) // 2, 14 + (894 - source.height) // 2))
        draw = ImageDraw.Draw(frame)
        draw.rectangle((0, 922, 1440, 1080), fill='#285e50')
        draw.text((38, 944), plain(title), font=title_font, fill='#ffffff')
        for line_no, line in enumerate(textwrap.wrap(plain(caption), width=125)):
            draw.text((38, 990 + line_no * 25), line, font=body_font, fill='#e0ecdd')
        draw.text((38, 1056), 'Actual application screenshots | Captioned walkthrough' + ('' if complete else ' | Incomplete demo preview'), font=label_font, fill='#c2d5bd')
        target = TEMP / f'frame-{i:02d}.png'; frame.save(target)
        rendered.append((target, seconds))
    output = DOCS / ('demo.mp4' if complete else 'demo-preview.mp4')
    # Explicit raw frames avoid image-concat timestamp rounding between scenes.
    process = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-y',
                    '-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size', '1440x1080', '-framerate', '2',
                    '-i', '-', '-vf', 'fps=24', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(output)], stdin=subprocess.PIPE)
    try:
        for target, seconds in rendered:
            pixels = Image.open(target).convert('RGB').tobytes()
            for _ in range(seconds * 2):
                process.stdin.write(pixels)
    finally:
        process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError('Video encoding failed')
    print('Created', output.name, f'({sum(s[3] for s in scenes)} seconds)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--complete-demo', action='store_true')
    args = parser.parse_args()
    build_pdf()
    build_video(args.complete_demo)
