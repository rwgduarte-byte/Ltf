# 🎲 Dashboard Lotofácil

Dashboard interativo para análise, geração e gerenciamento de concursos da **Lotofácil**, construído com **Python + Streamlit** e banco de dados **SQLite**.

## ✨ Funcionalidades

- **Cadastrar Concurso** — cadastro manual de novos sorteios ou importação em massa via arquivo Excel (.xlsx) com a aba `LOTOFÁCIL`.
- **Gerar Jogos** — geração de jogos com filtros inteligentes:
  - Repetição de dezenas do último concurso
  - Quantidade de dezenas pares e primas
  - Frequência histórica (dezenas mais sorteadas com mais peso)
  - Robustez (jogos que fariam 11+ pontos nos últimos 20 concursos)
  - Dezenas atrasadas (ciclo de atraso)
  - Ciclo fechado das 25 dezenas
- **Editar Concurso** — correção de dados de sorteios já cadastrados.
- **Análise de Dados** — frequência das dezenas, tendência recente, ciclo de atraso, ciclos fechados, evolução de pares/ímpares, soma e repetições entre concursos.

## 🛠️ Tecnologias

- **Python 3.12**
- **Streamlit** 1.41.1
- **Pandas** 2.2.3
- **SQLite** (arquivo `data/lotofacil.db`)
- **Openpyxl** (leitura de Excel)

## 📁 Estrutura do Projeto
```
ltf/
├── app.py              # Código principal do dashboard
├── requirements.txt    # Dependências
├── runtime.txt         # Versão do Python (3.12)
├── data/
│   └── lotofacil.db    # Banco de dados SQLite
└── outputs/            # Jogos exportados (gerado automaticamente)
```

## 🚀 Como rodar localmente

**Pré-requisitos:** Python 3.12 instalado.

1. Clone o repositório e entre na pasta:
```bash
   git clone https://github.com/rwgduarte/ltf.git
   cd ltf
```

2. Instale as dependências:
```bash
   pip install -r requirements.txt
```

3. Rode o app:
```bash
   streamlit run app.py
```

4. Abra no navegador: `http://localhost:8501`

## ☁️ Deploy no Streamlit Cloud

1. Acesse [share.streamlit.io](https://share.streamlit.io) e faça login com o GitHub.
2. Clique em **New app**.
3. Preencha:
   - **Repository:** `rwgduarte/ltf`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Em **Advanced settings**, selecione **Python 3.12**.
5. Clique em **Deploy**.

O app fica disponível em: **https://rwgduarte.streamlit.app**

> O Streamlit Cloud faz o redeploy automaticamente sempre que você fizer um commit no repositório.

## 🔄 Como atualizar o banco de dados na nuvem

O Streamlit Cloud usa **armazenamento temporário**: dados cadastrados dentro do app na nuvem se perdem quando o app "dorme" ou reinicia. Para manter os dados atualizados, siga este fluxo:

### Passo 1 — Atualize o banco no seu PC
1. Rode o app localmente: `streamlit run app.py`.
2. Cadastre o novo concurso manualmente ou importe o Excel atualizado.
3. Feche o app (`Ctrl + C`).

### Passo 2 — Localize o arquivo atualizado
- O banco fica em: `data/lotofacil.db`.

### Passo 3 — Envie para o GitHub (substituindo o antigo)
1. No GitHub, entre em `rwgduarte/ltf` → pasta `data`.
2. Clique em **Add file → Upload files**.
3. Arraste o `lotofacil.db` do seu PC.
4. Confirme que vai **substituir** (o GitHub mostra "Replace").
5. Clique em **Commit changes**.

### Passo 4 — Aguarde a sincronização
- O Streamlit detecta a mudança e faz o redeploy sozinho (1–2 minutos).
- Abra o app e confira se o concurso novo aparece.

### Como conferir o banco antes de subir
No Prompt de Comando, dentro da pasta do projeto:
```bash
py -3 -c "import sqlite3; con = sqlite3.connect('data/lotofacil.db'); print(con.execute('SELECT MAX(concurso), COUNT(*) FROM concursos').fetchall())"
```
O resultado mostra o **último concurso** e o **total** — se o número for o sorteio mais recente, o banco está pronto.

## 📊 Estrutura da tabela `concursos`

| Coluna | Descrição |
|---|---|
| `concurso` | Número do concurso (chave primária) |
| `data` | Data do sorteio (AAAA-MM-DD) |
| `d1` a `d15` | As 15 dezenas sorteadas |

## ⚠️ Cuidados

- O arquivo deve manter o nome `lotofacil.db` e a pasta `data/`.
- Sempre envie o arquivo **do PC para o GitHub** (nunca o contrário).
- O app na nuvem serve apenas para **consulta**; cadastros feitos lá são voláteis.
- Feche o app e editores de banco antes de subir o arquivo.

## 📄 Licença

Projeto de uso pessoal.
