from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

import streamlit as st

from pdm_assistant.catalog import read_pd_catalog
from pdm_assistant.document import (
    extract_all_pdf_text,
    extract_material_description,
)
from pdm_assistant.matcher import rank_candidates
from pdm_assistant.providers import (
    extract_fields_with_azure_openai,
    extract_layout_with_azure,
)


st.set_page_config(
    page_title="Assistente de cadastro de materiais | LDC",
    page_icon=":material/inventory_2:",
    layout="wide",
)


def _environment_value(name: str) -> str:
    return os.environ.get(name, "").strip()


def _write_temp_file(content: bytes, suffix: str) -> Path:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary_file:
        temporary_file.write(content)
        return Path(temporary_file.name)


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _initial_field_value(field: str, extracted_fields: dict | None) -> str:
    if extracted_fields and extracted_fields.get(field) is not None:
        value = extracted_fields[field]
        if field == "urgency":
            return {"yes": "Sim", "no": "Não", "unclear": "Não confirmado"}.get(
                str(value), ""
            )
        return str(value)
    return ""


def _format_candidate(candidate) -> str:
    return (
        f"{candidate.code} | {candidate.material_type} "
        f"| tensão: {candidate.voltage_compatibility}"
    )


if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "draft_json" not in st.session_state:
    st.session_state.draft_json = None

