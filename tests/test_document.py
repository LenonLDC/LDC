import tempfile
import unittest
from pathlib import Path

import pymupdf

from pdm_assistant.document import extract_material_description


class DocumentTests(unittest.TestCase):
    def test_extracts_material_from_technical_sheet_heading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "technical-sheet.pdf"
            document = pymupdf.open()
            page = document.new_page()
            page.insert_text(
                (72, 72),
                "TABELA DE DADOS TECNICOS GARANTIDOS\n"
                "TRANSFORMADOR DE CORRENTE\n"
                "Identificacao da Proposta",
            )
            document.save(pdf_path)
            document.close()

            result = extract_material_description(pdf_path)

        self.assertEqual(result.value, "TRANSFORMADOR DE CORRENTE")
        self.assertEqual(result.page, 1)
        self.assertEqual(result.method, "technical_sheet_heading")

    def test_manual_description_overrides_extracted_heading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "technical-sheet.pdf"
            document = pymupdf.open()
            page = document.new_page()
            page.insert_text(
                (72, 72),
                "TABELA DE DADOS TECNICOS GARANTIDOS\n"
                "TRANSFORMADOR DE CORRENTE",
            )
            document.save(pdf_path)
            document.close()

            result = extract_material_description(pdf_path, "TRANSFORMADOR DE INSTRUMENTO")

        self.assertEqual(result.value, "TRANSFORMADOR DE INSTRUMENTO")
        self.assertEqual(result.method, "manual_override")

    def test_uses_filename_when_pdf_does_not_expose_a_material_heading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / (
                "c5f2641a-5714-4fe9-a04f-909a4d7f3a59-"
                "TRANSFORMADOR DE CORRENTE - Dados técnicos.pdf"
            )
            document = pymupdf.open()
            document.new_page().insert_text((72, 72), "Nome do Projeto:\nLDC")
            document.save(pdf_path)
            document.close()

            result = extract_material_description(pdf_path)

        self.assertEqual(result.value, "TRANSFORMADOR DE CORRENTE")
        self.assertEqual(result.method, "filename")

    def test_extracts_max_voltage_from_technical_label_and_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "technical-sheet.pdf"
            document = pymupdf.open()
            page = document.new_page()
            page.insert_text(
                (72, 72),
                "Tensão Máxima (fase-fase) [kV]\n145",
            )
            document.save(pdf_path)
            document.close()

            result = extract_material_description(
                pdf_path, "TRANSFORMADOR DE CORRENTE"
            )

        self.assertEqual(result.max_voltage_kv, 145)
        self.assertIn("145 kV", result.voltage_evidence)


if __name__ == "__main__":
    unittest.main()
