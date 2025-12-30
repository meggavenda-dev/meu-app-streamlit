import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import hashlib
from datetime import datetime
import time

# =============================
# CONFIGURAÇÃO E ESTILO (CSS)
# =============================
st.set_page_config(page_title="GymManager Pro v4.1", layout="wide", page_icon="💪")

# CSS para simular o visual da imagem (Cards e Layout Escuro/Moderno)
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
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #1e2129;
        border-radius: 5px;
        color: white;
        padding: 10px 20px;
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
    
    # Tabela de Usuários
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT, login TEXT UNIQUE, senha TEXT, role TEXT,
        status_pagamento TEXT DEFAULT 'Em dia', objetivo TEXT)""")
    
    # MIGRAÇÃO: Tenta adicionar a coluna altura caso o banco seja antigo
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN altura REAL DEFAULT 170.0")
    except sqlite3.OperationalError:
        pass # A coluna já existe

    # Tabela de Treinos
    c.execute("""CREATE TABLE IF NOT EXISTS treinos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER, dia_semana TEXT, tipo_treino TEXT,
        exercicio TEXT, series INTEGER, repeticoes TEXT, carga REAL,
        link_video TEXT,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")

    # Tabela de Medidas
    c.execute("""CREATE TABLE IF NOT EXISTS medidas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER,
        peso REAL, cintura REAL, braco REAL, data TEXT,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")
    
    # Tabela de Histórico de Tempo
    c.execute("""CREATE TABLE IF NOT EXISTS historico_treinos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER, data TEXT, duracao_segundos INTEGER,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE)""")

    # Admin Padrão (Agora com 5 colunas especificadas)
    admin_hash = make_hashes('admin123')
    c.execute("""INSERT OR IGNORE INTO usuarios (nome, login, senha, role, altura) 
                 VALUES (?,?,?,?,?)""", 
              ('Master Admin', 'admin', admin_hash, 'admin', 175.0))
    
    conn.commit()
    conn.close()

init_db()

# =============================
# FUNÇÕES DE APOIO
# =============================
DIAS_SEMANA = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]

def painel_admin():
    st.sidebar.title("🔐 Admin Panel")
    menu = st.sidebar.selectbox("Menu", ["Alunos", "Prescrever", "Financeiro"])
    conn = get_connection()

    if menu == "Alunos":
        st
