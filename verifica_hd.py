#!/usr/bin/env python3
import os
import smtplib
import psutil
import ssl
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv("/root/.env")

# Variáveis do .env
remetente = os.getenv("EMAIL_REMETENTE")
senha = os.getenv("EMAIL_SENHA")
destinatarios = os.getenv("EMAIL_DESTINATARIOS").split(",")
smtp_server = os.getenv("EMAIL_SMTP_HOST")
smtp_port = int(os.getenv("EMAIL_SMTP_PORT"))
UNIT_NAME = os.getenv("UNIDADE")

THRESHOLD = int(os.getenv("LIMITE_USO_HD_PRINCIPAL"))
DIR_PRODUCAO = os.getenv("HD_PRINCIPAL")
DIR_BACKUP = os.getenv("HD_BACKUP")

# Verifica se partição está montada
def esta_montado(caminho):
    return any(part.mountpoint == caminho for part in psutil.disk_partitions(all=True))

# Retorna uso percentual de um disco
def get_usage(directory):
    try:
        usage = psutil.disk_usage(directory)
        return usage.percent
    except:
        return 0

# Uso do HD de produção
prod_usage = get_usage(DIR_PRODUCAO)

# Uso do HD de backup se estiver configurado e montado
if DIR_BACKUP and esta_montado(DIR_BACKUP):
    backup_usage = get_usage(DIR_BACKUP)
else:
    backup_usage = 0

# Envia e-mail
def send_email(subject, body):
    message = MIMEMultipart()
    message["From"] = remetente
    message["To"] = ", ".join(destinatarios)
    message["Subject"] = subject
    message.attach(MIMEText(body, "html"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(remetente, senha)
            server.sendmail(remetente, destinatarios, message.as_string())
            print("E-mail enviado com sucesso!")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

# Condição para envio
if prod_usage >= THRESHOLD and (not DIR_BACKUP or backup_usage < THRESHOLD):
    subject = f"Alerta de Gerenciamento de Disco: {UNIT_NAME}"
    body = f"""
    <html>
        <body>
            <h2>⚠️ Alerta de Disco - {UNIT_NAME}</h2>
            <p>HD de produção em <strong>{DIR_PRODUCAO}</strong> está com <strong>{prod_usage}%</strong> de uso.</p>
            <p>Backup: {"não configurado" if not DIR_BACKUP else f"{backup_usage}% de uso"}</p>
            <p><em>Este é um alerta automático.</em></p>
        </body>
    </html>
    """
    send_email(subject, body)
