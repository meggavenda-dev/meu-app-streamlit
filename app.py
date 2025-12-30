import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import hashlib
from io import BytesIO
from datetime import datetime
import time

# =============================
# CONFIGURAÇÃO E CSS
# =============================
st.set_page_config(page_title="GymManager Pro v3.2", layout="wide", page_icon="🏋️")

# =============================
# SEGURANÇA E BANCO DE DADOS
# =============================
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

def get_connection():
    # check_same_thread=False é vital para Streamlit
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

    # Admin padrão (admin / admin123)
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
# PAINEL ADMINISTRATIVO (CORRIGIDO)
# =============================
def painel_admin():
    st.sidebar.title(f"🛠️ Admin: {st.session_state.user['nome']}")
    menu = st.sidebar.radio("Navegação", ["Dashboard Alunos", "Prescrever Treino", "Financeiro"])
    conn = get_connection()

    if menu == "Dashboard Alunos":
        st.header("👥 Gestão de Alunos")
        
        # Formulário de Cadastro Corrigido
        with st.expander("➕ Cadastrar Novo Aluno", expanded=False):
            with st.form("form_novo_aluno", clear_on_submit=True):
                n = st.text_input("Nome Completo")
                l = st.text_input("Login")
                p = st.text_input("Senha Inicial", type="password")
                obj = st.selectbox("Objetivo", ["Hipertrofia", "Emagrecimento", "Saúde"])
                
                if st.form_submit_button("Salvar Cadastro"):
                    if n and l and p:
                        try:
                            h = make_hashes(p)
                            conn.execute("INSERT INTO usuarios (nome,login,senha,role,objetivo) VALUES (?,?,?,?,?)", 
                                         (n, l, h, 'aluno', obj))
                            conn.commit()
                            st.success(f"Aluno {n} cadastrado!")
                            time.sleep(1)
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Erro: Este login já existe.")
                    else:
                        st.warning("Preencha todos os campos.")

        df_alunos = pd.read_sql("SELECT id, nome, login, status_pagamento, objetivo FROM usuarios WHERE role='aluno'", conn)
        st.subheader("Lista de Alunos")
        st.dataframe(df_alunos, use_container_width=True)

    elif menu == "Prescrever Treino":
        st.header("📋 Montar Ficha")
        alunos = pd.read_sql("SELECT id, nome FROM usuarios WHERE role='aluno'", conn)
        
        if alunos.empty:
            st.warning("Nenhum aluno cadastrado para prescrever treino.")
        else:
            sel_aluno = st.selectbox("Selecione o Aluno", alunos["nome"])
            
            # PROTEÇÃO CONTRA INDEXERROR:
            # Filtramos o ID garantindo que o retorno não seja vazio
            aluno_row = alunos[alunos["nome"] == sel_aluno]
            if not aluno_row.empty:
                a_id = int(aluno_row.iloc[0]["id"])
                
                with st.form("ficha_treino", clear_on_submit=True):
                    c1, c2, c3, c4 = st.columns([2,2,1,1])
                    tp = c1.selectbox("Grupamento", ["Peito", "Costas", "Pernas", "Ombro", "Braços", "Cardio"])
                    ex = c2.text_input("Exercício")
                    se = c3.number_input("Séries", 1, 10, 3)
                    ca = c4.number_input("Carga (kg)", 0.0)
                    re = st.text_input("Repetições (Ex: 12)")
                    
                    if st.form_submit_button("Adicionar à Ficha"):
                        if ex:
                            conn.execute("INSERT INTO treinos (usuario_id, tipo_treino, exercicio, series, repeticoes, carga) VALUES (?,?,?,?,?,?)",
                                         (a_id, tp, ex, se, re, ca))
                            conn.commit()
                            st.toast(f"Adicionado: {ex}")
                        else:
                            st.error("Digite o nome do exercício.")
                
                st.subheader(f"Treino atual de {sel_aluno}")
                df_atual = pd.read_sql("SELECT id, tipo_treino, exercicio, series, repeticoes, carga FROM treinos WHERE usuario_id=?", conn, params=(a_id,))
                st.dataframe(df_atual, use_container_width=True)
                
                if st.button("🗑️ Limpar Toda a Ficha"):
                    conn.execute("DELETE FROM treinos WHERE usuario_id=?", (a_id,))
                    conn.commit()
                    st.rerun()

    elif menu == "Financeiro":
        st.header("💰 Controle de Pagamentos")
        df_fin = pd.read_sql("SELECT id, nome, status_pagamento FROM usuarios WHERE role='aluno'", conn)
        for _, r in df_fin.iterrows():
            col1, col2 = st.columns([3,1])
            col1.write(f"**{r['nome']}** | Status: `{r['status_pagamento']}`")
            if col2.button("Alternar Status", key=f"pay_{r['id']}"):
                novo = "Pendente" if r['status_pagamento'] == "Em dia" else "Em dia"
                conn.execute("UPDATE usuarios SET status_pagamento=? WHERE id=?", (novo, r['id']))
                conn.commit()
                st.rerun()
    conn.close()

