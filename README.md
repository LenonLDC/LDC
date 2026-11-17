# Assistente LDC para cadastro de materiais

Aplicação local para revisar uma solicitação SBS, analisar uma ficha técnica em PDF, consultar a referência `consultapds.xls` e preparar um rascunho de cadastro para revisão humana.

## Regras aplicadas

- Coluna **B** da planilha: código do PD.
- Coluna **C**: título/tipo do material usado para a busca.
- O cabeçalho é validado antes da leitura para evitar consultar colunas erradas.
- O leitor aceita `.xls` binário e a exportação HTML do portal que também usa a extensão `.xls`.
- O número da linha da planilha é incluído como referência.
- A similaridade lexical e os limites de tensão ajudam a ordenar os candidatos; não são probabilidade nem aprovação.
- A interface não acessa SBS/Astrein, não guarda credenciais e não envia cadastros. Campos extraídos e o PD precisam ser confirmados por uma pessoa.

O leitor local percorre as páginas do PDF e tenta extrair o título e a tensão máxima. Tipos de documento distintos podem exigir conferência ou a descrição manual. PDF digitalizado precisa de OCR.

## Instalação no Windows

No PowerShell, na pasta do projeto:

```powershell
python -m pip install -e .
```

## Abrir a interface

```powershell
python -m streamlit run streamlit_app.py
```

Na tela, carregue a planilha de referência e o PDF, preencha os dados do SBS e execute a análise. Revise candidatos, campos e evidências; então prepare e baixe um JSON de rascunho. Esse arquivo é uma saída para conferência e não é uma planilha de importação oficial da Astrein.

## APIs recomendadas

- **Azure AI Document Intelligence, modelo `prebuilt-layout`**: OCR e estrutura (texto, tabelas e linhas com página) para PDFs variados e digitalizados.
- **Azure OpenAI com Structured Outputs**: transformar o texto extraído em campos JSON controlados, exigindo trecho de evidência por campo e usando `null` quando o documento não fornece um valor. O modelo não escolhe nem inventa o PD; a planilha continua sendo a referência.
- **Consulta PD local**: comparar a descrição confirmada com colunas B/C da planilha e usar limites de tensão encontrados no título como filtro auxiliar.

As APIs Azure são opcionais e ficam desligadas por padrão. Para habilitá-las no protótipo, configure as variáveis de ambiente no processo que inicia o Streamlit:

```powershell
$env:AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT = "https://<recurso>.cognitiveservices.azure.com"
$env:AZURE_DOCUMENT_INTELLIGENCE_KEY = "<segredo>"
$env:AZURE_OPENAI_ENDPOINT = "https://<recurso>.openai.azure.com"
$env:AZURE_OPENAI_API_KEY = "<segredo>"
$env:AZURE_OPENAI_DEPLOYMENT = "<deployment-com-structured-outputs>"
python -m streamlit run streamlit_app.py
```

O envio do PDF ao Document Intelligence e do texto ao Azure OpenAI exige marcar as opções correspondentes na interface. Antes de usar documentos reais, a LDC deve aprovar região, privacidade, retenção, rede e custos. Para produção, prefira Microsoft Entra ID com identidade gerenciada e cofre corporativo a chaves de API. A autenticação do protótipo via variáveis de ambiente destina-se apenas à validação.

Documentação: [Document Intelligence layout](https://learn.microsoft.com/azure/ai-services/document-intelligence/prebuilt/layout) e [Structured Outputs no Azure OpenAI](https://learn.microsoft.com/azure/ai-services/openai/how-to/structured-outputs).

## CLI

A versão de linha de comando segue disponível:

```powershell
python -m pdm_assistant --catalog "C:\caminho\consultapds.xls" --pdf "C:\caminho\ficha.pdf" --material-description "TRANSFORMADOR DE CORRENTE"
```

Use `--json` para saída estruturada.

## Testes

```powershell
python -m unittest discover -s tests -v
```

## Próxima etapa para integração

Depois de validar os resultados com documentos representativos, integrar ao SBS/Astrein por API oficial, se disponível; caso contrário, avaliar RPA aprovado pela equipe de TI usando seletores estáveis. Autenticação, acesso à rede, aprovação, mapeamento dos campos e validações de duplicidade precisam ser definidos no ambiente LDC. A confirmação humana antes do envio deve permanecer até que haja evidência suficiente de confiabilidade.
