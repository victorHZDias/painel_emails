import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
from PIL import Image
import requests
from io import BytesIO

# Load environment variables
load_dotenv()

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT')
    )

# Get distinct values for the `REPORTE` column
def get_distinct_reporte():
    conn = get_db_connection()
    cur = conn.cursor()
    query = 'SELECT DISTINCT "REPORTE" FROM "Equipe_Completa" WHERE "REPORTE" IS NOT NULL ORDER BY "REPORTE"'
    cur.execute(query)
    data = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return data

# Page configuration
st.set_page_config(page_title="Gestão de Equipe - Cobrança",page_icon="https://github.com/victorHZDias/colaboradores/blob/main/avatar_outros.png?raw=true", layout="wide")
st.title("Gestão de Equipe - Cobrança")

st.sidebar.image("https://portal.uninter.com/wp-content/themes/portal/imagens/marca-uninter-horizontal.png")
# Sidebar filters
st.sidebar.title("Filtros")
cargo_filter = st.sidebar.selectbox("Filtrar por Cargo", ["Todos", "AVANÇADO", "ASSISTENTE","ANALISTA","MONITOR","ADVOGADO"])
situacao_filter = st.sidebar.selectbox("Filtrar por Situação", ["Todos", "ATIVO","ATESTADO", "INATIVO", "FÉRIAS", "AFASTADO", "BCO HORAS", "FOLGA ANIVERSÁRIO"])
reporte_options = ["Todos"] + get_distinct_reporte()
reporte_filter = st.sidebar.selectbox("Filtrar por Reporte", reporte_options)

# Get team data
def get_team_data():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    query = """
    SELECT *
    FROM "Equipe_Completa"
    WHERE 1=1
    """
    if cargo_filter != "Todos":
        query += f" AND \"CARGO\" = '{cargo_filter}' ORDER BY \"Nome_Colaborador\""
    if situacao_filter != "Todos":
        query += f" AND \"SIT_ATUAL\" = '{situacao_filter}' ORDER BY \"Nome_Colaborador\""
    if reporte_filter != "Todos":
        query += f" AND \"REPORTE\" = '{reporte_filter}' ORDER BY \"Nome_Colaborador\""
    else:
        query += f"ORDER BY \"Nome_Colaborador\""
    cur.execute(query)
    data = cur.fetchall()
    cur.close()
    conn.close()
    return data

# Display team members in a list format
def display_team_list(team_data):
    selected_member_id = st.selectbox(
        "Selecione um colaborador para editar ou excluir:",
        options=["Nenhum"] + [member['id'] for member in team_data],
        format_func=lambda x: "Nenhum" if x == "Nenhum" else next(
            (member['Nome_Colaborador'] for member in team_data if member['id'] == x), ""
        )
    )

    if selected_member_id != "Nenhum":
        selected_member = next(member for member in team_data if member['id'] == selected_member_id)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Editar"):
                st.session_state.show_modal = True
                st.session_state.editing_member = selected_member
                st.rerun()
        with col2:
            if st.button("Excluir"):
                st.session_state.show_delete_modal = True
                st.session_state.deleting_member = selected_member
                st.rerun()

    for member in team_data:
        cols = st.columns([1, 4])
        # Column 1: Photo
        with cols[0]:
            if member['Foto']:
                try:
                    # response = requests.get(member['Foto'])
                    # img = Image.open(BytesIO(response.content))
                    st.image(member['Foto'], width=100)
                except:
                    st.write("Foto não disponível")
            else:
                st.write("Sem foto")
        # Column 2: Member details
        with cols[1]:
            st.subheader(member['Nome_Colaborador'])
            st.write(f"**Cargo:** {member['CARGO']}")
            st.write(f"**Matrícula:** {member['MATRICULA']}")
            st.write(f"**Reporta para:** {member['REPORTE']}")
            st.write(f"**Equipe:** {member['EQUIPE']}")
            st.write(f"**Situação:** {member['SIT_ATUAL']}")
            if member['DATA_RETORNO']:
                st.write(f"**Data de Retorno:** {member['DATA_RETORNO']}")
            st.write(f"**E-mail:** {member['EMAIL']}")
            if member['ANIVERSARIO']:
                st.write(f"**Aniversário:** {member['ANIVERSARIO']}")
        st.divider()

