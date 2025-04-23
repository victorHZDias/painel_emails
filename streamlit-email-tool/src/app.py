import streamlit as st
from email_sender import EmailSender
import os

# Configurações do SMTP
SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587
SMTP_USER = os.getenv("SMTP_USER")  # Defina como variável de ambiente
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")  # Defina como variável de ambiente

# Inicializa o EmailSender
email_sender = EmailSender(SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD)

# Interface Streamlit
st.title("Envio de E-mails em Massa")

# Campos de entrada
subject = st.text_input("Assunto do E-mail")
body = st.text_area("Corpo do E-mail")
uploaded_file = st.file_uploader("Carregar arquivo Excel com lista de e-mails", type=["xlsx"])

# Botão para enviar e-mails
if st.button("Enviar E-mails"):
    if uploaded_file and subject and body:
        # Lê a lista de e-mails do arquivo Excel
        email_list = email_sender.read_email_list(uploaded_file)
        st.write(f"Total de e-mails carregados: {len(email_list)}")

        # Envia os e-mails
        try:
            email_sender.send_bulk_emails(email_list, subject, body)
            st.success("E-mails enviados com sucesso!")
        except Exception as e:
            st.error(f"Erro ao enviar e-mails: {e}")
    else:
        st.warning("Por favor, preencha todos os campos e carregue o arquivo Excel.")