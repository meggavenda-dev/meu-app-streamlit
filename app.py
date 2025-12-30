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
st.set_page_config(page_title="GymManager Pro v6.7", layout="wide", page_icon="💪")
LINK_PLAYLIST = "https://open.spotify.com/playlist/37i9dQZF1DX76W9SwwE3fk" 

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
            altura REAL DEFAULT 170.0, objetivo TEXT DEFAULT 'Saúde',
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

        admin_hash = make_hashes("admin123")
        c.execute("INSERT OR IGNORE INTO usuarios (nome, login, senha, role, altura) VALUES (?,?,?,?,?)",
                  ("Master Admin","admin",admin_hash,"admin",175.0))
        conn.commit()

init_db()

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
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, txt=f"Ficha de Treino - {nome_aluno}", ln=True, align='C')
    pdf.set_font("Arial", "I", 12)
    pdf.cell(200, 10, txt=f"Dia: {dia} | Gerado em: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(80, 10, "Exercicio", 1); pdf.cell(30, 10, "Series", 1); pdf.cell(30, 10, "Reps", 1); pdf.cell(30, 10, "Carga", 1)
    pdf.ln()
    
    pdf.set_font("Arial", "", 12)
    for _, row in df_treino.iterrows():
        pdf.cell(80, 10, str(row['exercicio']), 1)
        pdf.cell(30, 10, str(row['series']), 1)
        pdf.cell(30, 10, str(row['repeticoes']), 1)
        pdf.cell(30, 10, f"{row['carga']}kg", 1)
        pdf.ln()
    return pdf.output(dest='S').encode('latin-1')

# =============================
# PAINEL ADMINISTRATIVO
# =============================
def painel_admin():
    st.sidebar.title("🔐 Administração")
    menu = st.sidebar.selectbox("Opções", ["Gestão de Alunos", "Montar Treinos"])
    DIAS_SEMANA = ["Segunda-feira","Terça-feira","Quarta-feira","Quinta-feira","Sexta-feira","Sábado","Domingo"]
    
    with get_connection() as conn:
        if menu == "Gestão de Alunos":
            st.header("👥 Gestão de Alunos")
            
            # --- FORMULÁRIO DE INCLUSÃO ---
            with st.expander("➕ Incluir Novo Aluno"):
                with st.form("admin_incluir"):
                    c1, c2 = st.columns(2)
                    n = c1.text_input("Nome")
                    l = c2.text_input("Login")
                    p = c1.text_input("Senha", type="password")
                    o = c2.selectbox("Objetivo", ["Hipertrofia","Emagrecimento","Saúde"])
                    alt = c1.number_input("Altura (cm)", value=170.0)
                    if st.form_submit_button("Cadastrar"):
                        if n and l and p:
                            try:
                                conn.execute("INSERT INTO usuarios (nome, login, senha, role, altura, objetivo) VALUES (?,?,?,?,?,?)",
                                             (n, l, make_hashes(p), 'aluno', alt, o))
                                conn.commit()
                                st.success(f"Aluno {n} cadastrado!")
                                st.rerun()
                            except: st.error("Login já em uso!")

            st.divider()
            
            # --- LISTAGEM E RESET DE SENHA ---
            st.subheader("Alunos Cadastrados")
            df = pd.read_sql("SELECT id, nome, login, objetivo FROM usuarios WHERE role='aluno'", conn)
            for _, row in df.iterrows():
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 2, 1])
                    col1.write(f"**{row['nome']}** ({row['login']})")
                    
                    # Alterar Senha
                    nova_s = col2.text_input("Nova Senha", type="password", key=f"pwd_{row['id']}")
                    if col2.button("Resetar Senha", key=f"btn_pwd_{row['id']}"):
                        if nova_s:
                            conn.execute("UPDATE usuarios SET senha=? WHERE id=?", (make_hashes(nova_s), row['id']))
                            conn.commit()
                            st.success("Senha alterada!")
                        else: st.warning("Digite a nova senha.")
                    
                    if col3.button("🗑️ Excluir", key=f"del_{row['id']}"):
                        conn.execute("DELETE FROM usuarios WHERE id=?", (row['id'],))
                        conn.commit()
                        st.rerun()

        elif menu == "Montar Treinos":
            st.header("📋 Prescrição de Treinos")
            alunos = pd.read_sql("SELECT id, nome FROM usuarios WHERE role='aluno'", conn)
            if not alunos.empty:
                sel = st.selectbox("Selecione o Aluno", alunos["nome"])
                a_id = int(alunos.loc[alunos["nome"] == sel, "id"].iloc[0])
                
                with st.form("add_treino"):
                    d = st.selectbox("Dia", DIAS_SEMANA)
                    ex = st.text_input("Exercício")
                    c1, c2, c3 = st.columns(3)
                    se = c1.number_input("Séries", 1, 10, 3)
                    re = c2.text_input("Reps", "12")
                    ca = c3.number_input("Carga (kg)", 0.0)
                    if st.form_submit_button("Salvar Treino"):
                        if ex:
                            conn.execute("INSERT INTO treinos (usuario_id, dia_semana, exercicio, series, repeticoes, carga) VALUES (?,?,?,?,?,?)",
                                         (a_id, d, ex, se, re, ca))
                            conn.commit()
                            st.success("Adicionado!")
                        else: st.error("Nome do exercício obrigatório.")

