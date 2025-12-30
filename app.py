import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import plotly.express as px
from datetime import datetime
import time

# =============================
# CONFIGURAÇÃO
# =============================
st.set_page_config(page_title="GymManager Pro v5.1", layout="wide", page_icon="💪")

DIAS_SEMANA = ["Segunda-feira","Terça-feira","Quarta-feira","Quinta-feira","Sexta-feira","Sábado","Domingo"]

# =============================
# BANCO DE DADOS
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
        c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT, login TEXT UNIQUE, senha TEXT, role TEXT,
            altura REAL DEFAULT 170.0, objetivo TEXT,
            status_pagamento TEXT DEFAULT 'Em dia'
        )""")
        c.execute("CREATE TABLE IF NOT EXISTS tipos_treino (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)")
        c.execute("""
        CREATE TABLE IF NOT EXISTS treinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER,
            dia_semana TEXT, tipo_treino TEXT, exercicio TEXT,
            series INTEGER, repeticoes TEXT, carga REAL, link_video TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS medidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER,
            peso REAL, cintura REAL, braco REAL, data TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS historico_treinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER,
            data TEXT, duracao_segundos INTEGER,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )""")
        
        admin_hash = make_hashes("admin123")
        c.execute("INSERT OR IGNORE INTO usuarios (nome, login, senha, role, altura) VALUES (?,?,?,?,?)",
                  ("Master Admin","admin",admin_hash,"admin",175.0))
        
        tipos = ["Costas","Peito","Pernas","Ombro","Braços","Abdômen","Cardio"]
        for t in tipos:
            c.execute("INSERT OR IGNORE INTO tipos_treino (nome) VALUES (?)",(t,))
        conn.commit()

init_db()

# =============================
# LOGIN (CORRIGIDO)
# =============================
def login_screen():
    st.title("🏋️ GymManager Pro")
    tab1, tab2 = st.tabs(["Acessar Conta", "Criar Novo Cadastro"])

    with tab1:
        with st.form("form_login"):
            u = st.text_input("Login")
            s = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                with get_connection() as conn:
                    c = conn.cursor()
                    c.execute("SELECT * FROM usuarios WHERE login=?", (u,))
                    row = c.fetchone()
                
                if row and check_hashes(s, row[3]):
                    st.session_state.user = {
                        "id": row[0], "nome": row[1], "role": row[4],
                        "altura": row[5], "objetivo": row[6], "status_pagamento": row[7]
                    }
                    st.success("Login realizado! Redirecionando...")
                    time.sleep(1)
                    st.rerun() # ESSENCIAL: Recarrega o app para entrar no painel
                else:
                    st.error("Usuário ou senha incorretos")

    with tab2:
        with st.form("form_cadastro"):
            n = st.text_input("Nome completo")
            l = st.text_input("Escolha um Login")
            s = st.text_input("Senha", type="password")
            alt = st.number_input("Altura (cm)", value=170.0)
            obj = st.selectbox("Objetivo", ["Hipertrofia","Emagrecimento","Condicionamento","Saúde"])
            if st.form_submit_button("Cadastrar"):
                if n and l and s:
                    try:
                        with get_connection() as conn:
                            conn.execute("INSERT INTO usuarios (nome, login, senha, role, altura, objetivo) VALUES (?,?,?,?,?,?)",
                                         (n, l, make_hashes(s), 'aluno', alt, obj))
                            conn.commit()
                        st.success("Cadastro realizado! Use a aba Login.")
                    except:
                        st.error("Este Login já está sendo usado.")

# =============================
# PAINÉIS (REVISADOS)
# =============================
def painel_admin():
    st.sidebar.title("🔐 Administração")
    menu = st.sidebar.selectbox("Opções", ["Lista de Alunos", "Montar Treinos", "Financeiro"])
    conn = get_connection()

    if menu == "Lista de Alunos":
        st.header("👥 Alunos Ativos")
        df = pd.read_sql("SELECT id, nome, login, status_pagamento, objetivo FROM usuarios WHERE role='aluno'", conn)
        st.dataframe(df, use_container_width=True)

    elif menu == "Montar Treinos":
        st.header("📋 Prescrição")
        alunos = pd.read_sql("SELECT id, nome FROM usuarios WHERE role='aluno'", conn)
        if not alunos.empty:
            sel = st.selectbox("Aluno", alunos["nome"])
            a_id = int(alunos.loc[alunos["nome"] == sel, "id"].values[0])
            tipos = pd.read_sql("SELECT nome FROM tipos_treino", conn)["nome"].tolist()
            
            with st.form("add_ex"):
                dia = st.selectbox("Dia", DIAS_SEMANA)
                gp = st.selectbox("Grupo Muscular", tipos)
                ex = st.text_input("Exercício")
                c1, c2 = st.columns(2)
                se = c1.number_input("Séries", 1, 10, 3)
                ca = c2.number_input("Carga (kg)", 0.0)
                if st.form_submit_button("Salvar na Ficha"):
                    conn.execute("INSERT INTO treinos (usuario_id, dia_semana, tipo_treino, exercicio, series, carga) VALUES (?,?,?,?,?,?)",
                                 (a_id, dia, gp, ex, se, ca))
                    conn.commit()
                    st.success("Adicionado!")

    elif menu == "Financeiro":
        st.header("💰 Mensalidades")
        df_fin = pd.read_sql("SELECT id, nome, status_pagamento FROM usuarios WHERE role='aluno'", conn)
        for _, row in df_fin.iterrows():
            c1, c2 = st.columns([3,1])
            c1.write(f"**{row['nome']}**: {row['status_pagamento']}")
            if c2.button("Inverter Status", key=f"pay_{row['id']}"):
                novo = "Pendente" if row['status_pagamento'] == "Em dia" else "Em dia"
                conn.execute("UPDATE usuarios SET status_pagamento=? WHERE id=?", (novo, row['id']))
                conn.commit()
                st.rerun()

def painel_aluno():
    u_id = st.session_state.user["id"]
    with get_connection() as conn:
        st.title(f"Bem-vindo, {st.session_state.user['nome']}! 🔥")
        
        tab1, tab2 = st.tabs(["🏋️ Meu Treino", "📊 Progresso"])
        
        with tab1:
            dia_h = DIAS_SEMANA[datetime.now().weekday()]
            st.subheader(f"Treino de {dia_h}")
            df = pd.read_sql("SELECT * FROM treinos WHERE usuario_id=? AND dia_semana=?", conn, params=(u_id, dia_h))
            if df.empty:
                st.info("Hoje é dia de descanso ou sem treino prescrito.")
            else:
                for _, r in df.iterrows():
                    st.write(f"**{r['exercicio']}** | {r['series']} séries | {r['carga']}kg")

        with tab2:
            st.subheader("Minhas Medidas")
            with st.form("med"):
                p = st.number_input("Peso (kg)", 0.0)
                if st.form_submit_button("Registrar"):
                    conn.execute("INSERT INTO medidas (usuario_id, peso, data) VALUES (?,?,?)",
                                 (u_id, p, datetime.now().strftime("%Y-%m-%d")))
                    conn.commit()
                    st.success("Peso salvo!")
            
            df_m = pd.read_sql("SELECT peso, data FROM medidas WHERE usuario_id=? ORDER BY data ASC", conn, params=(u_id,))
            if not df_m.empty:
                st.plotly_chart(px.line(df_m, x="data", y="peso", markers=True), use_container_width=True)

# =============================
# FLUXO PRINCIPAL
# =============================
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    login_screen()
else:
    if st.sidebar.button("🚪 Sair do Sistema"):
        st.session_state.user = None
        st.rerun()
    
    if st.session_state.user["role"] == "admin":
        painel_admin()
    else:
        painel_aluno()
