"""Helpers that build small fictional PDFs for tests."""
try:
    import pymupdf as fitz
except ImportError:
    import fitz

GOOD_RESUME = """Test Person
test.person@example.com | +1 555 010 0199

SKILLS
Python, PostgreSQL, Microsoft Excel, strong communication skills

WORK EXPERIENCE
Analyst, Fictional Co (Jan 2020 - Dec 2022)

EDUCATION
B.Tech in Computer Science, Example University
"""


def make_pdf(path, text=GOOD_RESUME, fontsize=11):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 545, 790), text, fontsize=fontsize, fontname="helv")
    doc.save(str(path))
    doc.close()
    return str(path)


def make_scanned_pdf(path, text=GOOD_RESUME):
    """Image-only PDF (no text layer) to exercise OCR."""
    tmp = fitz.open()
    page = tmp.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 545, 790), text, fontsize=14, fontname="helv")
    png = page.get_pixmap(matrix=fitz.Matrix(200 / 72, 200 / 72), colorspace=fitz.csGRAY).tobytes("png")
    tmp.close()
    doc = fitz.open()
    p = doc.new_page()
    p.insert_image(p.rect, stream=png)
    doc.save(str(path))
    doc.close()
    return str(path)
