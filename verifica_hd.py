#!/usr/bin/env python3
import os
import smtplib
import psutil
import ssl
import base64
import io
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import matplotlib.pyplot as plt

load_dotenv("/root/.env")

remetente = os.getenv("EMAIL_REMETENTE")
senha = os.getenv("EMAIL_SENHA")
destinatarios = os.getenv("EMAIL_DESTINATARIOS").split(",")
smtp_server = os.getenv("EMAIL_SMTP_HOST")
smtp_port = int(os.getenv("EMAIL_SMTP_PORT"))
UNIT_NAME = os.getenv("UNIDADE")
THRESHOLD = int(os.getenv("LIMITE_USO_HD_PRINCIPAL"))
DIR_PRODUCAO = os.getenv("HD_PRINCIPAL")
DIR_BACKUP = os.getenv("HD_BACKUP")

def esta_montado(caminho):
    return any(part.mountpoint == caminho for part in psutil.disk_partitions(all=True))

def get_usage(directory):
    try:
        usage = psutil.disk_usage(directory)
        return usage.percent
    except:
        return 0

# Captura os valores de uso
prod_usage = get_usage(DIR_PRODUCAO)
backup_usage = get_usage(DIR_BACKUP) if DIR_BACKUP and esta_montado(DIR_BACKUP) else 0

# Gera gráfico em memória
def gerar_grafico():
    labels = ['Produção', 'Backup']
    values = [prod_usage, backup_usage]
    colors = ['#d9534f', '#5bc0de']

    fig, ax = plt.subplots()
    bars = ax.bar(labels, values, color=colors)
    ax.set_ylim(0, 100)
    ax.set_ylabel('% de Uso')
    ax.set_title(f'Uso de Disco - {UNIT_NAME}')
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, height + 1, f'{height:.1f}%', ha='center', va='bottom')

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    return buf

def send_email(subject, body, imagem_bytes):
    message = MIMEMultipart('related')
    message["From"] = remetente
    message["To"] = ", ".join(destinatarios)
    message["Subject"] = subject

    msg_alternative = MIMEMultipart('alternative')
    message.attach(msg_alternative)

    html_body = f'''
    <html>
        <body>
            <h2>⚠️ Alerta de Disco - {UNIT_NAME}</h2>
            <p>HD de produção em <strong>{DIR_PRODUCAO}</strong> está com <strong>{prod_usage}%</strong> de uso.</p>
            <p>Backup: {"não configurado" if not DIR_BACKUP else f"{backup_usage}% de uso"}</p>
            <img src="cid:disco_grafico"><br>
            <p><em>Este é um alerta automático.</em></p>
        </body>
    </html>
    '''
    msg_alternative.attach(MIMEText(html_body, 'html'))

    image = MIMEImage(imagem_bytes.read())
    image.add_header('Content-ID', '<disco_grafico>')
    image.add_header('Content-Disposition', 'inline', filename='grafico.png')
    message.attach(image)

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(remetente, senha)
            server.sendmail(remetente, destinatarios, message.as_string())
            print("E-mail enviado com sucesso!")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

# Verifica se precisa enviar
if prod_usage >= THRESHOLD and (not DIR_BACKUP or backup_usage < THRESHOLD):
    subject = f"Alerta de Gerenciamento de Disco: {UNIT_NAME}"
    grafico_bytes = gerar_grafico()
    send_email(subject, "Verifique o uso do disco", grafico_bytes)
