import streamlit as st
import pandas as pd
import sqlite3
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO

# Configuração da página
st.set_page_config(page_title="GymManager Pro", layout="wide", page_icon="🏋️")

# =============================
# GESTÃO DO BANCO DE DADOS
# =============================
def get_connection():
    return sqlite3.connect("gym.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Tabela de Usuários
    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        login TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,
        role TEXT NOT NULL
    )
    """)
    # Tabela de Tipos de Treino
    c.execute("""
    CREATE TABLE IF NOT EXISTS tipos_treino (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL
    )
    """)
    # Tabela de Treinos
    c.execute("""
    CREATE TABLE IF NOT EXISTS treinos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        tipo_treino TEXT,
        exercicio TEXT,
        series INTEGER,
        repeticoes TEXT,
        carga REAL,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    )
    """)
    # Admin padrão
    c.execute("INSERT OR IGNORE INTO usuarios (nome, login, senha, role) VALUES ('Administrador', 'admin', 'admin', 'admin')")
    
    # Tipos de treino padrão
    tipos = ["Costas", "Peito", "Pernas", "Ombro", "Braços", "Abdômen", "Full Body"]
    for t in tipos:
        c.execute("INSERT OR IGNORE INTO tipos_treino (nome) VALUES (?)", (t,))
    
    conn.commit()
    conn.close()

init_db()

# =============================
# LÓGICA DE LOGIN
# =============================
def login():
    st.title("🏋️ GymManager Pro")
    st.subheader("Acesse sua conta")
    
    with st.form("login_form"):
        login_user = st.text_input("Login")
        senha = st.text_input("Senha", type="password")
        submit = st.form_submit_button("Entrar")

        if submit:
            conn = get_connection()
            query = "SELECT * FROM usuarios WHERE login=? AND senha=?"
            df = pd.read_sql(query, conn, params=(login_user, senha))
            conn.close()

            if not df.empty:
                st.session_state.user = df.iloc[0].to_dict()
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

# =============================
# EXPORTAÇÃO PDF
# =============================
def gerar_pdf(nome, treinos_dict):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, y, f"Ficha de Treino: {nome}")
    y -= 40

    for tipo, exercicios in treinos_dict.items():
        if y < 100: p.showPage(); y = height - 50
        p.setFont("Helvetica-Bold", 14)
        p.setFillColorRGB(0.1, 0.3, 0.6)
        p.drawString(50, y, f"--- {tipo} ---")
        y -= 25
        p.setFillColorRGB(0, 0, 0)
        p.setFont("Helvetica", 11)

        for ex in exercicios:
            texto = f"• {ex['exercicio']}: {ex['series']}x{ex['repeticoes']} - Carga: {ex['carga']}kg"
            p.drawString(60, y, texto)
            y -= 20
            if y < 50: p.showPage(); y = height - 50
        y -= 10

    p.save()
    buffer.seek(0)
    return buffer

# =============================
# PAINEL ADMINISTRATIVO
# =============================
def painel_admin():
    st.sidebar.title("🔐 Administração")
    menu = st.sidebar.radio("Navegação", ["Gerenciar Alunos", "Configurar Treinos", "Tipos de Treino"])

    conn = get_connection()

    if menu == "Gerenciar Alunos":
        st.header("👥 Cadastro e Gestão de Alunos")
        
        # Cadastro
        with st.expander("Cadastrar Novo Aluno"):
            nome = st.text_input("Nome Completo")
            log = st.text_input("Login de Acesso")
            pwd = st.text_input("Senha Provisória", type="password")
            if st.button("Salvar Cadastro"):
                if nome and log and pwd:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO usuarios (nome, login, senha, role) VALUES (?, ?, ?, 'aluno')", (nome, log, pwd))
                        conn.commit()
                        st.success("Aluno cadastrado!")
                        st.rerun()
                    except: st.error("Este login já está em uso.")
                else: st.warning("Preencha todos os campos.")

        # Listagem e Exclusão
        st.subheader("Lista de Alunos")
        alunos_df = pd.read_sql("SELECT id, nome, login FROM usuarios WHERE role='aluno'", conn)
        if not alunos_df.empty:
            for _, row in alunos_df.iterrows():
                col1, col2 = st.columns([4, 1])
                col1.write(f"**{row['nome']}** (Login: {row['login']})")
                if col2.button("❌", key=f"del_{row['id']}"):
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM usuarios WHERE id=?", (row['id'],))
                    conn.commit()
                    st.rerun()
        else: st.info("Nenhum aluno cadastrado.")

    elif menu == "Configurar Treinos":
        st.header("🏋️ Montar Ficha de Treino")
        alunos = pd.read_sql("SELECT id, nome FROM usuarios WHERE role='aluno'", conn)
        tipos = pd.read_sql("SELECT nome FROM tipos_treino", conn)

        if alunos.empty:
            st.warning("Cadastre um aluno primeiro.")
        else:
            aluno_sel = st.selectbox("Selecione o Aluno", alunos["nome"])
            aluno_id = int(alunos[alunos["nome"] == aluno_sel]["id"].values[0])
            
            with st.container(border=True):
                c1, c2 = st.columns(2)
                tipo = c1.selectbox("Tipo de Treino", tipos["nome"])
                ex = c2.text_input("Nome do Exercício")
                
                c3, c4, c5 = st.columns(3)
                ser = c3.number_input("Séries", 1, 10, 3)
                rep = c4.text_input("Repetições", "12")
                car = c5.number_input("Carga (kg)", 0.0, 500.0, 10.0)
                
                if st.button("Adicionar Exercício"):
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO treinos (usuario_id, tipo_treino, exercicio, series, repeticoes, carga) VALUES (?,?,?,?,?,?)",
                                 (aluno_id, tipo, ex, ser, rep, car))
                    conn.commit()
                    st.toast("Adicionado!")

            # Visualizar e limpar treino atual
            st.subheader(f"Treino Atual de {aluno_sel}")
            treino_df = pd.read_sql("SELECT id, tipo_treino, exercicio, series, repeticoes, carga FROM treinos WHERE usuario_id=?", conn, params=(aluno_id,))
            if not treino_df.empty:
                st.table(treino_df.drop(columns=["id"]))
                if st.button("Limpar Toda a Ficha"):
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM treinos WHERE usuario_id=?", (aluno_id,))
                    conn.commit()
                    st.rerun()
            else: st.info("Ficha vazia.")

    elif menu == "Tipos de Treino":
        st.header("🏷️ Categorias de Treino")
        novo_tipo = st.text_input("Novo Tipo (Ex: Crossfit)")
        if st.button("Adicionar"):
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO tipos_treino (nome) VALUES (?)", (novo_tipo,))
                conn.commit()
                st.rerun()
            except: st.error("Já existe.")
        
        tipos_df = pd.read_sql("SELECT nome FROM tipos_treino", conn)
        st.dataframe(tipos_df, use_container_width=True)

    conn.close()

# =============================
# PAINEL DO ALUNO
# =============================
def painel_aluno():
    st.header(f"💪 Olá, {st.session_state.user['nome']}!")
    conn = get_connection()
    df = pd.read_sql("SELECT tipo_treino, exercicio, series, repeticoes, carga FROM treinos WHERE usuario_id=?", 
                     conn, params=(st.session_state.user["id"],))
    conn.close()

    if df.empty:
        st.info("Sua ficha ainda não foi montada pelos instrutores.")
    else:
        for tipo in df["tipo_treino"].unique():
            with st.expander(f"TREINO: {tipo.upper()}", expanded=True):
                sub_df = df[df["tipo_treino"] == tipo]
                st.table(sub_df[["exercicio", "series", "repeticoes", "carga"]])
        
        # Preparar dados para PDF
        treinos_pdf = df.groupby("tipo_treino").apply(lambda x: x.to_dict("records")).to_dict()
        pdf_file = gerar_pdf(st.session_state.user["nome"], treinos_pdf)
        st.download_button("📥 Baixar Minha Ficha (PDF)", pdf_file, file_name="meu_treino.pdf")

# =============================
# FLUXO PRINCIPAL
# =============================
if "user" not in st.session_state:
    login()
else:
    st.sidebar.markdown(f"### Bem-vindo, \n**{st.session_state.user['nome']}**")
    if st.sidebar.button("Sair"):
        st.session_state.clear()
        st.rerun()

    if st.session_state.user["role"] == "admin":
        painel_admin()
    else:
        painel_aluno()
