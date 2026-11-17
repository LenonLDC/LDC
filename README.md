# Assistente de consulta de PD

Protótipo local para ler uma ficha técnica em PDF, consultar a planilha `consultapds.xls` e apresentar os PDs mais compatíveis para revisão humana.

## Regras aplicadas

- Coluna **B** da planilha: código do PD.
- Coluna **C**: título/tipo do material usado para a busca.
- O cabeçalho é validado antes da leitura para evitar consultar colunas erradas.
- O leitor aceita `.xls` binário e a exportação HTML do portal que também usa a extensão `.xls`.
- O número da linha da planilha é incluído como referência.
- A pontuação é apenas uma ordem de similaridade lexical, não é probabilidade nem aprovação.
- O protótipo não acessa SBS/Astrein, não guarda credenciais e não envia cadastros. O PD e os campos devem ser confirmados antes de qualquer envio.

O nome do material é extraído do cabeçalho “Tabela de Dados Técnicos Garantidos” quando o título está disponível no texto do PDF. Se não estiver, o protótipo tenta o início do nome do arquivo (ignorando o identificador do anexo). Para outros formatos, informe `--material-description` após conferir a ficha. Valores de tensão máxima explicitamente rotulados no PDF também são usados para favorecer ou penalizar tipos de PD que tragam limites de tensão no título.

## Instalação no Windows

No PowerShell, na pasta do projeto:

```powershell
python -m pip install -e .
```

## Executar com os anexos atuais

```powershell
python -m pdm_assistant `
  --catalog "C:\Users\grassl\.copilot\workspaces\bcb869d0-469e-4427-8ea5-0874c3388779\attachments\e6f8efe1-1eb7-4c23-92a8-2834362b3ccc-consultapds.xls" `
  --pdf "C:\Users\grassl\.copilot\workspaces\bcb869d0-469e-4427-8ea5-0874c3388779\attachments\c5f2641a-5714-4fe9-a04f-909a4d7f3a59-TRANSFORMADOR DE CORRENTE  - Dados técnicos garantidos Balteau - Português.pdf"
```

Se a extração automática não encontrar o tipo, forneça-o explicitamente:

```powershell
python -m pdm_assistant --catalog "C:\caminho\consultapds.xls" --pdf "C:\caminho\ficha.pdf" --material-description "TRANSFORMADOR DE CORRENTE"
```

Para integração com outras etapas, use `--json`. A saída inclui a descrição pesquisada, evidência do PDF, candidatos, códigos PD e linhas de origem.

## Testes

```powershell
python -m unittest discover -s tests -v
```

## Próxima etapa para automação assistida

Depois de validar a qualidade das sugestões em fichas reais, conectar o processo ao SBS/Astrein por API oficial, se disponível; caso contrário, usar RPA autorizado com seletores estáveis. A primeira versão dessa integração deve preparar o formulário e aguardar confirmação humana. Acesso à rede corporativa, autenticação autorizada, regras de aprovação e mapeamento dos campos de tela ainda precisam ser configurados no ambiente LDC.
