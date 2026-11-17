from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

import pymupdf


@dataclass(frozen=True)
class MaterialDescription:
    value: str
    page: int
    evidence: str
    method: str
    max_voltage_kv: float | None = None
    voltage_page: int | None = None
    voltage_evidence: str | None = None


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).upper()


def _clean_line(value: str) -> str:
    value = value.replace("|", " ").strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"^\d+(?:\.\d+)*\s*", "", value)
    return value.strip(" :;-")


def _find_title(lines: list[str]) -> tuple[str, str] | None:
    for index, line in enumerate(lines):
        if "TABELA DE DADOS TECNICOS GARANTIDOS" not in _fold(line):
            continue

        inline_parts = [part.strip() for part in line.split("|") if part.strip()]
        if len(inline_parts) > 1:
            title = _clean_line(inline_parts[-1])
            if title and "TABELA DE DADOS" not in _fold(title):
                return title, line.strip()

        for following in lines[index + 1 : index + 5]:
            title = _clean_line(following)
            normalized = _fold(title)
            if not title:
                continue
            if any(
                marker in normalized
                for marker in (
                    "TABELA DE DADOS",
                    "IDENTIFICACAO DA PROPOSTA",
                    "NOME DO PROJETO",
                    "NUMERO DA PROPOSTA",
                    "CONDICOES DE SERVICO",
                    "CARACTERISTICAS TECNICAS",
                )
            ):
                break
            if normalized.isdigit():
                continue
            if len(re.findall(r"[A-Z0-9]+", normalized)) >= 2:
                return title, following.strip()
    return None


def _extract_max_voltage(pages: list[str]) -> tuple[float | None, int | None, str | None]:
    for page_number, text in enumerate(pages, start=1):
        lines = text.splitlines()
        for index, line in enumerate(lines):
            normalized = _fold(line)
            if "TENSAO MAXIMA" not in normalized or "KV" not in normalized:
                continue
            for following in lines[index + 1 : index + 4]:
                match = re.fullmatch(r"\s*(\d+(?:[,.]\d+)?)\s*(?:KV)?\s*", following, re.I)
                if match:
                    value = float(match.group(1).replace(",", "."))
                    return value, page_number, f"{line.strip()} {match.group(1)} kV"
    return None, None, None


def _filename_title(source: Path) -> str:
    stem = re.sub(
        r"^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}-",
        "",
        source.stem,
        flags=re.IGNORECASE,
    )
    return re.split(r"\s+-\s+", stem, maxsplit=1)[0].strip()


def extract_material_description(
    pdf_path: str | Path, manual_description: str | None = None
) -> MaterialDescription:
    """Extract a material title from a common technical-sheet heading or use an override."""
    source = Path(pdf_path)
    if source.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf technical sheet, got: {source.suffix or '(no extension)'}")
    if not source.is_file():
        raise FileNotFoundError(f"Technical sheet not found: {source}")

    with pymupdf.open(source) as document:
        if document.page_count == 0:
            raise ValueError("The technical sheet has no pages.")

        pages = [document[index].get_text("text") for index in range(min(6, document.page_count))]
        max_voltage, voltage_page, voltage_evidence = _extract_max_voltage(pages)
        for page_number, text in enumerate(pages[:3], start=1):
            found = _find_title(text.splitlines())
            if found:
                extracted, evidence = found
                if manual_description and manual_description.strip():
                    return MaterialDescription(
                        value=manual_description.strip(),
                        page=page_number,
                        evidence=evidence,
                        method="manual_override",
                        max_voltage_kv=max_voltage,
                        voltage_page=voltage_page,
                        voltage_evidence=voltage_evidence,
                    )
                return MaterialDescription(
                    value=extracted,
                    page=page_number,
                    evidence=evidence,
                    method="technical_sheet_heading",
                    max_voltage_kv=max_voltage,
                    voltage_page=voltage_page,
                    voltage_evidence=voltage_evidence,
                )

        if manual_description and manual_description.strip():
            return MaterialDescription(
                value=manual_description.strip(),
                page=1,
                evidence=pages[0][:500].strip(),
                method="manual_override",
                max_voltage_kv=max_voltage,
                voltage_page=voltage_page,
                voltage_evidence=voltage_evidence,
            )

        filename_title = _filename_title(source)
        if len(re.findall(r"[A-Z0-9]+", _fold(filename_title))) >= 2:
            return MaterialDescription(
                value=filename_title,
                page=1,
                evidence=f"PDF filename: {source.name}",
                method="filename",
                max_voltage_kv=max_voltage,
                voltage_page=voltage_page,
                voltage_evidence=voltage_evidence,
            )

    raise ValueError(
        "Could not identify the material title in the PDF or its filename. "
        "Review the sheet and pass --material-description."
    )
