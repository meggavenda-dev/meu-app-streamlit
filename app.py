import streamlit as st
import pandas as pd
import sqlite3
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO

# =============================
# CONFIG
# =============================
st.set_page_config("GymManager Pro", layout="wide")

# =============================
# BANCO
# =============================
def conn():
    return sqlite3.connect("gym.db", check_same_thread=False)

def criar_tabelas():
    c = conn().cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        email TEXT UNIQUE,
        senha TEXT
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

    c.connection.commit()

def seed_tipos():
    tipos = ["Costas", "Peito", "Pernas", "Ombro", "Braços", "Abdômen", "Full Body"]
    con = conn()
    for t in tipos:
        try:
            con.execute("INSERT INTO tipos_treino (nome) VALUES (?)", (t,))
        except:
            pass
    con.commit()
    con.close()

criar_tabelas()
seed_tipos()

# =============================
# LOGIN / CADASTRO
# =============================
def login():
    st.title("🏋️ GymManager Pro")

    tab1, tab2 = st.tabs(["Login", "Cadastro"])

    with tab1:
        email = st.text_input("Email")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            df = pd.read_sql(
                "SELECT * FROM usuarios WHERE email=? AND senha=?",
                conn(), params=(email, senha)
            )
            if df.empty:
                st.error("Credenciais inválidas")
            else:
                st.session_state.usuario_id = df.iloc[0]["id"]
                st.session_state.nome = df.iloc[0]["nome"]
                st.rerun()

    with tab2:
        nome = st.text_input("Nome")
        email = st.text_input("Email", key="cad_email")
        senha = st.text_input("Senha", type="password", key="cad_senha")
        if st.button("Criar Conta"):
            try:
                conn().execute(
                    "INSERT INTO usuarios (nome,email,senha) VALUES (?,?,?)",
                    (nome,email,senha)
                )
                conn().commit()
                st.success("Conta criada! Faça login.")
            except:
                st.error("Email já cadastrado")

# =============================
# PDF
# =============================
def gerar_pdf(nome, treinos):
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    y = A4[1] - 50

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, f"Treino - {nome}")
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

            if y < 80:
                pdf.showPage()
                y = A4[1] - 50

        y -= 10

    pdf.save()
    buf.seek(0)
    return buf

# =============================
# APP
# =============================
def app():
    st.sidebar.write(f"👤 {st.session_state.nome}")

    st.header("🏋️ Meu Treino")

    tipos = pd.read_sql("SELECT nome FROM tipos_treino ORDER BY nome", conn())["nome"].tolist()

    tipo = st.selectbox("Tipo de treino", tipos)
    novo_tipo = st.text_input("Ou criar novo tipo de treino")

    if novo_tipo:
        try:
            conn().execute("INSERT INTO tipos_treino (nome) VALUES (?)", (novo_tipo,))
            conn().commit()
            tipo = novo_tipo
            st.success("Tipo criado!")
        except:
            st.warning("Tipo já existe")

    with st.form("treino"):
        ex = st.text_input("Exercício")
        s = st.number_input("Séries", 1)
        r = st.text_input("Repetições")
        c = st.number_input("Carga (kg)", 0.0)
        if st.form_submit_button("Adicionar"):
            conn().execute(
                "INSERT INTO treinos VALUES (NULL,?,?,?,?,?,?)",
                (st.session_state.usuario_id, tipo, ex, s, r, c)
            )
            conn().commit()
            st.success("Exercício adicionado")

    df = pd.read_sql(
        "SELECT tipo_treino, exercicio, series, repeticoes, carga FROM treinos WHERE usuario_id=?",
        conn(), params=(st.session_state.usuario_id,)
    )

    if not df.empty:
        st.dataframe(df, use_container_width=True)

        treinos = df.groupby("tipo_treino").apply(lambda x: x.to_dict("records")).to_dict()
        pdf = gerar_pdf(st.session_state.nome, treinos)
        st.download_button("📄 Baixar PDF", pdf, "meu_treino.pdf")

# =============================
# MAIN
# =============================
if "usuario_id" not in st.session_state:
    login()
else:
    app()
