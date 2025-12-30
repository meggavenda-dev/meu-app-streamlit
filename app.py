import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import plotly.express as px
from datetime import datetime
import time

# =============================
# CONFIGURAÇÃO E ESTILO
# =============================
st.set_page_config(page_title="GymManager Pro v5.5", layout="wide", page_icon="💪")

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

DIAS_SEMANA = ["Segunda-feira","Terça-feira","Quarta-feira","Quinta-feira","Sexta-feira","Sábado","Domingo"]

# =============================
# BANCO DE DADOS E SEGURANÇA
# =============================
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

def get_connection():
    return sqlite3.connect("gym_v5.db", check_same_thread=False)

def init_db():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT, login TEXT UNIQUE, senha TEXT, role TEXT,
            altura REAL DEFAULT 170.0, objetivo TEXT,
            status_pagamento TEXT DEFAULT 'Em dia')""")
        
        c.execute("CREATE TABLE IF NOT EXISTS tipos_treino (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)")
        
        c.execute("""CREATE TABLE IF NOT EXISTS treinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER,
            dia_semana TEXT, tipo_treino TEXT, exercicio TEXT,
            series INTEGER, repeticoes TEXT, carga REAL, link_video TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")
            
        c.execute("""CREATE TABLE IF NOT EXISTS medidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER,
            peso REAL, cintura REAL, braco REAL, data TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")

        c.execute("""CREATE TABLE IF NOT EXISTS historico_treinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER,
            data TEXT, duracao_segundos INTEGER,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")
        
        admin_hash = make_hashes("admin123")
        c.execute("INSERT OR IGNORE INTO usuarios (nome, login, senha, role, altura) VALUES (?,?,?,?,?)",
                  ("Master Admin","admin",admin_hash,"admin",175.0))
        
        tipos = ["Costas","Peito","Pernas","Ombro","Braços","Abdômen","Cardio"]
        for t in tipos:
            c.execute("INSERT OR IGNORE INTO tipos_treino (nome) VALUES (?)",(t,))
        conn.commit()

init_db()

# =============================
# TELAS DE ACESSO
# =============================
def login_screen():
    st.title("🏋️ GymManager Pro")
    tab1, tab2 = st.tabs(["Acessar Conta", "Criar Novo Cadastro"])

    with tab1:
        with st.form("form_login"):
            u = st.text_input("Login")
            s = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                with get_connection() as conn:
                    c = conn.cursor()
                    c.execute("SELECT * FROM usuarios WHERE login=?", (u,))
                    row = c.fetchone()
                
                if row and check_hashes(s, row[3]):
                    st.session_state.user = {
                        "id": row[0], "nome": row[1], "role": row[4],
                        "altura": row[5], "objetivo": row[6], "status_pagamento": row[7]
                    }
                    st.success("Login realizado!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos")

    with tab2:
        with st.form("form_cadastro"):
            n = st.text_input("Nome completo")
            l = st.text_input("Escolha um Login")
            password = st.text_input("Senha", type="password")
            alt = st.number_input("Altura (cm)", value=170.0)
            obj = st.selectbox("Objetivo", ["Hipertrofia","Emagrecimento","Saúde"])
            if st.form_submit_button("Cadastrar"):
                if n and l and password:
                    try:
                        with get_connection() as conn:
                            conn.execute("INSERT INTO usuarios (nome, login, senha, role, altura, objetivo) VALUES (?,?,?,?,?,?)",
                                         (n, l, make_hashes(password), 'aluno', alt, obj))
                            conn.commit()
                        st.success("Cadastro realizado! Faça login.")
                    except:
                        st.error("Erro: Login já em uso.")

# =============================
# PAINEL ADMINISTRATIVO
# =============================
def painel_admin():
    st.sidebar.title("🔐 Administração")
    menu = st.sidebar.selectbox("Opções", ["Gestão de Alunos", "Montar Treinos", "Financeiro"])
    
    with get_connection() as conn:
        if menu == "Gestão de Alunos":
            st.header("👥 Gestão de Alunos")
            
            with st.expander("➕ CADASTRAR NOVO ALUNO", expanded=False):
                with st.form("admin_cad"):
                    col1, col2 = st.columns(2)
                    n = col1.text_input("Nome Completo")
                    l = col2.text_input("Login")
                    s = col1.text_input("Senha Inicial", type="password")
                    alt = col2.number_input("Altura (cm)", value=170.0)
                    if st.form_submit_button("Finalizar Cadastro"):
                        conn.execute("INSERT INTO usuarios (nome, login, senha, role, altura) VALUES (?,?,?,?,?)",
                                     (n, l, make_hashes(s), 'aluno', alt))
                        conn.commit()
                        st.success("Aluno cadastrado!")
                        st.rerun()

            st.subheader("Lista de Alunos")
            df = pd.read_sql("SELECT id, nome, login, objetivo FROM usuarios WHERE role='aluno'", conn)
            for _, row in df.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([4,1])
                    c1.write(f"**{row['nome']}** ({row['login']})")
                    if c2.button("🗑️ Excluir", key=f"del_{row['id']}"):
                        conn.execute("DELETE FROM usuarios WHERE id=?", (row['id'],))
                        conn.commit()
                        st.rerun()

        elif menu == "Montar Treinos":
            st.header("📋 Prescrição de Treino")
            alunos = pd.read_sql("SELECT id, nome FROM usuarios WHERE role='aluno'", conn)
            if not alunos.empty:
                sel = st.selectbox("Selecione o Aluno", alunos["nome"])
                a_id = int(alunos.loc[alunos["nome"] == sel, "id"].values[0])
                
                with st.form("add_treino"):
                    dia = st.selectbox("Dia da Semana", DIAS_SEMANA)
                    ex = st.text_input("Exercício")
                    se = st.number_input("Séries", 1, 10, 3)
                    re = st.text_input("Reps (ex: 12)")
                    ca = st.number_input("Carga (kg)", 0.0)
                    vi = st.text_input("Link Vídeo YouTube")
                    if st.form_submit_button("Adicionar à Ficha"):
                        conn.execute("INSERT INTO treinos (usuario_id, dia_semana, exercicio, series, repeticoes, carga, link_video) VALUES (?,?,?,?,?,?,?)",
                                     (a_id, dia, ex, se, re, ca, vi))
                        conn.commit()
                        st.success("Exercício adicionado!")

        elif menu == "Financeiro":
            st.header("💰 Mensalidades")
            df_fin = pd.read_sql("SELECT id, nome, status_pagamento FROM usuarios WHERE role='aluno'", conn)
            for _, row in df_fin.iterrows():
                c1, c2 = st.columns([3,1])
                c1.write(f"**{row['nome']}** - {row['status_pagamento']}")
                if c2.button("Inverter", key=f"pay_{row['id']}"):
                    novo = "Pendente" if row['status_pagamento'] == "Em dia" else "Em dia"
                    conn.execute("UPDATE usuarios SET status_pagamento=? WHERE id=?", (novo, row['id']))
                    conn.commit()
                    st.rerun()

# =============================
# PAINEL DO ALUNO
# =============================

def painel_aluno():
    u_id = st.session_state.user["id"]
    with get_connection() as conn:
        st.title(f"Olá, {st.session_state.user['nome']}! 🔥")
        
        m1, m2, m3 = st.columns(3)
        res_peso = pd.read_sql("SELECT peso FROM medidas WHERE usuario_id=? ORDER BY id DESC LIMIT 1", conn, params=(u_id,))
        peso_atual = res_peso.iloc[0]['peso'] if not res_peso.empty else 0
        m1.metric("Meu Peso", f"{peso_atual} kg")
        m2.metric("Pagamento", st.session_state.user.get("status_pagamento", "Em dia"))
        m3.metric("Objetivo", st.session_state.user.get("objetivo", "Saúde"))

        tab1, tab2 = st.tabs(["🏋️ Treino de Hoje", "📊 Evolução"])
        
        with tab1:
            dia_hoje = DIAS_SEMANA[datetime.now().weekday()]
            st.subheader(f"Hoje é {dia_hoje}")
            
            # Cronômetro
            if 'timer_start' not in st.session_state: st.session_state.timer_start = None
            c_i, c_f = st.columns(2)
            if c_i.button("▶️ Iniciar Treino"):
                st.session_state.timer_start = time.time()
                st.rerun()
            if c_f.button("⏹️ Finalizar"):
                if st.session_state.timer_start:
                    dur = int(time.time() - st.session_state.timer_start)
                    conn.execute("INSERT INTO historico_treinos (usuario_id, data, duracao_segundos) VALUES (?,?,?)",
                                 (u_id, datetime.now().strftime("%Y-%m-%d"), dur))
                    conn.commit()
                    st.session_state.timer_start = None
                    st.success(f"Concluído em {dur//60} minutos!")

            df = pd.read_sql("SELECT * FROM treinos WHERE usuario_id=? AND dia_semana=?", conn, params=(u_id, dia_hoje))
            for _, r in df.iterrows():
                with st.container(border=True):
                    st.write(f"**{r['exercicio']}** | {r['series']}x{r['repeticoes']} | {r['carga']}kg")
                    if r['link_video']: st.video(r['link_video'])

        with tab2:
            with st.form("med_aluno"):
                p = st.number_input("Peso (kg)", 0.0)
                if st.form_submit_button("Salvar Medida"):
                    conn.execute("INSERT INTO medidas (usuario_id, peso, data) VALUES (?,?,?)", (u_id, p, datetime.now().strftime("%Y-%m-%d")))
                    conn.commit()
                    st.rerun()

# =============================
# FLUXO PRINCIPAL
# =============================
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    login_screen()
else:
    if st.sidebar.button("🚪 Sair"):
        st.session_state.user = None
        st.rerun()
    if st.session_state.user["role"] == "admin":
        painel_admin()
    else:
        painel_aluno()
