import unittest

from pdm_assistant.catalog import PDCatalogEntry
from pdm_assistant.matcher import rank_candidates, similarity


class MatcherTests(unittest.TestCase):
    def test_exact_match_ignores_accents_and_stop_words(self) -> None:
        self.assertEqual(
            similarity("TRANSFORMADOR DE CORRENTE", "Transformador de Corrente"),
            1.0,
        )

    def test_different_material_type_has_lower_similarity(self) -> None:
        self.assertLess(
            similarity("TRANSFORMADOR DE CORRENTE", "TRANSFORMADOR DE POTENCIAL"),
            1.0,
        )

    def test_no_shared_terms_is_not_returned(self) -> None:
        catalog = [
            PDCatalogEntry("PD-1", "BOMBA CENTRIFUGA", (2,)),
        ]
        self.assertEqual(rank_candidates("TRANSFORMADOR DE CORRENTE", catalog), [])

    def test_ranked_results_include_catalog_source_rows(self) -> None:
        catalog = [
            PDCatalogEntry("PD-2", "TRANSFORMADOR DE POTENCIAL", (8,)),
            PDCatalogEntry("PD-1", "TRANSFORMADOR DE CORRENTE", (4, 5)),
        ]
        ranked = rank_candidates("TRANSFORMADOR DE CORRENTE", catalog)
        self.assertEqual(ranked[0].code, "PD-1")
        self.assertEqual(ranked[0].source_rows, (4, 5))

    def test_voltage_constraint_breaks_tie_between_catalog_types(self) -> None:
        catalog = [
            PDCatalogEntry(
                "TCRRE",
                "TRANSFORMADOR CORRENTE BAIXA TENSAO <=6KV",
                (2,),
            ),
            PDCatalogEntry(
                "TCORR1",
                "TRANSFORMADOR CORRENTE MT/AT >6KV",
                (3,),
            ),
        ]
        ranked = rank_candidates(
            "TRANSFORMADOR DE CORRENTE", catalog, max_voltage_kv=145
        )

        self.assertEqual(ranked[0].code, "TCORR1")
        self.assertEqual(ranked[0].voltage_compatibility, "compatible")
        self.assertEqual(ranked[1].voltage_compatibility, "incompatible")

    def test_limit_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            rank_candidates("MOTOR", [], 0)


if __name__ == "__main__":
    unittest.main()
