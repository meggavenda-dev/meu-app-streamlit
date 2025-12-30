import streamlit as st
import pandas as pd
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
# SESSION STATE
# =============================
if "alunos" not in st.session_state:
    st.session_state.alunos = {}

# =============================
# FUNÇÕES
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

            st.session_state.alunos[nome] = {
                "objetivo": objetivo,
                "treinos": {
                    "Treino A": [],
                    "Treino B": [],
                    "Treino C": []
                }
            }

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

            if st.button(f"Limpar {treino}", key=treino):
                st.session_state.alunos[aluno]["treinos"][treino] = []
                st.rerun()
        else:
            st.info("Nenhum exercício cadastrado.")

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
