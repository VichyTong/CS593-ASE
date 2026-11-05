"""Real synthetic PDFs for round 1, with deliberately known text and typography.

No application function is used to construct the expected metadata or lengths.
These are extraction fixtures, not publication-quality rendered documents.
"""
import io

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

PDF_BYTE_LIMIT = 20 * 1024 * 1024  # Explicit configured-unit interpretation.
PAGE_LIMIT = 150
TEXT_LIMIT = 1_000_000
TITLE = 'Reliable Storage for Research Libraries'
AUTHORS = ['Dana Tester', 'Evan Researcher']
ABSTRACT = ('We evaluate a synthetic research library with controlled documents. '
            'The experiment measures persistent records and reproducible PDF extraction.')
BODY = ('The dataset was collected in 2018, which is not a publication date. '
        'All documents are invented for this experiment. No external services or '
        'personal library records are used. The limitations concern synthetic data.')


def make_pdf(pages, *, document_metadata=None):
    """pages contains lists of (font size, text) lines; no trailing T* is added.

    A one-line page extracts exactly its ASCII text. Multiple lines use fixed
    downward positions, so line breaks convey title/byline/section boundaries.
    document_metadata=None removes the entire Info dictionary, even Producer.
    """
    writer = PdfWriter()
    writer.metadata = document_metadata
    font = DictionaryObject({
        NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica'),
    })
    font_ref = writer._add_object(font)
    for lines in pages:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject('/Resources')] = DictionaryObject({
            NameObject('/Font'): DictionaryObject({NameObject('/F1'): font_ref}),
        })
        commands = ['BT', '50 740 Td']
        for index, (size, text) in enumerate(lines):
            if index:
                commands.append('0 -28 Td')
            escaped = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            commands.extend([f'/F1 {size} Tf', f'({escaped}) Tj'])
        commands.append('ET')
        stream = DecodedStreamObject()
        stream.set_data('\n'.join(commands).encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def metadata_pdf(*, multiline=False, unknown_fields=False):
    """The title is 24 pt; the two-person byline is 12 pt; body is 10 pt.

    Publication is explicitly labeled 2024; dataset year 2018 is prose evidence
    about the study, not publication. unknown_fields omits byline and date.
    """
    titles = ['Reliable Storage for', 'Research Libraries'] if multiline else [TITLE]
    lines = [(24, title) for title in titles]
    if not unknown_fields:
        lines.extend([(12, 'Dana Tester and Evan Researcher'),
                      (10, 'Institute of Synthetic Studies'),
                      (10, 'Published in the Synthetic Systems Conference 2024')])
    lines.extend([(12, 'Abstract'), (10, ABSTRACT), (14, '1 Introduction'), (10, BODY)])
    return make_pdf([lines])


def limit_pdf(texts):
    """Explicit metadata keeps independent metadata heuristics out of limit tests."""
    return make_pdf([[(12, text)] for text in texts], document_metadata={
        '/Title': 'Synthetic PDF Limit Fixture', '/Author': 'Dana Tester',
    })


def pad_pdf(raw, target_bytes):
    """Pad a PDF using a legal comment before startxref, leaving offsets intact.

    The xref and all objects precede the comment; the startxref offset value
    still refers to the same byte. No huge decoded page stream is introduced.
    """
    extra = target_bytes - len(raw)
    if extra < 2:
        raise ValueError('Target must leave at least two padding bytes')
    position = raw.rindex(b'startxref')
    return raw[:position] + b'%' + b'P' * (extra - 2) + b'\n' + raw[position:]
