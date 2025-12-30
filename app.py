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
st.set_page_config(page_title="GymManager Pro v5.0", layout="wide", page_icon="💪")

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
        # Tabela usuários
        c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            login TEXT UNIQUE,
            senha TEXT,
            role TEXT,
            altura REAL DEFAULT 170.0,
            objetivo TEXT,
            status_pagamento TEXT DEFAULT 'Em dia'
        )
        """)
        # Tabela tipos de treino
        c.execute("CREATE TABLE IF NOT EXISTS tipos_treino (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)")
        # Tabela treinos
        c.execute("""
        CREATE TABLE IF NOT EXISTS treinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            dia_semana TEXT,
            tipo_treino TEXT,
            exercicio TEXT,
            series INTEGER,
            repeticoes TEXT,
            carga REAL,
            link_video TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )
        """)
        # Tabela medidas
        c.execute("""
        CREATE TABLE IF NOT EXISTS medidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            peso REAL,
            cintura REAL,
            braco REAL,
            data TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )
        """)
        # Tabela histórico de treinos
        c.execute("""
        CREATE TABLE IF NOT EXISTS historico_treinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            data TEXT,
            duracao_segundos INTEGER,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )
        """)
        # Criar admin padrão
        admin_hash = make_hashes("admin123")
        c.execute("INSERT OR IGNORE INTO usuarios (nome, login, senha, role, altura) VALUES (?,?,?,?,?)",
                  ("Master Admin","admin",admin_hash,"admin",175.0))
        # Criar tipos de treino padrão
        tipos = ["Costas","Peito","Pernas","Ombro","Braços","Abdômen","Cardio"]
        for t in tipos:
            c.execute("INSERT OR IGNORE INTO tipos_treino (nome) VALUES (?)",(t,))
        conn.commit()

init_db()

# =============================
# LOGIN
# =============================
def login():
    st.title("🏋️ GymManager Pro")
    tab1, tab2 = st.tabs(["Login", "Cadastro"])

    with tab1:
        u = st.text_input("Login")
        s = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            with get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM usuarios WHERE login=?", (u,))
                row = c.fetchone()
                if row and check_hashes(s,row[3]):
                    st.session_state.user = {
                        "id": row[0],
                        "nome": row[1],
                        "role": row[4],
                        "altura": row[5],
                        "objetivo": row[6],
                        "status_pagamento": row[7]
                    }
                    st.success(f"Bem-vindo {row[1]}! Atualize a página se necessário.")
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
    menu = st.sidebar.selectbox("Menu", ["Alunos","Prescrever Treinos","Financeiro"])

    with get_connection() as conn:
        if menu=="Alunos":
            st.header("👥 Gestão de Alunos")
            with st.expander("➕ Cadastrar Novo Aluno"):
                with st.form("cad_aluno", clear_on_submit=True):
                    n = st.text_input("Nome")
                    l = st.text_input("Login")
                    s = st.text_input("Senha", type="password")
                    alt = st.number_input("Altura (cm)", value=170.0)
                    obj = st.selectbox("Objetivo", ["Hipertrofia","Emagrecimento","Condicionamento","Saúde"])
                    if st.form_submit_button("Salvar"):
                        try:
                            conn.execute("INSERT INTO usuarios (nome,login,senha,role,altura,objetivo) VALUES (?,?,?,?,?,?)",
                                         (n,l,make_hashes(s),'aluno',alt,obj))
                            conn.commit()
                            st.success("Aluno cadastrado!")
                        except:
                            st.error("Login já existe!")
            df = pd.read_sql("SELECT id,nome,login,status_pagamento,objetivo FROM usuarios WHERE role='aluno'", conn)
            st.dataframe(df,use_container_width=True)

        elif menu=="Prescrever Treinos":
            st.header("📋 Prescrição de Treinos")
            alunos = pd.read_sql("SELECT id,nome FROM usuarios WHERE role='aluno'", conn)
            if not alunos.empty:
                sel = st.selectbox("Selecione o Aluno", alunos["nome"])
                a_id = int(alunos.loc[alunos["nome"]==sel,"id"].values[0])
                tipos = pd.read_sql("SELECT nome FROM tipos_treino", conn)["nome"].tolist()
                with st.form("add_treino", clear_on_submit=True):
                    dia = st.selectbox("Dia da Semana", DIAS_SEMANA)
                    tipo = st.selectbox("Grupo Muscular", tipos)
                    novo_tipo = st.text_input("Ou criar novo grupo")
                    ex = st.text_input("Exercício")
                    se = st.number_input("Séries",1,10,3)
                    ca = st.number_input("Carga (kg)",0.0)
                    vid = st.text_input("Link do Vídeo")
                    if st.form_submit_button("Adicionar"):
                        if novo_tipo:
                            try:
                                conn.execute("INSERT INTO tipos_treino (nome) VALUES (?)",(novo_tipo,))
                                conn.commit()
                                tipo = novo_tipo
                                st.success("Novo grupo criado!")
                            except: st.warning("Grupo já existe")
                        conn.execute("INSERT INTO treinos (usuario_id,dia_semana,tipo_treino,exercicio,series,carga,link_video) VALUES (?,?,?,?,?,?,?)",
                                     (a_id,dia,tipo,ex,se,ca,vid))
                        conn.commit()
                        st.success("Exercício adicionado!")
                df_treino = pd.read_sql("SELECT dia_semana,tipo_treino,exercicio,series,carga,link_video FROM treinos WHERE usuario_id=? ORDER BY dia_semana", conn, params=(a_id,))
                st.dataframe(df_treino,use_container_width=True)

        elif menu=="Financeiro":
            st.header("💰 Controle Financeiro")
            df_fin = pd.read_sql("SELECT id,nome,status_pagamento FROM usuarios WHERE role='aluno'", conn)
            for _, row in df_fin.iterrows():
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
        st.title(f"Foco Total, {st.session_state.user['nome']}! ⚡")
        # Últimas métricas
        res = pd.read_sql("SELECT peso FROM medidas WHERE usuario_id=? ORDER BY id DESC LIMIT 1", conn, params=(u_id,))
        peso_val = res.iloc[0]['peso'] if not res.empty else 0
        col1,col2,col3 = st.columns(3)
        col1.metric("Último Peso", f"{peso_val} kg")
        col2.metric("Status Conta", st.session_state.user.get("status_pagamento","Em dia"))
        col3.metric("Frequência", "Ativo")

        tab1,tab2 = st.tabs(["🏋️ Treino de Hoje","📊 Evolução"])
        with tab1:
            dia_hoje = DIAS_SEMANA[datetime.now().weekday()]
            st.subheader(f"Treino de {dia_hoje}")
            df = pd.read_sql("SELECT * FROM treinos WHERE usuario_id=? AND dia_semana=?", conn, params=(u_id,dia_hoje))
            if df.empty:
                st.info("Nenhuma atividade prescrita para hoje.")
            else:
                for _,row in df.iterrows():
                    st.write(f"**{row['exercicio']}** | {row['series']}x{row['repeticoes']} | {row['carga']}kg")
                    if row['link_video']:
                        try: st.video(row['link_video'])
                        except: st.warning("Vídeo indisponível")
            # Timer treino
            if 'timer_start' not in st.session_state: st.session_state.timer_start = None
            col_i,col_f = st.columns(2)
            if col_i.button("▶️ Iniciar Treino"):
                st.session_state.timer_start = time.time()
                st.success("Treino iniciado!")
            if col_f.button("⏹️ Finalizar Treino"):
                if st.session_state.timer_start:
                    dur = int(time.time()-st.session_state.timer_start)
                    conn.execute("INSERT INTO historico_treinos (usuario_id,data,duracao_segundos) VALUES (?,?,?)",
                                 (u_id,datetime.now().strftime("%Y-%m-%d"),dur))
                    conn.commit()
                    st.session_state.timer_start=None
                    st.success(f"Treino finalizado! Duração: {dur//60} min")

        with tab2:
            st.subheader("Registrar Peso / Medidas")
            with st.form("nova_medida"):
                p = st.number_input("Peso (kg)",0.0)
                c = st.number_input("Cintura (cm)",0.0)
                b = st.number_input("Braço (cm)",0.0)
                if st.form_submit_button("Registrar"):
                    conn.execute("INSERT INTO medidas (usuario_id,peso,cintura,braco,data) VALUES (?,?,?,?,?)",
                                 (u_id,p,c,b,datetime.now().strftime("%Y-%m-%d")))
                    conn.commit()
                    st.success("Medida registrada!")
            df_med = pd.read_sql("SELECT * FROM medidas WHERE usuario_id=? ORDER BY data ASC", conn, params=(u_id,))
            if not df_med.empty:
                df_med["IMC"] = df_med["peso"] / (st.session_state.user.get("altura",1)/100)**2
                st.plotly_chart(px.line(df_med,x="data",y=["peso","IMC"],markers=True,title="Evolução"),use_container_width=True)

# =============================
# FLUXO PRINCIPAL
# =============================
if "user" not in st.session_state: st.session_state.user = None

if st.session_state.user is None:
    login()
else:
    if st.sidebar.button("🚪 Sair"):
        st.session_state.user=None
        st.experimental_rerun()
    if st.session_state.user["role"]=="admin":
        painel_admin()
    else:
        painel_aluno()
