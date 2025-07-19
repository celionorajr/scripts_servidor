#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import psutil
import logging

load_dotenv("/root/.env")

# Variáveis do .env
unidade = os.getenv("UNIDADE")
caminho_hd_principal = os.getenv("HD_PRINCIPAL")
caminho_hd_backup = os.getenv("HD_BACKUP")

remetente = os.getenv("EMAIL_REMETENTE")
senha = os.getenv("EMAIL_SENHA")
smtp_host = os.getenv("EMAIL_SMTP_HOST")
smtp_port = int(os.getenv("EMAIL_SMTP_PORT"))
destinatarios = os.getenv("EMAIL_DESTINATARIOS").split(",")

limite_uso_hd_principal = int(os.getenv("LIMITE_USO_HD_PRINCIPAL"))
limite_livre_backup = int(os.getenv("LIMITE_LIVRE_BACKUP_GB")) * (1024 ** 3)

# Logging
logging.basicConfig(filename='/var/log/alerta.log', level=logging.ERROR)

# Funções
def verificar_uso_hd(caminho):
    try:
        uso_hd = psutil.disk_usage(caminho)
        return uso_hd.percent, uso_hd.total, uso_hd.used, uso_hd.free
    except Exception as e:
        logging.error(f"Erro ao verificar uso do HD {caminho}: {e}")
        return 0, 0, 0, 0

def esta_montado(caminho):
    return any(part.mountpoint == caminho for part in psutil.disk_partitions(all=True))

# Verifica o uso do HD principal
uso_principal, tamanho_total_principal, tamanho_usado_principal, tamanho_livre_principal = verificar_uso_hd(caminho_hd_principal)

# Verifica o uso do HD de backup (se houver)
if caminho_hd_backup and esta_montado(caminho_hd_backup):
    uso_backup, tamanho_total_backup, tamanho_usado_backup, tamanho_livre_backup = verificar_uso_hd(caminho_hd_backup)
else:
    uso_backup = tamanho_total_backup = tamanho_usado_backup = tamanho_livre_backup = 0

# Verifica se precisa enviar o alerta
if uso_principal >= limite_uso_hd_principal and (not caminho_hd_backup or tamanho_livre_backup < limite_livre_backup):

    # Corpo do email
    corpo = f"""
    <html>
    <body>
        <h2>Alerta Automático - Servidor PACS {unidade}</h2>
        <p><strong>HD principal</strong> atingiu <strong>{uso_principal}%</strong> de uso.</p>
        <p><strong>HD de backup</strong>: {'sem backup configurado' if not caminho_hd_backup else f'{uso_backup}% de uso'}</p>
        <p>Considere limpeza ou expansão.</p>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg["From"] = remetente
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = f"Alerta: Uso do HD do servidor PACS {unidade}"
    msg.attach(MIMEText(corpo, "html"))

    try:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, destinatarios, msg.as_string())
        server.quit()
        print("Email enviado com sucesso!")
    except Exception as e:
        logging.error(f"Falha ao enviar o email: {e}")
        print(f"Falha ao enviar o email: {e}")
else:
    print("Condições para envio de alerta não foram atendidas.")