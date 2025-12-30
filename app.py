import streamlit as st
import pandas as pd
import sqlite3
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO

# =============================
# CONFIGURAÇÃO
# =============================
st.set_page_config("GymManager Pro", layout="wide")

# =============================
# BANCO
# =============================
def get_connection():
    return sqlite3.connect("gym.db", check_same_thread=False)

def criar_tabelas():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        email TEXT UNIQUE,
        senha TEXT,
        perfil TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS alunos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        objetivo TEXT,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
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
        aluno_id INTEGER,
        tipo_treino TEXT,
        exercicio TEXT,
        series INTEGER,
        repeticoes TEXT,
        carga REAL
    )
    """)

    conn.commit()
    conn.close()

criar_tabelas()

# =============================
# LOGIN
# =============================
def login():
    st.title("🔐 Login")

    email = st.text_input("Email")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        conn = get_connection()
        df = pd.read_sql(
            "SELECT * FROM usuarios WHERE email=? AND senha=?",
            conn,
            params=(email, senha)
        )
        conn.close()

        if df.empty:
            st.error("Login inválido")
        else:
            user = df.iloc[0]
            st.session_state.usuario_id = user["id"]
            st.session_state.nome = user["nome"]
            st.session_state.perfil = user["perfil"]
            st.rerun()

# =============================
# PDF
# =============================
def gerar_pdf(aluno, objetivo, treinos):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = A4[1] - 50

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "Ficha de Treino")
    y -= 30

    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, y, f"Aluno: {aluno}")
    y -= 20
    pdf.drawString(50, y, f"Objetivo: {objetivo}")
    y -= 30

    for treino, exercicios in treinos.items():
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y, treino)
        y -= 20
        pdf.setFont("Helvetica", 10)

        for ex in exercicios:
            linha = f"{ex['exercicio']} | {ex['series']}x {ex['repeticoes']} | {ex['carga']}kg"
            pdf.drawString(60, y, linha)
            y -= 15

            if y < 80:
                pdf.showPage()
                y = A4[1] - 50

    pdf.save()
    buffer.seek(0)
    return buffer

# =============================
# TELAS PERSONAL
# =============================
def cadastrar_aluno():
    st.header("➕ Cadastrar Aluno")

    with st.form("cad_aluno"):
        nome = st.text_input("Nome")
        email = st.text_input("Email")
        senha = st.text_input("Senha")
        objetivo = st.selectbox("Objetivo", ["Hipertrofia", "Emagrecimento", "Condicionamento"])
        submit = st.form_submit_button("Cadastrar")

        if submit:
            conn = get_connection()
            c = conn.cursor()
            try:
                c.execute(
                    "INSERT INTO usuarios (nome,email,senha,perfil) VALUES (?,?,?,?)",
                    (nome,email,senha,"aluno")
                )
                usuario_id = c.lastrowid

                c.execute(
                    "INSERT INTO alunos (usuario_id, objetivo) VALUES (?,?)",
                    (usuario_id, objetivo)
                )
                conn.commit()
                st.success("Aluno cadastrado com login!")
            except:
                st.error("Erro ao cadastrar.")
            conn.close()

def cadastrar_tipo_treino():
    st.header("🏷️ Tipos de Treino")
    nome = st.text_input("Nome")
    if st.button("Salvar"):
        conn = get_connection()
        try:
            conn.execute("INSERT INTO tipos_treino (nome) VALUES (?)", (nome,))
            conn.commit()
            st.success("Cadastrado!")
        except:
            st.error("Já existe.")
        conn.close()

def montar_treino():
    st.header("🏋️ Montar Treino")

    conn = get_connection()
    alunos = pd.read_sql("""
        SELECT alunos.id, usuarios.nome 
        FROM alunos 
        JOIN usuarios ON usuarios.id = alunos.usuario_id
    """, conn)

    tipos = pd.read_sql("SELECT nome FROM tipos_treino", conn)
    conn.close()

    aluno_nome = st.selectbox("Aluno", alunos["nome"])
    aluno_id = alunos[alunos["nome"] == aluno_nome]["id"].values[0]
    tipo = st.selectbox("Tipo de treino", tipos["nome"])

    with st.form("treino"):
        ex = st.text_input("Exercício")
        s = st.number_input("Séries", 1)
        r = st.text_input("Repetições")
        c = st.number_input("Carga", 0.0)
        submit = st.form_submit_button("Adicionar")

        if submit:
            conn = get_connection()
            conn.execute(
                "INSERT INTO treinos VALUES (NULL,?,?,?,?,?,?)",
                (aluno_id, tipo, ex, s, r, c)
            )
            conn.commit()
            conn.close()
            st.success("Exercício adicionado")

# =============================
# TELA ALUNO
# =============================
def meu_treino():
    st.header("📋 Meu Treino")

    conn = get_connection()
    aluno = pd.read_sql(
        "SELECT * FROM alunos WHERE usuario_id=?",
        conn,
        params=(st.session_state.usuario_id,)
    ).iloc[0]

    df = pd.read_sql(
        "SELECT tipo_treino, exercicio, series, repeticoes, carga FROM treinos WHERE aluno_id=?",
        conn,
        params=(aluno["id"],)
    )
    conn.close()

    if df.empty:
        st.info("Nenhum treino cadastrado.")
        return

    st.dataframe(df)

    treinos = df.groupby("tipo_treino").apply(lambda x: x.to_dict("records")).to_dict()
    pdf = gerar_pdf(st.session_state.nome, aluno["objetivo"], treinos)

    st.download_button("📄 Baixar PDF", pdf, "meu_treino.pdf")

# =============================
# MAIN
# =============================
if "usuario_id" not in st.session_state:
    login()
else:
    st.sidebar.write(f"👤 {st.session_state.nome}")
    if st.session_state.perfil == "personal":
        menu = st.sidebar.radio("Menu", ["Cadastrar Aluno", "Tipos de Treino", "Montar Treino"])
        if menu == "Cadastrar Aluno":
            cadastrar_aluno()
        elif menu == "Tipos de Treino":
            cadastrar_tipo_treino()
        else:
            montar_treino()
    else:
        meu_treino()
