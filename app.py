import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import plotly.express as px
from datetime import datetime
import time
import random

# ================================
# CONFIGURAÇÃO E ESTILO
# ================================
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

# ================================
# BANCO DE DADOS E SEGURANÇA
# ================================
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
            dia_semana TEXT, tipo_treino TEXT, exercicio TEXT, series INTEGER, 
            repeticoes TEXT, carga REAL, link_video TEXT,
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

# ================================
# PAINEL ADMINISTRATIVO
# ================================
def painel_admin():
    st.sidebar.title("🔐 Administração")
    menu = st.sidebar.selectbox("Opções", ["Gestão de Alunos", "Montar Treinos", "Financeiro"])
    
    with get_connection() as conn:
        # ---------------------------
        # GESTÃO DE ALUNOS
        # ---------------------------
        if menu == "Gestão de Alunos":
            st.header("👥 Gestão de Alunos")
            
            # --- Cadastrar Aluno ---
            with st.expander("➕ Incluir Novo Aluno"):
                with st.form("admin_incluir_aluno"):
                    c1, c2 = st.columns(2)
                    novo_nome = c1.text_input("Nome Completo")
                    novo_login = c2.text_input("Login de Acesso")
                    nova_senha = c1.text_input("Senha Inicial", type="password")
                    novo_obj = c2.selectbox("Objetivo", ["Hipertrofia","Emagrecimento","Saúde"])
                    if st.form_submit_button("Cadastrar Aluno"):
                        if novo_nome and novo_login and nova_senha:
                            try:
                                conn.execute("INSERT INTO usuarios (nome, login, senha, role, objetivo) VALUES (?,?,?,?,?)",
                                             (novo_nome, novo_login, make_hashes(nova_senha), 'aluno', novo_obj))
                                conn.commit()
                                st.success("Aluno cadastrado com sucesso!")
                                st.rerun()
                            except:
                                st.error("Erro: Login já existe.")

            st.divider()
            
            # --- Lista de Alunos ---
            st.subheader("Alunos Cadastrados")
            df = pd.read_sql("SELECT id, nome, login, objetivo, status_pagamento FROM usuarios WHERE role='aluno'", conn)
            for _, row in df.iterrows():
                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([2,1,1,1])
                    col1.write(f"**{row['nome']}** ({row['login']})")
                    # Alterar objetivo
                    novo_obj = col2.selectbox("Alterar Objetivo", ["Hipertrofia","Emagrecimento","Saúde"],
                                              index=["Hipertrofia","Emagrecimento","Saúde"].index(row['objetivo']),
                                              key=f"obj_{row['id']}")
                    if novo_obj != row['objetivo']:
                        conn.execute("UPDATE usuarios SET objetivo=? WHERE id=?", (novo_obj, row['id']))
                        conn.commit()
                        st.rerun()
                    # Status pagamento
                    status = "✅ Em dia" if row['status_pagamento']=="Em dia" else "🚨 Pendente"
                    col3.write(f"Status: {status}")
                    # Remover aluno
                    if col4.button("🗑️ Remover", key=f"del_{row['id']}"):
                        conn.execute("DELETE FROM usuarios WHERE id=?", (row['id'],))
                        conn.commit()
                        st.rerun()
        
        # ---------------------------
        # MONTAR TREINOS
        # ---------------------------
        elif menu == "Montar Treinos":
            st.header("📋 Planner Semanal de Treinos")
            alunos = pd.read_sql("SELECT id, nome FROM usuarios WHERE role='aluno'", conn)
            if alunos.empty:
                st.info("Nenhum aluno cadastrado.")
                return
            sel = st.selectbox("Selecione o Aluno", alunos["nome"])
            a_id = int(alunos.loc[alunos["nome"]==sel,"id"].iloc[0])

            df_treino = pd.read_sql("SELECT * FROM treinos WHERE usuario_id=? ORDER BY dia_semana, tipo_treino", conn, params=(a_id,))
            st.subheader("🗓️ Semana do Aluno")
            cols = st.columns(len(DIAS_SEMANA))
            
            for i, dia in enumerate(DIAS_SEMANA):
                with cols[i]:
                    st.markdown(f"### {dia}")
                    df_dia = df_treino[df_treino['dia_semana']==dia]
                    
                    # Adicionar novo treino
                    with st.expander("➕ Adicionar Exercício", expanded=False):
                        tipo = st.text_input(f"Grupo Muscular ({dia})", key=f"tipo_{dia}")
                        ex = st.text_input(f"Exercício ({dia})", key=f"ex_{dia}")
                        se = st.number_input(f"Séries ({dia})", 1, 20, 3, key=f"se_{dia}")
                        re = st.text_input(f"Reps ({dia})", key=f"re_{dia}")
                        ca = st.number_input(f"Carga (kg) ({dia})", 0.0, 500.0, 0.0, key=f"ca_{dia}")
                        vi = st.text_input(f"Link Vídeo ({dia})", key=f"vi_{dia}")
                        if st.button(f"💾 Adicionar ({dia})", key=f"add_{dia}"):
                            if tipo and ex:
                                conn.execute("""INSERT INTO treinos (usuario_id, dia_semana, tipo_treino, exercicio, series, repeticoes, carga, link_video)
                                                VALUES (?,?,?,?,?,?,?,?,?)""",
                                             (a_id, dia, tipo, ex, se, re, ca, vi))
                                conn.commit()
                                st.success("Exercício adicionado!")
                                st.rerun()

                    # Mostrar exercícios existentes
                    if df_dia.empty:
                        st.info("Sem treinos para este dia.")
                    else:
                        grupos = df_dia['tipo_treino'].unique()
                        for grupo in grupos:
                            st.markdown(f"**{grupo}**")
                            df_grupo = df_dia[df_dia['tipo_treino']==grupo]
                            for _, r in df_grupo.iterrows():
                                with st.container(border=True):
                                    ex_edit = st.text_input("Exercício", value=r['exercicio'], key=f"ex_{r['id']}")
                                    se_edit = st.number_input("Séries", value=r['series'], min_value=1, max_value=20, key=f"se_{r['id']}")
                                    re_edit = st.text_input("Reps", value=r['repeticoes'], key=f"re_{r['id']}")
                                    ca_edit = st.number_input("Carga (kg)", value=r['carga'], min_value=0.0, key=f"ca_{r['id']}")
                                    vi_edit = st.text_input("Link Vídeo", value=r['link_video'], key=f"vi_{r['id']}")
                                    c1, c2 = st.columns(2)
                                    if c1.button("💾 Salvar", key=f"save_{r['id']}"):
                                        conn.execute("""UPDATE treinos SET exercicio=?, series=?, repeticoes=?, carga=?, link_video=? WHERE id=?""",
                                                     (ex_edit, se_edit, re_edit, ca_edit, vi_edit, r['id']))
                                        conn.commit()
                                        st.success("Treino atualizado!")
                                        st.rerun()
                                    if c2.button("🗑️ Excluir", key=f"del_{r['id']}"):
                                        conn.execute("DELETE FROM treinos WHERE id=?", (r['id'],))
                                        conn.commit()
                                        st.success("Exercício removido!")
                                        st.rerun()
        
        # ---------------------------
        # FINANCEIRO
        # ---------------------------
        elif menu == "Financeiro":
            st.header("💰 Gestão Financeira")
            df_fin = pd.read_sql("SELECT id, nome, status_pagamento FROM usuarios WHERE role='aluno'", conn)
            for _, row in df_fin.iterrows():
                c1, c2 = st.columns([3,1])
                cor = "green" if row['status_pagamento']=="Em dia" else "red"
                c1.markdown(f"**{row['nome']}** - Status: :{cor}[{row['status_pagamento']}]")
                if c2.button("Inverter", key=f"pay_{row['id']}"):
                    novo = "Pendente" if row['status_pagamento']=="Em dia" else "Em dia"
                    conn.execute("UPDATE usuarios SET status_pagamento=? WHERE id=?", (novo,row['id']))
                    conn.commit()
                    st.rerun()

