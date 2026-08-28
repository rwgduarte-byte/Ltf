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
VALOR_APOSTA = 3.50
PREMIOS = {11: 7.00, 12: 14.00, 13: 35.00, 14: 0.00, 15: 0.00}
MAX_SEQUENCIA_CONSECUTIVA = 10  # bloqueia jogos com 10+ números consecutivos
MODALIDADE_FILTRADO = "filtrado"
MODALIDADE_GRUPOS = "grupos"
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

def adicionar_colunas_se_necessario():
    conn = get_conn()
    cursor = conn.cursor()
    for sql in [
        "ALTER TABLE jogos_gerados ADD COLUMN aposta_confirmada INTEGER DEFAULT 0",
        "ALTER TABLE jogos_gerados ADD COLUMN concurso_jogado INTEGER",
        "ALTER TABLE jogos_gerados ADD COLUMN modalidade TEXT",
    ]:
        try:
            cursor.execute(sql)
        except Exception:
            pass
    conn.commit()
    conn.close()

def salvar_jogos_gerados(jogos, concurso_alvo=None, modalidade=None):
    conn = get_conn()
    cursor = conn.cursor()
    data_geracao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for jogo in jogos:
        cursor.execute(
            "INSERT INTO jogos_gerados (concurso_alvo, data_geracao, d1,d2,d3,d4,d5,d6,d7,d8,d9,d10,d11,d12,d13,d14,d15, conferido, modalidade) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?)",
            (concurso_alvo, data_geracao, *jogo, modalidade)
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

# =========================
# Avaliação de ROI das Apostas
# =========================
def calcular_premio(pontos):
    if pontos < 11:
        return 0.0
    return PREMIOS.get(pontos, 0.0)

def marcar_aposta_confirmada(jogos, concurso_jogado):
    conn = get_conn()
    cursor = conn.cursor()
    marcados = 0
    for jogo in jogos:
        cursor.execute(
            """UPDATE jogos_gerados SET aposta_confirmada=1, concurso_jogado=?
            WHERE d1=? AND d2=? AND d3=? AND d4=? AND d5=? AND d6=? AND d7=? AND d8=? AND d9=? AND d10=?
            AND d11=? AND d12=? AND d13=? AND d14=? AND d15=? AND aposta_confirmada=0""",
            (concurso_jogado, *jogo)
        )
        marcados += cursor.rowcount
    conn.commit()
    conn.close()
    return marcados

def calcular_resultado_aposta(concurso_num):
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT pontos, modalidade FROM jogos_gerados WHERE aposta_confirmada=1 AND concurso_jogado=? AND conferido=1 AND pontos IS NOT NULL",
        conn, params=(concurso_num,)
    )
    conn.close()
    if df.empty:
        return None
    n_jogos = len(df)
    investimento = n_jogos * VALOR_APOSTA
    premio = sum(calcular_premio(p) for p in df["pontos"])
    n_11plus = int((df["pontos"] >= 11).sum())
    return {"concurso": concurso_num, "n_jogos": n_jogos, "investimento": investimento, "premio": premio, "saldo": premio - investimento, "n_11plus": n_11plus}

def get_resultado_ultima_aposta():
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT DISTINCT concurso_jogado FROM jogos_gerados WHERE aposta_confirmada=1 AND conferido=1 AND concurso_jogado IS NOT NULL ORDER BY concurso_jogado DESC LIMIT 1",
        conn
    )
    conn.close()
    if df.empty:
        return None
    return calcular_resultado_aposta(int(df.iloc[0]["concurso_jogado"]))

def exibir_resultado_aposta(resultado):
    if not resultado:
        return
    st.markdown("#### 💰 Resultado da Aposta")
    st.write(f"Concurso **{resultado['concurso']}** | {resultado['n_jogos']} jogos | Investimento **R$ {resultado['investimento']:.2f}**")
    st.write(f"Prêmios: **R$ {resultado['premio']:.2f}** | Jogos com 11+: **{resultado['n_11plus']}**")
    if resultado["saldo"] >= 0:
        st.success(f"Saldo: **+R$ {resultado['saldo']:.2f}** (lucro)")
    else:
        st.error(f"Saldo: **-R$ {abs(resultado['saldo']):.2f}** (prejuízo)")

