import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import hashlib
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime

# =============================
# CONFIGURAÇÃO DA PÁGINA
# =============================
st.set_page_config(page_title="GymManager Pro v3.0", layout="wide", page_icon="🏋️")

# =============================
# SEGURANÇA E BANCO DE DADOS
# =============================
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

def get_connection():
    return sqlite3.connect("gym_v3.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Usuários
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT, login TEXT UNIQUE, senha TEXT, role TEXT,
        status_pagamento TEXT DEFAULT 'Em dia', objetivo TEXT)""")

    # Tipos de treino
    c.execute("CREATE TABLE IF NOT EXISTS tipos_treino (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)")

    # Treinos
    c.execute("""CREATE TABLE IF NOT EXISTS treinos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER, tipo_treino TEXT,
        exercicio TEXT, series INTEGER, repeticoes TEXT, carga REAL,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")

    # Medidas
    c.execute("""CREATE TABLE IF NOT EXISTS medidas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER,
        peso REAL, cintura REAL, braco REAL, data TEXT,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")

    # Admin padrão
    admin_hash = make_hashes('admin123')
    c.execute("INSERT OR IGNORE INTO usuarios (nome, login, senha, role) VALUES (?,?,?,?)",
              ('Master Admin', 'admin', admin_hash, 'admin'))

    # Tipos de treino iniciais
    tipos = ["Costas", "Peito", "Pernas", "Ombro", "Braços", "Abdômen", "Cardio"]
    for t in tipos:
        c.execute("INSERT OR IGNORE INTO tipos_treino (nome) VALUES (?)", (t,))

    conn.commit()
    conn.close()

init_db()

# =============================
# FUNÇÕES DE LOGIN / CADASTRO
# =============================
def login():
    st.title("🏋️ GymManager Pro - Login/Cadastro")

    if "user" not in st.session_state:
        st.session_state.user = None

    tab1, tab2 = st.tabs(["Login", "Cadastro"])

    # LOGIN
    with tab1:
        u = st.text_input("Usuário", key="login_u")
        s = st.text_input("Senha", type="password", key="login_s")
        entrar = st.button("Entrar", key="login_btn")
        if entrar:
            if not u or not s:
                st.error("Preencha todos os campos")
            else:
                conn = get_connection()
                c = conn.cursor()
                c.execute("SELECT * FROM usuarios WHERE login=?", (u,))
                user_data = c.fetchone()
                conn.close()
                if user_data and check_hashes(s, user_data[3]):
                    st.session_state.user = {
                        "id": user_data[0],
                        "nome": user_data[1],
                        "login": user_data[2],
                        "role": user_data[4],
                        "status": user_data[5],
                        "objetivo": user_data[6]
                    }
                    st.success(f"Bem-vindo(a) {user_data[1]}!")
                else:
                    st.error("Usuário ou senha incorretos")

    # CADASTRO
    with tab2:
        nome = st.text_input("Nome", key="cad_nome")
        login_input = st.text_input("Login", key="cad_login")
        senha_input = st.text_input("Senha", type="password", key="cad_senha")
        objetivo_input = st.selectbox("Objetivo", ["Hipertrofia", "Emagrecimento", "Condicionamento", "Saúde"])
        criar = st.button("Criar Conta", key="cad_btn")
        if criar:
            if not nome or not login_input or not senha_input:
                st.error("Preencha todos os campos")
            else:
                try:
                    h = make_hashes(senha_input)
                    conn = get_connection()
                    conn.execute("INSERT INTO usuarios (nome,login,senha,role,objetivo) VALUES (?,?,?,?,?)",
                                 (nome, login_input, h, 'aluno', objetivo_input))
                    conn.commit()
                    conn.close()
                    st.success("Conta criada! Faça login.")
                except:
                    st.error("Login já existe")

# =============================
# FUNÇÕES DE APP
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

# Painel Admin
def painel_admin():
    st.sidebar.title("🔐 Gestão Gym")
    menu = st.sidebar.selectbox("Menu", ["Alunos", "Montar Treinos", "Financeiro & Config"])
    conn = get_connection()

    if menu == "Alunos":
        st.header("👥 Gestão de Alunos")
        with st.expander("➕ Cadastrar Novo Aluno"):
            col1, col2 = st.columns(2)
            n = col1.text_input("Nome Completo")
            l = col2.text_input("Login (Único)")
            p = col1.text_input("Senha Inicial", type="password")
            obj = col2.selectbox("Objetivo", ["Hipertrofia", "Emagrecimento", "Condicionamento", "Saúde"])
            if st.button("Finalizar Cadastro"):
                try:
                    h = make_hashes(p)
                    conn.execute("INSERT INTO usuarios (nome,login,senha,role,objetivo) VALUES (?,?,?,?,?)",
                                 (n, l, h, 'aluno', obj))
                    conn.commit()
                    st.success("Aluno cadastrado com sucesso!")
                except:
                    st.error("Erro: Login já existe.")

        st.subheader("Lista de Alunos Ativos")
        alunos_df = pd.read_sql("SELECT id, nome, login, status_pagamento, objetivo FROM usuarios WHERE role='aluno'", conn)
        st.dataframe(alunos_df, use_container_width=True)

    elif menu == "Montar Treinos":
        st.header("📋 Prescrição de Treino")
        alunos = pd.read_sql("SELECT id, nome FROM usuarios WHERE role='aluno'", conn)
        if not alunos.empty:
            sel_aluno = st.selectbox("Selecione o Aluno", alunos["nome"])
            a_id = int(alunos[alunos["nome"] == sel_aluno]["id"].values[0])
            with st.form("ficha"):
                c1, c2, c3, c4, c5 = st.columns([2,2,1,1,1])
                tp = c1.selectbox("Grupamento", pd.read_sql("SELECT nome FROM tipos_treino", conn))
                ex = c2.text_input("Exercício")
                se = c3.number_input("Séries", 1, 10, 3)
                re = c4.text_input("Reps", "12")
                ca = c5.number_input("Carga(kg)", 0.0)
                if st.form_submit_button("Adicionar à Ficha"):
                    conn.execute("INSERT INTO treinos (usuario_id, tipo_treino, exercicio, series, repeticoes, carga) VALUES (?,?,?,?,?,?)",
                                 (a_id, tp, ex, se, re, ca))
                    conn.commit()
                    st.success("Exercício adicionado!")

# Painel Aluno
def painel_aluno():
    u_id = st.session_state.user["id"]
    conn = get_connection()
    
    st.title(f"Olá, {st.session_state.user['nome']}! 👋")

    tab1, tab2, tab3 = st.tabs(["🏋️ Meu Treino", "📊 Minha Evolução", "⚙️ Perfil"])

    with tab1:
        st.subheader("Ficha de Treino Atual")
        df = pd.read_sql("SELECT * FROM treinos WHERE usuario_id=?", conn, params=(u_id,))
        if df.empty:
            st.info("Sua ficha ainda não foi montada.")
        else:
            for t in df["tipo_treino"].unique():
                with st.expander(f"TREINO DE {t.upper()}", expanded=True):
                    sub_df = df[df["tipo_treino"] == t]
                    for _, row in sub_df.iterrows():
                        col1, col2 = st.columns([3,1])
                        col1.write(f"**{row['exercicio']}** | {row['series']}x{row['repeticoes']} | {row['carga']}kg")
    
    with tab2:
        st.subheader("Registrar Progresso")
        with st.form("medidas_form"):
            c1, c2, c3 = st.columns(3)
            p = c1.number_input("Peso Atual (kg)", 0.0)
            ci = c2.number_input("Cintura (cm)", 0.0)
            br = c3.number_input("Braço (cm)", 0.0)
            if st.form_submit_button("Salvar Medidas"):
                conn.execute("INSERT INTO medidas (usuario_id, peso, cintura, braco, data) VALUES (?,?,?,?,?)",
                             (u_id, p, ci, br, datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.success("Medidas atualizadas!")

# =============================
# LÓGICA PRINCIPAL
# =============================
if "user" not in st.session_state or st.session_state.user is None:
    login()
else:
    if st.sidebar.button("🚪 Sair"):
        st.session_state.clear()
        st.experimental_rerun()

    if st.session_state.user["role"] == "admin":
        painel_admin()
    else:
        painel_aluno()
