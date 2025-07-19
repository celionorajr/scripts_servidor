#!/usr/bin/env python3
import os
import time
import smtplib
from dotenv import load_dotenv
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import fcntl

load_dotenv("/root/.env")

EMAIL_HOST = os.getenv("EMAIL_SMTP_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_SMTP_PORT"))
EMAIL_USER = os.getenv("EMAIL_REMETENTE")
EMAIL_PASSWORD = os.getenv("EMAIL_SENHA")
DESTINATARIOS = os.getenv("EMAIL_DESTINATARIOS").split(',')
UNIDADE = os.getenv("UNIDADE")
CONTROLE_ARQUIVO = os.getenv("CONTROLE_ARQUIVO")
TEMPO_MINIMO_ENVIO = int(os.getenv("TEMPO_MINIMO_ENVIO"))
LOCK_FILE = os.getenv("LOCK_FILE")

def enviar_email_reinicio():
    msg = MIMEMultipart()
    msg['Subject'] = f'Aviso: Servidor Reiniciado - Unidade {UNIDADE}'
    msg['From'] = EMAIL_USER
    msg['To'] = ', '.join(DESTINATARIOS)
    data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
    html = f"""<html><body><h2>Reinicialização do Servidor - {UNIDADE}</h2><p>O servidor foi reiniciado em <strong>{data_hora}</strong>.</p></body></html>"""
    msg.attach(MIMEText(html, 'html'))

    try:
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
            with open(CONTROLE_ARQUIVO, 'w') as f:
                f.write(str(time.time()))
            print("Email enviado com sucesso.")
    except Exception as e:
        print(f"Erro ao enviar o email: {e}")

def verificar_envio():
    if os.path.exists(CONTROLE_ARQUIVO):
        with open(CONTROLE_ARQUIVO, 'r') as f:
            ultimo_envio = float(f.read())
            return (time.time() - ultimo_envio) < TEMPO_MINIMO_ENVIO
    return False

def acquire_lock():
    lock_file = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_file
    except IOError:
        print("Já está rodando.")
        exit(1)

if __name__ == '__main__':
    lock_file = acquire_lock()
    try:
        if not verificar_envio():
            enviar_email_reinicio()
        else:
            print("Já foi enviado recentemente.")
    finally:
        lock_file.close()