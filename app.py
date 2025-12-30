import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime

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
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        login TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,
        role TEXT NOT NULL)""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS tipos_treino (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL)""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS treinos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        tipo_treino TEXT,
        exercicio TEXT,
        series INTEGER,
        repeticoes TEXT,
        carga REAL,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS medidas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        peso REAL,
        cintura REAL,
        braço REAL,
        data TEXT,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")
    
    c.execute("INSERT OR IGNORE INTO usuarios (nome, login, senha, role) VALUES ('Administrador', 'admin', 'admin', 'admin')")
    tipos = ["Costas", "Peito", "Pernas", "Ombro", "Braços", "Abdômen", "Cardio"]
    for t in tipos:
        c.execute("INSERT OR IGNORE INTO tipos_treino (nome) VALUES (?)", (t,))
    conn.commit()
    conn.close()

init_db()

# =============================
# UTILITÁRIOS (PDF E LOGIN)
# =============================
def gerar_pdf(nome, treinos_dict):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, y, f"Ficha de Treino: {nome}")
    y -= 50
    for tipo, exercicios in treinos_dict.items():
        if y < 100: p.showPage(); y = 800
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, f"--- {tipo} ---")
        y -= 25
        p.setFont("Helvetica", 11)
        for ex in exercicios:
            p.drawString(60, y, f"• {ex['exercicio']}: {ex['series']}x{ex['repeticoes']} - {ex['carga']}kg")
            y -= 20
        y -= 10
    p.save()
    buffer.seek(0)
    return buffer

def login():
    st.title("🏋️ GymManager Pro")
    with st.form("login_form"):
        u, s = st.text_input("Login"), st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            conn = get_connection()
            df = pd.read_sql("SELECT * FROM usuarios WHERE login=? AND senha=?", conn, params=(u, s))
            conn.close()
            if not df.empty:
                st.session_state.user = df.iloc[0].to_dict()
                st.rerun()
            else: st.error("Acesso negado.")

# =============================
# PAINEL ADMINISTRATIVO
# =============================
def painel_admin():
    st.sidebar.title("🔐 Administração")
    menu = st.sidebar.radio("Navegação", ["Alunos", "Treinos", "Configurações"])
    conn = get_connection()

    if menu == "Alunos":
        st.header("👥 Gestão de Alunos")
        with st.expander("➕ Cadastrar Novo Aluno"):
            n, l, p = st.text_input("Nome"), st.text_input("Login"), st.text_input("Senha", type="password")
            if st.button("Salvar"):
                try:
                    c = conn.cursor()
                    c.execute("INSERT INTO usuarios (nome,login,senha,role) VALUES (?,?,?,'aluno')", (n,l,p))
                    conn.commit()
                    st.success("Cadastrado!"); st.rerun()
                except: st.error("Login duplicado.")

        alunos_df = pd.read_sql("SELECT id, nome, login FROM usuarios WHERE role='aluno'", conn)
        for _, row in alunos_df.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.write(f"**{row['nome']}**")
                if col2.button("🔑 Senha", key=f"pw_{row['id']}"): st.session_state[f"edit_{row['id']}"] = True
                if col3.button("❌", key=f"del_{row['id']}"):
                    conn.execute("DELETE FROM usuarios WHERE id=?", (row['id'],)); conn.commit(); st.rerun()
                
                if st.session_state.get(f"edit_{row['id']}", False):
                    nova = st.text_input("Nova Senha", type="password", key=f"in_{row['id']}")
                    if st.button("Confirmar", key=f"btn_{row['id']}"):
                        conn.execute("UPDATE usuarios SET senha=? WHERE id=?", (nova, row['id'])); conn.commit()
                        st.session_state[f"edit_{row['id']}"] = False; st.success("Alterada!"); st.rerun()

    elif menu == "Treinos":
        st.header("🏋️ Montar Ficha")
        alunos = pd.read_sql("SELECT id, nome FROM usuarios WHERE role='aluno'", conn)
        tipos = pd.read_sql("SELECT nome FROM tipos_treino", conn)
        
        if not alunos.empty:
            sel_aluno = st.selectbox("Aluno", alunos["nome"])
            a_id = int(alunos[alunos["nome"] == sel_aluno]["id"].values[0])
            
            with st.form("add_ex"):
                c1, c2, c3, c4 = st.columns(4)
                t = c1.selectbox("Tipo", tipos["nome"])
                ex = c2.text_input("Exercício")
                ser = c3.number_input("Séries", 1, 10)
                rep = c4.text_input("Reps", "12")
                car = st.number_input("Carga (kg)", 0.0)
                if st.form_submit_button("Adicionar"):
                    conn.execute("INSERT INTO treinos (usuario_id, tipo_treino, exercicio, series, repeticoes, carga) VALUES (?,?,?,?,?,?)",
                                 (a_id, t, ex, ser, rep, car)); conn.commit(); st.toast("Adicionado!")
            
            df_t = pd.read_sql("SELECT id, tipo_treino, exercicio, carga FROM treinos WHERE usuario_id=?", conn, params=(a_id,))
            st.dataframe(df_t, use_container_width=True)
            if st.button("Limpar Ficha"):
                conn.execute("DELETE FROM treinos WHERE usuario_id=?", (a_id,)); conn.commit(); st.rerun()

    elif menu == "Configurações":
        st.header("⚙️ Tipos de Treino")
        novo = st.text_input("Novo Tipo")
        if st.button("Adicionar"):
            try: conn.execute("INSERT INTO tipos_treino (nome) VALUES (?)", (novo,)); conn.commit(); st.rerun()
            except: st.error("Existe.")
    conn.close()

