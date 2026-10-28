"""Generate clearly FICTIONAL sample resumes (PDF) for testing.

Usage:  python sample_data/GenerateSampleResumes.py
Creates sample_data/resumes/*.pdf  (6 text-based PDFs, 1 scanned/image-only PDF, 1 invalid file).
All names use example.com e-mail addresses and 555-style phone numbers.
"""
import os

try:
    import pymupdf as fitz
except ImportError:
    import fitz

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resumes")

RESUMES = {
    "aarav_sharma.pdf": """Aarav Sharma
aarav.sharma@example.com | +91 90000 00101
Fictional sample resume - not a real person

SUMMARY
Data analyst with 3 years of experience turning data into decisions. Strong communication skills.

SKILLS
Python, pandas, PostgreSQL, Microsoft Excel, Power BI, Git

WORK EXPERIENCE
Data Analyst, Example Analytics Pvt Ltd (Jan 2022 - Present)
- Built Python scripts to automate weekly reports.
- Wrote PostgreSQL queries for sales dashboards.
- Presented insights to management teams.

EDUCATION
B.Tech in Computer Science, Example Institute of Technology, 2021
""",
    "meera_iyer.pdf": """MEERA IYER
meera.iyer@example.com
Phone: (555) 010-0102

PROFILE
Analyst who enjoys automation.

TECHNICAL SKILLS
Python, Excel, VBA, Teamwork

EXPERIENCE
Business Analyst, Sample Corp (Mar 2020 - Dec 2022)
Junior Analyst, Demo Systems (Jan 2023 - Present)

EDUCATION
Bachelor of Commerce, Sample University, 2019
""",
    "rohan_das.pdf": """Rohan Das
rohan.das@example.org | +1 555 010 0103

OBJECTIVE
Database-focused analyst seeking growth.

SKILLS
SQL, MySQL, Excel (pivot tables, VLOOKUP), written communication, Tableau

PROFESSIONAL EXPERIENCE
Reporting Analyst, Fictional Retail Ltd (2018 - 2021)
Senior Reporting Analyst, Fictional Retail Ltd (2021 - 2024)

EDUCATION
Master of Science in Statistics, Example University
""",
    "priya_nair.pdf": """Priya Nair
priya.nair@example.com | +91 90000 00104

SKILLS
Java, JavaScript, HTML5, CSS3, React, Node.js, Git

EXPERIENCE
Software Developer Intern, Demo Labs (Jun 2023 - Aug 2023)

EDUCATION
B.E. Information Technology, Example College, 2024
""",
    "karan_mehta.pdf": """Karan Mehta
karan.mehta@example.com | 9000000105

SKILLS
Used py scripts with pandas and numpy; MS Excel; MySQL; teamwork

Fresher with 1 year of experience in internships.

EDUCATION
BCA, Sample Institute, 2023
""",
    "sneha_rao.pdf": """Sneha Rao
sneha.rao@example.com | +1 555 010 0106

SUMMARY
Marketing associate with excellent communication skills and presentation skills.

SKILLS
Excel, social media, copywriting, public speaking, time management

WORK EXPERIENCE
Marketing Associate, Example Media (Feb 2021 - Present)

EDUCATION
Bachelor of Arts, Demo University
""",
}

SCANNED = ("scanned_vikram_singh.pdf", """Vikram Singh
vikram.singh@example.com
+1 555 010 0107

SKILLS
Python, SQL, Excel, Communication

EXPERIENCE
Data Analyst at Sample Co (2020 - 2023)

EDUCATION
Bachelor of Technology in Computer Science
""")


def _text_pdf(path, text, fontsize=10):
    doc = fitz.open()
    page = doc.new_page()
    leftover = page.insert_textbox(fitz.Rect(50, 50, 545, 790), text, fontsize=fontsize, fontname="helv")
    if leftover < 0:
        raise RuntimeError(f"Text did not fit on the page for {path}")
    doc.save(path)
    doc.close()


def _scanned_pdf(path, text):
    """Render the text to an image and embed ONLY the image, simulating a scanned document."""
    tmp = fitz.open()
    page = tmp.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 545, 790), text, fontsize=14, fontname="helv")
    png = page.get_pixmap(matrix=fitz.Matrix(200 / 72, 200 / 72), colorspace=fitz.csGRAY).tobytes("png")
    tmp.close()
    doc = fitz.open()
    new_page = doc.new_page()
    new_page.insert_image(new_page.rect, stream=png)
    doc.save(path)
    doc.close()


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, text in RESUMES.items():
        _text_pdf(os.path.join(OUT, name), text)
    _scanned_pdf(os.path.join(OUT, SCANNED[0]), SCANNED[1])
    with open(os.path.join(OUT, "invalid_not_a_pdf.pdf"), "w", encoding="utf-8") as fh:
        fh.write("This is plain text pretending to be a PDF. It should be rejected by validation.")
    print(f"Created {len(RESUMES) + 2} files in {OUT}")


if __name__ == "__main__":
    main()