# ================================
# PAINEL DO ALUNO
# ================================
def painel_aluno():
    u_id = st.session_state.user["id"]
    with get_connection() as conn:
        # Peso e IMC
        res_peso = pd.read_sql("SELECT peso FROM medidas WHERE usuario_id=? ORDER BY id DESC LIMIT 1", conn, params=(u_id,))
        peso_atual = res_peso.iloc[0]['peso'] if not res_peso.empty else 0
        altura_m = st.session_state.user.get("altura",170)/100
        imc = peso_atual/(altura_m**2) if peso_atual>0 else 0

        st.title(f"Olá, {st.session_state.user['nome']}! 🔥")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Meu Peso", f"{peso_atual} kg")
        m2.metric("Pagamento", st.session_state.user.get("status_pagamento","Em dia"))
        m3.metric("Objetivo", st.session_state.user.get("objetivo","Saúde"))
        m4.metric("Meu IMC", f"{imc:.1f}")

        tab1, tab2, tab3, tab4 = st.tabs(["🏋️ Meu Treino","📊 Evolução","🥗 Nutrição","💡 Motivação"])

        with tab1:
            data_sel = st.date_input("Escolha a data", datetime.now())
            trad_dias = {"Monday":"Segunda-feira","Tuesday":"Terça-feira","Wednesday":"Quarta-feira",
                         "Thursday":"Quinta-feira","Friday":"Sexta-feira","Saturday":"Sábado","Sunday":"Domingo"}
            dia_pt = trad_dias[data_sel.strftime("%A")]
            st.info(f"Treino de: **{dia_pt}**")

            df = pd.read_sql("SELECT * FROM treinos WHERE usuario_id=? AND dia_semana=?", conn, params=(u_id,dia_pt))
            if df.empty:
                st.write("😴 Descanso agendado.")
            else:
                for _, r in df.iterrows():
                    st.write(f"**{r['tipo_treino']} - {r['exercicio']}** | {r['series']}x{r['repeticoes']} | {r['carga']}kg")
                    if r['link_video']: st.video(r['link_video'])

        with tab2:
            with st.form("med"):
                p = st.number_input("Peso (kg)",0.0)
                if st.form_submit_button("Salvar"):
                    conn.execute("INSERT INTO medidas (usuario_id,peso,data) VALUES (?,?,?)",
                                 (u_id,p,datetime.now().strftime("%Y-%m-%d")))
                    conn.commit()
                    st.rerun()
            df_med = pd.read_sql("SELECT peso,data FROM medidas WHERE usuario_id=? ORDER BY data ASC", conn, params=(u_id,))
            if not df_med.empty:
                st.plotly_chart(px.line(df_med,x="data",y="peso",markers=True),use_container_width=True)

        with tab3:
            if peso_atual>0:
                agua = peso_atual*35
                proteina = peso_atual*2
                st.write(f"💧 Água: {agua/1000:.2f} L/dia")
                st.write(f"🥩 Proteína: {proteina:.0f} g/dia")
        with tab4:
            dicas = ["Consistência é a chave.","Foque na técnica.","Durma bem."]
            st.info(random.choice(dicas))