def calcular_ajuste_filtros():
    """Ajuste baseado no ROI da última aposta confirmada (e, sem aposta, na média de pontos)."""
    resultado = get_resultado_ultima_aposta()
    if resultado is not None:
        saldo = resultado["saldo"]
        if saldo >= 0:
            return {"robustez": 0, "atrasadas": 0, "rep_min": 0, "rep_max": 0}
        elif saldo >= -VALOR_APOSTA * 4:
            return {"robustez": -5, "atrasadas": -1, "rep_min": -1, "rep_max": 1}
        else:
            return {"robustez": -10, "atrasadas": -2, "rep_min": -2, "rep_max": 2}
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

def comparativo_modalidades():
    """Compara eficácia entre as modalidades 'filtrado' e 'grupos' nas apostas confirmadas."""
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT modalidade, pontos FROM jogos_gerados WHERE aposta_confirmada=1 AND conferido=1 AND pontos IS NOT NULL AND modalidade IS NOT NULL",
        conn
    )
    conn.close()
    if df.empty:
        return None
    linhas = []
    for mod in [MODALIDADE_FILTRADO, MODALIDADE_GRUPOS]:
        sub = df[df["modalidade"] == mod]
        if sub.empty:
            continue
        n = len(sub)
        invest = n * VALOR_APOSTA
        premio = sum(calcular_premio(p) for p in sub["pontos"])
        n_11plus = int((sub["pontos"] >= 11).sum())
        linhas.append({
            "Modalidade": "Filtrado (16)" if mod == MODALIDADE_FILTRADO else "Grupos (10)",
            "Jogos": n,
            "Investimento": round(invest, 2),
            "Prêmio": round(premio, 2),
            "Saldo": round(premio - invest, 2),
            "Jogos 11+": n_11plus,
            "Taxa 11+": f"{100*n_11plus/n:.1f}%",
        })
    return pd.DataFrame(linhas)

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
    """Calcula os ciclos fechados a partir do primeiro concurso e o ciclo atual (aberto)."""
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

def maior_sequencia_consecutiva(game):
    """Retorna o tamanho da maior sequência de números consecutivos no jogo."""
    maior = 1
    atual = 1
    for i in range(1, len(game)):
        if game[i] - game[i - 1] == 1:
            atual += 1
            maior = max(maior, atual)
        else:
            atual = 1
    return maior

def tem_sequencia_grande(game, limite=MAX_SEQUENCIA_CONSECUTIVA):
    """Retorna True se o jogo tiver uma sequência de 'limite' ou mais números consecutivos."""
    return maior_sequencia_consecutiva(game) >= limite

def generate_unique_game_with_filters(existing_games, last_contest_dezenas, min_rep, max_rep, min_pares, max_pares, min_primos, max_primos, freq=None, df_recentes=None, min_robustez=0.0, atrasadas=None, min_atrasadas=0, faltantes_ciclo=None, min_faltantes_ciclo=0, max_attempts=50000):
    attempts = 0
    while attempts < max_attempts:
        if freq:
            game = generate_weighted_random_game(freq)
        else:
            game = sorted(random.sample(range(1, 26), 15))
        if tem_sequencia_grande(game):
            attempts += 1
            continue
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
# Geração por Grupos (nova formatação)
# =========================
def sortear_grupos(last_contest_dezenas):
    """Gera os grupos A (sorteadas em 5x3), B (não sorteadas em 5x2)."""
    if not last_contest_dezenas or len(last_contest_dezenas) != 15:
        return None
    sorteadas = list(last_contest_dezenas)
    nao_sorteadas = [d for d in range(1, 26) if d not in sorteadas]
    random.shuffle(sorteadas)
    random.shuffle(nao_sorteadas)
    grupos_tres = [
        sorted(sorteadas[0:3]),
        sorted(sorteadas[3:6]),
        sorted(sorteadas[6:9]),
        sorted(sorteadas[9:12]),
        sorted(sorteadas[12:15]),
    ]
    grupos_dois = [
        sorted(nao_sorteadas[0:2]),
        sorted(nao_sorteadas[2:4]),
        sorted(nao_sorteadas[4:6]),
        sorted(nao_sorteadas[6:8]),
        sorted(nao_sorteadas[8:10]),
    ]
    return grupos_tres, grupos_dois

