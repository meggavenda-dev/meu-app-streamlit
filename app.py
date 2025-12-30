import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import hashlib
from datetime import datetime
import time

# =============================
# CONFIGURAÇÃO E CSS (Streamlit Padrão)
# =============================
st.set_page_config(page_title="GymManager Pro v4.0", layout="wide", page_icon="💪")

# CSS para um visual um pouco mais clean
st.markdown("""
<style>
    .reportview-container .main .block-container{
        padding-top: 2rem;
        padding-right: 1rem;
        padding-left: 1rem;
        padding-bottom: 2rem;
    }
    .css-1d391kg { /* sidebar */
        background-color: #f0f2f6;
    }
    .stSelectbox, .stTextInput, .stNumberInput {
        margin-bottom: 0.5rem;
    }
    .stButton>button {
        border-radius: 0.5rem;
        border: 1px solid #ff4b4b;
        color: #ff4b4b;
    }
    .stButton>button:hover {
        background-color: #ff4b4b;
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
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT, login TEXT UNIQUE, senha TEXT, role TEXT,
        status_pagamento TEXT DEFAULT 'Em dia', objetivo TEXT,
        altura REAL)""") # Adicionada altura para IMC
    
    c.execute("""CREATE TABLE IF NOT EXISTS treinos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER, dia_semana TEXT, tipo_treino TEXT,
        exercicio TEXT, series INTEGER, repeticoes TEXT, carga REAL,
        link_video TEXT, -- Adicionado campo para vídeo
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")

    c.execute("""CREATE TABLE IF NOT EXISTS medidas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER,
        peso REAL, cintura REAL, braco REAL, data TEXT,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")
    
    # Nova tabela para registrar o término do treino
    c.execute("""CREATE TABLE IF NOT EXISTS historico_treinos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER, data TEXT, duracao_segundos INTEGER,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")

    admin_hash = make_hashes('admin123')
    c.execute("INSERT OR IGNORE INTO usuarios (nome, login, senha, role) VALUES (?,?,?,?,?)",
              ('Master Admin', 'admin', admin_hash, 'admin', '175')) # Altura padrão para admin
    conn.commit()
    conn.close()

init_db()

DIAS_SEMANA = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]

# =============================
# PAINEL ADMINISTRATIVO (ATUALIZADO)
# =============================
def painel_admin():
    st.sidebar.title("🛠️ Painel de Controle Admin")
    menu = st.sidebar.radio("Navegação Principal", ["Dashboard Alunos", "Prescrever Treino", "Financeiro", "Configurações"])
    conn = get_connection()

    if menu == "Dashboard Alunos":
        st.header("📊 Resumo de Alunos")
        df_alunos = pd.read_sql("SELECT id, nome, login, status_pagamento, objetivo, altura FROM usuarios WHERE role='aluno'", conn)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Alunos", len(df_alunos))
        col2.metric("Alunos em Dia", len(df_alunos[df_alunos['status_pagamento'] == 'Em dia']), delta_color="normal")
        col3.metric("Alunos Pendentes", len(df_alunos[df_alunos['status_pagamento'] != 'Em dia']), delta_color="inverse")
        
        st.subheader("Lista Detalhada")
        st.dataframe(df_alunos, use_container_width=True)

        with st.expander("➕ Cadastrar Novo Aluno", expanded=False):
            with st.form("form_novo_aluno", clear_on_submit=True):
                n = st.text_input("Nome Completo")
                l = st.text_input("Login (único)")
                p = st.text_input("Senha Inicial", type="password")
                obj = st.selectbox("Objetivo", ["Hipertrofia", "Emagrecimento", "Saúde"])
                altura_cm = st.number_input("Altura (cm)", min_value=50, max_value=250, value=170)
                
                if st.form_submit_button("Salvar Cadastro"):
                    if n and l and p:
                        try:
                            h = make_hashes(p)
                            conn.execute("INSERT INTO usuarios (nome,login,senha,role,objetivo,altura) VALUES (?,?,?,?,?,?)", 
                                         (n, l, h, 'aluno', obj, altura_cm))
                            conn.commit()
                            st.success(f"Aluno {n} cadastrado com sucesso!")
                            time.sleep(1); st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Erro: Este login já existe.")
                    else:
                        st.warning("Preencha todos os campos obrigatórios.")

    elif menu == "Prescrever Treino":
        st.header("📝 Montar/Editar Treino Semanal")
        alunos = pd.read_sql("SELECT id, nome FROM usuarios WHERE role='aluno'", conn)
        
        if alunos.empty:
            st.warning("Nenhum aluno cadastrado. Cadastre um aluno primeiro.")
        else:
            sel_aluno = st.selectbox("Selecione o Aluno", alunos["nome"].tolist() if not alunos.empty else [])
            aluno_row = alunos[alunos["nome"] == sel_aluno]
            
            if not aluno_row.empty:
                a_id = int(aluno_row.iloc[0]["id"])
                
                # Exibir treino atual do aluno
                st.subheader(f"Cronograma atual de {sel_aluno}")
                df_atual_treino = pd.read_sql("SELECT id, dia_semana, tipo_treino, exercicio, series, repeticoes, carga, link_video FROM treinos WHERE usuario_id=?", conn, params=(a_id,))
                st.dataframe(df_atual_treino, use_container_width=True)

                col_limpar, col_editar = st.columns(2)
                if col_limpar.button("🗑️ Limpar Toda a Ficha", help="Apaga todos os exercícios deste aluno"):
                    conn.execute("DELETE FROM treinos WHERE usuario_id=?", (a_id,))
                    conn.commit()
                    st.success("Ficha limpa com sucesso!"); st.rerun()
                
                with st.expander("➕ Adicionar Novo Exercício", expanded=True):
                    with st.form("add_exercicio_form", clear_on_submit=True):
                        col_dia, col_tipo_treino = st.columns(2)
                        dia = col_dia.selectbox("Dia da Semana", DIAS_SEMANA)
                        tipo = col_tipo_treino.text_input("Grupamento (Ex: Peito, Costas, Pernas)")
                        
                        c1, c2, c3 = st.columns([2,1,1])
                        ex = c1.text_input("Nome do Exercício")
                        se = c2.number_input("Séries", min_value=1, max_value=20, value=3)
                        ca = c3.number_input("Carga (kg)", min_value=0.0, value=10.0)
                        
                        re = st.text_input("Repetições (Ex: 12-15, Até a falha)")
                        link_video = st.text_input("Link do Vídeo (YouTube)", help="Ex: https://www.youtube.com/watch?v=ExemploID")
                        
                        if st.form_submit_button("Salvar Exercício"):
                            if ex and tipo:
                                conn.execute("""INSERT INTO treinos (usuario_id, dia_semana, tipo_treino, exercicio, series, repeticoes, carga, link_video) 
                                             VALUES (?,?,?,?,?,?,?,?)""", (a_id, dia, tipo, ex, se, re, ca, link_video))
                                conn.commit()
                                st.success(f"Exercício '{ex}' adicionado para {dia}!")
                                st.rerun()
                            else:
                                st.error("Nome do Exercício e Grupamento são obrigatórios.")
                
    elif menu == "Financeiro":
        st.header("💰 Controle de Pagamentos")
        df_fin = pd.read_sql("SELECT id, nome, status_pagamento FROM usuarios WHERE role='aluno'", conn)
        
        st.dataframe(df_fin, use_container_width=True)

        for _, r in df_fin.iterrows():
            col1, col2 = st.columns([3,1])
            status_emoji = "✅" if r['status_pagamento'] == "Em dia" else "⚠️"
            col1.write(f"{status_emoji} **{r['nome']}** - Status: `{r['status_pagamento']}`")
            if col2.button("Alternar Status", key=f"pay_btn_{r['id']}", help="Muda entre 'Em dia' e 'Pendente'"):
                novo = "Pendente" if r['status_pagamento'] == "Em dia" else "Em dia"
                conn.execute("UPDATE usuarios SET status_pagamento=? WHERE id=?", (novo, r['id']))
                conn.commit()
                st.toast(f"Status de {r['nome']} alterado para {novo}!")
                st.rerun()

    elif menu == "Configurações":
        st.header("⚙️ Configurações Gerais")
        st.write("Em desenvolvimento...")
    
    conn.close()

# =============================
# PAINEL DO ALUNO (ATUALIZADO)
# =============================
def painel_aluno():
    u_id = st.session_state.user["id"]
    conn = get_connection()
    
    st.title(f"Bem-vindo(a), {st.session_state.user['nome']}! 💪")
    
    if st.session_state.user["status"] != "Em dia":
        st.warning("🚨 **Mensalidade Pendente:** Por favor, regularize seu pagamento para evitar bloqueio de acesso.")

    tab_treino, tab_progresso, tab_imc = st.tabs(["🏋️ Meu Treino", "📈 Meu Progresso", "📊 Calculadora IMC"])

    with tab_treino:
        st.subheader("📋 Treino do Dia")
        
        # Seleção do dia da semana
        dia_atual = datetime.now().weekday() # 0 = Segunda, 6 = Domingo
        dia_selecionado = st.selectbox("Selecione o dia para ver o treino:", DIAS_SEMANA, index=dia_atual)

        df_t = pd.read_sql("SELECT * FROM treinos WHERE usuario_id=? AND dia_semana=?", conn, params=(u_id, dia_selecionado))
        
        if df_t.empty:
            st.info(f"Nenhum treino agendado para **{dia_selecionado}**.")
        else:
            grupamento = df_t["tipo_treino"].iloc[0]
            st.markdown(f"**Foco principal: {grupamento.upper()}**")
            
            # --- Cronômetro de Descanso ---
            if 'timer_running' not in st.session_state:
                st.session_state.timer_running = False
            if 'rest_time_start' not in st.session_state:
                st.session_state.rest_time_start = None

            col_rest_btn, col_rest_display = st.columns([1,3])
            
            if col_rest_btn.button("⏱️ Iniciar Descanso (60s)"):
                st.session_state.timer_running = True
                st.session_state.rest_time_start = time.time()
                st.toast("Descanso iniciado! ⏰")
            
            if st.session_state.timer_running:
                elapsed_time = int(time.time() - st.session_state.rest_time_start)
                remaining_time = 60 - elapsed_time
                if remaining_time > 0:
                    col_rest_display.info(f"Descanso: {remaining_time}s restantes...")
                    time.sleep(1)
                    st.experimental_rerun() # Para atualizar o timer
                else:
                    st.session_state.timer_running = False
                    col_rest_display.success("✅ FIM DO DESCANSO! Próxima série!")
                    st.balloons()

            # --- Lista de Exercícios ---
            for _, row in df_t.iterrows():
                with st.container(border=True):
                    col_ex_info, col_ex_video = st.columns([3,2])
                    
                    col_ex_info.markdown(f"**{row['exercicio']}**")
                    col_ex_info.write(f"👉 {row['series']}x{row['repeticoes']} | Carga: {row['carga']}kg")
                    
                    if row['link_video']:
                        col_ex_video.video(row['link_video'])
                        # Ou um botão para abrir em nova aba
                        # col_ex_video.markdown(f"[Ver Vídeo]({row['link_video']}) 🎥")
            
            # --- Cronômetro de Treino (Total) ---
            st.markdown("---")
            st.subheader("⏰ Acompanhamento do Treino")
            if 'total_treino_start_time' not in st.session_state:
                st.session_state.total_treino_start_time = None
            
            c_start, c_stop, c_display = st.columns([1,1,2])
            
            if c_start.button("▶️ Iniciar Treino Total", key="start_total_treino"):
                st.session_state.total_treino_start_time = time.time()
                st.toast("Treino total iniciado!")
            
            if c_stop.button("⏹️ Finalizar Treino Total", key="stop_total_treino"):
                if st.session_state.total_treino_start_time:
                    duracao = int(time.time() - st.session_state.total_treino_start_time)
                    conn.execute("INSERT INTO historico_treinos (usuario_id, data, duracao_segundos) VALUES (?,?,?)",
                                 (u_id, datetime.now().strftime("%Y-%m-%d"), duracao))
                    conn.commit()
                    st.success(f"Treino finalizado! Duração: {duracao // 60}min {duracao % 60}s")
                    st.session_state.total_treino_start_time = None
                    st.balloons()
                else:
                    st.warning("O treino não foi iniciado.")
            
            if st.session_state.total_treino_start_time:
                total_elapsed = int(time.time() - st.session_state.total_treino_start_time)
                mins_total, secs_total = divmod(total_elapsed, 60)
                c_display.info(f"Tempo total: {mins_total:02d}:{secs_total:02d}")
                time.sleep(1)
                st.experimental_rerun() # Atualiza o tempo

    with tab_progresso:
        st.subheader("📈 Minha Evolução")
        
        # --- Gráfico de Peso e Medidas ---
        df_m = pd.read_sql("SELECT peso, cintura, braco, data FROM medidas WHERE usuario_id=? ORDER BY data ASC", conn, params=(u_id,))
        if not df_m.empty:
            fig = px.line(df_m, x="data", y=["peso", "cintura", "braco"], markers=True, title="Evolução Corporal")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Registre suas medidas para ver o gráfico.")
        
        with st.expander("➕ Registrar Novas Medidas"):
            with st.form("form_medidas", clear_on_submit=True):
                p = st.number_input("Peso (kg)", min_value=0.0, value=70.0, format="%.1f")
                ci = st.number_input("Cintura (cm)", min_value=0.0, value=80.0, format="%.1f")
                br = st.number_input("Braço (cm)", min_value=0.0, value=30.0, format="%.1f")
                if st.form_submit_button("Salvar Medidas"):
                    conn.execute("INSERT INTO medidas (usuario_id, peso, cintura, braco, data) VALUES (?,?,?,?,?)",
                                 (u_id, p, ci, br, datetime.now().strftime("%Y-%m-%d")))
                    conn.commit()
                    st.success("Medidas registradas com sucesso!"); st.rerun()
        
        # --- Histórico de Duração de Treino ---
        st.subheader("Histórico de Duração dos Treinos")
        df_hist_treino = pd.read_sql("SELECT data, duracao_segundos FROM historico_treinos WHERE usuario_id=? ORDER BY data ASC", conn, params=(u_id,))
        if not df_hist_treino.empty:
            df_hist_treino['duracao_minutos'] = df_hist_treino['duracao_segundos'] / 60
            fig_duracao = px.bar(df_hist_treino, x="data", y="duracao_minutos", title="Duração dos Treinos (minutos)")
            st.plotly_chart(fig_duracao, use_container_width=True)
        else:
            st.info("Inicie e finalize seus treinos para registrar a duração.")

    with tab_imc:
        st.subheader("📊 Calculadora de IMC")
        st.info("IMC: Índice de Massa Corporal. Não substitui avaliação profissional.")
        
        # Obter altura do usuário logado (se disponível)
        altura_usuario = pd.read_sql("SELECT altura FROM usuarios WHERE id=?", conn, params=(u_id,)).iloc[0]['altura'] if not pd.read_sql("SELECT altura FROM usuarios WHERE id=?", conn, params=(u_id,)).empty else 0
        
        with st.form("form_imc", clear_on_submit=True):
            peso_imc = st.number_input("Seu Peso (kg)", min_value=0.0, value=70.0, format="%.1f", key="peso_imc")
            altura_imc = st.number_input("Sua Altura (cm)", min_value=50, max_value=250, value=int(altura_usuario), key="altura_imc")
            
            if st.form_submit_button("Calcular IMC"):
                if peso_imc > 0 and altura_imc > 0:
                    altura_metros = altura_imc / 100
                    imc = peso_imc / (altura_metros ** 2)
                    
                    st.write(f"Seu IMC é: **{imc:.2f}**")
                    
                    if imc < 18.5:
                        st.warning("Classificação: Abaixo do peso")
                    elif 18.5 <= imc < 24.9:
                        st.success("Classificação: Peso normal")
                    elif 25 <= imc < 29.9:
                        st.warning("Classificação: Sobrepeso")
                    elif 30 <= imc < 34.9:
                        st.error("Classificação: Obesidade Grau I")
                    elif 35 <= imc < 39.9:
                        st.error("Classificação: Obesidade Grau II")
                    else:
                        st.error("Classificação: Obesidade Grau III")
                else:
                    st.error("Peso e altura devem ser maiores que zero.")
        
        st.markdown("---")
        st.write("Deseja atualizar sua altura no cadastro?")
        with st.form("form_atualizar_altura", clear_on_submit=True):
            nova_altura = st.number_input("Nova Altura (cm)", min_value=50, max_value=250, value=int(altura_usuario), key="nova_altura_profile")
            if st.form_submit_button("Salvar Nova Altura"):
                conn.execute("UPDATE usuarios SET altura=? WHERE id=?", (nova_altura, u_id))
                conn.commit()
                st.success("Altura atualizada com sucesso!"); st.rerun()

    conn.close()

# =============================
# LÓGICA DE LOGIN/CADASTRO
# =============================
def login_screen():
    st.title("🏋️ GymManager Pro - Acesso")
    tab_l, tab_c = st.tabs(["Entrar", "Criar Conta"])
    
    with tab_l:
        with st.form("login_form"):
            u = st.text_input("Login")
            s = st.text_input("Senha", type="password")
            if st.form_submit_button("Acessar", use_container_width=True):
                conn = get_connection()
                c = conn.cursor()
                c.execute("SELECT * FROM usuarios WHERE login=?", (u,))
                res = c.fetchone()
                conn.close()
                if res and check_hashes(s, res[3]):
                    st.session_state.user = {"id": res[0], "nome": res[1], "role": res[4], "status": res[5]}
                    st.rerun()
                else:
                    st.error("Login ou senha inválidos.")

    with tab_c:
        with st.form("cadastro_form"):
            n = st.text_input("Nome Completo")
            l = st.text_input("Escolha um Login")
            p = st.text_input("Escolha uma Senha", type="password")
            altura_cadastro = st.number_input("Sua Altura (cm)", min_value=50, max_value=250, value=170)
            if st.form_submit_button("Cadastrar", use_container_width=True):
                if n and l and p:
                    try:
                        conn = get_connection()
                        conn.execute("INSERT INTO usuarios (nome,login,senha,role,altura) VALUES (?,?,?,?,?)", (n,l,make_hashes(p),'aluno', altura_cadastro))
                        conn.commit()
                        conn.close()
                        st.success("Conta criada! Agora faça login.")
                    except sqlite3.IntegrityError:
                        st.error("Este login já está em uso.")
                else:
                    st.error("Preencha todos os campos para cadastrar.")

# =============================
# MAIN APP LOGIC
# =============================
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    login_screen()
else:
    with st.sidebar:
        st.write(f"Conectado como: **{st.session_state.user['nome']}**")
        if st.button("🚪 Sair", key="logout_btn"):
            st.session_state.user = None
            st.rerun()
    
    if st.session_state.user["role"] == "admin":
        painel_admin()
    else:
        painel_aluno()
