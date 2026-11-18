from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
import re
import unicodedata

import xlrd
from xlrd.biffh import XLRDError


@dataclass(frozen=True)
class PDCatalogEntry:
    code: str
    material_type: str
    source_rows: tuple[int, ...]


class _HTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def _normalize_header(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]+", " ", ascii_text.upper()).strip()


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _entries_from_rows(rows: list[list[str]]) -> list[PDCatalogEntry]:
    if len(rows) < 2 or any(len(row) < 3 for row in rows[:2]):
        raise ValueError("The first worksheet/table must contain headers and columns B and C.")

    pd_header = _normalize_header(rows[0][1])
    type_header = _normalize_header(rows[0][2])
    if pd_header != "PD" or not type_header.startswith("TITULO"):
        raise ValueError(
            "Unexpected catalog headers: expected column B 'PD' and column C "
            f"'Título - Português'; found B={rows[0][1]!r}, C={rows[0][2]!r}."
        )

    entries: dict[tuple[str, str], list[int]] = {}
    for row_number, row in enumerate(rows[1:], start=2):
        if len(row) < 3:
            continue
        code = _cell_text(row[1])
        material_type = _cell_text(row[2])
        if code and material_type:
            entries.setdefault((code, material_type), []).append(row_number)

    if not entries:
        raise ValueError("No rows with both a PD code and material type were found.")

    return [
        PDCatalogEntry(code, material_type, tuple(source_rows))
        for (code, material_type), source_rows in entries.items()
    ]


def _read_html_table(source: Path) -> list[list[str]]:
    try:
        text = source.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("The HTML-exported catalog is not valid UTF-8.") from error

    parser = _HTMLTableParser()
    parser.feed(text)
    if not parser.rows:
        raise ValueError("The HTML-exported catalog contains no table rows.")
    return parser.rows


def _is_html_export(source: Path) -> bool:
    sample = source.read_bytes()[:512].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    return sample.startswith((b"<html", b"<!doctype", b"<div", b"<table"))


def read_pd_catalog(path: str | Path) -> list[PDCatalogEntry]:
    """Read PD from column B and material type from column C in XLS or HTML-exported XLS."""
    source = Path(path)
    if source.suffix.lower() != ".xls":
        raise ValueError(f"Expected an .xls catalog file, got: {source.suffix or '(no extension)'}")
    if not source.is_file():
        raise FileNotFoundError(f"PD catalog not found: {source}")

    if _is_html_export(source):
        return _entries_from_rows(_read_html_table(source))

    workbook = None
    try:
        workbook = xlrd.open_workbook(str(source), on_demand=True)
        if workbook.nsheets == 0:
            raise ValueError("The PD catalog contains no worksheets.")

        sheet = workbook.sheet_by_index(0)
        rows = [
            [_cell_text(sheet.cell_value(row, column)) for column in range(sheet.ncols)]
            for row in range(sheet.nrows)
        ]
        return _entries_from_rows(rows)
    except XLRDError as error:
        raise ValueError(f"Could not read the binary Excel catalog: {error}") from error
    finally:
        if workbook is not None:
            workbook.release_resources()
