import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import plotly.express as px
from datetime import datetime
import time
import random
from fpdf import FPDF
import io
import qrcode
from PIL import Image

# =============================
# CONFIGURAÇÃO E PLAYLIST
# =============================
st.set_page_config(page_title="GymManager Pro v6.6", layout="wide", page_icon="💪")
LINK_PLAYLIST = "https://open.spotify.com/playlist/37i9dQZF1DX76W9SfsLp3d" # Cole seu link aqui

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
# FUNÇÕES AUXILIARES
# =============================
def gerar_qr_code(link):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf

def gerar_pdf_treino(nome_aluno, dia, df_treino):
    pdf = FPDF()
    pdf.add_page()
    
    # Cabeçalho
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, txt=f"Ficha de Treino - {nome_aluno}", ln=True, align='C')
    pdf.set_font("Arial", "I", 12)
    pdf.cell(200, 10, txt=f"Dia: {dia} | Gerado em: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='C')
    pdf.ln(10)
    
    # Tabela
    pdf.set_font("Arial", "B", 12)
    pdf.cell(80, 10, "Exercicio", 1)
    pdf.cell(30, 10, "Series", 1)
    pdf.cell(30, 10, "Reps", 1)
    pdf.cell(30, 10, "Carga", 1)
    pdf.ln()
    
    pdf.set_font("Arial", "", 12)
    for _, row in df_treino.iterrows():
        pdf.cell(80, 10, str(row['exercicio']), 1)
        pdf.cell(30, 10, str(row['series']), 1)
        pdf.cell(30, 10, str(row['repeticoes']), 1)
        pdf.cell(30, 10, f"{row['carga']}kg", 1)
        pdf.ln()
    
    # Adicionar QR Code da Playlist no final do PDF
    pdf.ln(10)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(200, 10, txt="Escaneie para ouvir a Playlist da Academia:", ln=True, align='L')
    
    qr_buf = gerar_qr_code(LINK_PLAYLIST)
    # FPDF precisa de um arquivo físico ou um objeto que se comporte como tal
    with open("temp_qr.png", "wb") as f:
        f.write(qr_buf.getvalue())
    pdf.image("temp_qr.png", x=10, y=pdf.get_y(), w=30)
    
    return pdf.output(dest='S').encode('latin-1')

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
# PAINEL ADMINISTRATIVO
# =============================
def painel_admin():
    st.sidebar.title("🔐 Administração")
    menu = st.sidebar.selectbox("Opções", ["Gestão de Alunos", "Montar Treinos", "Financeiro"])
    
    with get_connection() as conn:
        if menu == "Gestão de Alunos":
            st.header("👥 Gestão de Alunos")
            with st.expander("➕ Incluir Novo Aluno"):
                with st.form("admin_incluir"):
                    c1, c2 = st.columns(2)
                    n = c1.text_input("Nome")
                    l = c2.text_input("Login")
                    p = c1.text_input("Senha", type="password")
                    o = c2.selectbox("Objetivo", ["Hipertrofia","Emagrecimento","Saúde"])
                    if st.form_submit_button("Cadastrar"):
                        conn.execute("INSERT INTO usuarios (nome, login, senha, role, objetivo) VALUES (?,?,?,?,?)",
                                     (n, l, make_hashes(p), 'aluno', o))
                        conn.commit()
                        st.success("Aluno incluído!")
                        st.rerun()

            df = pd.read_sql("SELECT id, nome, login, objetivo FROM usuarios WHERE role='aluno'", conn)
            for _, row in df.iterrows():
                with st.container(border=True):
                    col1, col2 = st.columns([4,1])
                    col1.write(f"**{row['nome']}** - {row['objetivo']}")
                    if col2.button("Excluir", key=f"del_{row['id']}"):
                        conn.execute("DELETE FROM usuarios WHERE id=?", (row['id'],))
                        conn.commit()
                        st.rerun()

        elif menu == "Montar Treinos":
            st.header("📋 Prescrição e Duplicação")
            alunos = pd.read_sql("SELECT id, nome FROM usuarios WHERE role='aluno'", conn)
            if not alunos.empty:
                sel = st.selectbox("Selecione o Aluno", alunos["nome"])
                a_id = int(alunos.loc[alunos["nome"] == sel, "id"].iloc[0])
                
                with st.expander("👯 Duplicar Treino"):
                    col_orig, col_dest = st.columns(2)
                    dia_origem = col_orig.selectbox("Copiar de:", DIAS_SEMANA, key="orig")
                    dia_destino = col_dest.selectbox("Colar em:", DIAS_SEMANA, key="dest")
                    if st.button("Duplicar"):
                        ex_origem = pd.read_sql("SELECT * FROM treinos WHERE usuario_id=? AND dia_semana=?", conn, params=(a_id, dia_origem))
                        for _, r in ex_origem.iterrows():
                            conn.execute("INSERT INTO treinos (usuario_id, dia_semana, exercicio, series, repeticoes, carga, link_video) VALUES (?,?,?,?,?,?,?)",
                                         (a_id, dia_destino, r['exercicio'], r['series'], r['repeticoes'], r['carga'], r['link_video']))
                        conn.commit()
                        st.success("Copiado!")

                with st.form("add_treino"):
                    dia = st.selectbox("Dia", DIAS_SEMANA)
                    ex = st.text_input("Exercício")
                    c1, c2, c3 = st.columns(3)
                    se = c1.number_input("Séries", 1, 10, 3)
                    re = c2.text_input("Reps", "12")
                    ca = c3.number_input("Carga", 0.0)
                    if st.form_submit_button("Salvar"):
                        conn.execute("INSERT INTO treinos (usuario_id, dia_semana, exercicio, series, repeticoes, carga) VALUES (?,?,?,?,?,?)",
                                     (a_id, dia, ex, se, re, ca))
                        conn.commit()
                        st.rerun()

# =============================
# PAINEL DO ALUNO
# =============================
def painel_aluno():
    u_id = st.session_state.user["id"]
    with get_connection() as conn:
        st.title(f"Olá, {st.session_state.user['nome']}! 🔥")
        
        tab1, tab2, tab3 = st.tabs(["🏋️ Consultar Treino", "📊 Evolução", "💡 Motivação"])
        
        with tab1:
            data_sel = st.date_input("Escolha a data", datetime.now())
            trad_dias = {"Monday": "Segunda-feira", "Tuesday": "Terça-feira", "Wednesday": "Quarta-feira",
                         "Thursday": "Quinta-feira", "Friday": "Sexta-feira", "Saturday": "Sábado", "Sunday": "Domingo"}
            dia_pt = trad_dias[data_sel.strftime("%A")]
            
            df = pd.read_sql("SELECT * FROM treinos WHERE usuario_id=? AND dia_semana=?", conn, params=(u_id, dia_pt))
            
            if not df.empty:
                pdf_data = gerar_pdf_treino(st.session_state.user['nome'], dia_pt, df)
                st.download_button(
                    label="📄 Baixar Treino em PDF",
                    data=pdf_data,
                    file_name=f"treino_{dia_pt}.pdf",
                    mime="application/pdf"
                )
                
                for _, r in df.iterrows():
                    with st.container(border=True):
                        st.write(f"**{r['exercicio']}** | {r['series']}x{r['repeticoes']} | {r['carga']}kg")
            else:
                st.write("Sem treino para hoje.")

        with tab2:
            df_m = pd.read_sql("SELECT peso, data FROM medidas WHERE usuario_id=? ORDER BY data ASC", conn, params=(u_id,))
            if not df_m.empty: st.plotly_chart(px.line(df_m, x="data", y="peso"))

        with tab3:
            st.subheader("🔥 Foco Total")
            c1, c2 = st.columns(2)
            c1.info(random.choice(["A disciplina vence a motivação!", "Sua única competição é você mesmo.", "Treine hoje para orgulhar o seu eu de amanhã."]))
            
            c2.write("🎶 **Playlist Oficial da Academia**")
            qr_buf = gerar_qr_code(LINK_PLAYLIST)
            c2.image(qr_buf, width=200, caption="Escaneie no Spotify")

# =============================
# LOGIN SCREEN
# =============================
def login_screen():
    st.title("🏋️ GymManager Pro")
    tab1, tab2 = st.tabs(["Login", "Cadastro"])
    with tab1:
        with st.form("login"):
            u = st.text_input("Usuário")
            s = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                with get_connection() as conn:
                    c = conn.cursor()
                    c.execute("SELECT * FROM usuarios WHERE login=?", (u,))
                    row = c.fetchone()
                if row and check_hashes(s, row[3]):
                    st.session_state.user = {"id": row[0], "nome": row[1], "role": row[4], "altura": row[5], "objetivo": row[6], "status_pagamento": row[7]}
                    st.rerun()
    with tab2:
        with st.form("cad"):
            n = st.text_input("Nome")
            l = st.text_input("Login")
            p = st.text_input("Senha", type="password")
            if st.form_submit_button("Cadastrar"):
                with get_connection() as conn:
                    conn.execute("INSERT INTO usuarios (nome, login, senha, role) VALUES (?,?,?,?)", (n, l, make_hashes(p), 'aluno'))
                    conn.commit()
                st.success("OK!")

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
