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

    # usuário master
    c.execute("""
    INSERT OR IGNORE INTO usuarios (nome, login, senha, role)
    VALUES ('Administrador', 'admin', 'admin', 'master')
    """)

    con.commit()
    con.close()

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
# LOGIN
# =============================
def tela_login():
    st.title("🏋️ GymManager Pro")

    tab1, tab2 = st.tabs(["Login", "Cadastro"])

    with tab1:
        login = st.text_input("Login", key="login_user")
        senha = st.text_input("Senha", type="password", key="login_pass")

        if st.button("Entrar", key="btn_login"):
            df = pd.read_sql(
                "SELECT * FROM usuarios WHERE login=? AND senha=?",
                conn(), params=(login, senha)
            )
            if df.empty:
                st.error("Credenciais inválidas")
            else:
                st.session_state.usuario = df.iloc[0].to_dict()
                st.rerun()

    with tab2:
        nome = st.text_input("Nome", key="cad_nome")
        login = st.text_input("Login", key="cad_login")
        senha = st.text_input("Senha", type="password", key="cad_senha")

        if st.button("Criar Conta", key="btn_cadastro"):
            try:
                conn().execute(
                    "INSERT INTO usuarios (nome, login, senha, role) VALUES (?,?,?,'aluno')",
                    (nome, login, senha)
                )
                conn().commit()
                st.success("Conta criada! Faça login.")
            except:
                st.error("Login já existe")

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
            if y < 80:
                pdf.showPage()
                y = A4[1] - 50

        y -= 10

    pdf.save()
    buf.seek(0)
    return buf

# =============================
# MASTER
# =============================
def painel_master():
    st.header("🔐 Painel Master")

    st.subheader("Tipos de Treino")
    novo = st.text_input("Novo tipo", key="novo_tipo")
    if st.button("Adicionar", key="btn_tipo"):
        try:
            conn().execute("INSERT INTO tipos_treino (nome) VALUES (?)", (novo,))
            conn().commit()
            st.success("Tipo adicionado")
        except:
            st.warning("Tipo já existe")

    tipos = pd.read_sql("SELECT nome FROM tipos_treino ORDER BY nome", conn())
    st.dataframe(tipos, use_container_width=True)

    st.subheader("Usuários")
    usuarios = pd.read_sql("SELECT nome, login, role FROM usuarios", conn())
    st.dataframe(usuarios, use_container_width=True)

# =============================
# ALUNO
# =============================
def painel_aluno():
    st.header("🏋️ Meu Treino")

    tipos = pd.read_sql("SELECT nome FROM tipos_treino", conn())["nome"].tolist()
    tipo = st.selectbox("Tipo de treino", tipos, key="tipo_treino")

    with st.form("form_treino"):
        ex = st.text_input("Exercício")
        s = st.number_input("Séries", 1)
        r = st.text_input("Repetições")
        c = st.number_input("Carga", 0.0)
        if st.form_submit_button("Adicionar"):
            conn().execute(
                "INSERT INTO treinos VALUES (NULL,?,?,?,?,?,?)",
                (st.session_state.usuario["id"], tipo, ex, s, r, c)
            )
            conn().commit()
            st.success("Exercício adicionado")

    df = pd.read_sql(
        "SELECT tipo_treino, exercicio, series, repeticoes, carga FROM treinos WHERE usuario_id=?",
        conn(), params=(st.session_state.usuario["id"],)
    )

    if not df.empty:
        st.dataframe(df, use_container_width=True)
        treinos = df.groupby("tipo_treino").apply(lambda x: x.to_dict("records")).to_dict()
        pdf = gerar_pdf(st.session_state.usuario["nome"], treinos)
        st.download_button("📄 Baixar PDF", pdf, "meu_treino.pdf")

# =============================
# MAIN
# =============================
if "usuario" not in st.session_state:
    tela_login()
else:
    st.sidebar.write(f"👤 {st.session_state.usuario['nome']}")
    if st.sidebar.button("Sair"):
        st.session_state.clear()
        st.rerun()

    if st.session_state.usuario["role"] == "master":
        painel_master()
    else:
        painel_aluno()
