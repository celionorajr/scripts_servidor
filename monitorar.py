#!/usr/bin/env python3
import os
import time
import smtplib
from dotenv import load_dotenv
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import fcntl
import ssl

load_dotenv("/root/.env")

EMAIL_HOST = os.getenv("EMAIL_SMTP_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_SMTP_PORT"))
EMAIL_USER = os.getenv("EMAIL_REMETENTE")
EMAIL_PASSWORD = os.getenv("EMAIL_SENHA")
DESTINATARIOS = os.getenv("EMAIL_DESTINATARIOS_2").split(',')
UNIDADE = os.getenv("UNIDADE")
CONTROLE_ARQUIVO = os.getenv("CONTROLE_ARQUIVO")
TEMPO_MINIMO_ENVIO = int(os.getenv("TEMPO_MINIMO_ENVIO"))
LOCK_FILE = os.getenv("LOCK_FILE")

def enviar_email_reinicio():
    msg = MIMEMultipart()
    msg['Subject'] = f'⚠️ Alerta: Servidor Reiniciado - {UNIDADE}'
    msg['From'] = EMAIL_USER
    msg['To'] = ', '.join(DESTINATARIOS)
    
    current_year = datetime.now().year
    data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
    
    html = f"""
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alerta de Reinicialização - {UNIDADE}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #f9f9f9;
            margin: 0;
            padding: 0;
            color: #333;
        }}
        .container {{
            max-width: 600px;
            margin: 20px auto;
            background-color: #fff;
            border: 1px solid #ddd;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.08);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(to right, #04546c, #029687);
            color: white;
            text-align: center;
            padding: 20px;
        }}
        .logo {{
            height: 70px;
            margin-bottom: 15px;
        }}
        .content {{
            padding: 25px;
        }}
        .alert-title {{
            background-color: #ffebee;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 20px;
            border-left: 5px solid #d32f2f;
        }}
        .info-box {{
            background-color: #f2f9f9;
            border-left: 5px solid #029687;
            padding: 15px 20px;
            margin: 20px 0;
            border-radius: 6px;
        }}
        .warning-box {{
            background-color: #fff3cd;
            border-left: 5px solid #ffc107;
            padding: 15px 20px;
            margin: 20px 0;
            border-radius: 6px;
        }}
        .footer {{
            background: linear-gradient(to right, #04546c, #029687);
            color: white;
            text-align: center;
            padding: 20px;
        }}
        .signature {{
            margin-top: 5px;
            text-align: center;
            color: #04ecd4;
            font-size: 14px;
        }}
        .important {{
            font-weight: bold;
            color: #d32f2f;
            font-size: 18px;
        }}
        .time-display {{
            font-size: 20px;
            color: #04546c;
            font-weight: bold;
            text-align: center;
            padding: 10px;
            background-color: #f0f8ff;
            border-radius: 6px;
            margin: 15px 0;
        }}

        /* Responsivo */
        @media (max-width: 600px) {{
            .container {{
                width: 95%;
                margin: 10px auto;
            }}
            .header {{
                padding: 15px;
            }}
            .logo {{
                height: 50px;
            }}
            .content {{
                padding: 15px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://i.imgur.com/M4fVy4y.png" alt="Polos Tecnologia" class="logo">
            <h2 style="margin: 0; font-size: 22px;">⚠️ Alerta de Reinicialização</h2>
            <p style="margin: 5px 0 0;">Servidor PACS - {UNIDADE}</p>
        </div>

        <div class="content">
            <div class="alert-title">
                <p style="margin: 0; font-size: 16px;">
                    <strong>AVISO AUTOMÁTICO:</strong> O servidor foi reiniciado
                </p>
            </div>

            <p class="important">Atenção! O servidor PACS da unidade {UNIDADE} foi reiniciado.</p>

            <div class="info-box">
                <p style="margin: 0; font-size: 16px;">
                    <strong>📅 Data e Hora do Reinício:</strong>
                </p>
                <div class="time-display">
                    {data_hora}
                </div>
            </div>

            <div class="warning-box">
                <p style="margin: 0; font-size: 16px;">
                    <strong>🔧 Ação Recomendada:</strong><br>
                    Verifique se todos os serviços essenciais foram iniciados corretamente após o reboot.
                    Confirme a operação normal do sistema PACS e seus componentes.
                </p>
            </div>

            <div class="info-box">
                <p style="margin: 0; font-size: 16px;">
                    <strong>📋 Checklist Recomendado:</strong><br>
                    • Serviço PACS em execução<br>
                    • Banco de dados operacional<br>
                    • Conexões de rede estabelecidas<br>
                    • Storage montado e acessível<br>
                    • Aplicações auxiliares funcionando
                </p>
            </div>

            <p style="font-size: 15px; color: #555;">
                Este é um alerta automático do sistema de monitoramento.
                Se o reinício não foi planejado, investigue as causas.
            </p>
        </div>

        <div class="footer">
            <p style="margin: 5px 0;">Desenvolvido por Celio Nora Junior - Analista de Suporte Técnico</p>
            <div class="signature">
                Sistema de monitoramento automático
            </div>
            <p style="margin: 10px 0 0; font-size: 12px;">© {current_year} Polos Tecnologia</p>
        </div>
    </div>
</body>
</html>
"""
    msg.attach(MIMEText(html, 'html'))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls(context=context)
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
            with open(CONTROLE_ARQUIVO, 'w') as f:
                f.write(str(time.time()))
            print("Email de reinicialização enviado com sucesso.")
    except Exception as e:
        print(f"Erro ao enviar o email: {e}")

def verificar_envio():
    if os.path.exists(CONTROLE_ARQUIVO):
        with open(CONTROLE_ARQUIVO, 'r') as f:
            try:
                ultimo_envio = float(f.read())
                tempo_decorrido = time.time() - ultimo_envio
                return tempo_decorrido < TEMPO_MINIMO_ENVIO
            except ValueError:
                return False
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
            tempo_restante = TEMPO_MINIMO_ENVIO - (time.time() - float(open(CONTROLE_ARQUIVO).read()))
            print(f"Já foi enviado recentemente. Próximo envio em {int(tempo_restante/60)} minutos.")
    except FileNotFoundError:
        enviar_email_reinicio()
    finally:
        lock_file.close()