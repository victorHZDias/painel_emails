import streamlit as st
import pandas as pd
import requests
import os
import psycopg2
from dotenv import load_dotenv
from minio import Minio
from minio.error import S3Error
from urllib3.exceptions import InsecureRequestWarning
import urllib3
import uuid

# Desabilita os avisos de SSL inseguros
urllib3.disable_warnings(InsecureRequestWarning)

load_dotenv(".env")

st.set_page_config(
    page_title="Envio de Emails",
    page_icon="📧",  # Ícone de e-mail
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Configuração do webhook do n8n
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")  # Defina a URL do webhook como variável de ambiente

# Configuração do MinIO
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME")

# Configuração do banco de dados PostgreSQL
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Inicializa o cliente do MinIO
minio_client = Minio(
    MINIO_ENDPOINT.strip(),
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=True,  # HTTPS
    http_client=urllib3.PoolManager(cert_reqs='CERT_NONE')  # Ignora a verificação do certificado
)

try:
    # Lista os buckets para verificar a conexão
    buckets = minio_client.list_buckets()
    print("Conexão bem-sucedida. Buckets disponíveis:")
    for bucket in buckets:
        print(bucket.name)
except Exception as e:
    print(f"Erro ao conectar ao MinIO: {e}")

# Função para enviar arquivo para o MinIO
def enviar_para_minio(file_data, file_name, content_type):
    try:
        # Verifica se o bucket existe
        if not minio_client.bucket_exists(MINIO_BUCKET_NAME):
            minio_client.make_bucket(MINIO_BUCKET_NAME)

        # Envia o arquivo para o MinIO
        minio_client.put_object(
            MINIO_BUCKET_NAME,
            file_name,
            file_data,
            length=len(file_data.getvalue()),
            content_type=content_type
        )
        return f"Arquivo {file_name} enviado com sucesso para o MinIO!"
    except S3Error as e:
        print(f"Erro ao enviar arquivo para o MinIO: {e}")
        return None

# Função para enviar arquivo para o MinIO com identificação única
def enviar_para_minio_com_identificacao(file_data, recipient_email, content_type):
    try:
        # Gera um nome de arquivo único usando o e-mail do destinatário e um UUID
        unique_id = str(uuid.uuid4())
        file_name = f"{recipient_email}_{unique_id}.pdf"

        # Verifica se o bucket existe
        if not minio_client.bucket_exists(MINIO_BUCKET_NAME):
            minio_client.make_bucket(MINIO_BUCKET_NAME)

        # Envia o arquivo para o MinIO
        minio_client.put_object(
            MINIO_BUCKET_NAME,
            file_name,
            file_data,
            length=len(file_data.getvalue()),
            content_type=content_type
        )

        # Gera o link público para o arquivo
        link = minio_client.presigned_get_object(MINIO_BUCKET_NAME, file_name)
        return link
    except S3Error as e:
        print(f"Erro ao enviar arquivo para o MinIO: {e}")
        return None

# Função para obter o link do último item adicionado ao bucket
def obter_link_ultimo_item(bucket_name):
    try:
        # Lista todos os objetos no bucket
        objects = minio_client.list_objects(bucket_name, recursive=True)

        # Encontra o objeto mais recente
        ultimo_objeto = max(objects, key=lambda obj: obj.last_modified)

        # Gera o link público para o objeto
        link = minio_client.presigned_get_object(bucket_name, ultimo_objeto.object_name)
        return link
    except Exception as e:
        print(f"Erro ao obter o último item do bucket: {e}")
        return None

# Exemplo de uso
link_ultimo_item = obter_link_ultimo_item(MINIO_BUCKET_NAME)
if link_ultimo_item:
    print(f"Link do último item adicionado: {link_ultimo_item}")

# Função para verificar login
def verificar_login(email, senha):
    try:
        # Conexão com o banco de dados
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        # Consulta para verificar as credenciais
        query = 'SELECT * FROM "Equipe_Completa" WHERE "EMAIL" = %s AND "Senha" = %s'
        cursor.execute(query, (email, senha))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result is not None  # Retorna True se as credenciais forem válidas
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return False

# Função para alterar a senha
def alterar_senha(email, senha_atual, nova_senha):
    try:
        # Conexão com o banco de dados
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        # Verifica se a senha atual está correta
        query_verificar = 'SELECT * FROM "Equipe_Completa" WHERE "EMAIL" = %s AND "Senha" = %s'
        cursor.execute(query_verificar, (email, senha_atual))
        result = cursor.fetchone()

        if result:
            # Atualiza a senha no banco de dados
            query_atualizar = 'UPDATE "Equipe_Completa" SET "Senha" = %s WHERE "EMAIL" = %s'
            cursor.execute(query_atualizar, (nova_senha, email))
            conn.commit()
            cursor.close()
            conn.close()
            return True  # Senha alterada com sucesso
        else:
            cursor.close()
            conn.close()
            return False  # Senha atual incorreta
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return False

# Controle de login
if "logado" not in st.session_state:
    st.session_state["logado"] = False

if "usuario" not in st.session_state:
    st.session_state["usuario"] = None

# Tela de login
def tela_login():
    col1, col2,col3 = st.columns([3, 2,3])
    with col2:
        st.image("https://portal.uninter.com/wp-content/themes/portal/imagens/marca-uninter-horizontal.png", width=150)
        st.title("Login")
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if verificar_login(email, senha):
                st.session_state["logado"] = True
                st.session_state["usuario"] = email  # Armazena o e-mail do usuário logado
                st.success("Login realizado com sucesso!")
                st.rerun()  # Atualiza a interface
            else:
                st.error("E-mail ou senha inválidos.")

# Tela principal
def tela_principal():
    # Exibe o e-mail do usuário logado
    st.sidebar.image("https://portal.uninter.com/wp-content/themes/portal/imagens/marca-uninter-horizontal.png", width=150)
    st.sidebar.write(f"Usuário logado: {st.session_state['usuario']}")
    st.sidebar.button("Sair", on_click=lambda: [st.session_state.clear(), st.rerun()])
    
    # Adicionar um ícone clicável para limpar o formulário e atualizar a página
    if st.sidebar.button("🔄 Atualizar e Limpar"):
        st.session_state.clear()  # Limpa os dados armazenados na sessão
        st.rerun()  # Atualiza a página

    col1, col2, col3 = st.columns([3, 6, 3])
    with col2:
        # Título do app
        st.title("Envio de E-mails em Massa")

        # Aba para selecionar o tipo de envio
        tab1, tab2 = st.tabs(["Envio em Massa", "Alterar Senha"])

        # Aba 1: Envio em Massa
        with tab1:
            st.header("Envio de E-mails em Massa")
            subject = st.text_input("Assunto do E-mail", key="mass_subject")
            body = st.text_area("Corpo do E-mail", key="mass_body")

            # Tabela editável para entrada de dados
            st.write("Insira os dados dos destinatários (Nome-RU e Email):")
            data = [
                {"Nome-RU": "", "Email": ""}  # Exemplo de estrutura inicial
            ]
            editable_table = st.data_editor(data, num_rows="dynamic", key="mass_table")

            if st.button("Enviar E-mails em Massa", key="mass_button"):
                if subject and body and editable_table:
                    # Verifica se os campos obrigatórios estão preenchidos
                    email_list = [row for row in editable_table if row["Nome-RU"] and row["Email"]]
                    if email_list:
                        payload = {
                            "subject": subject,
                            "body": body,
                            "email_user": st.session_state["usuario"],
                            "email_list": email_list,
                            "type": "mass_email",
                        }
                        try:
                            # Envia os dados para o webhook do n8n
                            response = requests.post(N8N_WEBHOOK_URL, json=payload, verify=False)
                            if response.status_code == 200:
                                st.success("E-mails enviados com sucesso!")
                            else:
                                st.error(f"Erro ao enviar e-mails: {response.text}")
                        except Exception as e:
                            st.error(f"Erro ao conectar ao webhook: {e}")
                    else:
                        st.error("Por favor, preencha todos os campos da tabela.")
                else:
                    st.warning("Por favor, preencha todos os campos obrigatórios.")

        # Aba 2: Envio Único
        # with tab2:
        #     st.header("Envio de E-mail Único")
        #     recipient_email = st.text_input("E-mail do Destinatário", key="single_email")
        #     subject_single = st.text_input("Assunto do E-mail", key="single_subject")
        #     body_single = st.text_area("Corpo do E-mail", key="single_body")
        #     attachment = st.file_uploader("Anexar arquivo (opcional)", type=["pdf"], key="single_attachment")

        #     if st.button("Enviar E-mail Único", key="single_button"):
        #         if recipient_email and subject_single and body_single:
        #             # Configura os dados do payload
        #             payload = {
        #                 "recipient_email": recipient_email,
        #                 "subject": subject_single,
        #                 "body": body_single,
        #                 "email_user": st.session_state["usuario"],
        #                 "type": "single_email",
        #                 "link_boleto": "",
        #             }

        #             # Envia o arquivo para o MinIO e obtém o link
        #             if attachment:
        #                 link_boleto = enviar_para_minio_com_identificacao(attachment, recipient_email, attachment.type)
        #                 if link_boleto:
        #                     st.success(f"Boleto enviado para o MinIO! Link: {link_boleto}")
        #                     # Adiciona o link ao corpo do e-mail
        #                     payload["link_boleto"] += f"{link_boleto}"

        #             try:
        #                 # Envia os dados para o webhook do n8n
        #                 response = requests.post(N8N_WEBHOOK_URL, json=payload, verify=False)
        #                 if response.status_code == 200:
        #                     st.success("E-mail enviado com sucesso!")
        #                 else:
        #                     st.error(f"Erro ao enviar e-mail: {response.text}")
        #             except Exception as e:
        #                 st.error(f"Erro ao conectar ao webhook: {e}")
        #         else:
        #             st.warning("Por favor, preencha todos os campos obrigatórios.")

        # Aba 3: Alterar Senha
        with tab2:
            st.header("Alterar Senha")
            senha_atual = st.text_input("Senha Atual", type="password", key="current_password")
            nova_senha = st.text_input("Nova Senha", type="password", key="new_password")
            confirmar_senha = st.text_input("Confirmar Nova Senha", type="password", key="confirm_password")

            if st.button("Alterar Senha", key="change_password_button"):
                if nova_senha != confirmar_senha:
                    st.error("A nova senha e a confirmação não coincidem.")
                elif alterar_senha(st.session_state["usuario"], senha_atual, nova_senha):
                    st.success("Senha alterada com sucesso!")
                else:
                    st.error("Senha atual incorreta ou erro ao alterar a senha.")

# Controle de login
if st.session_state["logado"]:
    tela_principal()
else:
    tela_login()