import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
import plotly.express as px

# =============================
# CONFIGURAÇÃO
# =============================
st.set_page_config(page_title="GymManager Pro v3.0", layout="wide", page_icon="🏋️")

# =============================
# BANCO DE DADOS
# =============================
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

def get_connection():
    return sqlite3.connect("gym_v3.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Usuários
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            login TEXT UNIQUE,
            senha TEXT,
            role TEXT,
            status_pagamento TEXT DEFAULT 'Em dia',
            objetivo TEXT
        )
    """)

    # Tipos de treino
    c.execute("CREATE TABLE IF NOT EXISTS tipos_treino (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)")

    # Fichas de treino
    c.execute("""
        CREATE TABLE IF NOT EXISTS fichas_treino (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            nome TEXT,
            data_criacao TEXT,
            ativo INTEGER DEFAULT 1,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    """)

    # Exercícios dentro da ficha
    c.execute("""
        CREATE TABLE IF NOT EXISTS exercicios_treino (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ficha_id INTEGER,
            tipo_treino TEXT,
            exercicio TEXT,
            series INTEGER,
            repeticoes TEXT,
            carga REAL,
            FOREIGN KEY(ficha_id) REFERENCES fichas_treino(id)
        )
    """)

    # Histórico de medidas
    c.execute("""
        CREATE TABLE IF NOT EXISTS medidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            peso REAL,
            cintura REAL,
            braco REAL,
            data TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    """)

    # Admin master padrão
    admin_hash = make_hashes('admin123')
    c.execute("INSERT OR IGNORE INTO usuarios (nome, login, senha, role) VALUES (?,?,?,?)",
              ('Master Admin','admin',admin_hash,'admin'))

    # Tipos de treino padrão
    tipos = ["Costas", "Peito", "Pernas", "Ombro", "Braços", "Abdômen", "Cardio"]
    for t in tipos:
        c.execute("INSERT OR IGNORE INTO tipos_treino (nome) VALUES (?)", (t,))

    conn.commit()
    conn.close()

init_db()

# =============================
# FUNÇÕES PDF
# =============================
def gerar_pdf(nome, ficha_nome, exercicios):
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    largura, altura = A4
    y = altura - 50

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, f"Ficha: {ficha_nome} - {nome}")
    y -= 40

    for tipo, exs in exercicios.items():
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y, tipo)
        y -= 20
        pdf.setFont("Helvetica", 10)

        for ex in exs:
            pdf.drawString(
                60, y,
                f"{ex['exercicio']} | {ex['series']}x{ex['repeticoes']} | {ex['carga']}kg"
            )
            y -= 15
            if y < 80:
                pdf.showPage()
                y = altura - 50
        y -= 10

    pdf.save()
    buf.seek(0)
    return buf

# =============================
# LOGIN / CADASTRO
# =============================
def login():
    st.title("🏋️ GymManager Pro v3.0 - Login")
    tab1, tab2 = st.tabs(["Login","Cadastro"])

    with tab1:
        u = st.text_input("Usuário")
        s = st.text_input("Senha", type="password")
        if st.button("Entrar", key="login_btn"):
            if not u or not s:
                st.error("Preencha todos os campos")
                return
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM usuarios WHERE login=?", (u,))
            user_data = c.fetchone()
            conn.close()
            if user_data and check_hashes(s, user_data[3]):
                st.session_state.user = {
                    "id": user_data[0],
                    "nome": user_data[1],
                    "login": user_data[2],
                    "role": user_data[4],
                    "status": user_data[5],
                    "objetivo": user_data[6]
                }
                st.success(f"Bem-vindo(a) {user_data[1]}")
                st.experimental_rerun()
            else:
                st.error("Usuário ou senha incorretos")

    with tab2:
        nome = st.text_input("Nome")
        login_input = st.text_input("Login", key="cad_login")
        senha_input = st.text_input("Senha", type="password", key="cad_senha")
        objetivo_input = st.selectbox("Objetivo", ["Hipertrofia","Emagrecimento","Condicionamento","Saúde"])
        if st.button("Criar Conta", key="cad_btn"):
            if not nome or not login_input or not senha_input:
                st.error("Preencha todos os campos")
                return
            try:
                h = make_hashes(senha_input)
                conn = get_connection()
                conn.execute("INSERT INTO usuarios (nome,login,senha,role,objetivo) VALUES (?,?,?,?,?)",
                             (nome,login_input,h,'aluno',objetivo_input))
                conn.commit()
                conn.close()
                st.success("Conta criada! Faça login.")
            except:
                st.error("Login já existe.")

# =============================
# PAINEL ADMIN
# =============================
def painel_admin():
    st.sidebar.title("🔐 Painel Master Admin")
    menu = st.sidebar.selectbox("Menu Admin", ["Alunos","Fichas & Treinos","Financeiro / Config"])
    conn = get_connection()

    if menu=="Alunos":
        st.header("👥 Gestão de Alunos")
        with st.expander("➕ Cadastrar Novo Aluno"):
            n = st.text_input("Nome", key="adm_n")
            l = st.text_input("Login", key="adm_l")
            s = st.text_input("Senha", key="adm_s", type="password")
            obj = st.selectbox("Objetivo", ["Hipertrofia","Emagrecimento","Condicionamento","Saúde"])
            if st.button("Cadastrar Aluno", key="adm_cad_btn"):
                try:
                    h = make_hashes(s)
                    conn.execute("INSERT INTO usuarios (nome,login,senha,role,objetivo) VALUES (?,?,?,?,?)",
                                 (n,l,h,'aluno',obj))
                    conn.commit()
                    st.success("Aluno cadastrado!")
                    st.experimental_rerun()
                except:
                    st.error("Login já existe")

        st.subheader("Lista de Alunos")
        df_alunos = pd.read_sql("SELECT id,nome,login,status_pagamento,objetivo FROM usuarios WHERE role='aluno'", conn)
        st.dataframe(df_alunos,use_container_width=True)

    elif menu=="Fichas & Treinos":
        st.header("📋 Gerenciar Treinos dos Alunos")
        alunos = pd.read_sql("SELECT id,nome FROM usuarios WHERE role='aluno'", conn)
        if not alunos.empty:
            sel = st.selectbox("Aluno", alunos["nome"])
            u_id = int(alunos[alunos["nome"]==sel]["id"].values[0])
            
            # Nova Ficha
            with st.expander("➕ Criar Nova Ficha"):
                nome_ficha = st.text_input("Nome da Ficha", key="adm_ficha_nome")
                if st.button("Criar Ficha", key="adm_ficha_btn"):
                    conn.execute("INSERT INTO fichas_treino (usuario_id,nome,data_criacao) VALUES (?,?,?)",
                                 (u_id,nome_ficha,datetime.now().strftime("%Y-%m-%d")))
                    conn.commit()
                    st.success("Ficha criada!"); st.experimental_rerun()
            
            # Selecionar ficha existente
            fichas = pd.read_sql("SELECT id,nome FROM fichas_treino WHERE usuario_id=? ORDER BY id DESC", conn, params=(u_id,))
            if not fichas.empty:
                sel_ficha = st.selectbox("Ficha Existente", fichas["nome"])
                f_id = int(fichas[fichas["nome"]==sel_ficha]["id"].values[0])

                tipos = pd.read_sql("SELECT nome FROM tipos_treino ORDER BY nome", conn)["nome"].tolist()
                tp = st.selectbox("Tipo de Treino", tipos, key="adm_tipo")
                ex = st.text_input("Exercício", key="adm_ex")
                se = st.number_input("Séries", 1,10,3,key="adm_se")
                re = st.text_input("Repetições", "12", key="adm_re")
                ca = st.number_input("Carga (kg)",0.0,key="adm_ca")
                if st.button("Adicionar Exercício", key="adm_add_ex"):
                    conn.execute("INSERT INTO exercicios_treino (ficha_id,tipo_treino,exercicio,series,repeticoes,carga) VALUES (?,?,?,?,?,?)",
                                 (f_id,tp,ex,se,re,ca))
                    conn.commit(); st.success("Exercício adicionado!")
                
                df_ex = pd.read_sql("SELECT tipo_treino,exercicio,series,repeticoes,carga FROM exercicios_treino WHERE ficha_id=?", conn, params=(f_id,))
                if not df_ex.empty:
                    st.table(df_ex)
                if st.button("Limpar Ficha", key="adm_clear_ficha"):
                    conn.execute("DELETE FROM exercicios_treino WHERE ficha_id=?", (f_id,))
                    conn.commit(); st.experimental_rerun()

    conn.close()

# =============================
# PAINEL ALUNO
# =============================
def painel_aluno():
    u_id = st.session_state.user["id"]
    conn = get_connection()
    st.title(f"Olá, {st.session_state.user['nome']}! 👋")
    
    # Aviso pagamento
    if st.session_state.user["status"] != "Em dia":
        st.warning("⚠️ Pendência de pagamento detectada!")

    tab1,tab2,tab3 = st.tabs(["🏋️ Meu Treino","📊 Minha Evolução","⚙️ Perfil"])
    
    with tab1:
        st.subheader("➕ Criar Nova Ficha de Treino")
        nome_ficha = st.text_input("Nome da Ficha", key="alu_ficha_nome")
        if st.button("Criar Ficha", key="alu_ficha_btn"):
            conn.execute("INSERT INTO fichas_treino (usuario_id,nome,data_criacao) VALUES (?,?,?)",
                         (u_id,nome_ficha,datetime.now().strftime("%Y-%m-%d")))
            conn.commit(); st.success("Ficha criada!"); st.experimental_rerun()
        
        # Selecionar ficha existente
        fichas = pd.read_sql("SELECT id,nome FROM fichas_treino WHERE usuario_id=? ORDER BY id DESC", conn, params=(u_id,))
        if not fichas.empty:
            sel_ficha = st.selectbox("Ficha Existente", fichas["nome"], key="alu_sel_ficha")
            f_id = int(fichas[fichas["nome"]==sel_ficha]["id"].values[0])

            tipos = pd.read_sql("SELECT nome FROM tipos_treino ORDER BY nome", conn)["nome"].tolist()
            novo_tipo = st.text_input("Ou novo Tipo de Treino", key="alu_novo_tipo")
            if novo_tipo:
                conn.execute("INSERT OR IGNORE INTO tipos_treino (nome) VALUES (?)",(novo_tipo,))
                conn.commit()
                st.success("Tipo adicionado!")
                tipos.append(novo_tipo)

            tp = st.selectbox("Tipo de Treino", tipos, key="alu_tipo")
            ex = st.text_input("Exercício", key="alu_ex")
            se = st.number_input("Séries",1,10,3,key="alu_se")
            re = st.text_input("Repetições","12",key="alu_re")
            ca = st.number_input("Carga(kg)",0.0,key="alu_ca")
            if st.button("Adicionar Exercício", key="alu_add_ex"):
                conn.execute("INSERT INTO exercicios_treino (ficha_id,tipo_treino,exercicio,series,repeticoes,carga) VALUES (?,?,?,?,?,?)",
                             (f_id,tp,ex,se,re,ca))
                conn.commit(); st.success("Exercício adicionado!")

            df_ex = pd.read_sql("SELECT tipo_treino,exercicio,series,repeticoes,carga FROM exercicios_treino WHERE ficha_id=?", conn, params=(f_id,))
            if not df_ex.empty:
                st.table(df_ex)
                treinos_dict = df_ex.groupby("tipo_treino").apply(lambda x: x.to_dict("records")).to_dict()
                pdf = gerar_pdf(st.session_state.user["nome"], sel_ficha, treinos_dict)
                st.download_button("📄 Baixar PDF", pdf, file_name=f"{sel_ficha}.pdf")

    with tab2:
        st.subheader("Registrar Medidas / Evolução")
        with st.form("medidas_form"):
            p = st.number_input("Peso (kg)",0.0,key="m_peso")
            ci = st.number_input("Cintura (cm)",0.0,key="m_cintura")
            br = st.number_input("Braço (cm)",0.0,key="m_braco")
            if st.form_submit_button("Salvar Medidas"):
                conn.execute("INSERT INTO medidas (usuario_id,peso,cintura,braco,data) VALUES (?,?,?,?,?)",
                             (u_id,p,ci,br,datetime.now().strftime("%Y-%m-%d")))
                conn.commit(); st.success("Medidas salvas!")

        df_m = pd.read_sql("SELECT peso,cintura,braco,data FROM medidas WHERE usuario_id=? ORDER BY data ASC", conn, params=(u_id,))
        if not df_m.empty:
            fig = px.line(df_m, x="data", y=["peso","cintura","braco"], markers=True, title="Evolução Corporal")
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("⚙️ Perfil")
        st.write(f"Login: {st.session_state.user['login']}")
        st.write(f"Objetivo: {st.session_state.user['objetivo']}")
        st.write(f"Status Pagamento: {st.session_state.user['status']}")
        if st.button("Alterar Senha"):
            st.info("Solicite ao admin reset da senha")

    conn.close()

# =============================
# LÓGICA PRINCIPAL
# =============================
if "user" not in st.session_state:
    login()
else:
    if st.sidebar.button("🚪 Sair"):
        st.session_state.clear()
        st.experimental_rerun()
    
    if st.session_state.user["role"]=="admin":
        painel_admin()
    else:
        painel_aluno()
