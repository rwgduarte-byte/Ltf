import streamlit as st
import pandas as pd
import sqlite3
import os
import random
from datetime import datetime, date
from dateutil import parser as dateparser
# =========================
# Configurações e Constantes
# =========================
DB_FOLDER = "data"
DB_FILE = os.path.join(DB_FOLDER, "lotofacil.db")
OUTPUT_FOLDER = "outputs"
EXCEL_SHEET_NAME = "LOTOFÁCIL"
PRIMES = [2, 3, 5, 7, 11, 13, 17, 19, 23]
# =========================
# Funções de Utilitário
# =========================
def setup_folders():
    os.makedirs(DB_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def get_conn():
    return sqlite3.connect(DB_FILE)

def create_table():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS concursos (
        concurso INTEGER PRIMARY KEY,
        data TEXT NOT NULL,
        d1 INTEGER, d2 INTEGER, d3 INTEGER, d4 INTEGER, d5 INTEGER,
        d6 INTEGER, d7 INTEGER, d8 INTEGER, d9 INTEGER, d10 INTEGER,
        d11 INTEGER, d12 INTEGER, d13 INTEGER, d14 INTEGER, d15 INTEGER
    )
    """)
    conn.commit()
    conn.close()

def create_jogos_table():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jogos_gerados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        concurso_alvo INTEGER,
        data_geracao TEXT NOT NULL,
        d1 INTEGER, d2 INTEGER, d3 INTEGER, d4 INTEGER, d5 INTEGER,
        d6 INTEGER, d7 INTEGER, d8 INTEGER, d9 INTEGER, d10 INTEGER,
        d11 INTEGER, d12 INTEGER, d13 INTEGER, d14 INTEGER, d15 INTEGER,
        pontos INTEGER,
        conferido INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()

def salvar_jogos_gerados(jogos, concurso_alvo=None):
    conn = get_conn()
    cursor = conn.cursor()
    data_geracao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for jogo in jogos:
        cursor.execute(
            "INSERT INTO jogos_gerados (concurso_alvo, data_geracao, d1,d2,d3,d4,d5,d6,d7,d8,d9,d10,d11,d12,d13,d14,d15, conferido) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)",
            (concurso_alvo, data_geracao, *jogo)
        )
    conn.commit()
    conn.close()

def conferir_jogos_pendentes(resultado_concurso, dezenas_resultado):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jogos_gerados WHERE conferido = 0")
    jogos = cursor.fetchall()
    atualizados = 0
    for jogo in jogos:
        jogo_id = jogo[0]
        dezenas_jogo = [jogo[i] for i in range(3, 18)]
        pontos = len(set(dezenas_jogo) & set(dezenas_resultado))
        cursor.execute("UPDATE jogos_gerados SET pontos=?, conferido=1, concurso_alvo=? WHERE id=?", (pontos, resultado_concurso, jogo_id))
        atualizados += 1
    conn.commit()
    conn.close()
    return atualizados

def get_aprendizado_dezenas():
    """Peso por dezena baseado no desempenho histórico dos jogos gerados (11+ pontos)."""
    conn = get_conn()
    try:
        df = pd.read_sql_query("SELECT * FROM jogos_gerados WHERE conferido=1 AND pontos IS NOT NULL", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    if df.empty:
        return None
    peso = {d: 0 for d in range(1, 26)}
    for _, row in df.iterrows():
        if row["pontos"] >= 11:
            for i in range(1, 16):
                peso[int(row[f"d{i}"])] += 1
    return peso

def calcular_ajuste_filtros():
    """Retorna ajuste de filtros baseado no desempenho dos últimos 16 palpites conferidos."""
    conn = get_conn()
    try:
        df = pd.read_sql_query(
            "SELECT pontos FROM jogos_gerados WHERE conferido=1 AND pontos IS NOT NULL ORDER BY id DESC LIMIT 16",
            conn
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    if df.empty:
        return {"robustez": 0, "atrasadas": 0, "rep_min": 0, "rep_max": 0}
    media = df["pontos"].mean()
    if media >= 11:
        return {"robustez": 0, "atrasadas": 0, "rep_min": 0, "rep_max": 0}
    elif media >= 9:
        return {"robustez": -5, "atrasadas": -1, "rep_min": -1, "rep_max": 1}
    else:
        return {"robustez": -10, "atrasadas": -2, "rep_min": -2, "rep_max": 2}

def iso_to_br(data_iso):
    if not data_iso:
        return ""
    try:
        return datetime.strptime(str(data_iso), "%Y-%m-%d").date().strftime("%d/%m/%Y")
    except Exception:
        return str(data_iso)

def normalize_date_input(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").date().strftime("%Y-%m-%d")
    except ValueError:
        try:
            return dateparser.parse(date_str, dayfirst=True).date().strftime("%Y-%m-%d")
        except Exception:
            return None

def validate_dezenas(dezenas_str):
    try:
        dezenas = sorted([int(d) for d in dezenas_str if d.strip()])
        if len(dezenas) != 15:
            return False, "Deve haver exatamente 15 dezenas."
        if not all(1 <= d <= 25 for d in dezenas):
            return False, "Dezenas devem estar entre 1 e 25."
        if len(set(dezenas)) != 15:
            return False, "Dezenas não podem ser repetidas."
        return True, dezenas
    except ValueError:
        return False, "Dezenas inválidas. Use apenas números."

def insert_concurso(concurso, data_iso, dezenas):
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO concursos (concurso, data, d1,d2,d3,d4,d5,d6,d7,d8,d9,d10,d11,d12,d13,d14,d15) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (concurso, data_iso, *dezenas)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        st.warning(f"Concurso {concurso} já existe e foi ignorado.")
        return False
    except Exception as e:
        st.error(f"Erro ao inserir concurso {concurso}: {e}")
        return False
    finally:
        conn.close()

def update_concurso(concurso, data_iso, dezenas):
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """UPDATE concursos SET data=?, d1=?,d2=?,d3=?,d4=?,d5=?,d6=?,d7=?,d8=?,d9=?,d10=?,d11=?,d12=?,d13=?,d14=?,d15=? WHERE concurso=?""",
            (data_iso, *dezenas, concurso)
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar concurso {concurso}: {e}")
        return False
    finally:
        conn.close()

def fetch_all_concursos():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM concursos ORDER BY concurso DESC", conn)
    conn.close()
    return df

def fetch_concurso(concurso_num):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM concursos WHERE concurso = ?", (concurso_num,))
    row = cursor.fetchone()
    conn.close()
    if row:
        cols = ["concurso", "data"] + [f"d{i}" for i in range(1, 16)]
        return dict(zip(cols, row))
    return None

def fetch_ultimo_concurso():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM concursos ORDER BY concurso DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        cols = ["concurso", "data"] + [f"d{i}" for i in range(1, 16)]
        return dict(zip(cols, row))
    return None

def importar_xlsx_lotofacil(arquivo_xlsx, sheet_name="LOTOFÁCIL"):
    """
    Lê o XLSX (aba LOTOFÁCIL) e insere no SQLite.
    Aceita caminho de arquivo (str) OU arquivo enviado pelo usuário (st.file_uploader).
    """
    import io
    try:
        if hasattr(arquivo_xlsx, "read"):  # arquivo enviado pelo usuário no app
            df = pd.read_excel(io.BytesIO(arquivo_xlsx.read()), sheet_name=sheet_name, engine="openpyxl")
        else:  # caminho de arquivo local
            if not os.path.exists(arquivo_xlsx):
                st.error(f"Arquivo Excel não encontrado em: {arquivo_xlsx}")
                return 0, 0
            df = pd.read_excel(arquivo_xlsx, sheet_name=sheet_name, engine="openpyxl")
    except Exception as e:
        st.error(f"Erro ao ler o arquivo Excel ou aba '{sheet_name}': {e}")
        return 0, 0
    required_cols = ["Concurso", "Data Sorteio"] + [f"Bola{i}" for i in range(1, 16)]
    df_filtered = df[required_cols].copy()
    df_filtered["Concurso"] = pd.to_numeric(df_filtered["Concurso"], errors="coerce").astype("Int64")
    df_filtered = df_filtered.dropna(subset=["Concurso"])
    def parse_excel_date(val):
        if pd.isna(val):
            return None
        if isinstance(val, (datetime, date)):
            return val.strftime("%Y-%m-%d")
        try:
            return datetime.strptime(str(val).strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            try:
                return dateparser.parse(str(val).strip(), dayfirst=True).strftime("%Y-%m-%d")
            except Exception:
                return None
    df_filtered["DataISO"] = df_filtered["Data Sorteio"].apply(parse_excel_date)
    df_filtered = df_filtered.dropna(subset=["DataISO"])
    bola_cols = [f"Bola{i}" for i in range(1, 16)]
    for col in bola_cols:
        df_filtered[col] = pd.to_numeric(df_filtered[col], errors="coerce").astype("Int64")
    df_filtered = df_filtered.dropna(subset=bola_cols)
    inseridos = 0
    duplicados = 0
    conn = get_conn()
    cursor = conn.cursor()
    for _, row in df_filtered.iterrows():
        concurso_num = int(row["Concurso"])
        data_iso = str(row["DataISO"])
        dezenas = sorted([int(row[f"Bola{i}"]) for i in range(1, 16)])
        is_valid, validated_dezenas = validate_dezenas([str(d) for d in dezenas])
        if not is_valid:
            st.warning(f"Concurso {concurso_num} ignorado por dezenas inválidas: {validated_dezenas}")
            continue
        try:
            cursor.execute(
                "INSERT INTO concursos (concurso, data, d1,d2,d3,d4,d5,d6,d7,d8,d9,d10,d11,d12,d13,d14,d15) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (concurso_num, data_iso, *validated_dezenas)
            )
            inseridos += 1
        except sqlite3.IntegrityError:
            duplicados += 1
        except Exception as e:
            st.error(f"Erro ao inserir concurso {concurso_num} do Excel: {e}")
    conn.commit()
    conn.close()
    return inseridos, duplicados

# =========================
# Funções de Geração de Jogos
# =========================
def count_repetitions(game, last_contest_dezenas):
    return len(set(game) & set(last_contest_dezenas))

def count_even_odd(game):
    pares = sum(1 for d in game if d % 2 == 0)
    return pares, 15 - pares

def count_primes(game):
    return sum(1 for d in game if d in PRIMES)

def get_dezenas_freq(df_concursos):
    freq = {d: 0 for d in range(1, 26)}
    for _, row in df_concursos.iterrows():
        for i in range(1, 16):
            freq[int(row[f"d{i}"])] += 1
    return freq

def generate_weighted_random_game(freq):
    dezenas = list(range(1, 26))
    pesos = [freq[d] + 1 for d in dezenas]
    return sorted(random.sample(dezenas, 15, counts=pesos))

def calcular_pontos(jogo, resultado):
    return len(set(jogo) & set(resultado))

def calcular_robustez(jogo, df_concursos_recentes, min_pontos=11):
    if df_concursos_recentes is None or len(df_concursos_recentes) == 0:
        return 1.0
    acertos = 0
    total = len(df_concursos_recentes)
    for _, row in df_concursos_recentes.iterrows():
        resultado = [int(row[f"d{i}"]) for i in range(1, 16)]
        if calcular_pontos(jogo, resultado) >= min_pontos:
            acertos += 1
    return acertos / total

def get_atraso_e_ciclo(df_concursos):
    df = df_concursos.sort_values("concurso").copy()
    concursos = df["concurso"].tolist()
    ultimo_concurso = concursos[-1] if concursos else 0
    aparicoes = {d: [] for d in range(1, 26)}
    for _, row in df.iterrows():
        c = int(row["concurso"])
        for i in range(1, 16):
            aparicoes[int(row[f"d{i}"])].append(c)
    dados = []
    for d in range(1, 26):
        lista = aparicoes[d]
        if not lista:
            dados.append({"Dezena": d, "Último Concurso": None, "Atraso": len(concursos), "Ciclo Médio": None})
            continue
        ultimo = lista[-1]
        atraso = ultimo_concurso - ultimo
        if len(lista) >= 2:
            intervalos = [lista[i+1] - lista[i] for i in range(len(lista)-1)]
            ciclo = round(sum(intervalos) / len(intervalos), 2)
        else:
            ciclo = None
        dados.append({"Dezena": d, "Último Concurso": ultimo, "Atraso": atraso, "Ciclo Médio": ciclo})
    return pd.DataFrame(dados)

def get_dezenas_atrasadas(df_concursos, min_atraso=3):
    df_ciclo = get_atraso_e_ciclo(df_concursos)
    return set(df_ciclo[df_ciclo["Atraso"] >= min_atraso]["Dezena"].tolist())

# =========================
# Ciclo Fechado das Dezenas
# =========================
def calcular_ciclos_fechados(df_concursos):
    """Calcula os ciclos fechados a partir do primeiro concurso e o ciclo atual (aberto).
    Um ciclo fecha quando as 25 dezenas aparecem; abre outro na sequência,
    começando com as 15 dezenas do sorteio que fechou o ciclo anterior.
    """
    df = df_concursos.sort_values("concurso").copy()
    concursos = df["concurso"].tolist()
    if not concursos:
        return [], None
    ciclos = []
    visto = set()
    inicio = concursos[0]
    ultimo_concurso = concursos[-1]
    for c in concursos:
        row = df[df["concurso"] == c].iloc[0]
        dezenas = set(int(row[f"d{i}"]) for i in range(1, 16))
        faltavam_antes = set(range(1, 26)) - visto
        visto |= dezenas
        if len(visto) == 25:
            fechadoras = sorted(dezenas & faltavam_antes)
            ciclos.append({
                "ciclo": len(ciclos) + 1,
                "inicio": inicio,
                "fim": c,
                "duracao": c - inicio + 1,
                "fechadoras": fechadoras,
            })
            visto = set(dezenas)
            inicio = c
    faltantes = sorted(set(range(1, 26)) - visto)
    ciclo_atual = {
        "num_ciclo": len(ciclos) + 1,
        "inicio": inicio,
        "ultimo_concurso": ultimo_concurso,
        "faltantes": faltantes,
        "num_faltantes": len(faltantes),
    }
    return ciclos, ciclo_atual

def regra_faltantes_ciclo(num_faltantes):
    """Regra: faltam 1-3 -> força todas | faltam 4+ -> metade (arredondado p/ cima)."""
    if num_faltantes <= 0:
        return 0
    if num_faltantes <= 3:
        return num_faltantes
    return (num_faltantes + 1) // 2

def check_game_filters(game, last_contest_dezenas, min_rep, max_rep, min_pares, max_pares, min_primos, max_primos, atrasadas=None, min_atrasadas=0, faltantes_ciclo=None, min_faltantes_ciclo=0):
    if last_contest_dezenas:
        rep = count_repetitions(game, last_contest_dezenas)
        if not (min_rep <= rep <= max_rep):
            return False
    pares, _ = count_even_odd(game)
    if not (min_pares <= pares <= max_pares):
        return False
    primos = count_primes(game)
    if not (min_primos <= primos <= max_primos):
        return False
    if atrasadas:
        n_atrasadas = len(set(game) & atrasadas)
        if n_atrasadas < min_atrasadas:
            return False
    if faltantes_ciclo:
        n_falt = len(set(game) & faltantes_ciclo)
        if n_falt < min_faltantes_ciclo:
            return False
    return True

def generate_unique_game_with_filters(existing_games, last_contest_dezenas, min_rep, max_rep, min_pares, max_pares, min_primos, max_primos, freq=None, df_recentes=None, min_robustez=0.0, atrasadas=None, min_atrasadas=0, faltantes_ciclo=None, min_faltantes_ciclo=0, max_attempts=5000):
    attempts = 0
    while attempts < max_attempts:
        if freq:
            game = generate_weighted_random_game(freq)
        else:
            game = sorted(random.sample(range(1, 26), 15))
        if tuple(game) in existing_games:
            attempts += 1
            continue
        if not check_game_filters(game, last_contest_dezenas, min_rep, max_rep, min_pares, max_pares, min_primos, max_primos, atrasadas, min_atrasadas, faltantes_ciclo, min_faltantes_ciclo):
            attempts += 1
            continue
        if min_robustez > 0 and calcular_robustez(game, df_recentes) < min_robustez:
            attempts += 1
            continue
        return game
    return None

def export_games(games, folder=OUTPUT_FOLDER):
    if not os.path.exists(folder):
        os.makedirs(folder)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(os.path.join(folder, f"jogos_lotofacil_{timestamp}_espaco.txt"), "w", encoding="utf-8") as f:
        for game in games:
            f.write(" ".join(f"{d:02d}" for d in game) + "\n")
    with open(os.path.join(folder, f"jogos_lotofacil_{timestamp}_hifen.txt"), "w", encoding="utf-8") as f:
        for game in games:
            f.write("-".join(f"{d:02d}" for d in game) + "\n")
    with open(os.path.join(folder, f"jogos_lotofacil_{timestamp}.csv"), "w", encoding="utf-8") as f:
        f.write("D1,D2,D3,D4,D5,D6,D7,D8,D9,D10,D11,D12,D13,D14,D15\n")
        for game in games:
            f.write(",".join(f"{d:02d}" for d in game) + "\n")
    st.success(f"Jogos exportados para a pasta '{folder}/'")

def conferir_caderno(caderno, resultado, min_pontos=11):
    linhas = []
    for jogo in caderno:
        pontos = calcular_pontos(jogo, resultado)
        if pontos >= min_pontos:
            acertos = sorted(set(jogo) & set(resultado))
            linhas.append({
                "Pontos": pontos,
                "Acertos": " ".join(f"{d:02d}" for d in acertos),
                **{f"D{i}": f"{jogo[i-1]:02d}" for i in range(1, 16)}
            })
    df = pd.DataFrame(linhas)
    if not df.empty:
        df = df.sort_values(["Pontos"], ascending=False)
    return df

# =========================
# Funções de Análise de Dados
# =========================
def get_dezenas_df(df_concursos):
    freq = {d: 0 for d in range(1, 26)}
    for _, row in df_concursos.iterrows():
        for i in range(1, 16):
            freq[int(row[f"d{i}"])] += 1
    return pd.DataFrame({"Dezena": list(freq.keys()), "Frequência": list(freq.values())})

def get_pares_impares_series(df_concursos):
    df = df_concursos.sort_values("concurso").copy()
    pares = []
    for _, row in df.iterrows():
        dezenas = [int(row[f"d{i}"]) for i in range(1, 16)]
        pares.append(sum(1 for d in dezenas if d % 2 == 0))
    df["Pares"] = pares
    df["Ímpares"] = 15 - df["Pares"]
    return df

def get_soma_series(df_concursos):
    df = df_concursos.sort_values("concurso").copy()
    somas = []
    for _, row in df.iterrows():
        dezenas = [int(row[f"d{i}"]) for i in range(1, 16)]
        somas.append(sum(dezenas))
    df["Soma"] = somas
    return df

def get_repeticao_series(df_concursos):
    df = df_concursos.sort_values("concurso").copy()
    anteriores = []
    for _, row in df.iterrows():
        anteriores.append(set(int(row[f"d{i}"]) for i in range(1, 16)))
    repeticoes = [0]
    for i in range(1, len(anteriores)):
        repeticoes.append(len(anteriores[i] & anteriores[i - 1]))
    df["Repetições"] = repeticoes
    return df

# =========================
# Configuração da Página Streamlit
# =========================
st.set_page_config(layout="wide", page_title="Dashboard Lotofácil")
st.title("🎲 Dashboard Lotofácil")
setup_folders()
create_table()
create_jogos_table()
if "caderno" not in st.session_state:
    st.session_state["caderno"] = []
tab1, tab2, tab3, tab4 = st.tabs(["Cadastrar Concurso", "Gerar Jogos", "Editar Concurso", "Análise de Dados"])

# =========================
# Aba 1: Cadastrar Concurso
# =========================
with tab1:
    st.header("Cadastrar Novo Concurso")
    with st.form("form_cadastrar_concurso"):
        col1, col2 = st.columns(2)
        with col1:
            concurso_num = st.number_input("Número do Concurso", min_value=1, step=1, value=None, format="%d")
        with col2:
            data_sorteio_br = st.text_input("Data do Sorteio (dd/mm/aaaa)", value=datetime.now().strftime("%d/%m/%Y"))
        dezenas_input = st.text_input("Dezenas (separadas por espaço ou vírgula, ex: 01 02 03 ... 15)")
        submitted = st.form_submit_button("Salvar Concurso")
        if submitted:
            if not concurso_num:
                st.error("O número do concurso é obrigatório.")
            else:
                data_iso = normalize_date_input(data_sorteio_br)
                if not data_iso:
                    st.error("Formato de data inválido. Use dd/mm/aaaa.")
                else:
                    is_valid, dezenas_validadas = validate_dezenas(dezenas_input.replace(",", " ").split())
                    if is_valid:
                        if insert_concurso(concurso_num, data_iso, dezenas_validadas):
                            st.success(f"Concurso {concurso_num} cadastrado com sucesso!")
                            conferidos = conferir_jogos_pendentes(concurso_num, dezenas_validadas)
                            if conferidos > 0:
                                st.info(f"{conferidos} jogo(s) gerado(s) anteriormente conferidos contra o concurso {concurso_num}.")
                    else:
                        st.error(dezenas_validadas)
    st.divider()
    st.subheader("Importar Concursos do Excel")
    arquivo_excel = st.file_uploader("Selecione o arquivo Excel (.xlsx) com os concursos", type=["xlsx"])
    st.info(f"A aba esperada no Excel é `{EXCEL_SHEET_NAME}` (colunas: Concurso, Data Sorteio, Bola1..Bola15).")
    if st.button("Importar XLSX para o banco", disabled=arquivo_excel is None):
        if arquivo_excel is None:
            st.warning("Selecione o arquivo Excel primeiro.")
        else:
            with st.spinner("Importando dados do Excel..."):
                inseridos, duplicados = importar_xlsx_lotofacil(arquivo_excel, EXCEL_SHEET_NAME)
            if inseridos > 0 or duplicados > 0:
                st.success(f"Importação concluída. Inseridos: {inseridos} | Duplicados ignorados: {duplicados}")
                ultimo_importado = fetch_ultimo_concurso()
                if ultimo_importado:
                    dezenas_ultimo = [ultimo_importado[f"d{i}"] for i in range(1, 16)]
                    conferidos_imp = conferir_jogos_pendentes(ultimo_importado["concurso"], dezenas_ultimo)
                    if conferidos_imp > 0:
                        st.info(f"{conferidos_imp} jogo(s) gerado(s) anteriormente conferidos contra o concurso {ultimo_importado['concurso']}.")
            else:
                st.info("Nenhum novo concurso foi inserido ou o arquivo não pôde ser lido.")
    st.divider()
    st.subheader("Últimos Concursos Cadastrados")
    all_concursos_df = fetch_all_concursos()
    if not all_concursos_df.empty:
        df_display = all_concursos_df.copy()
        df_display["data"] = df_display["data"].apply(iso_to_br)
        df_display.rename(columns={"data": "Data Sorteio"}, inplace=True)
        st.dataframe(df_display.set_index("concurso"))
    else:
        st.info("Nenhum concurso cadastrado ainda.")

# =========================
# Aba 2: Gerar Jogos
# =========================
with tab2:
    st.header("Gerar Jogos com Frequência, Robustez, Ciclo e Ciclo Fechado")
    last_contest = fetch_ultimo_concurso()
    last_contest_dezenas = []
    if last_contest:
        st.info(f"Último concurso cadastrado: **{last_contest['concurso']}** ({iso_to_br(last_contest['data'])})")
        last_contest_dezenas = [last_contest[f"d{i}"] for i in range(1, 16)]
        st.write(f"Dezenas do último concurso: **{' '.join(f'{d:02d}' for d in last_contest_dezenas)}**")
    else:
        st.warning("Nenhum concurso cadastrado. Filtro de repetição não será aplicado.")
    df_concursos_tab2 = fetch_all_concursos()
    freq_historica = get_dezenas_freq(df_concursos_tab2) if not df_concursos_tab2.empty else None
    aprendizado = get_aprendizado_dezenas()
    if aprendizado and freq_historica:
        for d in range(1, 26):
            freq_historica[d] = freq_historica[d] + aprendizado[d] * 2
    df_recentes_robustez = df_concursos_tab2.sort_values("concurso", ascending=False).head(10) if not df_concursos_tab2.empty else None
    ciclos_fechados, ciclo_atual = calcular_ciclos_fechados(df_concursos_tab2) if not df_concursos_tab2.empty else ([], None)
    faltantes_ciclo = set(ciclo_atual["faltantes"]) if ciclo_atual else None
    min_faltantes_ciclo = regra_faltantes_ciclo(ciclo_atual["num_faltantes"]) if ciclo_atual else 0
    st.subheader("Configurar Filtros")
    ajuste = calcular_ajuste_filtros()
    if any(v != 0 for v in ajuste.values()):
        st.caption(f"🤖 Ajuste automático (média dos últimos palpites): robustez {ajuste['robustez']:+d} | atrasadas {ajuste['atrasadas']:+d} | repetições {ajuste['rep_min']:+d} a {ajuste['rep_max']:+d}")
    col_filters1, col_filters2, col_filters3 = st.columns(3)
    with col_filters1:
        st.markdown("#### Repetições do Último Concurso")
        min_rep = st.slider("Mínimo de Repetições", 0, 15, max(0, 9 + ajuste["rep_min"]) if last_contest else 0)
        max_rep = st.slider("Máximo de Repetições", 0, 15, min(15, 10 + ajuste["rep_max"]) if last_contest else 15)
        if min_rep > max_rep:
            st.error("Mínimo de repetições não pode ser maior que o máximo.")
    with col_filters2:
        st.markdown("#### Dezenas Pares")
        min_pares = st.slider("Mínimo de Pares", 0, 15, 7)
        max_pares = st.slider("Máximo de Pares", 0, 15, 8)
        if min_pares > max_pares:
            st.error("Mínimo de pares não pode ser maior que o máximo.")
    with col_filters3:
        st.markdown("#### Dezenas Primas")
        min_primos = st.slider("Mínimo de Primos", 0, len(PRIMES), 4)
        max_primos = st.slider("Máximo de Primos", 0, len(PRIMES), 6)
        if min_primos > max_primos:
            st.error("Mínimo de primos não pode ser maior que o máximo.")
    st.divider()
    st.subheader("Frequência e Robustez (Tendência)")
    if df_concursos_tab2.empty:
        st.info("Cadastre concursos para ativar a geração por frequência e robustez.")
        usar_freq = False
        min_robustez = 0.0
    else:
        usar_freq = st.checkbox("Usar frequência histórica (dezenas mais sorteadas têm mais peso)", value=True)
        min_robustez = st.slider(
            "Robustez mínima: % de concursos (últimos 10) em que o jogo faria 11+ pontos",
            0, 100, max(0, 30 + ajuste["robustez"]), 5,
            help="Só aceita jogos que teriam premiado (11+) em pelo menos esse % dos últimos 10 concursos. Ajustado automaticamente conforme o desempenho dos palpites anteriores."
        ) / 100.0
        st.caption(f"Base de robustez: últimos **{len(df_recentes_robustez)}** concursos.")
    st.divider()
    st.subheader("Ciclo das Dezenas (Atraso)")
    if df_concursos_tab2.empty:
        st.info("Cadastre concursos para ativar o filtro de dezenas atrasadas.")
        atrasadas_set = None
        min_atrasadas = 0
    else:
        min_atraso = st.slider("Atraso mínimo para considerar uma dezena 'atrasada'", 1, 15, 3)
        atrasadas_set = get_dezenas_atrasadas(df_concursos_tab2, min_atraso)
        st.write(f"Dezenas atrasadas (atraso ≥ {min_atraso}): **{' '.join(f'{d:02d}' for d in sorted(atrasadas_set))}**")
        min_atrasadas = st.slider("Mínimo de dezenas atrasadas por jogo", 0, min(10, len(atrasadas_set)), max(0, 4 + ajuste["atrasadas"]))
        st.caption(f"Total de dezenas atrasadas disponíveis: **{len(atrasadas_set)}**")
    st.divider()
    st.subheader("Ciclo Fechado das Dezenas")
    if ciclo_atual is None:
        st.info("Cadastre concursos para ativar o filtro de ciclo fechado.")
        faltantes_ciclo = None
        min_faltantes_ciclo = 0
    else:
        st.write(f"Ciclo atual: **{ciclo_atual['num_ciclo']}** (iniciado no concurso **{ciclo_atual['inicio']}**)")
        st.write(f"Dezenas que ainda faltam no ciclo: **{' '.join(f'{d:02d}' for d in ciclo_atual['faltantes'])}**")
        st.write(f"Total faltando: **{ciclo_atual['num_faltantes']}**")
        if ciclo_atual["num_faltantes"] == 0:
            st.success("Ciclo fechado! Todas as 25 dezenas já apareceram. Um novo ciclo será iniciado no próximo sorteio.")
            faltantes_ciclo = None
            min_faltantes_ciclo = 0
        elif ciclo_atual["num_faltantes"] <= 3:
            st.info(f"Faltam apenas **{ciclo_atual['num_faltantes']}** dezenas. Regra aplicada: **forçar as {ciclo_atual['num_faltantes']} faltantes em cada jogo**.")
        else:
            st.info(f"Faltam **{ciclo_atual['num_faltantes']}** dezenas. Regra aplicada: **metade ({min_faltantes_ciclo}) das faltantes por jogo**.")
        st.caption("Regra automática: faltam 1-3 → força todas | faltam 4+ → metade por jogo.")
    st.divider()
    st.subheader("Gerar Jogos")
    num_jogos_to_generate = st.radio("Quantos jogos deseja gerar?", (16, 32, 64, 128), horizontal=True)
    if st.button(f"Gerar {num_jogos_to_generate} Jogos"):
        generated_games = []
        existing_games_set = set()
        progress_bar = st.progress(0)
        for i in range(num_jogos_to_generate):
            game = generate_unique_game_with_filters(
                existing_games_set,
                last_contest_dezenas,
                min_rep, max_rep,
                min_pares, max_pares,
                min_primos, max_primos,
                freq=freq_historica if usar_freq else None,
                df_recentes=df_recentes_robustez,
                min_robustez=min_robustez,
                atrasadas=atrasadas_set,
                min_atrasadas=min_atrasadas,
                faltantes_ciclo=faltantes_ciclo,
                min_faltantes_ciclo=min_faltantes_ciclo
            )
            if game:
                generated_games.append(game)
                existing_games_set.add(tuple(game))
            else:
                st.warning(f"Não foi possível gerar todos os {num_jogos_to_generate} jogos com os filtros especificados. Tente reduzir a robustez, o mínimo de atrasadas ou o mínimo de faltantes do ciclo.")
                break
            progress_bar.progress((i + 1) / num_jogos_to_generate)
        if generated_games:
            st.success(f"{len(generated_games)} jogos gerados com sucesso!")
            salvar_jogos_gerados(generated_games, concurso_alvo=last_contest["concurso"] if last_contest else None)
            st.dataframe(pd.DataFrame(generated_games, columns=[f"D{i}" for i in range(1, 16)]))
            caderno_set = set(tuple(j) for j in st.session_state["caderno"])
            novos = 0
            for j in generated_games:
                tj = tuple(j)
                if tj not in caderno_set:
                    st.session_state["caderno"].append(j)
                    caderno_set.add(tj)
                    novos += 1
            st.info(f"Caderno atualizado: +{novos} jogos (total: {len(st.session_state['caderno'])}).")
            export_games(generated_games)
        else:
            st.error("Nenhum jogo foi gerado. Verifique os filtros e se há concursos cadastrados.")
    st.divider()
       st.subheader("Caderno de Jogos")
    total_caderno = len(st.session_state["caderno"])
    st.write(f"Total de jogos no caderno: **{total_caderno}**")
    colA, colB = st.columns(2)
    with colA:
        if st.button("Conferir Caderno (último sorteio)"):
            ultimo = fetch_ultimo_concurso()
            if not ultimo:
                st.warning("Não há sorteios cadastrados para conferir. Cadastre ou importe o resultado primeiro.")
            elif total_caderno == 0:
                st.info("O caderno está vazio. Gere jogos primeiro.")
            else:
                resultado = [ultimo[f"d{i}"] for i in range(1, 16)]
                st.write(f"Resultado usado: concurso **{ultimo['concurso']}** ({iso_to_br(ultimo['data'])}) — **{' '.join(f'{d:02d}' for d in resultado)}**")
                df_premiados = conferir_caderno(st.session_state["caderno"], resultado, min_pontos=11)
                if df_premiados.empty:
                    st.warning("Nenhum jogo do caderno pontuou (11 a 15 pontos) com o último sorteio.")
                else:
                    resumo = df_premiados["Pontos"].value_counts().reindex([15, 14, 13, 12, 11], fill_value=0)
                    st.write("Resumo (quantidade por pontuação):")
                    st.write(resumo)
                    st.dataframe(df_premiados, use_container_width=True)
    with colB:
        if st.button("Limpar Caderno"):
            st.session_state["caderno"] = []
            st.success("Caderno limpo.")
        if st.button("Conferir Caderno (último sorteio)"):