# =============================
# PAINEL DO ALUNO
# =============================
def painel_aluno():
    u_id = st.session_state.user["id"]
    conn = get_connection()
    st.title(f"Bem-vindo, {st.session_state.user['nome']}! 🔥")
    
    if st.session_state.user["status"] != "Em dia":
        st.error("🚨 Verificamos uma pendência em sua mensalidade. Procure a recepção.")

    t1, t2 = st.tabs(["🏋️ Meu Treino", "📈 Evolução"])
    
    with t1:
        df_t = pd.read_sql("SELECT * FROM treinos WHERE usuario_id=?", conn, params=(u_id,))
        if df_t.empty:
            st.info("Sua ficha ainda não foi montada.")
        else:
            for g in df_t["tipo_treino"].unique():
                with st.expander(f"TREINO DE {g.upper()}", expanded=True):
                    for _, row in df_t[df_t["tipo_treino"] == g].iterrows():
                        st.write(f"✅ **{row['exercicio']}** - {row['series']}x{row['repeticoes']} | {row['carga']}kg")
    
    with t2:
        st.subheader("📊 Histórico de Peso")
        df_m = pd.read_sql("SELECT peso, data FROM medidas WHERE usuario_id=? ORDER BY data ASC", conn, params=(u_id,))
        if not df_m.empty:
            st.plotly_chart(px.line(df_m, x="data", y="peso", markers=True))
        
        with st.form("medidas_aluno"):
            p = st.number_input("Peso (kg)", 0.0)
            if st.form_submit_button("Registrar Peso"):
                conn.execute("INSERT INTO medidas (usuario_id, peso, data) VALUES (?,?,?)",
                             (u_id, p, datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                st.success("Registrado!")
                st.rerun()
    conn.close()

# =============================
# LOGIN (CORRIGIDO)
# =============================
def login_screen():
    st.title("🏋️ GymManager Pro")
    tab_l, tab_c = st.tabs(["Entrar", "Criar Conta"])
    
    with tab_l:
        with st.form("login"):
            u = st.text_input("Login")
            s = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                conn = get_connection()
                c = conn.cursor()
                c.execute("SELECT * FROM usuarios WHERE login=?", (u,))
                res = c.fetchone()
                conn.close()
                if res and check_hashes(s, res[3]):
                    st.session_state.user = {"id": res[0], "nome": res[1], "role": res[4], "status": res[5]}
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos")

    with tab_c:
        with st.form("cadastro"):
            n = st.text_input("Nome Completo")
            l = st.text_input("Escolha um Login")
            p = st.text_input("Escolha uma Senha", type="password")
            if st.form_submit_button("Cadastrar"):
                try:
                    conn = get_connection()
                    conn.execute("INSERT INTO usuarios (nome,login,senha,role) VALUES (?,?,?,?)", (n,l,make_hashes(p),'aluno'))
                    conn.commit()
                    conn.close()
                    st.success("Cadastrado! Use a aba Entrar.")
                except:
                    st.error("Login já em uso.")

# =============================
# MAIN
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
