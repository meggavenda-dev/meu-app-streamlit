import streamlit as st
import pandas as pd
import sqlite3
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO

st.set_page_config(page_title="GymManager Pro", layout="wide")

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

    # Admin padrão
    c.execute("""
    INSERT OR IGNORE INTO usuarios (nome, login, senha, role)
    VALUES ('Administrador', 'admin', 'admin', 'admin')
    """)

    # Tipos padrão
    tipos = ["Costas", "Peito", "Pernas", "Ombro", "Braços", "Abdômen", "Full Body"]
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

    login_user = st.text_input("Login", key="login_user")
    senha = st.text_input("Senha", type="password", key="login_senha")

    if st.button("Entrar"):
        df = pd.read_sql(
            "SELECT * FROM usuarios WHERE login=? AND senha=?",
            conn(),
            params=(login_user, senha)
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
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = A4[1] - 50

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, f"Ficha de Treino - {nome}")
    y -= 40

    for tipo, exercicios in treinos.items():
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y, tipo)
        y -= 20
        pdf.setFont("Helvetica", 10)

        for ex in exercicios:
            pdf.drawString(
                60, y,
                f"{ex['exercicio']} | {ex['series']}x{ex['repeticoes']} | {ex['carga']}kg"
            )
            y -= 15

            if y < 80:
                pdf.showPage()
                y = A4[1] - 50

        y -= 10

    pdf.save()
    buffer.seek(0)
    return buffer

# =============================
# PAINEL ADMIN
# =============================
def painel_admin():
    st.sidebar.title("🔐 Admin")

    menu = st.sidebar.radio(
        "Menu",
        ["Cadastrar Aluno", "Tipos de Treino", "Montar Treino"]
    )

    if menu == "Cadastrar Aluno":
        st.header("➕ Cadastrar Aluno")

        nome = st.text_input("Nome do aluno")
        login_aluno = st.text_input("Login")
        senha = st.text_input("Senha", type="password")

        if st.button("Cadastrar"):
            try:
                conn().execute(
                    "INSERT INTO usuarios (nome, login, senha, role) VALUES (?, ?, ?, 'aluno')",
                    (nome, login_aluno, senha)
                )
                conn().commit()
                st.success("Aluno cadastrado com sucesso")
            except:
                st.error("Login já existe")

    elif menu == "Tipos de Treino":
        st.header("🏷️ Tipos de Treino")

        novo = st.text_input("Novo tipo")
        if st.button("Adicionar"):
            try:
                conn().execute("INSERT INTO tipos_treino (nome) VALUES (?)", (novo,))
                conn().commit()
                st.success("Tipo adicionado")
            except:
                st.warning("Tipo já existe")

        df = pd.read_sql("SELECT nome FROM tipos_treino ORDER BY nome", conn())
        st.dataframe(df, use_container_width=True)

    elif menu == "Montar Treino":
        st.header("🏋️ Montar Treino")

        alunos = pd.read_sql(
            "SELECT id, nome FROM usuarios WHERE role='aluno'",
            conn()
        )
        tipos = pd.read_sql("SELECT nome FROM tipos_treino", conn())

        if alunos.empty:
            st.warning("Nenhum aluno cadastrado")
            return

        aluno_nome = st.selectbox("Aluno", alunos["nome"])
        aluno_id = alunos[alunos["nome"] == aluno_nome]["id"].values[0]
        tipo = st.selectbox("Tipo de treino", tipos["nome"])

        exercicio = st.text_input("Exercício")
        series = st.number_input("Séries", 1)
        repeticoes = st.text_input("Repetições")
        carga = st.number_input("Carga (kg)", 0.0)

        if st.button("Adicionar exercício"):
            conn().execute(
                "INSERT INTO treinos VALUES (NULL,?,?,?,?,?,?)",
                (aluno_id, tipo, exercicio, series, repeticoes, carga)
            )
            conn().commit()
            st.success("Exercício adicionado")

# =============================
# PAINEL ALUNO
# =============================
def painel_aluno():
    st.header("🏋️ Meu Treino")

    df = pd.read_sql(
        "SELECT tipo_treino, exercicio, series, repeticoes, carga FROM treinos WHERE usuario_id=?",
        conn(),
        params=(st.session_state.user["id"],)
    )

    if df.empty:
        st.info("Nenhum treino cadastrado.")
        return

    st.dataframe(df, use_container_width=True)

    treinos = df.groupby("tipo_treino").apply(
        lambda x: x.to_dict("records")
    ).to_dict()

    pdf = gerar_pdf(st.session_state.user["nome"], treinos)
    st.download_button("📄 Baixar PDF", pdf, "meu_treino.pdf")

# =============================
# MAIN
# =============================
if "user" not in st.session_state:
    login()
else:
    st.sidebar.write(f"👤 {st.session_state.user['nome']}")

    if st.sidebar.button("Sair"):
        st.session_state.clear()
        st.rerun()

    if st.session_state.user["role"] == "admin":
        painel_admin()
    else:
        painel_aluno()
