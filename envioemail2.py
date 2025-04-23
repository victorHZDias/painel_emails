import streamlit as st
import pandas as pd
import requests
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from minio import Minio
from minio.error import S3Error
from urllib3.exceptions import InsecureRequestWarning
import urllib3
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import bcrypt  # Importa a biblioteca para hashing de senhas
from pytz import timezone

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
# link_ultimo_item = obter_link_ultimo_item(MINIO_BUCKET_NAME)
# if link_ultimo_item:
#     print(f"Link do último item adicionado: {link_ultimo_item}")

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
        query = 'SELECT "Senha" FROM "Equipe_Completa" WHERE "EMAIL" = %s'
        cursor.execute(query, (email,))
        result = cursor.fetchone()

        if result:
            senha_armazenada = result[0]
            # Verifica se a senha armazenada é um hash do bcrypt
            if senha_armazenada.startswith("$2b$"):
                # Verifica a senha usando bcrypt
                if bcrypt.checkpw(senha.encode('utf-8'), senha_armazenada.encode('utf-8')):
                    return True
            else:
                # Senha armazenada não está no formato bcrypt (senha antiga)
                if senha == senha_armazenada:
                    return True

        cursor.close()
        conn.close()
        return False  # Credenciais inválidas
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
        query_verificar = 'SELECT "Senha" FROM "Equipe_Completa" WHERE "EMAIL" = %s'
        cursor.execute(query_verificar, (email,))
        result = cursor.fetchone()

        if result:
            senha_armazenada = result[0]
            # Verifica se a senha armazenada é um hash do bcrypt
            if senha_armazenada.startswith("$2b$"):
                if not bcrypt.checkpw(senha_atual.encode('utf-8'), senha_armazenada.encode('utf-8')):
                    cursor.close()
                    conn.close()
                    return False  # Senha atual incorreta
            else:
                # Senha armazenada não está no formato bcrypt (senha antiga)
                if senha_atual != senha_armazenada:
                    cursor.close()
                    conn.close()
                    return False  # Senha atual incorreta

            # Criptografa a nova senha
            nova_senha_hash = bcrypt.hashpw(nova_senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            # Atualiza a senha no banco de dados
            query_atualizar = 'UPDATE "Equipe_Completa" SET "Senha" = %s WHERE "EMAIL" = %s'
            cursor.execute(query_atualizar, (nova_senha_hash, email))
            conn.commit()
            cursor.close()
            conn.close()
            return True  # Senha alterada com sucesso
        else:
            cursor.close()
            conn.close()
            return False  # Usuário não encontrado
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return False

# Função para hospedar a imagem de rastreamento no MinIO com nome único
def hospedar_imagem_rastreamento(file_name):
    try:
        # Nome do bucket
        bucket_name = "rastreiaemail"

        # Verifica se o bucket existe
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)

        # Cria uma imagem de 1x1 pixel
        from io import BytesIO
        from PIL import Image
        img = Image.new("RGB", (1, 1), color=(255, 255, 255))
        img_data = BytesIO()
        img.save(img_data, format="PNG")
        img_data.seek(0)

        # Envia a imagem para o MinIO
        minio_client.put_object(
            bucket_name,
            file_name,
            img_data,
            length=img_data.getbuffer().nbytes,
            content_type="image/png"
        )

        # Gera o link público para a imagem
        link = minio_client.presigned_get_object(bucket_name, file_name)
        return link
    except Exception as e:
        st.error(f"Erro ao hospedar a imagem de rastreamento: {e}")
        return None

