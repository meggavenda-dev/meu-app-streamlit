import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
import sqlite3

# =============================
# CONFIGURAÇÃO DA PÁGINA
# =============================
st.set_page_config(
    page_title="GymManager Pro",
    layout="wide"
)

# =============================
# FUNÇÃO PDF
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
        CREATE TABLE IF NOT EXISTS treinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER,
            treino TEXT,
            exercicio TEXT,
            series INTEGER,
            repeticoes TEXT,
            carga REAL
        )
    """)

    conn.commit()
    conn.close()

criar_tabelas()

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

        if not exercicios:
            pdf.drawString(60, y, "Nenhum exercício cadastrado.")
            y -= 15

        for ex in exercicios:
            linha = (
                f"{ex['exercicio']} | "
                f"Séries: {ex['series']} | "
                f"Reps: {ex['repeticoes']} | "
                f"Carga: {ex['carga_kg']}kg"
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
# FUNÇÕES APP
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

            if nome in st.session_state.alunos:
                st.error("Aluno já cadastrado.")
                return

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO alunos (nome, objetivo) VALUES (?, ?)",
            (nome, objetivo)
            )

        conn.commit()
        conn.close()


            st.success(f"Aluno {nome} cadastrado com sucesso!")

# -------------------------------------------------

def montar_treino():
    st.header("🏋️ Montar Treino")

    if not st.session_state.alunos:
        st.warning("Nenhum aluno cadastrado.")
        return

    aluno = st.selectbox(
        "Selecione o Aluno",
        list(st.session_state.alunos.keys())
    )

    treino_tipo = st.selectbox(
        "Selecione o Treino",
        ["Treino A", "Treino B", "Treino C"]
    )

    with st.form("form_treino"):
        col1, col2, col3, col4 = st.columns(4)

        exercicio = col1.text_input("Exercício")
        series = col2.number_input("Séries", min_value=1, step=1)
        repeticoes = col3.text_input("Repetições (ex: 8-12)")
        carga = col4.number_input("Carga (kg)", min_value=0)

        submitted = st.form_submit_button("Adicionar Exercício")

        if submitted:
            if not exercicio or not repeticoes:
                st.error("Preencha exercício e repetições.")
                return

            item = {
                "exercicio": exercicio,
                "series": series,
                "repeticoes": repeticoes,
                "carga_kg": carga
            }

            st.session_state.alunos[aluno]["treinos"][treino_tipo].append(item)
            st.success("Exercício adicionado ao treino.")

# -------------------------------------------------

def visualizar_ficha():
    st.header("📋 Ficha de Treino")

    if not st.session_state.alunos:
        st.warning("Nenhum aluno cadastrado.")
        return

    aluno = st.selectbox(
        "Selecione o Aluno",
        list(st.session_state.alunos.keys())
    )

    dados = st.session_state.alunos[aluno]

    st.subheader(f"Aluno: {aluno}")
    st.caption(f"Objetivo: {dados['objetivo']}")

    for treino, exercicios in dados["treinos"].items():
        st.markdown(f"### {treino}")

        if exercicios:
            df = pd.DataFrame(exercicios)
            st.table(df)

            if st.button(f"🗑️ Limpar {treino}", key=treino):
                st.session_state.alunos[aluno]["treinos"][treino] = []
                st.rerun()
        else:
            st.info("Nenhum exercício cadastrado.")

    st.divider()

    pdf_buffer = gerar_pdf(
        aluno,
        dados["objetivo"],
        dados["treinos"]
    )

    st.download_button(
        label="📄 Baixar ficha em PDF",
        data=pdf_buffer,
        file_name=f"ficha_{aluno}.pdf",
        mime="application/pdf"
    )

def listar_alunos():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM alunos", conn)
    conn.close()
    return df
    
df = listar_alunos()
st.dataframe(df)

# =============================
# MAIN
# =============================

  
def main():
    st.title("🏋️ GymManager Pro")

    menu = st.sidebar.radio(
        "Menu",
        ["Cadastrar Aluno", "Montar Treino", "Visualizar Ficha"]
    )

    if menu == "Cadastrar Aluno":
        cadastrar_aluno()
    elif menu == "Montar Treino":
        montar_treino()
    elif menu == "Visualizar Ficha":
        visualizar_ficha()

# =============================
# EXECUÇÃO
# =============================
if __name__ == "__main__":
    main()
