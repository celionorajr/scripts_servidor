#!/usr/bin/env python3
import os
import smtplib
import psutil
import ssl
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

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
        return usage.percent, usage.total, usage.used, usage.free
    except:
        return 0, 0, 0, 0

# Captura os valores de uso
prod_usage, prod_total, prod_used, prod_free = get_usage(DIR_PRODUCAO)
if DIR_BACKUP and esta_montado(DIR_BACKUP):
    backup_usage, backup_total, backup_used, backup_free = get_usage(DIR_BACKUP)
else:
    backup_usage = backup_total = backup_used = backup_free = 0

def send_email(subject):
    current_year = datetime.now().year

    message = MIMEMultipart('alternative')
    message["From"] = remetente
    message["To"] = ", ".join(destinatarios)
    message["Subject"] = subject

    html_body = f'''
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alerta Polos - {UNIT_NAME}</title>
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
            background-color: #7cfcef;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 20px;
            border-left: 5px solid #04546c;
        }}
        .info-box {{
            background-color: #f2f9f9;
            border-left: 5px solid #029687;
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
            color: #04546c;
            font-size: 18px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 10px 8px;
            text-align: center;
        }}
        th {{
            background-color: #029687;
            color: white;
        }}
        tr:nth-child(even) {{
            background-color: #f2f9f9;
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
            <h2 style="margin: 0; font-size: 22px;">⚠️ Alerta de Armazenamento</h2>
            <p style="margin: 5px 0 0;">{UNIT_NAME}</p>
        </div>

        <div class="content">
            <div class="alert-title">
                <p style="margin: 0; font-size: 16px;">
                    Aviso: Hora de gerenciar o espaco dos HDs do servidor
                </p>
            </div>

            <p class="important">O uso do HD de producao atingiu {prod_usage}%, acima do limite de {THRESHOLD}%.</p>

            <table>
                <thead>
                    <tr>
                        <th>Disco</th>
                        <th>Tamanho Total</th>
                        <th>Espaco Usado</th>
                        <th>Espaco Livre</th>
                        <th>Uso (%)</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>HD Producao</td>
                        <td>{prod_total / (1024 ** 3):.2f} GB</td>
                        <td>{prod_used / (1024 ** 3):.2f} GB</td>
                        <td>{prod_free / (1024 ** 3):.2f} GB</td>
                        <td>{prod_usage}%</td>
                    </tr>
                    <tr>
                        <td>HD Backup</td>
                        <td>{backup_total / (1024 ** 3):.2f} GB</td>
                        <td>{backup_used / (1024 ** 3):.2f} GB</td>
                        <td>{backup_free / (1024 ** 3):.2f} GB</td>
                        <td>{backup_usage}%</td>
                    </tr>
                </tbody>
            </table>

            <div class="info-box">
                <p style="margin: 0; font-size: 16px;">
                    <strong>📋 Acao Requerida:</strong><br>
                    A equipe de TI deve realizar a gestao do espaco em disco para evitar interrupcoes no servidor.
                </p>
            </div>

            <p style="font-size: 15px; color: #555;">
                Este e um aviso automatico para gestao proativa do armazenamento.
            </p>
        </div>

        <div class="footer">
            <p style="margin: 5px 0;">Desenvolvido por Celio Nora Junior - Analista de Suporte Tecnico</p>
            <div class="signature">
                Sistema de monitoramento automatico
            </div>
            <p style="margin: 10px 0 0; font-size: 12px;">© {current_year} Polos Tecnologia</p>
        </div>
    </div>
</body>
</html>
'''

    message.attach(MIMEText(html_body, 'html'))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(remetente, senha)
            server.sendmail(remetente, destinatarios, message.as_string())
            print("Aviso enviado com sucesso!")
    except Exception as e:
        print("Erro ao enviar aviso: {}".format(e))

# Verifica se precisa enviar o aviso
# APENAS se existir backup configurado E produção >= threshold E backup < threshold
if DIR_BACKUP and esta_montado(DIR_BACKUP) and prod_usage >= THRESHOLD and backup_usage < THRESHOLD:
    subject = f"Aviso: Gestao de HD Requerida - {UNIT_NAME}"
    send_email(subject)
else:
    if not DIR_BACKUP:
        print("Backup nao configurado. Nenhum aviso sera enviado.")
    elif not esta_montado(DIR_BACKUP):
        print("Backup configurado mas nao esta montado. Nenhum aviso sera enviado.")
    else:
        print("Uso dos HDs dentro dos limites. Producao: {}% | Backup: {}%".format(prod_usage, backup_usage))