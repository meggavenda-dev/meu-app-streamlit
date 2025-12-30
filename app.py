import streamlit as st
import pandas as pd
import sqlite3
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO

# =============================
# CONFIGURAÇÃO DA PÁGINA
# =============================
st.set_page_config(
    page_title="GymManager Pro",
    layout="wide"
)

# =============================
# BANCO DE DADOS
# =============================
def get_connection():
    return sqlite3.connect("gym.db", check_same_thread=False)

def criar_tabelas():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alunos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE,
            objetivo TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tipos_treino (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS treinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER,
            tipo_treino TEXT,
            exercicio TEXT,
            series INTEGER,
            repeticoes TEXT,
            carga REAL,
            FOREIGN KEY(aluno_id) REFERENCES alunos(id)
        )
    """)

    conn.commit()
    conn.close()

criar_tabelas()

# =============================
# PDF
# =============================
def gerar_pdf(aluno, objetivo, treinos):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4
    y = altura - 50

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "Ficha de Treino")
    y -= 30

    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, y, f"Aluno: {aluno}")
    y -= 20
    pdf.drawString(50, y, f"Objetivo: {objetivo}")
    y -= 30

    for treino, exercicios in treinos.items():
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y, treino)
        y -= 20
        pdf.setFont("Helvetica", 10)

        for ex in exercicios:
            linha = (
                f"{ex['exercicio']} | "
                f"Séries: {ex['series']} | "
                f"Reps: {ex['repeticoes']} | "
                f"Carga: {ex['carga']}kg"
            )
            pdf.drawString(60, y, linha)
            y -= 15

            if y < 80:
                pdf.showPage()
                y = altura - 50
                pdf.setFont("Helvetica", 10)

        y -= 10

    pdf.save()
    buffer.seek(0)
    return buffer

# =============================
# TELAS
# =============================
def cadastrar_aluno():
    st.header("➕ Cadastrar Aluno")

    with st.form("form_cadastro"):
        nome = st.text_input("Nome do Aluno")
        objetivo = st.selectbox(
            "Objetivo",
            ["Hipertrofia", "Emagrecimento", "Condicionamento"]
        )
        submitted = st.form_submit_button("Salvar Aluno")

        if submitted:
            if not nome:
                st.error("Informe o nome do aluno.")
                return

            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO alunos (nome, objetivo) VALUES (?, ?)",
                    (nome, objetivo)
                )
                conn.commit()
                st.success("Aluno cadastrado com sucesso!")
            except sqlite3.IntegrityError:
                st.error("Aluno já cadastrado.")
            finally:
                conn.close()

# -------------------------------------------------

def cadastrar_tipo_treino():
    st.header("🏷️ Tipos de Treino")

    with st.form("form_tipo_treino"):
        nome = st.text_input("Nome do tipo de treino (ex: Costas, Pernas)")
        submitted = st.form_submit_button("Adicionar")

        if submitted:
            if not nome:
                st.error("Informe o nome do tipo.")
                return

            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO tipos_treino (nome) VALUES (?)",
                    (nome,)
                )
                conn.commit()
                st.success("Tipo de treino cadastrado!")
            except sqlite3.IntegrityError:
                st.error("Esse tipo já existe.")
            finally:
                conn.close()

    conn = get_connection()
    df = pd.read_sql("SELECT nome FROM tipos_treino ORDER BY nome", conn)
    conn.close()

    if not df.empty:
        st.subheader("Tipos cadastrados")
        st.dataframe(df, use_container_width=True)

# -------------------------------------------------

def montar_treino():
    st.header("🏋️ Montar Treino")

    conn = get_connection()
    alunos = pd.read_sql("SELECT id, nome FROM alunos", conn)
    tipos = pd.read_sql("SELECT nome FROM tipos_treino", conn)
    conn.close()

    if alunos.empty:
        st.warning("Nenhum aluno cadastrado.")
        return

    if tipos.empty:
        st.warning("Cadastre um tipo de treino primeiro.")
        return

    aluno_nome = st.selectbox("Aluno", alunos["nome"])
    aluno_id = alunos[alunos["nome"] == aluno_nome]["id"].values[0]

    tipo_treino = st.selectbox("Tipo de Treino", tipos["nome"])

    with st.form("form_treino"):
        col1, col2, col3, col4 = st.columns(4)

        exercicio = col1.text_input("Exercício")
        series = col2.number_input("Séries", min_value=1)
        repeticoes = col3.text_input("Repetições")
        carga = col4.number_input("Carga (kg)", min_value=0.0)

        submitted = st.form_submit_button("Adicionar Exercício")

        if submitted:
            if not exercicio or not repeticoes:
                st.error("Preencha todos os campos.")
                return

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO treinos
                (aluno_id, tipo_treino, exercicio, series, repeticoes, carga)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                aluno_id, tipo_treino, exercicio, series, repeticoes, carga
            ))
            conn.commit()
            conn.close()

            st.success("Exercício adicionado com sucesso!")

# -------------------------------------------------

def visualizar_ficha():
    st.header("📋 Ficha de Treino")

    conn = get_connection()
    alunos = pd.read_sql("SELECT id, nome, objetivo FROM alunos", conn)
    conn.close()

    if alunos.empty:
        st.warning("Nenhum aluno cadastrado.")
        return

    aluno_nome = st.selectbox("Aluno", alunos["nome"])
    aluno = alunos[alunos["nome"] == aluno_nome].iloc[0]

    conn = get_connection()
    df = pd.read_sql("""
        SELECT tipo_treino, exercicio, series, repeticoes, carga
        FROM treinos
        WHERE aluno_id = ?
        ORDER BY tipo_treino
    """, conn, params=(aluno["id"],))
    conn.close()

    st.caption(f"Objetivo: {aluno['objetivo']}")

    if df.empty:
        st.info("Nenhum treino cadastrado.")
        return

    st.dataframe(df, use_container_width=True)

    treinos_dict = df.groupby("tipo_treino").apply(
        lambda x: x.to_dict("records")
    ).to_dict()

    pdf_buffer = gerar_pdf(
        aluno_nome,
        aluno["objetivo"],
        treinos_dict
    )

    st.download_button(
        "📄 Baixar ficha em PDF",
        pdf_buffer,
        file_name=f"ficha_{aluno_nome}.pdf",
        mime="application/pdf"
    )

# =============================
# MAIN
# =============================
def main():
    st.title("🏋️ GymManager Pro")

    menu = st.sidebar.radio(
        "Menu",
        ["Cadastrar Aluno", "Tipos de Treino", "Montar Treino", "Visualizar Ficha"]
    )

    if menu == "Cadastrar Aluno":
        cadastrar_aluno()
    elif menu == "Tipos de Treino":
        cadastrar_tipo_treino()
    elif menu == "Montar Treino":
        montar_treino()
    elif menu == "Visualizar Ficha":
        visualizar_ficha()

# =============================
# EXECUÇÃO
# =============================
if __name__ == "__main__":
    main()
