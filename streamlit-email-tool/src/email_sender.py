from openpyxl import load_workbook
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
from datetime import datetime, timedelta
import time

class EmailSender:
    def __init__(self, smtp_server, smtp_port, smtp_user, smtp_password):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.sent_emails = 0
        self.start_time = datetime.now()

    def read_email_list(self, file_path):
        df = pd.read_excel(file_path)
        return df['Email'].tolist()

    def send_email(self, recipient, subject, body):
        msg = MIMEMultipart()
        msg['From'] = self.smtp_user
        msg['To'] = recipient
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)

    def rate_limit(self):
        if self.sent_emails >= 500:
            if datetime.now() < self.start_time + timedelta(days=1):
                time_to_wait = (self.start_time + timedelta(days=1)) - datetime.now()
                time.sleep(time_to_wait.total_seconds())
            self.sent_emails = 0
            self.start_time = datetime.now()

    def send_bulk_emails(self, email_list, subject, body):
        for recipient in email_list:
            self.rate_limit()
            self.send_email(recipient, subject, body)
            self.sent_emails += 1
            time.sleep(6)  # Sleep for 6 seconds to average 10 emails per minute
