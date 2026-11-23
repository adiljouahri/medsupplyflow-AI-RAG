import csv
from pathlib import Path

from openpyxl import load_workbook
from PIL import Image
import pymupdf
import pytesseract


def parse_file(path: str | Path) -> list[dict[str, str]]:
    """Extract messy raw rows from CSV, Excel, TXT, or PDF sources."""
    source = Path(path)
    suffix = source.suffix.lower()

    if suffix == ".csv":
        return _parse_csv(source)
    if suffix == ".xlsx":
        return _parse_excel(source)
    if suffix in {".txt", ".text"}:
        return _parse_text(source)
    if suffix == ".pdf":
        return _parse_pdf(source)

    raise ValueError(f"unsupported source type: {suffix}")


def _parse_csv(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            cleaned = {
                (key or "").strip(): (value or "").strip()
                for key, value in row.items()
            }
            if any(cleaned.values()):
                rows.append(cleaned)
    return rows


def _parse_excel(path: Path) -> list[dict[str, str]]:
    workbook = load_workbook(path, data_only=True, read_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return []

    headers = [str(cell).strip() if cell is not None else "column" for cell in rows[0]]
    parsed: list[dict[str, str]] = []
    for row in rows[1:]:
        values = [str(cell).strip() if cell is not None else "" for cell in row]
        if any(values):
            parsed.append(dict(zip(headers, values)))
    return parsed


def _parse_text(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line:
            rows.append({"raw_text": line})
    return rows


def _parse_pdf(path: Path) -> list[dict[str, str]]:
    document = pymupdf.open(path)
    rows: list[dict[str, str]] = []

    for page in document:
        text = page.get_text("text")
        if not text.strip():
            pixmap = page.get_pixmap(dpi=200)
            image = Image.frombytes(
                "RGB", [pixmap.width, pixmap.height], pixmap.samples
            )
            text = pytesseract.image_to_string(image)

        for line in text.splitlines():
            line = line.strip()
            if line:
                rows.append({"raw_text": line})

    return rows