def validar_grupos(grupos_tres, grupos_dois):
    """Valida os grupos editados. Retorna (valido, mensagem)."""
    erros = []
    todos = []
    for i, g in enumerate(grupos_tres):
        if len(g) != 3:
            erros.append(f"A{i+1} deve ter exatamente 3 dezenas (tem {len(g)}).")
        if len(set(g)) != len(g):
            erros.append(f"A{i+1} tem dezenas repetidas.")
        if any(not (1 <= d <= 25) for d in g):
            erros.append(f"A{i+1} tem dezena fora de 1 a 25.")
        todos.extend(g)
    for i, g in enumerate(grupos_dois):
        if len(g) != 2:
            erros.append(f"B{i+1} deve ter exatamente 2 dezenas (tem {len(g)}).")
        if len(set(g)) != len(g):
            erros.append(f"B{i+1} tem dezenas repetidas.")
        if any(not (1 <= d <= 25) for d in g):
            erros.append(f"B{i+1} tem dezena fora de 1 a 25.")
        todos.extend(g)
    if len(set(todos)) != len(todos):
        erros.append("Há dezenas repetidas entre grupos diferentes.")
    if erros:
        return False, " ".join(erros)
    return True, "Grupos válidos."

def combinar_grupos(grupos_tres, grupos_dois):
    """Monta G1..G5 (A_i + B_i) e combina 3 a 3 -> 10 jogos de 15 dezenas."""
    grupos_cinco = [
        sorted(grupos_tres[i] + grupos_dois[i]) for i in range(5)
    ]
    jogos = []
    for i in range(5):
        for j in range(i + 1, 5):
            for k in range(j + 1, 5):
                jogos.append(sorted(grupos_cinco[i] + grupos_cinco[j] + grupos_cinco[k]))
    return grupos_cinco, jogos

# =========================
# Melhoria 1: Aprender o padrão real dos sorteios
# =========================
def calcular_padrao_real(df_concursos, ultimas=20):
    """Mede o padrão real dos últimos sorteios para posicionar os filtros."""
    if df_concursos is None or df_concursos.empty:
        return None
    df = df_concursos.sort_values("concurso").tail(ultimas).copy()
    pares_list = []
    primos_list = []
    soma_list = []
    for _, row in df.iterrows():
        dezenas = [int(row[f"d{i}"]) for i in range(1, 16)]
        pares_list.append(sum(1 for d in dezenas if d % 2 == 0))
        primos_list.append(sum(1 for d in dezenas if d in PRIMES))
        soma_list.append(sum(dezenas))
    sets = [set(int(row[f"d{i}"]) for i in range(1, 16)) for _, row in df.iterrows()]
    rep_list = [len(sets[i] & sets[i - 1]) for i in range(1, len(sets))]
    atrasadas_list = []
    df_ciclo_hist = get_atraso_e_ciclo(df_concursos)
    atrasadas_hist = set(df_ciclo_hist[df_ciclo_hist["Atraso"] >= 3]["Dezena"].tolist())
    for _, row in df.iterrows():
        dezenas = [int(row[f"d{i}"]) for i in range(1, 16)]
        atrasadas_list.append(len(set(dezenas) & atrasadas_hist))
    def q(serie, p):
        if len(serie) == 0:
            return 0
        return int(round(pd.Series(serie).quantile(p)))
    min_pares = q(pares_list, 0.25)
    max_pares = max(min_pares, q(pares_list, 0.75))
    min_rep = q(rep_list, 0.25) if rep_list else 0
    max_rep = max(min_rep, q(rep_list, 0.75)) if rep_list else 15
    min_primos = q(primos_list, 0.25)
    max_primos = max(min_primos, q(primos_list, 0.75))
    min_atrasadas = int(round(pd.Series(atrasadas_list).median())) if atrasadas_list else 0
    return {
        "min_pares": min_pares, "max_pares": max_pares,
        "min_rep": min_rep, "max_rep": max_rep,
        "min_primos": min_primos, "max_primos": max_primos,
        "min_atrasadas": min_atrasadas,
        "soma_media": int(round(pd.Series(soma_list).mean())) if soma_list else 0,
    }

