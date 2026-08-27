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
                st.error("Arquivo Excel não encontrado em: " + str(arquivo_xlsx))
                return 0, 0
            df = pd.read_excel(arquivo_xlsx, sheet_name=sheet_name, engine="openpyxl")
    except Exception as e:
        st.error('Erro ao ler o arquivo Excel ou aba ' + str(sheet_name) + ': ' + str(e))
        return 0, 0

    # CORREÇÃO: define e valida as colunas obrigatórias
    df.columns = [str(c).strip() for c in df.columns]
    required_cols = ["Concurso", "Data Sorteio"] + [f"Bola{i}" for i in range(1, 16)]
    faltando = [c for c in required_cols if c not in df.columns]
    if faltando:
        st.error("Colunas obrigatórias não encontradas no Excel: " + ", ".join(faltando))
        return 0, 0

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
            st.warning("Concurso " + str(concurso_num) + " ignorado por dezenas inválidas: " + str(validated_dezenas))
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
            st.error("Erro ao inserir concurso " + str(concurso_num) + " do Excel: " + str(e))
    conn.commit()
    conn.close()
    return inseridos, duplicados
