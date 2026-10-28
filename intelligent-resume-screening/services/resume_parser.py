"""PDF text extraction (with OCR fallback), text normalisation and full resume parsing."""
import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import pymupdf as fitz  # PyMuPDF >= 1.24.3
except ImportError:
    import fitz  # older PyMuPDF releases

from services import ocr_service
from services.contact_extractor import extract_email, extract_name, extract_phone
from services.experience_extractor import extract_education, extract_experience


class ResumeParseError(Exception):
    """Raised when a PDF cannot be read at all."""


@dataclass
class ExtractionResult:
    text: str
    page_count: int
    method: str  # 'text' | 'ocr' | 'mixed' | 'none'
    ocr_confidence: Optional[float] = None
    warnings: List[str] = field(default_factory=list)


def is_pdf_file(path: str) -> bool:
    """Content check: real PDFs begin with the %PDF- signature."""
    try:
        with open(path, "rb") as fh:
            return fh.read(1024).lstrip().startswith(b"%PDF-")
    except OSError:
        return False


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\x00", "")
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    text = text.replace("\t", " ").replace("•", "- ").replace("●", "- ").replace("▪", "- ")
    lines = [re.sub(r"[ ]{2,}", " ", ln).strip() for ln in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(path: str, *, ocr_enabled: bool = True, ocr_dpi: int = 200, ocr_max_pages: int = 10,
                 min_chars_per_page: int = 50, tesseract_cmd: str = "", max_pages: int = 30) -> ExtractionResult:
    if not is_pdf_file(path):
        raise ResumeParseError("File content is not a valid PDF.")
    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise ResumeParseError(f"PDF could not be opened: {exc}")
    try:
        if doc.needs_pass:
            raise ResumeParseError("PDF is password protected.")
        page_count = doc.page_count
        if page_count == 0:
            raise ResumeParseError("PDF has no pages.")
        if page_count > max_pages:
            raise ResumeParseError(f"PDF has {page_count} pages (limit {max_pages}); this does not look like a resume.")

        page_texts = [doc[i].get_text("text") or "" for i in range(page_count)]
        weak = [i for i, t in enumerate(page_texts) if len(t.strip()) < min_chars_per_page]
        warnings: List[str] = []
        method, confidence = "text", None

        if weak:
            if not ocr_enabled:
                warnings.append(f"{len(weak)} page(s) have little or no text and OCR is disabled.")
            else:
                targets = weak[:ocr_max_pages]
                if len(weak) > len(targets):
                    warnings.append(f"OCR limited to the first {ocr_max_pages} scanned pages.")
                try:
                    ocr_texts, confidence = ocr_service.ocr_pages(doc, targets, ocr_dpi, tesseract_cmd)
                    for idx, txt in ocr_texts.items():
                        page_texts[idx] = (page_texts[idx] + "\n" + txt).strip()
                    method = "ocr" if len(targets) == page_count else "mixed"
                    if confidence is None:
                        warnings.append("OCR ran but returned no confidence values.")
                except ocr_service.OCRUnavailable as exc:
                    warnings.append(f"Scanned page(s) detected but OCR unavailable: {exc}")
                except Exception as exc:  # pytesseract / Pillow errors
                    warnings.append(f"OCR failed: {exc}")

        text = normalize_text("\n\n".join(page_texts))
        if not text:
            raise ResumeParseError("No text could be extracted (scanned PDF and OCR unavailable or failed). "
                                   + " ".join(warnings))
        if len(text) < 100:
            warnings.append("Very little text was extracted; results may be incomplete.")
        return ExtractionResult(text=text, page_count=page_count, method=method,
                                ocr_confidence=confidence, warnings=warnings)
    finally:
        doc.close()


def parse_fields(text: str) -> dict:
    """Extract contact details, education and experience from normalised text."""
    edu = extract_education(text)
    exp = extract_experience(text)
    return {
        "name": extract_name(text),
        "email": extract_email(text),
        "phone": extract_phone(text),
        "education": edu["text"] if edu else None,
        "education_level": edu["level"] if edu else 0,
        "experience_years": exp["years"] if exp else None,
        "experience_method": exp["method"] if exp else None,
    }