# ================================
# LOGIN / CADASTRO
# ================================
def login_screen():
    st.title("🏋️ GymManager Pro")
    tab1, tab2 = st.tabs(["Login","Novo Cadastro"])
    with tab1:
        with st.form("form_login"):
            u = st.text_input("Login")
            s = st.text_input("Senha",type="password")
            if st.form_submit_button("Entrar",use_container_width=True):
                with get_connection() as conn:
                    c = conn.cursor()
                    c.execute("SELECT * FROM usuarios WHERE login=?", (u,))
                    row = c.fetchone()
                if row and check_hashes(s,row[3]):
                    st.session_state.user = {"id":row[0],"nome":row[1],"role":row[4],
                                             "altura":row[5],"objetivo":row[6],"status_pagamento":row[7]}
                    st.rerun()
                else: st.error("Erro no login")
    with tab2:
        with st.form("form_cadastro"):
            n = st.text_input("Nome")
            l = st.text_input("Login")
            p = st.text_input("Senha",type="password")
            if st.form_submit_button("Criar Aluno"):
                if n and l and p:
                    with get_connection() as conn:
                        conn.execute("INSERT INTO usuarios (nome,login,senha,role) VALUES (?,?,?,?)",
                                     (n,l,make_hashes(p),'aluno'))
                        conn.commit()
                    st.success("Conta criada!")

# ================================
# FLUXO PRINCIPAL
# ================================
if "user" not in st.session_state: st.session_state.user = None

if st.session_state.user is None:
    login_screen()
else:
    if st.sidebar.button("🚪 Sair"):
        st.session_state.user = None
        st.rerun()
    elif st.session_state.user["role"]=="admin":
        painel_admin()
    else:
        painel_aluno()