# =============================
# PAINEL DO ALUNO
# =============================
def painel_aluno():
    u_id = st.session_state.user["id"]
    with get_connection() as conn:
        st.title(f"Olá, {st.session_state.user['nome']}! 🔥")
        tab1, tab2 = st.tabs(["🏋️ Meu Treino", "📊 Evolução"])
        
        with tab1:
            data_sel = st.date_input("Data do treino", datetime.now())
            # Tradução robusta de dias
            dias_dict = {"Monday": "Segunda-feira", "Tuesday": "Terça-feira", "Wednesday": "Quarta-feira",
                         "Thursday": "Quinta-feira", "Friday": "Sexta-feira", "Saturday": "Sábado", "Sunday": "Domingo"}
            dia_pt = dias_dict[data_sel.strftime("%A")]
            
            df = pd.read_sql("SELECT * FROM treinos WHERE usuario_id=? AND dia_semana=?", conn, params=(u_id, dia_pt))
            if not df.empty:
                pdf_data = gerar_pdf_treino(st.session_state.user['nome'], dia_pt, df)
                st.download_button("📄 Baixar PDF", data=pdf_data, file_name=f"treino_{dia_pt}.pdf")
                for _, r in df.iterrows():
                    st.write(f"✅ **{r['exercicio']}** | {r['series']}x{r['repeticoes']} | {r['carga']}kg")
            else: st.info("Nenhum treino para este dia.")

# =============================
# TELA DE LOGIN
# =============================
def login_screen():
    st.title("🏋️ GymManager Pro")
    t1, t2 = st.tabs(["Login", "Novo Cadastro"])
    
    with t1:
        with st.form("login_f"):
            u = st.text_input("Usuário")
            s = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                with get_connection() as conn:
                    c = conn.cursor()
                    c.execute("SELECT * FROM usuarios WHERE login=?", (u,))
                    row = c.fetchone()
                if row and check_hashes(s, row[3]):
                    st.session_state.user = {"id": row[0], "nome": row[1], "role": row[4], "altura": row[5]}
                    st.rerun()
                else: st.error("Usuário ou senha inválidos.")

    with t2:
        with st.form("cad_f"):
            n = st.text_input("Nome Completo")
            l = st.text_input("Login")
            p = st.text_input("Senha", type="password")
            if st.form_submit_button("Criar Conta"):
                if n and l and p:
                    try:
                        with get_connection() as conn:
                            conn.execute("INSERT INTO usuarios (nome, login, senha, role, altura, objetivo) VALUES (?,?,?,?,?,?)",
                                         (n, l, make_hashes(p), 'aluno', 170.0, 'Saúde'))
                            conn.commit()
                        st.success("Conta criada! Faça login.")
                    except: st.error("Login já existe.")

# =============================
# FLUXO PRINCIPAL
# =============================
if "user" not in st.session_state: st.session_state.user = None

if st.session_state.user is None:
    login_screen()
else:
    st.sidebar.button("🚪 Sair", on_click=lambda: st.session_state.update({"user": None}))
    if st.session_state.user["role"] == "admin":
        painel_admin()
    else:
        painel_aluno()