# Função para exibir os dados de rastreamento com filtros e métricas
def exibir_dados_rastreamento():
    st.header("Rastreamento de E-mails")
    filtro_avancado = st.selectbox(
        "Filtrar por Avançado", 
        ["Todos"] + obter_lista_avancados(), 
        key="filtro_avancado_rastreamento"
    )
    filtro_assistente = st.selectbox(
        "Filtrar por Assistente", 
        ["Todos"] + obter_lista_assistentes(), 
        key="filtro_assistente_rastreamento"
    )
    filtro_data = st.date_input(
        "Filtrar por Data", 
        value=datetime.now(fuso_horario_brasil).date(), 
        key="filtro_data_rastreamento"
    )

    # Conexão com o banco de dados para buscar os dados de rastreamento
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Consulta para buscar os dados de rastreamento
        query = """
        SELECT data_envio, remetente, destinatario, status, data_abertura
        FROM rastreamento_emails
        WHERE status IN ('Aberto', 'Não Aberto')
        """
        params = []

        # Aplica os filtros
        if filtro_avancado != "Todos":
            query += ' AND remetente IN (SELECT "EMAIL" FROM "Equipe_Completa" WHERE "Nome_Colaborador" = %s)'
            params.append(filtro_avancado)
        if filtro_assistente != "Todos":
            query += ' AND destinatario IN (SELECT "EMAIL" FROM "Equipe_Completa" WHERE "Nome_Colaborador" = %s)'
            params.append(filtro_assistente)
        if filtro_data:
            query += ' AND DATE("data_envio") = %s'
            params.append(filtro_data)

        cursor.execute(query, tuple(params))
        rastreamento = cursor.fetchall()
        cursor.close()
        conn.close()

        if rastreamento:
            # Converte os dados em um DataFrame
            df = pd.DataFrame(rastreamento)

            # Converte as datas para o fuso horário do Brasil
            df["data_envio"] = pd.to_datetime(df["data_envio"]).dt.tz_localize("UTC").dt.tz_convert("America/Sao_Paulo")
            df["data_abertura"] = pd.to_datetime(df["data_abertura"]).dt.tz_localize("UTC").dt.tz_convert("America/Sao_Paulo")

            # Calcula as métricas
            total_enviados = len(df)
            total_lidos = len(df[df["status"] == "Aberto"])
            total_nao_lidos = len(df[df["status"] == "Não Aberto"])

            # Exibe as métricas
            col1, col2, col3 = st.columns(3)
            col1.metric("E-mails Enviados", total_enviados)
            col2.metric("E-mails Lidos", total_lidos)
            col3.metric("E-mails Não Lidos", total_nao_lidos)

            # Exibe os dados de rastreamento
            st.write("Dados de Rastreamento:")
            st.dataframe(df[["data_envio", "remetente", "destinatario", "status", "data_abertura"]], use_container_width=True)
        else:
            st.write("Nenhum dado de rastreamento encontrado para os filtros selecionados.")
    except Exception as e:
        st.error(f"Erro ao carregar os dados de rastreamento: {e}")

# Função para enviar e-mails em massa usando SMTP do Office 365
def enviar_emails_smtp(subject, body_html, email_list, email_user, email_password):
    try:
        # Configuração do servidor SMTP do Office 365
        smtp_server = "smtp.office365.com"
        smtp_port = 587

        # Conexão com o servidor SMTP
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Inicia a conexão segura

        try:
            server.login(email_user, email_password)  # Autenticação
        except smtplib.SMTPAuthenticationError:
            st.error("Erro de autenticação no servidor SMTP. Verifique o e-mail e a senha.")
            return False

        # Envia e-mails para cada destinatário
        for recipient in email_list:
            msg = MIMEMultipart("alternative")
            msg["From"] = email_user
            msg["To"] = recipient["Email"]
            msg["Subject"] = subject

            # Gera um ID único para rastreamento
            id_rastreamento = str(uuid.uuid4())

            # Gera o link da imagem de rastreamento para o destinatário
            link_rastreamento = hospedar_imagem_rastreamento(f"{id_rastreamento}.png")

            # Personaliza o HTML com o nome do destinatário e o link de rastreamento
            body_personalizado = body_html.replace("Nome-RU", recipient["Nome-RU"])
            body_personalizado = body_personalizado.replace("rastreamento_url", link_rastreamento)

            # Adiciona o corpo do e-mail em HTML
            msg.attach(MIMEText(body_personalizado, "html"))

            # Envia o e-mail
            server.sendmail(email_user, recipient["Email"], msg.as_string())

            # Registra o envio no banco de dados
            registrar_envio_email(
                email_user,
                recipient["Email"],
                recipient["Nome-RU"],
                subject,
                body_personalizado,
                id_rastreamento
            )

        server.quit()  # Fecha a conexão com o servidor
        st.rerun()
        return True
    except Exception as e:
        st.error(f"Erro ao enviar e-mails: {e}")
        return False

# Define o fuso horário do Brasil
fuso_horario_brasil = timezone("America/Sao_Paulo")

