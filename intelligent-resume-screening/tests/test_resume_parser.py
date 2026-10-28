import pytest

from services import ocr_service
from services.contact_extractor import extract_email, extract_name, extract_phone
from services.experience_extractor import extract_education, extract_experience
from services.resume_parser import ResumeParseError, extract_text, normalize_text, parse_fields
import datetime as dt

from tests.helpers import GOOD_RESUME, make_pdf, make_scanned_pdf


def test_normalize_text_cleans_whitespace_and_control_chars():
    assert normalize_text("a   b\x00\n\n\n\nc\t d") == "a b\n\nc d"


def test_email_extraction():
    assert extract_email("Contact: Jane.Doe+cv@Example.com.") == "jane.doe+cv@example.com"
    assert extract_email("no email here") is None


@pytest.mark.parametrize("text,expected_digits", [
    ("Call +91 98765 43210 now", "919876543210"),
    ("Phone: (555) 010-0102", "5550100102"),
    ("9000000105", "9000000105"),
])
def test_phone_extraction(text, expected_digits):
    phone = extract_phone(text)
    assert phone and "".join(c for c in phone if c.isdigit()) == expected_digits


def test_phone_ignores_years_and_short_numbers():
    assert extract_phone("2018 - 2021, ID 12345") is None
    assert extract_phone("Born 1999") is None


def test_name_extraction():
    assert extract_name("Aarav Sharma\naarav@example.com\nData Analyst") == "Aarav Sharma"
    assert extract_name("MEERA IYER\nmeera@example.com") == "Meera Iyer"
    assert extract_name("Name: Rohan Das\nSkills: SQL") == "Rohan Das"
    assert extract_name("RESUME\nData Analyst\n12345") is None


def test_experience_stated_and_dates():
    assert extract_experience("I have 5+ years of experience in data")["years"] == 5
    text = "WORK EXPERIENCE\nAnalyst (Jan 2020 - Dec 2022)\n\nEDUCATION\nB.Tech 2015 - 2019"
    exp = extract_experience(text, today=dt.date(2024, 1, 1))
    assert exp["method"] == "estimated from dates" and exp["years"] == pytest.approx(2.9, abs=0.1)


def test_experience_ignores_education_dates_and_unknown():
    assert extract_experience("EDUCATION\nB.Tech 2015 - 2019") is None
    assert extract_experience("No dates at all") is None


def test_overlapping_ranges_not_double_counted():
    text = "EXPERIENCE\nA (Jan 2020 - Dec 2021)\nB (Jun 2021 - Dec 2021)\nSKILLS\nx"
    assert extract_experience(text)["years"] == pytest.approx(1.9, abs=0.1)


def test_education():
    assert extract_education("EDUCATION\nMaster of Science in Statistics")["level"] == 3
    assert extract_education("B.Tech in CS\nDiploma in IT")["level"] == 2
    assert extract_education("I will be at the office") is None  # 'BE'/'be' must not match


def test_extract_text_from_text_pdf(tmp_path):
    res = extract_text(make_pdf(tmp_path / "a.pdf"))
    assert res.method == "text" and "Python" in res.text and res.ocr_confidence is None


def test_parse_fields_on_good_resume(tmp_path):
    fields = parse_fields(extract_text(make_pdf(tmp_path / "a.pdf")).text)
    assert fields["name"] == "Test Person"
    assert fields["email"] == "test.person@example.com"
    assert fields["phone"] and fields["education"].startswith("B.Tech")
    assert fields["experience_years"] is not None


@pytest.mark.skipif(not ocr_service.is_available(), reason="Tesseract not installed")
def test_ocr_on_scanned_pdf(tmp_path):
    res = extract_text(make_scanned_pdf(tmp_path / "scan.pdf"))
    assert res.method == "ocr"
    assert res.ocr_confidence and res.ocr_confidence > 50
    assert "python" in res.text.lower()


def test_scanned_pdf_without_ocr_fails_cleanly(tmp_path):
    with pytest.raises(ResumeParseError):
        extract_text(make_scanned_pdf(tmp_path / "scan.pdf"), ocr_enabled=False)


def test_not_a_pdf_rejected(tmp_path):
    p = tmp_path / "fake.pdf"
    p.write_text("hello world")
    with pytest.raises(ResumeParseError):
        extract_text(str(p))


def test_corrupt_pdf_rejected(tmp_path):
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"%PDF-1.4\nthis is garbage")
    with pytest.raises(ResumeParseError):
        extract_text(str(p))
