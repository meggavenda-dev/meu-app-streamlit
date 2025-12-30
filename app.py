import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime
import plotly.express as px
import time

# =============================
# CONFIGURAÇÃO DA PÁGINA
# =============================
st.set_page_config(page_title="GymManager Pro v5.0", layout="wide", page_icon="💪")

# =============================
# UTILITÁRIOS DE SEGURANÇA
# =============================
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

# =============================
# BANCO DE DADOS
# =============================
def get_connection():
    return sqlite3.connect("gym_v5.db", check_same_thread=False)

def init_db():
    with get_connection() as conn:
        c = conn.cursor()
        # Usuários
        c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT, login TEXT UNIQUE, senha TEXT, role TEXT,
            altura REAL DEFAULT 170.0, status_pagamento TEXT DEFAULT 'Em dia',
            objetivo TEXT)""")
        # Grupos musculares
        c.execute("""CREATE TABLE IF NOT EXISTS grupos_musculares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE)""")
        # Treinos
        c.execute("""CREATE TABLE IF NOT EXISTS treinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            dia_semana TEXT,
            grupo_id INTEGER,
            exercicio TEXT,
            series INTEGER,
            repeticoes TEXT,
            carga REAL,
            link_video TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY(grupo_id) REFERENCES grupos_musculares(id) ON DELETE CASCADE)""")
        # Medidas corporais
        c.execute("""CREATE TABLE IF NOT EXISTS medidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            peso REAL,
            cintura REAL,
            braco REAL,
            data TEXT,
            imc REAL,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")
        # Histórico de treinos (tempo de duração)
        c.execute("""CREATE TABLE IF NOT EXISTS historico_treinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            data TEXT,
            duracao_segundos INTEGER,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")
        # Admin padrão
        admin_hash = make_hashes('admin123')
        c.execute("INSERT OR IGNORE INTO usuarios (nome, login, senha, role, altura) VALUES (?,?,?,?,?)",
                  ('Master Admin', 'admin', admin_hash, 'admin', 175.0))
        # Grupos musculares padrão
        grupos = ["Peito", "Costas", "Pernas", "Ombros", "Braços", "Abdômen", "Cardio"]
        for g in grupos:
            c.execute("INSERT OR IGNORE INTO grupos_musculares (nome) VALUES (?)", (g,))
        conn.commit()

init_db()

# =============================
# CONSTANTES
# =============================
DIAS_SEMANA = ["Segunda-feira","Terça-feira","Quarta-feira","Quinta-feira",
               "Sexta-feira","Sábado","Domingo"]

# =============================
# FUNÇÕES DE LOGIN
# =============================
def login():
    st.title("🏋️ GymManager Pro Login")
    tab1, tab2 = st.tabs(["Login", "Cadastro"])
    
    with tab1:
        u = st.text_input("Login")
        s = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            with get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM usuarios WHERE login=?", (u,))
                row = c.fetchone()
                if row and check_hashes(s, row[3]):
                    st.session_state.user = {
                        "id": row[0], "nome": row[1], "role": row[4],
                        "altura": row[5], "status_pagamento": row[6]
                    }
                    st.experimental_rerun()
                else:
                    st.error("Credenciais inválidas")
    
    with tab2:
        n = st.text_input("Nome", key="cad_nome")
        l = st.text_input("Login", key="cad_login")
        s = st.text_input("Senha", type="password", key="cad_senha")
        alt = st.number_input("Altura (cm)", value=170.0, key="cad_altura")
        obj = st.selectbox("Objetivo", ["Hipertrofia","Emagrecimento","Condicionamento","Saúde"])
        if st.button("Criar Conta"):
            if n and l and s:
                try:
                    with get_connection() as conn:
                        conn.execute("INSERT INTO usuarios (nome, login, senha, role, altura, objetivo) VALUES (?,?,?,?,?,?)",
                                     (n,l,make_hashes(s),'aluno',alt,obj))
                        conn.commit()
                        st.success("Conta criada! Faça login.")
                except:
                    st.error("Login já existe!")

# =============================
# PAINEL ADMIN
# =============================
def painel_admin():
    st.sidebar.title("🔐 Painel Admin")
    menu = st.sidebar.selectbox("Menu", ["Alunos","Grupos Musculares","Prescrever Treino","Financeiro"])
    
    with get_connection() as conn:
        if menu == "Alunos":
            st.header("👥 Gestão de Alunos")
            with st.expander("➕ Cadastrar Aluno"):
                with st.form("cad_aluno", clear_on_submit=True):
                    n = st.text_input("Nome")
                    l = st.text_input("Login")
                    s = st.text_input("Senha", type="password")
                    alt = st.number_input("Altura (cm)", 170.0)
                    obj = st.selectbox("Objetivo", ["Hipertrofia","Emagrecimento","Condicionamento","Saúde"])
                    if st.form_submit_button("Salvar"):
                        try:
                            conn.execute("INSERT INTO usuarios (nome, login, senha, role, altura, objetivo) VALUES (?,?,?,?,?,?)",
                                         (n,l,make_hashes(s),'aluno',alt,obj))
                            conn.commit()
                            st.success("Aluno cadastrado!")
                            st.experimental_rerun()
                        except:
                            st.error("Login já existe!")
            df = pd.read_sql("SELECT id,nome,login,status_pagamento,objetivo FROM usuarios WHERE role='aluno'", conn)
            st.dataframe(df,use_container_width=True)
        
        elif menu == "Grupos Musculares":
            st.header("🏷️ Grupos Musculares")
            with st.form("add_grupo", clear_on_submit=True):
                g = st.text_input("Novo Grupo")
                if st.form_submit_button("Adicionar"):
                    try:
                        conn.execute("INSERT INTO grupos_musculares (nome) VALUES (?)", (g,))
                        conn.commit()
                        st.success("Grupo adicionado!")
                        st.experimental_rerun()
                    except:
                        st.warning("Grupo já existe!")
            df = pd.read_sql("SELECT * FROM grupos_musculares", conn)
            st.dataframe(df,use_container_width=True)
        
        elif menu == "Prescrever Treino":
            st.header("📋 Prescrever Treino Semanal")
            alunos = pd.read_sql("SELECT id,nome FROM usuarios WHERE role='aluno'", conn)
            grupos = pd.read_sql("SELECT id,nome FROM grupos_musculares", conn)
            if not alunos.empty:
                sel = st.selectbox("Selecione o Aluno", alunos["nome"])
                a_id = int(alunos.loc[alunos["nome"]==sel,"id"].values[0])
                
                with st.form("add_treino", clear_on_submit=True):
                    dia = st.selectbox("Dia da Semana", DIAS_SEMANA)
                    grupo_sel = st.selectbox("Grupo Muscular", grupos["nome"])
                    grupo_id = int(grupos.loc[grupos["nome"]==grupo_sel,"id"].values[0])
                    ex = st.text_input("Exercício")
                    se = st.number_input("Séries",1,10,3)
                    re = st.text_input("Repetições","12")
                    ca = st.number_input("Carga (kg)",0.0)
                    vid = st.text_input("Link Vídeo (YouTube)")
                    if st.form_submit_button("Adicionar"):
                        conn.execute("INSERT INTO treinos (usuario_id,dia_semana,grupo_id,exercicio,series,repeticoes,carga,link_video) VALUES (?,?,?,?,?,?,?,?)",
                                     (a_id,dia,grupo_id,ex,se,re,ca,vid))
                        conn.commit()
                        st.success("Exercício adicionado!")
                
                df_treinos = pd.read_sql("SELECT t.id,g.nome as grupo,t.dia_semana,t.exercicio,t.series,t.repeticoes,t.carga FROM treinos t JOIN grupos_musculares g ON t.grupo_id=g.id WHERE t.usuario_id=?",
                                         conn, params=(a_id,))
                st.dataframe(df_treinos,use_container_width=True)
        
        elif menu == "Financeiro":
            st.header("💰 Status de Pagamento")
            df = pd.read_sql("SELECT id,nome,status_pagamento FROM usuarios WHERE role='aluno'", conn)
            for _, row in df.iterrows():
                col1,col2 = st.columns([3,1])
                col1.write(f"**{row['nome']}** - Status: {row['status_pagamento']}")
                if col2.button("Alterar", key=f"pay_{row['id']}"):
                    novo = "Pendente" if row['status_pagamento']=="Em dia" else "Em dia"
                    conn.execute("UPDATE usuarios SET status_pagamento=? WHERE id=?",(novo,row['id']))
                    conn.commit()
                    st.experimental_rerun()

# =============================
# PAINEL ALUNO
# =============================
def painel_aluno():
    u_id = st.session_state.user["id"]
    with get_connection() as conn:
        st.title(f"Olá, {st.session_state.user['nome']}! 👋")
        # Último peso e IMC
        df_med = pd.read_sql("SELECT * FROM medidas WHERE usuario_id=? ORDER BY id DESC LIMIT 1", conn, params=(u_id,))
        peso = df_med['peso'].values[0] if not df_med.empty else 0
        imc = df_med['imc'].values[0] if not df_med.empty else 0
        st.metric("Último Peso", f"{peso} kg")
        st.metric("Último IMC", f"{imc}")
        st.metric("Status Mensalidade", st.session_state.user.get("status_pagamento","Em dia"))
        
        tab1,tab2 = st.tabs(["🏋️ Treino Semanal","📊 Evolução"])
        
        # Treino semanal
        with tab1:
            df_t = pd.read_sql("SELECT t.id,g.nome as grupo,t.dia_semana,t.exercicio,t.series,t.repeticoes,t.carga,t.link_video FROM treinos t JOIN grupos_musculares g ON t.grupo_id=g.id WHERE t.usuario_id=? ORDER BY CASE t.dia_semana WHEN 'Segunda-feira' THEN 1 WHEN 'Terça-feira' THEN 2 WHEN 'Quarta-feira' THEN 3 WHEN 'Quinta-feira' THEN 4 WHEN 'Sexta-feira' THEN 5 WHEN 'Sábado' THEN 6 WHEN 'Domingo' THEN 7 END",
                               conn, params=(u_id,))
            if df_t.empty:
                st.info("Nenhum treino registrado para esta semana.")
            else:
                for dia in DIAS_SEMANA:
                    dia_df = df_t[df_t['dia_semana']==dia]
                    if not dia_df.empty:
                        st.subheader(dia)
                        for _, row in dia_df.iterrows():
                            col1,col2 = st.columns([3,1])
                            col1.write(f"**{row['exercicio']}** ({row['grupo']}) {row['series']}x{row['repeticoes']} - {row['carga']}kg")
                            if row['link_video']:
                                try: col2.video(row['link_video'])
                                except: col2.warning("Vídeo indisponível")
        
        # Evolução
        with tab2:
            df_med = pd.read_sql("SELECT peso,imc,data FROM medidas WHERE usuario_id=? ORDER BY data ASC", conn, params=(u_id,))
            if not df_med.empty:
                st.plotly_chart(px.line(df_med, x="data", y=["peso","imc"], markers=True, title="Evolução Peso e IMC"), use_container_width=True)
            
            with st.form("nova_medida"):
                p_new = st.number_input("Peso (kg)",0.0)
                alt = st.session_state.user.get("altura",170)
                if st.form_submit_button("Registrar Medida"):
                    imc_calc = round(p_new/((alt/100)**2),2)
                    conn.execute("INSERT INTO medidas (usuario_id,peso,data,imc) VALUES (?,?,?,?)",
                                 (u_id,p_new,datetime.now().strftime("%Y-%m-%d"),imc_calc))
                    conn.commit()
                    st.success(f"Medida registrada! IMC: {imc_calc}")
                    st.experimental_rerun()

# =============================
# EXECUÇÃO PRINCIPAL
# =============================
if "user" not in st.session_state: st.session_state.user = None

if st.session_state.user is None:
    login()
else:
    if st.sidebar.button("🚪 Sair"):
        st.session_state.user = None
        st.experimental_rerun()
    if st.session_state.user["role"]=="admin":
        painel_admin()
    else:
        painel_aluno()
