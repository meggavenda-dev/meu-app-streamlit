import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import plotly.express as px
from datetime import datetime
import time
import random

# =============================
# CONFIGURAÇÃO E ESTILO
# =============================
st.set_page_config(page_title="GymManager Pro v7", layout="wide", page_icon="💪")

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
    .stButton button { width: 100%; }
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
    return sqlite3.connect("gym_v7.db", check_same_thread=False)

def init_db():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT, login TEXT UNIQUE, senha TEXT, role TEXT,
            altura REAL DEFAULT 170.0, objetivo TEXT,
            status_pagamento TEXT DEFAULT 'Em dia')""")
        
        c.execute("""CREATE TABLE IF NOT EXISTS treinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER,
            dia_semana TEXT, tipo_treino TEXT, exercicio TEXT,
            series INTEGER, repeticoes TEXT, carga REAL, link_video TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")
            
        c.execute("""CREATE TABLE IF NOT EXISTS medidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER,
            peso REAL, data TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")

        c.execute("""CREATE TABLE IF NOT EXISTS historico_treinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER,
            data TEXT, duracao_segundos INTEGER,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")
        
        admin_hash = make_hashes("admin123")
        c.execute("INSERT OR IGNORE INTO usuarios (nome, login, senha, role, altura) VALUES (?,?,?,?,?)",
                  ("Master Admin","admin",admin_hash,"admin",175.0))
        conn.commit()

init_db()

# =============================
# PAINEL ADMINISTRATIVO
# =============================
def painel_admin():
    st.sidebar.title("🔐 Administração")
    menu = st.sidebar.selectbox("Opções", ["Gestão de Alunos", "Montar Treinos", "Financeiro"])
    
    with get_connection() as conn:
        if menu == "Gestão de Alunos":
            st.header("👥 Gestão de Alunos")
            
            # --- CADASTRO DE ALUNOS ---
            with st.expander("➕ Incluir Novo Aluno"):
                with st.form("admin_incluir_aluno"):
                    c1, c2 = st.columns(2)
                    novo_nome = c1.text_input("Nome Completo")
                    novo_login = c2.text_input("Login de Acesso")
                    nova_senha = c1.text_input("Senha Inicial", type="password")
                    nova_altura = c2.number_input("Altura (cm)", value=170.0)
                    novo_obj = c2.selectbox("Objetivo", ["Hipertrofia","Emagrecimento","Saúde"])
                    if st.form_submit_button("Cadastrar Aluno"):
                        if novo_nome and novo_login and nova_senha:
                            try:
                                conn.execute(
                                    "INSERT INTO usuarios (nome, login, senha, role, altura, objetivo) VALUES (?,?,?,?,?,?)",
                                    (novo_nome, novo_login, make_hashes(nova_senha), 'aluno', nova_altura, novo_obj)
                                )
                                conn.commit()
                                st.success("Aluno cadastrado!")
                                st.rerun()
                            except:
                                st.error("Erro: Login já existe!")

            st.divider()
            
            # --- LISTA DE ALUNOS E ALTERAÇÃO ---
            st.subheader("Alunos Cadastrados")
            df = pd.read_sql("SELECT id, nome, login, objetivo, status_pagamento FROM usuarios WHERE role='aluno'", conn)
            
            for _, row in df.iterrows():
                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                    col1.write(f"**{row['nome']}** ({row['login']})")
                    
                    # Alterar Objetivo
                    novo_objetivo = col2.selectbox("Alterar Obj.", ["Hipertrofia","Emagrecimento","Saúde"], 
                                                   index=["Hipertrofia","Emagrecimento","Saúde"].index(row['objetivo']),
                                                   key=f"obj_{row['id']}")
                    if novo_objetivo != row['objetivo']:
                        conn.execute("UPDATE usuarios SET objetivo=? WHERE id=?", (novo_objetivo, row['id']))
                        conn.commit()
                        st.rerun()

                    # Status Financeiro
                    status = "✅ Em dia" if row['status_pagamento'] == "Em dia" else "🚨 Pendente"
                    col3.write(f"Status: {status}")
                    
                    # Botão Excluir
                    if col4.button("🗑️ Remover", key=f"del_{row['id']}"):
                        conn.execute("DELETE FROM usuarios WHERE id=?", (row['id'],))
                        conn.commit()
                        st.rerun()

        elif menu == "Montar Treinos":
            st.header("📋 Prescrição de Treino")
            alunos = pd.read_sql("SELECT id, nome FROM usuarios WHERE role='aluno'", conn)
            if not alunos.empty:
                sel = st.selectbox("Selecione o Aluno", alunos["nome"])
                a_id = int(alunos.loc[alunos["nome"] == sel, "id"].iloc[0])
                
                # --- CADASTRAR TREINO ---
                with st.form("add_treino"):
                    dia = st.selectbox("Dia da Semana", DIAS_SEMANA)
                    tipo = st.text_input("Grupo Muscular")
                    ex = st.text_input("Exercício")
                    se = st.number_input("Séries", 1, 10, 3)
                    re = st.text_input("Reps")
                    ca = st.number_input("Carga (kg)", 0.0)
                    vi = st.text_input("Link Vídeo YouTube")
                    if st.form_submit_button("Salvar Treino"):
                        conn.execute(
                            "INSERT INTO treinos (usuario_id, dia_semana, tipo_treino, exercicio, series, repeticoes, carga, link_video) VALUES (?,?,?,?,?,?,?,?)",
                            (a_id, dia, tipo, ex, se, re, ca, vi)
                        )
                        conn.commit()
                        st.success("Treino cadastrado!")
                        st.rerun()
                
                st.divider()
                
                # --- LISTA DE TREINOS EXISTENTES COM OPÇÃO DE ALTERAR ---
                st.subheader("Treinos Cadastrados")
                df_treinos = pd.read_sql("SELECT * FROM treinos WHERE usuario_id=?", conn, params=(a_id,))
                
                for _, r in df_treinos.iterrows():
                    with st.container(border=True):
                        c1, c2, c3, c4, c5, c6 = st.columns([2,2,1,1,1,1])
                        c1.write(f"**{r['exercicio']}** ({r['tipo_treino']})")
                        c2.write(f"{r['series']}x{r['repeticoes']} | {r['carga']}kg")
                        c3.write(r['dia_semana'])
                        if r['link_video']: c4.write("🎬")
                        
                        # Alterar Treino
                        new_ex = c1.text_input("Exercício", value=r['exercicio'], key=f"ex_{r['id']}")
                        new_se = c2.number_input("Séries", value=r['series'], min_value=1, max_value=20, key=f"se_{r['id']}")
                        new_re = c2.text_input("Reps", value=r['repeticoes'], key=f"re_{r['id']}")
                        new_ca = c2.number_input("Carga (kg)", value=r['carga'], key=f"ca_{r['id']}")
                        if c5.button("💾 Salvar Alterações", key=f"save_{r['id']}"):
                            conn.execute(
                                "UPDATE treinos SET exercicio=?, series=?, repeticoes=?, carga=? WHERE id=?",
                                (new_ex, new_se, new_re, new_ca, r['id'])
                            )
                            conn.commit()
                            st.success("Alterações salvas!")
                            st.rerun()
                        if c6.button("🗑️ Excluir", key=f"del_t_{r['id']}"):
                            conn.execute("DELETE FROM treinos WHERE id=?", (r['id'],))
                            conn.commit()
                            st.rerun()

        elif menu == "Financeiro":
            st.header("💰 Gestão Financeira")
            df_fin = pd.read_sql("SELECT id, nome, status_pagamento FROM usuarios WHERE role='aluno'", conn)
            for _, row in df_fin.iterrows():
                c1, c2 = st.columns([3,1])
                cor = "green" if row['status_pagamento'] == "Em dia" else "red"
                c1.markdown(f"**{row['nome']}** - Status: :{cor}[{row['status_pagamento']}]")
                if c2.button("Inverter Pagamento", key=f"pay_{row['id']}"):
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
        res_peso = pd.read_sql("SELECT peso FROM medidas WHERE usuario_id=? ORDER BY id DESC LIMIT 1", conn, params=(u_id,))
        peso_atual = res_peso.iloc[0]['peso'] if not res_peso.empty else 0
        altura_m = st.session_state.user.get("altura", 170)/100
        imc = peso_atual / altura_m**2 if peso_atual>0 else 0

        st.title(f"Olá, {st.session_state.user['nome']}! 🔥")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Peso Atual", f"{peso_atual} kg")
        m2.metric("Pagamento", st.session_state.user.get("status_pagamento", "Em dia"))
        m3.metric("Objetivo", st.session_state.user.get("objetivo","Saúde"))
        m4.metric("IMC", f"{imc:.1f}")

        tab1, tab2 = st.tabs(["🏋️ Meu Treino","📊 Evolução"])

        with tab1:
            dia_hoje = DIAS_SEMANA[datetime.now().weekday()]
            st.subheader(f"Treino de {dia_hoje}")
            df = pd.read_sql("SELECT * FROM treinos WHERE usuario_id=? AND dia_semana=?", conn, params=(u_id, dia_hoje))
            if df.empty:
                st.write("😴 Descanso programado.")
            else:
                for _, r in df.iterrows():
                    with st.container(border=True):
                        st.write(f"**{r['exercicio']}** ({r['tipo_treino']}) | {r['series']}x{r['repeticoes']} | {r['carga']}kg")
                        if r['link_video']: st.video(r['link_video'])

        with tab2:
            with st.form("form_medidas"):
                p = st.number_input("Peso (kg)", 0.0)
                if st.form_submit_button("Salvar Medida"):
                    conn.execute("INSERT INTO medidas (usuario_id, peso, data) VALUES (?,?,?)",
                                 (u_id, p, datetime.now().strftime("%Y-%m-%d")))
                    conn.commit()
                    st.rerun()
            df_med = pd.read_sql("SELECT peso, data FROM medidas WHERE usuario_id=? ORDER BY data ASC", conn, params=(u_id,))
            if not df_med.empty:
                st.plotly_chart(px.line(df_med, x="data", y="peso", markers=True), use_container_width=True)

# =============================
# LOGIN SCREEN
# =============================
def login_screen():
    st.title("🏋️ GymManager Pro")
    tab1, tab2 = st.tabs(["Login","Novo Cadastro"])
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
                    st.session_state.user = {"id": row[0], "nome": row[1], "role": row[4], "altura": row[5], "objetivo": row[6], "status_pagamento": row[7]}
                    st.rerun()
                else:
                    st.error("Login inválido")
    with tab2:
        with st.form("form_cadastro"):
            n = st.text_input("Nome")
            l = st.text_input("Login")
            p = st.text_input("Senha", type="password")
            if st.form_submit_button("Criar Conta"):
                if n and l and p:
                    with get_connection() as conn:
                        conn.execute("INSERT INTO usuarios (nome, login, senha, role) VALUES (?,?,?,?)", (n,l,make_hashes(p),'aluno'))
                        conn.commit()
                    st.success("Conta criada!")

# =============================
# FLUXO PRINCIPAL
# =============================
if "user" not in st.session_state: st.session_state.user = None

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
