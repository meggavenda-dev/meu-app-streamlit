import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import hashlib
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
import time

# =============================
# CONFIGURAÇÃO DA PÁGINA
# =============================
st.set_page_config(page_title="GymManager Pro v3.1", layout="wide", page_icon="🏋️")

# Estilo CSS para cards e métricas
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #ff4b4b;
    }
    </style>
""", unsafe_allow_html=True)

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
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT, login TEXT UNIQUE, senha TEXT, role TEXT,
        status_pagamento TEXT DEFAULT 'Em dia', objetivo TEXT)""")
    
    c.execute("CREATE TABLE IF NOT EXISTS tipos_treino (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)")
    
    c.execute("""CREATE TABLE IF NOT EXISTS treinos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER, tipo_treino TEXT,
        exercicio TEXT, series INTEGER, repeticoes TEXT, carga REAL,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")

    c.execute("""CREATE TABLE IF NOT EXISTS medidas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER,
        peso REAL, cintura REAL, braco REAL, data TEXT,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")

    admin_hash = make_hashes('admin123')
    c.execute("INSERT OR IGNORE INTO usuarios (nome, login, senha, role) VALUES (?,?,?,?)",
              ('Master Admin', 'admin', admin_hash, 'admin'))

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
    st.title("🏋️ GymManager Pro")
    
    tab1, tab2 = st.tabs(["Acessar Conta", "Novo Cadastro"])

    with tab1:
        with st.form("login_form"):
            u = st.text_input("Usuário")
            s = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                conn = get_connection()
                c = conn.cursor()
                c.execute("SELECT * FROM usuarios WHERE login=?", (u,))
                user_data = c.fetchone()
                conn.close()
                
                if user_data and check_hashes(s, user_data[3]):
                    st.session_state.user = {
                        "id": user_data[0], "nome": user_data[1],
                        "login": user_data[2], "role": user_data[4],
                        "status": user_data[5], "objetivo": user_data[6]
                    }
                    st.rerun() # Correção: Força o recarregamento imediato
                else:
                    st.error("Credenciais inválidas")

    with tab2:
        with st.form("cad_form"):
            nome = st.text_input("Nome Completo")
            login_in = st.text_input("Login")
            senha_in = st.text_input("Senha", type="password")
            obj = st.selectbox("Seu Objetivo", ["Hipertrofia", "Emagrecimento", "Condicionamento"])
            if st.form_submit_button("Criar Conta"):
                try:
                    conn = get_connection()
                    conn.execute("INSERT INTO usuarios (nome,login,senha,role,objetivo) VALUES (?,?,?,?,?)",
                                 (nome, login_in, make_hashes(senha_in), 'aluno', obj))
                    conn.commit()
                    st.success("Conta criada! Vá para a aba Login.")
                except:
                    st.error("Este login já está em uso.")

# =============================
# PAINEL ADMINISTRATIVO
# =============================
def painel_admin():
    st.sidebar.title(f"🛠️ Admin: {st.session_state.user['nome']}")
    menu = st.sidebar.radio("Navegação", ["Dashboard Alunos", "Prescrever Treino", "Financeiro"])
    conn = get_connection()

    if menu == "Dashboard Alunos":
        st.header("👥 Gestão de Alunos")
        df_alunos = pd.read_sql("SELECT id, nome, status_pagamento, objetivo FROM usuarios WHERE role='aluno'", conn)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Alunos", len(df_alunos))
        col2.metric("Inadimplentes", len(df_alunos[df_alunos['status_pagamento'] != 'Em dia']))
        
        st.dataframe(df_alunos, use_container_width=True)

    elif menu == "Prescrever Treino":
        st.header("📋 Montar Ficha")
        alunos = pd.read_sql("SELECT id, nome FROM usuarios WHERE role='aluno'", conn)
        sel_aluno = st.selectbox("Aluno", alunos["nome"])
        a_id = int(alunos[alunos["nome"] == sel_aluno]["id"].values[0])
        
        with st.expander("➕ Adicionar Exercício"):
            with st.form("add_ex"):
                c1, c2, c3, c4 = st.columns([2,2,1,1])
                tp = c1.selectbox("Tipo", ["Peito", "Costas", "Pernas", "Ombro", "Braços", "Cardio"])
                ex = c2.text_input("Exercício")
                se = c3.number_input("Séries", 1, 10, 3)
                ca = c4.number_input("Carga (kg)", 0.0)
                re = st.text_input("Repetições (Ex: 12 ou Até a falha)")
                if st.form_submit_button("Salvar na Ficha"):
                    conn.execute("INSERT INTO treinos (usuario_id, tipo_treino, exercicio, series, repeticoes, carga) VALUES (?,?,?,?,?,?)",
                                 (a_id, tp, ex, se, re, ca))
                    conn.commit()
                    st.rerun()

    elif menu == "Financeiro":
        st.header("💰 Controle de Pagamentos")
        df_fin = pd.read_sql("SELECT id, nome, status_pagamento FROM usuarios WHERE role='aluno'", conn)
        for _, r in df_fin.iterrows():
            c1, c2 = st.columns([3,1])
            status_color = "green" if r['status_pagamento'] == "Em dia" else "red"
            c1.markdown(f"**{r['nome']}** - Status: :{status_color}[{r['status_pagamento']}]")
            if c2.button("Inverter Status", key=f"btn_{r['id']}"):
                novo = "Pendente" if r['status_pagamento'] == "Em dia" else "Em dia"
                conn.execute("UPDATE usuarios SET status_pagamento=? WHERE id=?", (novo, r['id']))
                conn.commit()
                st.rerun()

# =============================
# PAINEL DO ALUNO
# =============================
def painel_aluno():
    u_id = st.session_state.user["id"]
    conn = get_connection()
    
    # Header com Resumo
    st.title(f"Foco no Treino, {st.session_state.user['nome']}! 🔥")
    
    # Widget de Pagamento
    if st.session_state.user["status"] != "Em dia":
        st.error("🚨 Identificamos uma pendência na sua mensalidade. Fale com o instrutor.")

    tab1, tab2, tab3 = st.tabs(["🏋️ Treino de Hoje", "📈 Meu Progresso", "⏱️ Timer"])

    with tab1:
        df_t = pd.read_sql("SELECT * FROM treinos WHERE usuario_id=?", conn, params=(u_id,))
        if df_t.empty:
            st.info("Sua ficha está sendo preparada. Aguarde!")
        else:
            for t in df_t["tipo_treino"].unique():
                with st.expander(f"TREINO {t.upper()}", expanded=True):
                    for _, row in df_t[df_t["tipo_treino"] == t].iterrows():
                        st.checkbox(f"**{row['exercicio']}** - {row['series']}x{row['repeticoes']} ({row['carga']}kg)", key=f"ex_{row['id']}")

    with tab2:
        st.subheader("📊 Histórico de Peso")
        df_m = pd.read_sql("SELECT * FROM medidas WHERE usuario_id=? ORDER BY data ASC", conn, params=(u_id,))
        if not df_m.empty:
            fig = px.line(df_m, x="data", y="peso", markers=True, line_shape="spline", title="Evolução do Peso")
            st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("Registrar Novo Peso/Medidas"):
            with st.form("medidas"):
                p = st.number_input("Peso (kg)", 0.0)
                br = st.number_input("Braço (cm)", 0.0)
                if st.form_submit_button("Salvar"):
                    conn.execute("INSERT INTO medidas (usuario_id, peso, braco, data) VALUES (?,?,?,?)",
                                 (u_id, p, br, datetime.now().strftime("%Y-%m-%d")))
                    conn.commit()
                    st.rerun()

    with tab3:
        st.subheader("⏱️ Cronômetro de Descanso")
        seconds = st.number_input("Segundos de descanso", 30, 300, 60)
        if st.button("Iniciar"):
            ph = st.empty()
            for i in range(seconds, 0, -1):
                ph.metric("Descanse!", f"{i}s")
                time.sleep(1)
            ph.success("⏰ HORA DA SÉRIE!")
            st.balloons()

# =============================
# LÓGICA DE INICIALIZAÇÃO
# =============================
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    login()
else:
    if st.sidebar.button("🚪 Sair"):
        st.session_state.user = None
        st.rerun()
    
    if st.session_state.user["role"] == "admin":
        painel_admin()
    else:
        painel_aluno()