# Modal for adding or editing a member
def show_modal_form(title, member=None):
    with st.form("member_form"):
        nome = st.text_input("Nome", value=member['Nome_Colaborador'] if member else "")
        matricula = st.text_input("Matrícula", value=member['MATRICULA'] if member else "")
        cargo = st.selectbox("Cargo", ["AVANÇADO", "ASSISTENTE", "ANALISTA", "MONITOR", "ADVOGADO"], index=0 if member and member['CARGO'] == "AVANÇADO" else 1)
        reporte_options = ["Todos"] + get_distinct_reporte()
        reporte = st.selectbox("Reporta para", reporte_options, index=reporte_options.index(member['REPORTE']) if member else 0)
        equipe = st.selectbox("Equipe", ["COBRANÇA"], index=0)
        situacao = st.selectbox("Situação", ["Todos", "ATIVO", "ATESTADO", "INATIVO", "FÉRIAS", "AFASTADO", "BCO HORAS", "FOLGA ANIVERSÁRIO"], index=0 if not member or member['SIT_ATUAL'] == "ATIVO" else 1)
        aniversario = st.text_input("Aniversário", value=member['ANIVERSARIO'] if member else None)
        data_retorno = st.text_input("Data de Retorno", value=member['DATA_RETORNO'] if member else None)
        email = st.text_input("E-mail", value=member['EMAIL'] if member else "")
        foto_url = st.text_input("URL da Foto", value=member['Foto'] if member else "")
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Salvar"):
                # Convert empty strings to None
                matricula = matricula.strip() if matricula and matricula.strip() else None
                aniversario = aniversario.strip() if aniversario and aniversario.strip() else None
                data_retorno = data_retorno.strip() if data_retorno and data_retorno.strip() else None
                foto_url = foto_url.strip() if foto_url and foto_url.strip() else None

                if member:
                    update_member(member['id'], nome, matricula, cargo, reporte, equipe, situacao, email, aniversario, data_retorno, foto_url)
                else:
                    add_member(nome, matricula, cargo, reporte, equipe, situacao, email, aniversario, data_retorno, foto_url)
                st.success("Operação realizada com sucesso!")
                st.session_state.show_modal = False
                st.rerun()
        with col2:
            if st.form_submit_button("Cancelar"):
                st.session_state.show_modal = False
                st.rerun()

# Modal for delete confirmation
def show_delete_confirmation(member_id, member_name):
    st.warning(f"Tem certeza que deseja excluir {member_name}?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Sim"):
            delete_member(member_id)
            st.success("Membro excluído com sucesso!")
            st.session_state.show_delete_modal = False
            st.rerun()
    with col2:
        if st.button("Não"):
            st.session_state.show_delete_modal = False
            st.rerun()

# Add a new member to the database
def add_member(nome, matricula, cargo, reporte, equipe, situacao, email, aniversario, data_retorno, foto_url):
    conn = get_db_connection()
    cur = conn.cursor()
    query = """
    INSERT INTO "Equipe_Completa" 
    ("MATRICULA", "Nome_Colaborador", "CARGO", "REPORTE", "EQUIPE", "SIT_ATUAL", "EMAIL", "ANIVERSARIO", "DATA_RETORNO", "Foto")
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cur.execute(query, (matricula, nome, cargo, reporte, equipe, situacao, email, aniversario, data_retorno, foto_url))
    conn.commit()
    cur.close()
    conn.close()

# Update an existing member in the database
def update_member(id, nome, matricula, cargo, reporte, equipe, situacao, email, aniversario, data_retorno, foto_url):
    conn = get_db_connection()
    cur = conn.cursor()
    query = """
    UPDATE "Equipe_Completa" 
    SET "MATRICULA" = %s, "Nome_Colaborador" = %s, "CARGO" = %s, 
        "REPORTE" = %s, "EQUIPE" = %s, "SIT_ATUAL" = %s, 
        "EMAIL" = %s, "ANIVERSARIO" = %s, "DATA_RETORNO" = %s, "Foto" = %s
    WHERE "id" = %s
    """
    cur.execute(query, (matricula, nome, cargo, reporte, equipe, situacao, email, aniversario, data_retorno, foto_url, id))
    conn.commit()
    cur.close()
    conn.close()

# Delete a member from the database
def delete_member(id):
    conn = get_db_connection()
    cur = conn.cursor()
    query = 'DELETE FROM "Equipe_Completa" WHERE "id" = %s'
    cur.execute(query, (id,))
    conn.commit()
    cur.close()
    conn.close()

# Initialize session state variables
if 'show_modal' not in st.session_state:
    st.session_state.show_modal = False
if 'show_delete_modal' not in st.session_state:
    st.session_state.show_delete_modal = False
if 'editing_member' not in st.session_state:
    st.session_state.editing_member = None
if 'deleting_member' not in st.session_state:
    st.session_state.deleting_member = None

# Add new member button
if st.button("Adicionar Novo Membro"):
    st.session_state.show_modal = True
    st.session_state.editing_member = None
    st.rerun()

# Show modals if needed
if st.session_state.show_modal:
    show_modal_form(
        "Editar Membro" if st.session_state.editing_member else "Adicionar Novo Membro",
        st.session_state.editing_member
    )
    st.stop()

if st.session_state.show_delete_modal:
    show_delete_confirmation(
        st.session_state.deleting_member['id'],
        st.session_state.deleting_member['Nome_Colaborador']
    )
    st.stop()

# Display team members
team_data = get_team_data()
display_team_list(team_data)