# =========================
# Configuração da Página Streamlit
# =========================
st.set_page_config(layout="wide", page_title="Dashboard Lotofácil")
st.title("🎲 Dashboard Lotofácil")
setup_folders()
create_table()
create_jogos_table()
adicionar_colunas_se_necessario()
if "caderno" not in st.session_state:
    st.session_state["caderno"] = []
if "grupos_tres" not in st.session_state:
    st.session_state["grupos_tres"] = None
    st.session_state["grupos_dois"] = None
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
                            exibir_resultado_aposta(calcular_resultado_aposta(concurso_num))
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
                    exibir_resultado_aposta(calcular_resultado_aposta(ultimo_importado["concurso"]))
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
        st.warning("Nenhum concurso cadastrado. Cadastre ou importe o resultado para gerar jogos.")
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
        st.caption(f"🤖 Ajuste automático (ROI da última aposta): robustez {ajuste['robustez']:+d} | atrasadas {ajuste['atrasadas']:+d} | repetições {ajuste['rep_min']:+d} a {ajuste['rep_max']:+d}")
    padrao = calcular_padrao_real(df_concursos_tab2)
    if padrao:
        st.caption(f"📈 Padrão real dos últimos 20 sorteios: pares {padrao['min_pares']}–{padrao['max_pares']} | repetições {padrao['min_rep']}–{padrao['max_rep']} | primos {padrao['min_primos']}–{padrao['max_primos']} | soma média {padrao['soma_media']}")
    col_filters1, col_filters2, col_filters3 = st.columns(3)
    with col_filters1:
        st.markdown("#### Repetições do Último Concurso")
        if padrao and last_contest:
            min_rep = st.slider("Mínimo de Repetições", 0, 15, max(0, padrao["min_rep"] + ajuste["rep_min"]))
            max_rep = st.slider("Máximo de Repetições", 0, 15, min(15, padrao["max_rep"] + ajuste["rep_max"]))
        else:
            min_rep = st.slider("Mínimo de Repetições", 0, 15, max(0, 9 + ajuste["rep_min"]) if last_contest else 0)
            max_rep = st.slider("Máximo de Repetições", 0, 15, min(15, 10 + ajuste["rep_max"]) if last_contest else 15)
        if min_rep > max_rep:
            st.error("Mínimo de repetições não pode ser maior que o máximo.")
    with col_filters2:
        st.markdown("#### Dezenas Pares")
        if padrao:
            min_pares = st.slider("Mínimo de Pares", 0, 15, padrao["min_pares"])
            max_pares = st.slider("Máximo de Pares", 0, 15, padrao["max_pares"])
        else:
            min_pares = st.slider("Mínimo de Pares", 0, 15, 7)
            max_pares = st.slider("Máximo de Pares", 0, 15, 8)
        if min_pares > max_pares:
            st.error("Mínimo de pares não pode ser maior que o máximo.")
    with col_filters3:
        st.markdown("#### Dezenas Primas")
        if padrao:
            min_primos = st.slider("Mínimo de Primos", 0, len(PRIMES), padrao["min_primos"])
            max_primos = st.slider("Máximo de Primos", 0, len(PRIMES), padrao["max_primos"])
        else:
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
        if len(atrasadas_set) == 0:
            st.info("Não há dezenas atrasadas no momento. Filtro de atrasadas desativado.")
            min_atrasadas = 0
        elif padrao:
            max_atrasadas = min(10, len(atrasadas_set))
            valor_padrao = max(0, min(padrao["min_atrasadas"] + ajuste["atrasadas"], max_atrasadas))
            min_atrasadas = st.slider("Mínimo de dezenas atrasadas por jogo", 0, max_atrasadas, valor_padrao)
        else:
            max_atrasadas = min(10, len(atrasadas_set))
            valor_padrao = max(0, min(4 + ajuste["atrasadas"], max_atrasadas))
            min_atrasadas = st.slider("Mínimo de dezenas atrasadas por jogo", 0, max_atrasadas, valor_padrao)
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
    st.subheader("Gerar Jogos Filtrados (16)")
    num_jogos_to_generate = st.radio("Quantos jogos deseja gerar?", (16, 32, 64, 128), horizontal=True)
    gerar_habilitado = not df_concursos_tab2.empty
    if st.button(f"Gerar {num_jogos_to_generate} Jogos Filtrados", disabled=not gerar_habilitado):
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
            st.success(f"{len(generated_games)} jogos filtrados gerados com sucesso!")
            salvar_jogos_gerados(generated_games, concurso_alvo=last_contest["concurso"] if last_contest else None, modalidade=MODALIDADE_FILTRADO)
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
    st.subheader("Gerar 10 Jogos por Grupos (nova formatação)")
    if st.button("🎲 Sortear Grupos (5x3 sorteadas + 5x2 restantes)", disabled=not gerar_habilitado):
        if not last_contest:
            st.warning("Cadastre o último concurso primeiro.")
        else:
            resultado = sortear_grupos(last_contest_dezenas)
            if resultado:
                st.session_state["grupos_tres"], st.session_state["grupos_dois"] = resultado
                st.success("Grupos sorteados! Confira e edite abaixo antes de combinar.")
    if st.session_state["grupos_tres"] is not None:
        st.markdown("#### Grupos Sorteados (edite se quiser)")
        grupos_tres = st.session_state["grupos_tres"]
        grupos_dois = st.session_state["grupos_dois"]
        col_a1, col_a2, col_a3, col_a4, col_a5 = st.columns(5)
        cols_a = [col_a1, col_a2, col_a3, col_a4, col_a5]
        for i, col in enumerate(cols_a):
            with col:
                st.markdown(f"**A{i+1}** (sorteadas)")
                grupos_tres[i] = sorted([int(x) for x in st.text_input(
                    f"A{i+1}", value=" ".join(f"{d:02d}" for d in grupos_tres[i]), key=f"a{i}"
                ).replace(",", " ").split() if x.strip()])
        col_b1, col_b2, col_b3, col_b4, col_b5 = st.columns(5)
        cols_b = [col_b1, col_b2, col_b3, col_b4, col_b5]
        for i, col in enumerate(cols_b):
            with col:
                st.markdown(f"**B{i+1}** (restantes)")
                grupos_dois[i] = sorted([int(x) for x in st.text_input(
                    f"B{i+1}", value=" ".join(f"{d:02d}" for d in grupos_dois[i]), key=f"b{i}"
                ).replace(",", " ").split() if x.strip()])
        st.divider()
        valido, mensagem = validar_grupos(grupos_tres, grupos_dois)
        if valido:
            st.success(mensagem)
        else:
            st.error(mensagem)
        st.markdown("#### Grupos de 5 (G1..G5 = A + B)")
        grupos_cinco = [sorted(grupos_tres[i] + grupos_dois[i]) for i in range(5)]
        for i in range(5):
            st.write(f"**G{i+1}**: {' '.join(f'{d:02d}' for d in grupos_cinco[i])}")
        if st.button("🎯 Gerar 10 Jogos (combinar G1..G5)", disabled=not valido):
            grupos_cinco_final, generated_games = combinar_grupos(grupos_tres, grupos_dois)
            if generated_games:
                st.success(f"{len(generated_games)} jogos gerados com sucesso!")
                salvar_jogos_gerados(generated_games, concurso_alvo=last_contest["concurso"] if last_contest else None, modalidade=MODALIDADE_GRUPOS)
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
        st.info("Clique em '🎲 Sortear Grupos' para começar.")
    st.divider()
    st.subheader("Caderno de Jogos")
    total_caderno = len(st.session_state["caderno"])
    st.write(f"Total de jogos no caderno: **{total_caderno}** (meta: 26 = 16 filtrados + 10 grupos)")
    exibir_resultado_aposta(get_resultado_ultima_aposta())
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
        if st.button("✅ Confirmar Aposta (usar caderno)"):
            if total_caderno == 0:
                st.warning("O caderno está vazio. Gere jogos primeiro.")
            else:
                proximo = (last_contest["concurso"] + 1) if last_contest else None
                marcados = marcar_aposta_confirmada(st.session_state["caderno"], proximo)
                st.success(f"Aposta confirmada: {marcados} jogo(s) marcados para o concurso {proximo}. Será conferido automaticamente ao cadastrar o resultado.")
        if st.button("Limpar Caderno"):
            st.session_state["caderno"] = []
            st.success("Caderno limpo.")