# Função para registrar o envio de e-mails no banco de dados
def registrar_envio_email(remetente, destinatario, nome_destinatario, assunto, corpo, id_rastreamento):
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

        # Obtém a data e hora atual no fuso horário do Brasil
        data_envio = datetime.now(fuso_horario_brasil)

        # Inserir os dados do envio no banco
        query = """
        INSERT INTO rastreamento_emails (remetente, destinatario, nome_destinatario, assunto, corpo, id_rastreamento, data_envio)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (remetente, destinatario, nome_destinatario, assunto, corpo, id_rastreamento, data_envio))
        conn.commit()

        cursor.close()
        conn.close()
    except Exception as e:
        st.error(f"Erro ao registrar o envio no banco de dados: {e}")

# Função para salvar os e-mails pendentes no banco de dados
def salvar_emails_pendentes(email_user, email_list, subject, body_html):
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()

        # Insere os e-mails pendentes no banco de dados
        query = """
        INSERT INTO rastreamento_emails (remetente, destinatario, nome_destinatario, assunto, corpo, id_rastreamento, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'Pendente')
        """
        for recipient in email_list:
            id_rastreamento = str(uuid.uuid4())
            cursor.execute(query, (
                email_user,
                recipient["Email"],
                recipient["Nome-RU"],
                subject,
                body_html.replace("{{ Nome-RU }}", recipient["Nome-RU"]),
                id_rastreamento
            ))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        st.error(f"Erro ao salvar e-mails pendentes: {e}")

# Função para exibir a tela de aprovação com filtros e seleção de mensagens
def tela_aprovacao():
    st.header("Aprovação de E-mails")
    filtro_avancado = st.selectbox(
        "Filtrar por Avançado", 
        ["Todos"] + obter_lista_avancados(), 
        key="filtro_avancado_aprovacao"
    )
    filtro_assistente = st.selectbox(
        "Filtrar por Assistente", 
        ["Todos"] + obter_lista_assistentes(), 
        key="filtro_assistente_aprovacao"
    )
    filtro_data = st.date_input(
        "Filtrar por Data", 
        value=datetime.now().date(), 
        key="filtro_data_aprovacao"
    )

    # Conexão com o banco de dados para buscar os e-mails pendentes
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Consulta para buscar os e-mails pendentes
        query = """
        SELECT id, remetente, destinatario, nome_destinatario, assunto, corpo, data_envio
        FROM rastreamento_emails
        WHERE status = 'Pendente'
        """
        params = []

        # Aplica os filtros
        if filtro_avancado != "Todos":
            query += ' AND remetente IN (SELECT "EMAIL" FROM "Equipe_Completa" WHERE "Nome_Colaborador" = %s)'
            params.append(filtro_avancado)
        if filtro_assistente != "Todos":
            query += ' AND destinatario IN (SELECT "EMAIL" FROM "Equipe_Completa" WHERE "Nome_Colaborador" = %s)'
            params.append(filtro_assistente)
        if filtro_data:
            query += ' AND DATE("data_envio") = %s'
            params.append(filtro_data)

        cursor.execute(query, tuple(params))
        emails_pendentes = cursor.fetchall()
        cursor.close()
        conn.close()

        if emails_pendentes:
            st.write("E-mails Pendentes de Aprovação:")
            df = pd.DataFrame(emails_pendentes)

            # Adiciona uma coluna de seleção
            df["Selecionar"] = False

            # Checkbox global para selecionar todas as linhas
            selecionar_todos = st.checkbox("Selecionar Todos", key="selecionar_todos")
            if selecionar_todos:
                df["Selecionar"] = True

            # Exibe a tabela sem o corpo do e-mail
            selected_rows = st.data_editor(
                df[["Selecionar", "id", "remetente", "destinatario", "nome_destinatario", "assunto", "data_envio"]],
                use_container_width=True,
                key="aprovacao_table"
            )

            # Exibe o corpo do e-mail apenas se um assistente for selecionado
            if filtro_assistente != "Todos":
                st.markdown("**Modelo do Corpo do E-mail:**", unsafe_allow_html=True)
                st.markdown(emails_pendentes[0]["corpo"], unsafe_allow_html=True)

            # Botões de aprovação ou rejeição
            if st.button("Aprovar Selecionados"):
                emails_selecionados = df[df["Selecionar"] == True]
                if not emails_selecionados.empty:
                    # Atualiza o status para "Aprovado"
                    atualizar_status_emails(emails_selecionados.to_dict("records"), "Aprovado")

                    # Envia os e-mails aprovados
                    for email in emails_selecionados.to_dict("records"):
                        enviar_emails_smtp(
                            subject=email["assunto"],
                            body_html=email["corpo"],
                            email_list=[{"Email": email["destinatario"], "Nome-RU": email["nome_destinatario"]}],
                            email_user=st.session_state["usuario"],
                            email_password=st.session_state["senha"]
                        )

                    st.success("E-mails aprovados e enviados com sucesso!")
                else:
                    st.warning("Nenhum e-mail selecionado para aprovação.")

            if st.button("Rejeitar Selecionados"):
                emails_selecionados = df[df["Selecionar"] == True]
                if not emails_selecionados.empty:
                    motivo = st.text_area("Motivo da Rejeição", key="motivo_rejeicao_aprovacao")
                    atualizar_status_emails(emails_selecionados.to_dict("records"), "Rejeitado", motivo)
                    st.warning("E-mails rejeitados e aviso enviado aos assistentes.")
                else:
                    st.warning("Nenhum e-mail selecionado para rejeição.")
        else:
            st.write("Nenhum e-mail pendente para aprovação.")
    except Exception as e:
        st.error(f"Erro ao carregar os e-mails pendentes: {e}")

# Função para atualizar o status dos e-mails no banco de dados
def atualizar_status_emails(emails, status, motivo=None):
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()

        for email in emails:
            query = "UPDATE rastreamento_emails SET status = %s WHERE id = %s"
            cursor.execute(query, (status, email["id"]))

            # Envia aviso ao assistente em caso de rejeição
            if status == "Rejeitado" and motivo:
                enviar_aviso_rejeicao(email["remetente"], motivo)

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        st.error(f"Erro ao atualizar o status dos e-mails: {e}")

# Função para enviar aviso de rejeição ao assistente
def enviar_aviso_rejeicao(email_assistente, motivo):
    try:
        smtp_server = "smtp.office365.com"
        smtp_port = 587
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(st.session_state["usuario"], st.session_state["senha"])

        subject = "Envio de E-mails Não Autorizado"
        body = f"Seu envio de e-mails foi rejeitado. Motivo: {motivo}"
        msg = MIMEMultipart()
        msg["From"] = st.session_state["usuario"]
        msg["To"] = email_assistente
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server.sendmail(st.session_state["usuario"], email_assistente, msg.as_string())
        server.quit()
    except Exception as e:
        st.error(f"Erro ao enviar aviso de rejeição: {e}")

# Função para obter o perfil do usuário logado
def obter_perfil_usuario(email):
    try:
        # Conexão com o banco de dados
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        # Consulta para obter o perfil do usuário
        query = 'SELECT "Perfil" FROM "Equipe_Completa" WHERE "EMAIL" = %s'
        cursor.execute(query, (email,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result["Perfil"] if result else None
    except Exception as e:
        st.error(f"Erro ao obter o perfil do usuário: {e}")
        return None

# Função para obter o nome do remetente a partir do e-mail
def obter_nome_remetente(email):
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
        # Consulta para obter o nome do colaborador
        query = 'SELECT "Nome_Colaborador" FROM "Equipe_Completa" WHERE "EMAIL" = %s'
        cursor.execute(query, (email,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] if result else "Equipe UNINTER"
    except Exception as e:
        st.error(f"Erro ao obter o nome do remetente: {e}")
        return "Equipe UNINTER"

# Função para obter a lista de avançados (nomes)
def obter_lista_avancados():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        query = 'SELECT DISTINCT "Nome_Colaborador" FROM "Equipe_Completa" WHERE "Perfil" = %s'
        cursor.execute(query, ("avançado",))
        avancados = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return avancados
    except Exception as e:
        st.error(f"Erro ao obter a lista de avançados: {e}")
        return []

# Função para obter a lista de assistentes (nomes)
def obter_lista_assistentes():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        query = 'SELECT DISTINCT "Nome_Colaborador" FROM "Equipe_Completa" WHERE "Perfil" = %s'
        cursor.execute(query, ("assistente",))
        assistentes = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return assistentes
    except Exception as e:
        st.error(f"Erro ao obter a lista de assistentes: {e}")
        return []

# Controle de login
if "logado" not in st.session_state:
    st.session_state["logado"] = False

if "usuario" not in st.session_state:
    st.session_state["usuario"] = None

# Tela de login
def tela_login():
    col1, col2, col3 = st.columns([3, 2, 3])
    with col2:
        st.image("https://portal.uninter.com/wp-content/themes/portal/imagens/marca-uninter-horizontal.png", width=150)
        st.title("Login")
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if verificar_login(email, senha):
                st.session_state["logado"] = True
                st.session_state["usuario"] = email  # Armazena o e-mail do usuário logado
                st.session_state["senha"] = senha  # Armazena a senha do usuário logado
                st.success("Login realizado com sucesso!")
                st.rerun()  # Atualiza a interface
            else:
                st.error("E-mail ou senha inválidos.")

# Tela principal
def tela_principal():
    # Obtém o perfil do usuário logado
    perfil_usuario = obter_perfil_usuario(st.session_state["usuario"])

    # Exibe o e-mail e o perfil do usuário logado na sidebar
    st.sidebar.image("https://portal.uninter.com/wp-content/themes/portal/imagens/marca-uninter-horizontal.png", width=150)
    st.sidebar.write(f"Usuário logado: {st.session_state['usuario']}")
    st.sidebar.write(f"Perfil: {perfil_usuario}")
    st.sidebar.button("Sair", on_click=lambda: [st.session_state.clear(), st.rerun()])
    st.sidebar.button("Atualizar", on_click=lambda: st.rerun())
    col1, col2, col3 = st.columns([3, 6, 3])
    with col2:
        # Título do app
        st.title("Envio de E-mails em Massa")

        # Define as abas disponíveis com base no perfil do usuário
        if perfil_usuario == "assistente":
            abas = ["Envio em Massa", "Alterar Senha"]
        else:
            abas = ["Envio em Massa", "Alterar Senha", "Rastreamento", "Aprovação"]

        # Aba para selecionar o tipo de envio
        tab1, tab2, *rest = st.tabs(abas)

        # Aba 1: Envio em Massa
        with tab1:
            st.header("Envio de E-mails em Massa")
            subject = st.text_input("Assunto do E-mail", key="mass_subject")
            body_text = st.text_area("Texto da Mensagem", key="mass_body")

            # Configuração de cores
            st.subheader("Configuração de Cores")
            bg_color = st.color_picker("Cor de Fundo", "#87CEFA")
            border_color = st.color_picker("Cor da Borda", "#1E90FF")
            text_color = st.color_picker("Cor do Texto", "#000000")

            remetente_nome = obter_nome_remetente(st.session_state["usuario"])
            
            # Gera o HTML com as cores e texto configurados
            body_html = f"""
            <div style="background-color:{bg_color};border:2px solid {border_color};margin: 0 auto;padding: 40px;">
                <body>
                    <div style="background-color:{border_color};border:1px solid Tomato;text-align: center">
                        <p><img src="https://portal.uninter.com/wp-content/themes/portal/imagens/marca-uninter-horizontal.png" alt="Logo UNINTER"></p>
                        <h1 style="color:{text_color};">Olá Nome-RU ,</h1>
                    </div>
                    <div style="background-color:white;font-size: 28px;border: 5px solid black;margin: 0 auto;padding: 10px;">
                        <h2 style="color:{text_color};">{subject}</h2>
                        <p style="color:{text_color};">{body_text}</p>
                        <p style="color:{text_color};">Atenciosamente,</p>
                        <p style="color:{text_color};">{remetente_nome}</p>
                        <p><img src="https://res.cloudinary.com/dilr8ucsa/image/upload/v1744312588/image001_mu3fan.jpg" alt="Logo UNINTER" style="width: auto; height: auto;"></p>
                        <!-- Marcador de rastreamento -->
                        <img src="rastreamento_url" alt="" style="display:none;width:1px;height:1px;">
                    </div>
                </body>
            </div>
            """

            # Prévia do HTML
            st.subheader("Prévia do HTML")
            st.markdown(body_html.replace("{{ rastreamento_url }}", "URL_DE_EXEMPLO"), unsafe_allow_html=True)

            # Tabela editável para entrada de dados
            st.write("Insira os dados dos destinatários (Nome-RU e Email):")
            data = [
                {"Nome-RU": "", "Email": ""}  # Exemplo de estrutura inicial
            ]
            editable_table = st.data_editor(data, num_rows="dynamic", key="mass_table")

            if st.button("Salvar para Aprovação", key="save_button"):
                if subject and body_text and editable_table:
                    email_list = [row for row in editable_table if row["Nome-RU"] and row["Email"]]
                    if email_list:
                        salvar_emails_pendentes(
                            st.session_state["usuario"],
                            email_list,
                            subject,
                            body_html
                        )
                        st.success("E-mails salvos para aprovação!")
                    else:
                        st.error("Por favor, preencha todos os campos da tabela.")
                else:
                    st.warning("Por favor, preencha todos os campos obrigatórios.")

        # Aba 2: Alterar Senha
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

        # Aba 3: Rastreamento (somente para não-assistentes)
        if perfil_usuario != "assistente" and len(rest) > 0:
            with rest[0]:
                exibir_dados_rastreamento()

        # Aba 4: Aprovação (somente para não-assistentes)
        if perfil_usuario != "assistente" and len(rest) > 1:
            with rest[1]:
                tela_aprovacao()

# Controle de login
if st.session_state["logado"]:
    tela_principal()
else:
    tela_login()