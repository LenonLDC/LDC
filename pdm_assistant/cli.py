from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .catalog import read_pd_catalog
from .document import MaterialDescription, extract_material_description
from .matcher import rank_candidates
from .matcher import RankedPDCandidate


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Suggest PD codes from a technical PDF and the approved .xls reference."
    )
    parser.add_argument("--catalog", required=True, help="Path to consultapds.xls")
    parser.add_argument("--pdf", required=True, help="Path to the material technical sheet")
    parser.add_argument(
        "--material-description",
        help="Reviewed material type to use instead of relying only on the PDF heading",
    )
    parser.add_argument("--top", type=int, default=5, help="Number of candidates to show")
    parser.add_argument("--json", action="store_true", help="Write machine-readable JSON")
    return parser


def _result_payload(
    catalog_path: str,
    pdf_path: str,
    material: MaterialDescription,
    candidates: list[RankedPDCandidate],
    valid_catalog_entries: int,
) -> dict[str, object]:
    return {
        "catalog": {
            "file": str(Path(catalog_path)),
            "pd_column": "B",
            "material_type_column": "C",
            "unique_pairs_read": valid_catalog_entries,
        },
        "technical_sheet": {
            "file": str(Path(pdf_path)),
            "material_type": material.value,
            "extraction_method": material.method,
            "evidence": {"page": material.page, "text": material.evidence},
            "max_voltage_kv": material.max_voltage_kv,
            "voltage_evidence": (
                {"page": material.voltage_page, "text": material.voltage_evidence}
                if material.voltage_evidence
                else None
            ),
        },
        "candidates": [
            {
                "rank": rank,
                "pd": candidate.code,
                "material_type": candidate.material_type,
                "ranking_score": round(candidate.score, 4),
                "lexical_score": round(candidate.lexical_score, 4),
                "voltage_compatibility": candidate.voltage_compatibility,
                "source_rows": list(candidate.source_rows),
            }
            for rank, candidate in enumerate(candidates, start=1)
        ],
        "score_note": (
            "Ranking combines lexical similarity and explicit voltage constraints in "
            "the catalog title; not a probability or approval."
        ),
        "review_required": True,
        "automatic_submission": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top must be at least 1.")

    try:
        material = extract_material_description(args.pdf, args.material_description)
        catalog = read_pd_catalog(args.catalog)
        candidates = rank_candidates(
            material.value,
            catalog,
            args.top,
            max_voltage_kv=material.max_voltage_kv,
        )
    except (OSError, ValueError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 2

    result = _result_payload(args.catalog, args.pdf, material, candidates, len(catalog))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"Material analisado: {material.value}")
    print(f"Origem: {material.method}; página {material.page}")
    print(f"Evidência: {material.evidence}")
    if material.max_voltage_kv is not None:
        print(
            f"Tensão máxima extraída: {material.max_voltage_kv:g} kV "
            f"({material.voltage_evidence})"
        )
    print(f"Referência consultada: {len(catalog)} pares PD/tipo válidos nas colunas B/C")
    if not candidates:
        print("Nenhum candidato compartilha termos com o tipo informado; revisão manual necessária.")
    else:
        print("\nCandidatos (pontuação lexical, não probabilidade):")
        for rank, candidate in enumerate(candidates, start=1):
            rows = ", ".join(str(row) for row in candidate.source_rows)
            print(
                f"{rank}. PD={candidate.code} | tipo={candidate.material_type} "
                f"| ranking={candidate.score:.3f} "
                f"| tensão={candidate.voltage_compatibility} | linha(s)={rows}"
            )
    print("\nRevisão humana obrigatória. Este protótipo não preenche nem envia cadastro.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