# =========================
# Aba 3: Editar Concurso
# =========================
with tab3:
    st.header("Editar Concurso Existente")
    all_concursos_df = fetch_all_concursos()
    if all_concursos_df.empty:
        st.info("Nenhum concurso cadastrado para editar.")
    else:
        concursos_list = all_concursos_df["concurso"].tolist()
        selected_concurso_num = st.selectbox("Selecione o Concurso para Editar", sorted(concursos_list, reverse=True))
        if selected_concurso_num:
            concurso_data = fetch_concurso(selected_concurso_num)
            if concurso_data:
                with st.form("form_editar_concurso"):
                    st.write(f"Editando Concurso **{selected_concurso_num}**")
                    current_data_br = iso_to_br(concurso_data["data"])
                    edited_data_br = st.text_input("Data do Sorteio (dd/mm/aaaa)", value=current_data_br)
                    current_dezenas = [concurso_data[f"d{i}"] for i in range(1, 16)]
                    edited_dezenas_str = st.text_input("Dezenas (separadas por espaço ou vírgula)", value=" ".join(f"{d:02d}" for d in current_dezenas))
                    update_submitted = st.form_submit_button("Atualizar Concurso")
                    if update_submitted:
                        edited_data_iso = normalize_date_input(edited_data_br)
                        if not edited_data_iso:
                            st.error("Formato de data inválido. Use dd/mm/aaaa.")
                        else:
                            is_valid, dezenas_validadas = validate_dezenas(edited_dezenas_str.replace(",", " ").split())
                            if is_valid:
                                if update_concurso(selected_concurso_num, edited_data_iso, dezenas_validadas):
                                    st.success(f"Concurso {selected_concurso_num} atualizado com sucesso!")
                                else:
                                    st.error("Falha ao atualizar concurso.")
                            else:
                                st.error(dezenas_validadas)
            else:
                st.error("Dados do concurso selecionado não encontrados.")

