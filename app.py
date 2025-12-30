def login():
    st.title("🏋️ GymManager Pro Login")
    tab1, tab2 = st.tabs(["Login", "Cadastro"])
    
    with tab1:
        u = st.text_input("Login")
        s = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            with get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM usuarios WHERE login=?", (u,))
                row = c.fetchone()
                if row and check_hashes(s, row[3]):
                    st.session_state.user = {
                        "id": row[0], "nome": row[1], "role": row[4],
                        "altura": row[5], "status_pagamento": row[6]
                    }
                    # Evitar rerun direto: apenas mostra mensagem de sucesso
                    st.success(f"Bem-vindo {row[1]}! Atualize a página ou clique no menu.")
                else:
                    st.error("Credenciais inválidas")
    
    with tab2:
        n = st.text_input("Nome", key="cad_nome")
        l = st.text_input("Login", key="cad_login")
        s = st.text_input("Senha", type="password", key="cad_senha")
        alt = st.number_input("Altura (cm)", value=170.0, key="cad_altura")
        obj = st.selectbox("Objetivo", ["Hipertrofia","Emagrecimento","Condicionamento","Saúde"])
        if st.button("Criar Conta"):
            if n and l and s:
                try:
                    with get_connection() as conn:
                        conn.execute("INSERT INTO usuarios (nome, login, senha, role, altura, objetivo) VALUES (?,?,?,?,?,?)",
                                     (n,l,make_hashes(s),'aluno',alt,obj))
                        conn.commit()
                        st.success("Conta criada! Faça login e atualize a página.")
                except:
                    st.error("Login já existe!")
