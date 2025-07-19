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
    html = f"""
    
    <!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>⚠️ Alerta de Reinicialização - {UNIDADE}</title>
</head>
<body style="font-family: Arial, sans-serif; background-color: #fefefe; margin: 0; padding: 0;">
    <div style="max-width: 600px; margin: 30px auto; background-color: #fff; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 0 12px rgba(255, 0, 0, 0.15); overflow: hidden;">
        
        <!-- Cabeçalho de alerta -->
        <div style="background-color: #c62828; color: white; text-align: center; padding: 20px;">
            <h2 style="margin: 0; font-size: 22px;">⚠️ ALERTA DE REINICIALIZAÇÃO</h2>
            <p style="margin: 5px 0 0;">Servidor PACS - {UNIDADE}</p>
        </div>

        <!-- Conteúdo principal -->
        <div style="padding: 25px;">
            <p style="font-size: 16px; color: #333;">
                Este é um <strong>aviso automático</strong> indicando que o servidor foi reiniciado.
            </p>

            <div style="background-color: #fff3cd; border-left: 6px solid #ffc107; padding: 15px 20px; margin: 20px 0; border-radius: 6px;">
                <p style="margin: 0; font-size: 16px;">
                    📅 <strong>Data e Hora:</strong><br>
                    <span style="font-size: 18px; color: #856404;"><strong>{data_hora}</strong></span>
                </p>
            </div>

            <p style="font-size: 15px; color: #555;">
                Recomendamos verificar se todos os serviços essenciais foram iniciados corretamente após o reboot.
            </p>
        </div>

        <!-- Rodapé -->
        <div style="background-color: #f5f5f5; text-align: center; padding: 18px;">
            <p style="margin: 5px 0;">🔧 Suporte Técnico - Equipe Polos</p>
        </div>
    </div>
</body>
</html>
    
    """
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