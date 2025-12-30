import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import hashlib
from datetime import datetime
import time

# =============================
# CONFIGURAÇÃO E ESTILO (CSS)
# =============================
st.set_page_config(page_title="GymManager Pro v4.2", layout="wide", page_icon="💪")

st.markdown("""
<style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetricContainer"] {
        background-color: #1e2129;
        border: 1px solid #31333f;
        padding: 15px;
        border-radius: 10px;
        color: white;
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
    return sqlite3.connect("gym_v4.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT, login TEXT UNIQUE, senha TEXT, role TEXT,
            status_pagamento TEXT DEFAULT 'Em dia', objetivo TEXT)""")
        
        try:
            c.execute("ALTER TABLE usuarios ADD COLUMN altura REAL DEFAULT 170.0")
        except: pass

        c.execute("""CREATE TABLE IF NOT EXISTS treinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER, dia_semana TEXT, tipo_treino TEXT,
            exercicio TEXT, series INTEGER, repeticoes TEXT, carga REAL,
            link_video TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")

        c.execute("""CREATE TABLE IF NOT EXISTS medidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER,
            peso REAL, cintura REAL, braco REAL, data TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")
        
        c.execute("""CREATE TABLE IF NOT EXISTS historico_treinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER, data TEXT, duracao_segundos INTEGER,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")

        admin_hash = make_hashes('admin123')
        c.execute("INSERT OR IGNORE INTO usuarios (nome, login, senha, role, altura) VALUES (?,?,?,?,?)", 
                  ('Master Admin', 'admin', admin_hash, 'admin', 175.0))
        conn.commit()
    finally:
        conn.close()

init_db()

# =============================
# COMPONENTES
# =============================
DIAS_SEMANA = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]

def painel_admin():
    st.sidebar.title("🔐 Painel Admin")
    menu = st.sidebar.selectbox("Menu", ["Alunos", "Prescrever", "Financeiro"])
    conn = get_connection()

    try:
        if menu == "Alunos":
            st.header("👥 Gestão de Alunos")
            with st.expander("Cadastrar Novo"):
                with st.form("cad_aluno", clear_on_submit=True):
                    n = st.text_input("Nome")
                    l = st.text_input("Login")
                    p = st.text_input("Senha", type="password")
                    alt = st.number_input("Altura (cm)", value=170.0)
                    if st.form_submit_button("Salvar"):
                        if n and l and p:
                            conn.execute("INSERT INTO usuarios (nome, login, senha, role, altura) VALUES (?,?,?,?,?)",
                                         (n, l, make_hashes(p), 'aluno', alt))
                            conn.commit()
                            st.success("Cadastrado!")
                            st.rerun()

            df = pd.read_sql("SELECT id, nome, login, status_pagamento FROM usuarios WHERE role='aluno'", conn)
            st.dataframe(df, use_container_width=True)

        elif menu == "Prescrever":
            st.header("📋 Prescrever Treino")
            alunos = pd.read_sql("SELECT id, nome FROM usuarios WHERE role='aluno'", conn)
            if not alunos.empty:
                sel = st.selectbox("Selecione o Aluno", alunos["nome"])
                a_id = int(alunos[alunos["nome"] == sel]["id"].iloc[0])
                
                with st.form("add_treino", clear_on_submit=True):
                    dia = st.selectbox("Dia da Semana", DIAS_SEMANA)
                    tipo = st.text_input("Grupamento (Ex: Peito)")
                    ex = st.text_input("Exercício")
                    c1, c2 = st.columns(2)
                    se = c1.number_input("Séries", 1, 10, 3)
                    ca = c2.number_input("Carga (kg)", 0.0)
                    vid = st.text_input("Link Vídeo (YouTube)")
                    if st.form_submit_button("Adicionar"):
                        conn.execute("INSERT INTO treinos (usuario_id, dia_semana, tipo_treino, exercicio, series, carga, link_video) VALUES (?,?,?,?,?,?,?)",
                                     (a_id, dia, tipo, ex, se, ca, vid))
                        conn.commit()
                        st.success("Exercício adicionado!")
    finally:
        conn.close()

def painel_aluno():
    u_id = st.session_state.user["id"]
    conn = get_connection()

    try:
        st.title(f"Foco Total, {st.session_state.user['nome']}! ⚡")
        
        # Dashboard de métricas
        m1, m2, m3 = st.columns(3)
        res_medida = pd.read_sql("SELECT peso FROM medidas WHERE usuario_id=? ORDER BY id DESC LIMIT 1", conn, params=(u_id,))
        peso_val = res_medida.iloc[0]['peso'] if not res_medida.empty else 0
        
        m1.metric("Meu Último Peso", f"{peso_val} kg")
        m2.metric("Status da Conta", st.session_state.user.get("status_pagamento", "Em dia"))
        m3.metric("Frequência", "Ativo")

        tab1, tab2 = st.tabs(["🏋️ Treino de Hoje", "📊 Evolução"])

        with tab1:
            dia_hoje = DIAS_SEMANA[datetime.now().weekday()]
            st.subheader(f"Treino de {dia_hoje}")
            
            # Cronômetro simplificado (sem loop while para não travar o app)
            if 'timer_start' not in st.session_state: st.session_state.timer_start = None
            
            c1, c2 = st.columns(2)
            if c1.button("▶️ Iniciar Treino"): 
                st.session_state.timer_start = time.time()
                st.rerun()
            if c2.button("⏹️ Finalizar"):
                if st.session_state.timer_start:
                    duracao = int(time.time() - st.session_state.timer_start)
                    conn.execute("INSERT INTO historico_treinos (usuario_id, data, duracao_segundos) VALUES (?,?,?)",
                                 (u_id, datetime.now().strftime("%Y-%m-%d"), duracao))
                    conn.commit()
                    st.session_state.timer_start = None
                    st.success(f"Treino de {duracao//60} min finalizado!"); st.rerun()

            df = pd.read_sql("SELECT * FROM treinos WHERE usuario_id=? AND dia_semana=?", conn, params=(u_id, dia_hoje))
            if df.empty:
                st.info("Nenhum exercício agendado para hoje.")
            else:
                for _, row in df.iterrows():
                    with st.container(border=True):
                        col_i, col_v = st.columns([2,1])
                        col_i.markdown(f"### {row['exercicio']}")
                        col_i.write(f"**Sets:** {row['series']} | **Carga:** {row['carga']}kg")
                        if row['link_video']:
                            col_v.video(row['link_video
