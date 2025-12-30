import streamlit as st
import pandas as pd
import sqlite3
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO

st.set_page_config("GymManager Pro", layout="wide")

# =============================
# BANCO
# =============================
def conn():
    return sqlite3.connect("gym.db", check_same_thread=False)

def init_db():
    con = conn()
    c = con.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        login TEXT UNIQUE,
        senha TEXT,
        role TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS tipos_treino (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS treinos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        tipo_treino TEXT,
        exercicio TEXT,
        series INTEGER,
        repeticoes TEXT,
        carga REAL
    )
    """)

    # admin padrão
    c.execute("""
    INSERT OR IGNORE INTO usuarios (nome, login, senha, role)
    VALUES ('Administrador','admin','admin','admin')
    """)

    # tipos padrão
    tipos = ["Costas","Peito","Pernas","Ombro","Braços","Abdômen","Full Body"]
    for t in tipos:
        c.execute("INSERT OR IGNORE INTO tipos_treino (nome) VALUES (?)", (t,))

    con.commit()
    con.close()

init_db()

# =============================
# LOGIN
# =============================
def login():
    st.title("🏋️ GymManager Pro")

    login = st.text_input("Login")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        df = pd.read_sql(
            "SELECT * FROM usuarios WHERE login=? AND senha=?",
            conn(), params=(login, senha)
        )

        if df.empty:
            st.error("Credenciais inválidas")
        else:
            st.session_state.user = df.iloc[0].to_dict()
            st.rerun()

# =============================
# PDF
# =============================
def gerar_pdf(nome, treinos):
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    y = A4[1] - 50

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, f"Ficha de Treino - {nome}")
    y -= 40

    for tipo, exs in treinos.items():
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y, tipo)
        y -= 20
        pdf.setFont("Helvetica", 10)

        for ex in exs:
            pdf.drawString(
                60, y,
                f"{ex['exercicio']} | {ex['series']}x{ex['repeticoes']} | {ex['carga']}kg"
            )
            y -= 15

        y -= 10

    pdf.save()
    buf.seek(0)
    return buf

# =============================
# ADMIN
# =============================
def painel_admin():
    st.sidebar.title("🔐 Admin")

    menu = st.sidebar.radio(
        "Menu",