# =============================
# PAINEL DO ALUNO
# =============================
def painel_aluno():
    st.header(f"👋 Bem-vindo, {st.session_state.user['nome']}!")
    tab1, tab2, tab3 = st.tabs(["🏋️ Meu Treino", "📈 Evolução", "⚙️ Perfil"])
    conn = get_connection()
    u_id = st.session_state.user["id"]

    with tab1:
        df = pd.read_sql("SELECT * FROM treinos WHERE usuario_id=?", conn, params=(u_id,))
        if df.empty: st.info("Sem treino cadastrado.")
        else:
            for t in df["tipo_treino"].unique():
                with st.expander(f"TREINO {t.upper()}"):
                    st.table(df[df["tipo_treino"] == t][["exercicio", "series", "repeticoes", "carga"]])
            pdf = gerar_pdf(st.session_state.user["nome"], df.groupby("tipo_treino").apply(lambda x: x.to_dict("records")).to_dict())
            st.download_button("📥 PDF da Ficha", pdf, "treino.pdf")

    with tab2:
        st.subheader("Registrar Medidas")
        with st.form("medidas"):
            c1, c2, c3 = st.columns(3)
            p = c1.number_input("Peso (kg)", 0.0)
            cin = c2.number_input("Cintura (cm)", 0.0)
            br = c3.number_input("Braço (cm)", 0.0)
            if st.form_submit_button("Salvar Medida"):
                conn.execute("INSERT INTO medidas (usuario_id, peso, cintura, braço, data) VALUES (?,?,?,?,?)",
                             (u_id, p, cin, br, datetime.now().strftime("%d/%m/%Y")))
                conn.commit(); st.success("Registrado!")
        
        df_m = pd.read_sql("SELECT peso, cintura, braço, data FROM medidas WHERE usuario_id=? ORDER BY id DESC", conn, params=(u_id,))
        if not df_m.empty:
            fig = px.line(df_m, x="data", y="peso", title="Evolução do Peso")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_m, use_container_width=True)

    with tab3:
        st.subheader("Alterar Senha")
        with st.form("perfil"):
            n1 = st.text_input("Nova Senha", type="password")
            n2 = st.text_input("Confirme", type="password")
            if st.form_submit_button("Atualizar"):
                if n1 == n2 and n1 != "":
                    conn.execute("UPDATE usuarios SET senha=? WHERE id=?", (n1, u_id)); conn.commit()
                    st.success("Senha alterada!")
                else: st.error("Senhas não conferem.")
    conn.close()

# =============================
# MAIN
# =============================
if "user" not in st.session_state:
    login()
else:
    if st.sidebar.button("🚪 Sair"):
        st.session_state.clear(); st.rerun()
    if st.session_state.user["role"] == "admin": painel_admin()
    else: painel_aluno()
