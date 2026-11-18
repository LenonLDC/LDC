import tempfile
import unittest
from pathlib import Path

from pdm_assistant.catalog import read_pd_catalog


class CatalogTests(unittest.TestCase):
    def test_reads_pd_from_column_b_and_type_from_column_c_in_html_export(self) -> None:
        content = """<div><table>
        <tr><th>Tipo PD - PORTUGUÊS</th><th>PD</th><th>Título - PORTUGUÊS</th></tr>
        <tr><td>Material</td><td>TFCR</td><td>TRANSFORMADOR DE CORRENTE</td></tr>
        </table></div>"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "consultapds.xls"
            path.write_text(content, encoding="utf-8")

            catalog = read_pd_catalog(path)

        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[0].code, "TFCR")
        self.assertEqual(catalog[0].material_type, "TRANSFORMADOR DE CORRENTE")
        self.assertEqual(catalog[0].source_rows, (2,))

    def test_rejects_unexpected_column_headers(self) -> None:
        content = """<table>
        <tr><th>Wrong</th><th>Code</th><th>Description</th></tr>
        <tr><td>Material</td><td>TFCR</td><td>TRANSFORMADOR</td></tr>
        </table>"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.xls"
            path.write_text(content, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Unexpected catalog headers"):
                read_pd_catalog(path)


if __name__ == "__main__":
    unittest.main()