# =========================
# Aba 4: Análise de Dados (apenas Comparativo de Modalidades)
# =========================
with tab4:
    st.header("📊 Comparativo entre Modalidades (Filtrado vs Grupos)")
    df_comp = comparativo_modalidades()
    if df_comp is None or df_comp.empty:
        st.info("Ainda não há apostas confirmadas e conferidas para comparar. Confirme apostas e cadastre resultados para ver o comparativo.")
    else:
        st.dataframe(df_comp, use_container_width=True)
        if len(df_comp) == 2:
            linha_f = df_comp[df_comp["Modalidade"].str.contains("Filtrado")]
            linha_g = df_comp[df_comp["Modalidade"].str.contains("Grupos")]
            if not linha_f.empty and not linha_g.empty:
                saldo_f = float(linha_f.iloc[0]["Saldo"])
                saldo_g = float(linha_g.iloc[0]["Saldo"])
                taxa_f = float(linha_f.iloc[0]["Taxa 11+"].replace("%", ""))
                taxa_g = float(linha_g.iloc[0]["Taxa 11+"].replace("%", ""))
                if saldo_f > saldo_g:
                    st.success(f"🏆 Modalidade **Filtrado** está com melhor saldo (R$ {saldo_f:.2f} vs R$ {saldo_g:.2f}).")
                elif saldo_g > saldo_f:
                    st.success(f"🏆 Modalidade **Grupos** está com melhor saldo (R$ {saldo_g:.2f} vs R$ {saldo_f:.2f}).")
                else:
                    st.info("As duas modalidades estão empatadas em saldo.")
                st.caption(f"Taxa de acerto 11+: Filtrado {taxa_f:.1f}% | Grupos {taxa_g:.1f}%")