with st.sidebar:
    st.title("LDC")
    st.caption("Assistente de cadastro de materiais")
    st.header("Referência de PD")
    catalog_upload = st.file_uploader(
        "Planilha de consulta de PDs (.xls)",
        type=["xls"],
        help="Código do PD na coluna B e tipo/título do material na coluna C.",
        key="catalog_upload",
    )
    st.divider()
    st.header("Dados do chamado SBS")
    request_number = st.text_input("Número da solicitação", key="request_number")
    requester = st.text_input("Requerente", key="requester")
    requester_email = st.text_input(
        "E-mail pessoal",
        value="lenon.grassetti@ldc.com",
        key="requester_email",
    )
    company = st.selectbox("Empresa", ["1037 - LDC Sucos"], key="company")
    cost_center = st.text_input("Centro de custo (Centro2)", key="cost_center")
    st.divider()
    st.subheader("APIs opcionais")
    st.caption(
        "As chamadas externas ficam desativadas por padrão. O arquivo só é enviado "
        "ao Azure se você marcar a opção correspondente antes de analisar."
    )
    di_configured = bool(
        _environment_value("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        and _environment_value("AZURE_DOCUMENT_INTELLIGENCE_KEY")
    )
    openai_configured = bool(
        _environment_value("AZURE_OPENAI_ENDPOINT")
        and _environment_value("AZURE_OPENAI_API_KEY")
        and _environment_value("AZURE_OPENAI_DEPLOYMENT")
    )
    st.caption(
        f"Document Intelligence: {'configurado' if di_configured else 'não configurado'}"
    )
    st.caption(f"Azure OpenAI: {'configurado' if openai_configured else 'não configurado'}")
    st.markdown(
        "[Document Intelligence Layout](https://learn.microsoft.com/azure/ai-services/"
        "document-intelligence/prebuilt/layout) · "
        "[Structured Outputs](https://learn.microsoft.com/azure/ai-services/openai/"
        "how-to/structured-outputs)"
    )

st.title("Assistente de cadastro de materiais")
st.write(
    "Carregue a ficha técnica e a referência de PD para preparar uma sugestão revisável. "
    "Esta versão não acessa SBS/Astrein nem envia o cadastro."
)

pdf_upload = st.file_uploader(
    "Ficha técnica em PDF",
    type=["pdf"],
    help="PDF com texto ou digitalizado. A opção local não faz OCR de páginas digitalizadas.",
    key="pdf_upload",
)
material_override = st.text_input(
    "Tipo do material (opcional, para orientar a busca)",
    placeholder="Ex.: transformador de corrente",
    key="material_override",
)

cloud_col1, cloud_col2 = st.columns(2)
with cloud_col1:
    use_document_intelligence = st.checkbox(
        "Enviar PDF ao Azure Document Intelligence para OCR/layout",
        disabled=not di_configured,
        key="use_document_intelligence",
    )
with cloud_col2:
    use_azure_openai = st.checkbox(
        "Enviar texto ao Azure OpenAI para extrair campos",
        disabled=not openai_configured,
        key="use_azure_openai",
    )

if use_document_intelligence or use_azure_openai:
    st.warning(
        "Ao analisar, o PDF e/ou o texto extraído será enviado à instância Azure "
        "configurada pela organização. Confirme a classificação e as regras internas "
        "de tratamento antes de prosseguir."
    )

analyze_clicked = st.button(
    "Analisar ficha e sugerir PD",
    type="primary",
    icon=":material/search:",
    disabled=not (catalog_upload and pdf_upload),
)

if analyze_clicked:
    pdf_temp = _write_temp_file(pdf_upload.getvalue(), ".pdf")
    catalog_temp = _write_temp_file(catalog_upload.getvalue(), ".xls")
    try:
        with st.spinner("Lendo o documento e consultando a referência de PD..."):
            catalog = read_pd_catalog(catalog_temp)
            local_text, page_count, text_page_count = extract_all_pdf_text(pdf_temp)
            document_text = local_text
            extraction_method = "Texto local do PDF"

            if use_document_intelligence:
                document_text, page_count, text_page_count = extract_layout_with_azure(
                    pdf_upload.getvalue(),
                    _environment_value("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"),
                    _environment_value("AZURE_DOCUMENT_INTELLIGENCE_KEY"),
                )
                extraction_method = "Azure Document Intelligence prebuilt-layout"

            extracted_fields = None
            if use_azure_openai:
                extracted_fields = extract_fields_with_azure_openai(
                    document_text,
                    _environment_value("AZURE_OPENAI_ENDPOINT"),
                    _environment_value("AZURE_OPENAI_API_KEY"),
                    _environment_value("AZURE_OPENAI_DEPLOYMENT"),
                )

            requested_type = material_override.strip()
            if not requested_type and extracted_fields:
                requested_type = str(extracted_fields.get("material_type") or "").strip()

            material = extract_material_description(
                pdf_temp,
                requested_type or None,
                extracted_text=document_text if use_document_intelligence else None,
                filename_hint=pdf_upload.name,
            )

            # Keep the more complete OCR text when the cloud layout model was selected.
            if use_document_intelligence:
                full_text = document_text
            else:
                full_text = local_text

            candidates = rank_candidates(
                material.value,
                catalog,
                limit=10,
                max_voltage_kv=material.max_voltage_kv,
            )
            for widget_key in (
                "selected_pd",
                "document_text_preview",
                "draft_sap_code",
                "draft_unit",
                "draft_quantity",
                "draft_urgency",
                "draft_description",
            ):
                st.session_state.pop(widget_key, None)
            st.session_state.analysis = {
                "material": material,
                "candidates": candidates,
                "document_text": full_text,
                "page_count": page_count,
                "text_page_count": text_page_count,
                "extraction_method": extraction_method,
                "catalog_entries": len(catalog),
                "extracted_fields": extracted_fields,
                "pdf_name": pdf_upload.name,
            }
            st.session_state.draft_json = None
    except (OSError, ValueError, RuntimeError, TimeoutError) as error:
        st.error(f"Não foi possível concluir a análise: {error}")
    finally:
        _safe_unlink(pdf_temp)
        _safe_unlink(catalog_temp)

analysis = st.session_state.analysis
if analysis:
    st.divider()
    st.header("Resultado da análise")
    st.caption(
        f"Arquivo: {analysis['pdf_name']} · "
        f"Extração: {analysis['extraction_method']} · "
        f"{analysis['page_count']} página(s), "
        f"{analysis['text_page_count']} com texto detectável · "
        f"{analysis['catalog_entries']} referências PD/tipo"
    )
    if analysis["text_page_count"] < analysis["page_count"]:
        st.warning(
            "Algumas páginas não têm texto extraível. Para analisá-las, configure e "
            "selecione Azure Document Intelligence ou informe/revise os campos manualmente."
        )

    extracted_fields = analysis["extracted_fields"]
    if extracted_fields:
        st.subheader("Campos extraídos pela IA (não confirmados)")
        st.caption(
            "Revise todos os valores. A IA não escolhe o PD e pode não encontrar "
            "campos em documentos com layout diferente."
        )
        if extracted_fields["evidence"]:
            evidence_rows = [
                {
                    "Campo": item["field"],
                    "Trecho citado": item["quote"],
                    "Página": item["page"],
                    "Trecho conferido no texto": (
                        "Sim" if item.get("evidence_verified") else "Não"
                    ),
                }
                for item in extracted_fields["evidence"]
            ]
            st.dataframe(
                evidence_rows,
                hide_index=True,
                alt="Campos sugeridos pela IA e trechos de evidência extraídos do PDF",
            )

    st.subheader("Sugestão de PD")
    if analysis["candidates"]:
        candidate_labels = [_format_candidate(item) for item in analysis["candidates"]]
        selected_label = st.selectbox(
            "Selecione o PD após conferir o tipo e a tensão",
            candidate_labels,
            key="selected_pd",
        )
        selected_candidate = analysis["candidates"][candidate_labels.index(selected_label)]
        st.caption(
            f"Tipo extraído para a busca: {analysis['material'].value}. "
            f"Evidência: {analysis['material'].evidence}"
        )
        st.dataframe(
            [
                {
                    "PD": candidate.code,
                    "Tipo na coluna C": candidate.material_type,
                    "Similaridade lexical": round(candidate.lexical_score, 3),
                    "Compatibilidade de tensão": candidate.voltage_compatibility,
                    "Linha da planilha": ", ".join(
                        str(row) for row in candidate.source_rows
                    ),
                }
                for candidate in analysis["candidates"]
            ],
            hide_index=True,
            alt="Candidatos a código PD, tipo de material, compatibilidade e linha da planilha",
        )
    else:
        selected_candidate = None
        st.warning(
            "Nenhum candidato compartilhou termos com o tipo identificado. "
            "Informe um tipo mais específico e rode a análise novamente."
        )

    with st.expander("Texto extraído da ficha técnica"):
        st.text_area(
            "Texto por página",
            value=analysis["document_text"],
            height=320,
            key="document_text_preview",
        )

    st.subheader("Revisar campos do cadastro")
    fields_col1, fields_col2 = st.columns(2)
    with fields_col1:
        sap_code = st.text_input(
            "Código SAP",
            value=_initial_field_value("sap_code", extracted_fields),
            key="draft_sap_code",
        )
        unit = st.text_input(
            "Unidade de medida",
            value=_initial_field_value("unit_of_measure", extracted_fields),
            key="draft_unit",
        )
        quantity = st.text_input(
            "Quantidade de linhas na planilha",
            value=_initial_field_value("quantity_rows", extracted_fields),
            key="draft_quantity",
        )
    with fields_col2:
        urgency_options = ["Não confirmado", "Não", "Sim"]
        urgency_default = _initial_field_value("urgency", extracted_fields)
        urgency_index = (
            urgency_options.index(urgency_default)
            if urgency_default in urgency_options
            else 0
        )
        urgency = st.selectbox(
            "Urgência",
            urgency_options,
            index=urgency_index,
            key="draft_urgency",
        )
        description = st.text_area(
            "Descrição do material",
            value=_initial_field_value("description", extracted_fields),
            key="draft_description",
        )

    if st.button(
        "Preparar rascunho para conferência",
        icon=":material/draft:",
        disabled=selected_candidate is None,
    ):
        if not requester.strip() or not requester_email.strip() or not cost_center.strip():
            st.error("Preencha Requerente, e-mail e Centro de custo antes de preparar o rascunho.")
        elif not description.strip():
            st.error("Preencha e confirme a descrição do material.")
        else:
            st.session_state.draft_json = {
                "sbs_request_number": request_number.strip() or None,
                "requester": requester.strip(),
                "requester_email": requester_email.strip(),
                "company": "1037",
                "cost_center": cost_center.strip(),
                "material_type_for_pd_search": analysis["material"].value,
                "pd": selected_candidate.code,
                "pd_catalog_type": selected_candidate.material_type,
                "pd_catalog_rows": list(selected_candidate.source_rows),
                "sap_code": sap_code.strip() or None,
                "unit_of_measure": unit.strip() or None,
                "quantity_rows": quantity.strip() or None,
                "urgency": urgency,
                "description": description.strip(),
                "technical_sheet": analysis["pdf_name"],
                "document_extraction": analysis["extraction_method"],
                "human_review_required": True,
                "submitted_to_astrein": False,
            }

    if st.session_state.draft_json:
        st.success("Rascunho preparado. Nada foi enviado à Astrein.")
        st.json(st.session_state.draft_json)
        st.download_button(
            "Baixar rascunho JSON",
            data=json.dumps(
                st.session_state.draft_json,
                ensure_ascii=False,
                indent=2,
            ),
            file_name="rascunho_cadastro_material.json",
            mime="application/json",
            icon=":material/download:",
        )
