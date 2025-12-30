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
st.set_page_config(page_title="GymManager Pro v6.1", layout="wide", page_icon="💪")

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
        
        c.execute("""CREATE TABLE IF NOT EXISTS treinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER,
            dia_semana TEXT, exercicio TEXT, series INTEGER, 
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

# =============================
# TELAS DE ACESSO
# =============================
def login_screen():
    st.title("🏋️ GymManager Pro")
    tab1, tab2 = st.tabs(["Acessar Conta", "Novo Cadastro"])

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
            l = st.text_input("Login")
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
                        st.success("Cadastro realizado!")
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
                    re = st.text_input("Reps")
                    ca = st.number_input("Carga (kg)", 0.0)
                    vi = st.text_input("Link Vídeo YouTube")
                    if st.form_submit_button("Salvar na Ficha"):
                        conn.execute("INSERT INTO treinos (usuario_id, dia_semana, exercicio, series, repeticoes, carga, link_video) VALUES (?,?,?,?,?,?,?)",
                                     (a_id, dia, ex, se, re, ca, vi))
                        conn.commit()
                        st.success("Adicionado!")

        elif menu == "Financeiro":
            st.header("💰 Financeiro")
            df_fin = pd.read_sql("SELECT id, nome, status_pagamento FROM usuarios WHERE role='aluno'", conn)
            for _, row in df_fin.iterrows():
                c1, c2 = st.columns([3,1])
                c1.write(f"**{row['nome']}** - {row['status_pagamento']}")
                if c2.button("Inverter Status", key=f"pay_{row['id']}"):
                    novo = "Pendente" if row['status_pagamento'] == "Em dia" else "Em dia"
                    conn.execute("UPDATE usuarios SET status_pagamento=? WHERE id=?", (novo, row['id']))
                    conn.commit()
                    st.rerun()

# =============================
# PAINEL DO ALUNO (V6.1)
# =============================
def painel_aluno():
    u_id = st.session_state.user["id"]
    with get_connection() as conn:
        # Busca peso para IMC
        res_peso = pd.read_sql("SELECT peso FROM medidas WHERE usuario_id=? ORDER BY id DESC LIMIT 1", conn, params=(u_id,))
        peso_atual = res_peso.iloc[0]['peso'] if not res_peso.empty else 0
        altura_m = st.session_state.user.get("altura", 170) / 100
        imc = peso_atual / (altura_m**2) if peso_atual > 0 else 0

        # Busca histórico para contador
        res_hist = pd.read_sql("SELECT COUNT(*) as total FROM historico_treinos WHERE usuario_id=?", conn, params=(u_id,))
        total_treinos = res_hist.iloc[0]['total']

        st.title(f"Olá, {st.session_state.user['nome']}! 🔥")
        
        # Métricas Principais
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Meu Peso", f"{peso_atual} kg")
        m2.metric("Sessões Realizadas", f"{total_treinos}")
        m3.metric("Objetivo", st.session_state.user.get("objetivo", "Saúde"))
        m4.metric("Meu IMC", f"{imc:.1f}")

        tab1, tab2, tab3, tab4 = st.tabs(["🏋️ Consultar Treino", "📊 Evolução", "🥗 Nutrição", "💡 Motivação"])
        
        with tab1:
            col_data, col_timer = st.columns([2, 1])
            
            with col_data:
                # Escolha da Data para ver o treino
                data_sel = st.date_input("Escolha a data", datetime.now())
                trad_dias = {
                    "Monday": "Segunda-feira", "Tuesday": "Terça-feira", "Wednesday": "Quarta-feira",
                    "Thursday": "Quinta-feira", "Friday": "Sexta-feira", "Saturday": "Sábado", "Sunday": "Domingo"
                }
                dia_pt = trad_dias[data_sel.strftime("%A")]
                st.info(f"Visualizando treino de: **{dia_pt}**")

            with col_timer:
                st.write("⏱️ Timer de Descanso")
                if st.button("Iniciar 60s"):
                    bar = st.progress(0)
                    for i in range(60):
                        time.sleep(1)
                        bar.progress((i + 1) / 60)
                    st.success("Fim do descanso! Próxima série.")

            st.divider()

            # Cronômetro de Sessão Real
            if 'timer_start' not in st.session_state: st.session_state.timer_start = None
            ci, cf, cs = st.columns([1, 1, 2])
            if ci.button("▶️ Começar Agora"):
                st.session_state.timer_start = time.time()
                st.rerun()
            if cf.button("⏹️ Finalizar Treino"):
                if st.session_state.timer_start:
                    dur = int(time.time() - st.session_state.timer_start)
                    conn.execute("INSERT INTO historico_treinos (usuario_id, data, duracao_segundos) VALUES (?,?,?)",
                                 (u_id, datetime.now().strftime("%Y-%m-%d"), dur))
                    conn.commit()
                    st.session_state.timer_start = None
                    st.success(f"Salvo com sucesso! Duração: {dur//60} min")
                    st.rerun()
            if st.session_state.timer_start: cs.warning("⏳ Cronômetro em andamento...")

            # Lista de Treino com Check-in
            df = pd.read_sql("SELECT * FROM treinos WHERE usuario_id=? AND dia_semana=?", conn, params=(u_id, dia_pt))
            if df.empty:
                st.write("😴 Dia de descanso ou sem treino agendado.")
            else:
                st.subheader(f"Ficha de {dia_pt}")
                for index, r in df.iterrows():
                    with st.container(border=True):
                        col_check, col_info = st.columns([1, 9])
                        col_check.checkbox("Feito", key=f"ex_{r['id']}")
                        col_info.write(f"**{r['exercicio']}** | {r['series']}x{r['repeticoes']} | {r['carga']}kg")
                        if r['link_video']:
                            with col_info.expander("🎥 Ver execução"):
                                st.video(r['link_video'])

        with tab2:
            st.subheader("Registrar Peso")
            with st.form("med"):
                p = st.number_input("Peso (kg)", 0.0)
                if st.form_submit_button("Salvar"):
                    conn.execute("INSERT INTO medidas (usuario_id, peso, data) VALUES (?,?,?)", (u_id, p, datetime.now().strftime("%Y-%m-%d")))
                    conn.commit()
                    st.rerun()
            
            df_med = pd.read_sql("SELECT peso, data FROM medidas WHERE usuario_id=? ORDER BY data ASC", conn, params=(u_id,))
            if not df_med.empty:
                st.plotly_chart(px.line(df_med, x="data", y="peso", markers=True, title="Evolução do Peso"), use_container_width=True)

        with tab3:
            st.subheader("🥤 Sugestão Nutricional")
            if peso_atual > 0:
                agua = peso_atual * 35 # 35ml por kg
                proteina = peso_atual * 2 # 2g por kg para hipertrofia
                st.success(f"Consumo diário sugerido para seu peso ({peso_atual}kg):")
                st.write(f"💧 **Água:** {agua/1000:.2f} litros")
                st.write(f"🥩 **Proteína:** {proteina:.0f}g - {proteina+40:.0f}g")
                st.caption("Nota: Consulte sempre um nutricionista para um plano personalizado.")
            else:
                st.warning("Registre seu peso na aba Evolução para ver os cálculos.")

        with tab4:
            st.subheader("💡 Dicas e Mentalidade")
            dicas = [
                "A disciplina te leva onde a motivação não consegue.",
                "Não compare o seu capítulo 1 com o capítulo 20 de outra pessoa.",
                "Seu único limite é você mesmo.",
                "O suor de hoje é a glória de amanhã."
            ]
            st.info(random.choice(dicas))
            st.image("https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=800&q=80")

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
