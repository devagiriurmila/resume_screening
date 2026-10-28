"""OCR for scanned PDF pages using Tesseract (via pytesseract). Fully local, no API keys."""
import os
import shutil
from typing import List, Optional, Tuple

try:
    import pymupdf as fitz  # PyMuPDF >= 1.24.3
except ImportError:
    import fitz  # older PyMuPDF releases

import pytesseract
from PIL import Image
import io

WINDOWS_DEFAULTS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


class OCRUnavailable(RuntimeError):
    pass


def configure(tesseract_cmd: str = "") -> Optional[str]:
    """Point pytesseract at the executable. Returns the path used, or None if not found."""
    candidates = [tesseract_cmd] if tesseract_cmd else []
    candidates += [shutil.which("tesseract") or ""] + WINDOWS_DEFAULTS
    for cand in candidates:
        if cand and os.path.isfile(cand):
            pytesseract.pytesseract.tesseract_cmd = cand
            return cand
    return None


def is_available(tesseract_cmd: str = "") -> bool:
    if configure(tesseract_cmd) is None:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def ocr_pages(doc, page_indexes: List[int], dpi: int = 200, tesseract_cmd: str = "") -> Tuple[dict, Optional[float]]:
    """OCR the given page indexes. Returns ({index: text}, mean_confidence_or_None)."""
    if not is_available(tesseract_cmd):
        raise OCRUnavailable("Tesseract OCR was not found. Install it and set TESSERACT_CMD in .env.")
    texts, confs = {}, []
    zoom = dpi / 72.0
    for idx in page_indexes:
        pix = doc[idx].get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csGRAY)
        image = Image.open(io.BytesIO(pix.tobytes("png")))
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        words, lines = [], {}
        for i, word in enumerate(data["text"]):
            word = (word or "").strip()
            if not word:
                continue
            try:
                conf = float(data["conf"][i])
            except (TypeError, ValueError):
                conf = -1
            if conf >= 0:
                confs.append(conf)
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, []).append(word)
            words.append(word)
        texts[idx] = "\n".join(" ".join(ws) for _k, ws in sorted(lines.items()))
    return texts, (round(sum(confs) / len(confs), 1) if confs else None)
