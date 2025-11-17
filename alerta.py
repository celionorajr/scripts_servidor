#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
from dotenv import load_dotenv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import psutil
import logging
from datetime import datetime

load_dotenv("/root/.env")

# Variáveis do .env
unidade = os.getenv("UNIDADE")
caminho_hd_principal = os.getenv("HD_PRINCIPAL")
caminho_hd_backup = os.getenv("HD_BACKUP")

remetente = os.getenv("EMAIL_REMETENTE")
senha = os.getenv("EMAIL_SENHA")
smtp_host = os.getenv("EMAIL_SMTP_HOST")
smtp_port = int(os.getenv("EMAIL_SMTP_PORT"))
destinatarios = os.getenv("EMAIL_DESTINATARIOS_2").split(",")

limite_uso_hd_principal = int(os.getenv("LIMITE_USO_HD_PRINCIPAL"))
limite_livre_backup = int(os.getenv("LIMITE_LIVRE_BACKUP_GB")) * (1024 ** 3)

# Logging (compatível com Python 3.6)
logging.basicConfig(filename='/var/log/alerta.log', level=logging.ERROR)

# Funções
def verificar_uso_hd(caminho):
    try:
        uso_hd = psutil.disk_usage(caminho)
        return uso_hd.percent, uso_hd.total, uso_hd.used, uso_hd.free
    except Exception as e:
        logging.error("Erro ao verificar uso do HD {}: {}".format(caminho, e))
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

    # Corpo do email atualizado
    corpo = f"""
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alerta Polos - Servidor PACS {unidade}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            color: #333;
            background-color: #f9f9f9;
            margin: 0;
            padding: 0;
        }}
        .container {{
            width: 580px;
            margin: 20px auto;
            background-color: #fff;
            border: 1px solid #ddd;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.08);
            overflow: hidden;
        }}
        .header {{
            width: 100%;
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
        .content p {{
            font-size: 16px;
            margin-bottom: 15px;
            line-height: 1.5;
        }}
        .alert-title {{
            background-color: #7cfcef;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 20px;
            border-left: 5px solid #04546c;
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
        .important {{
            font-weight: bold;
            color: #04546c;
            font-size: 18px;
        }}
        .footer {{
            background: linear-gradient(to right, #04546c, #029687);
            color: white;
            text-align: center;
            padding: 20px;
        }}
        .footer p {{
            margin: 5px 0;
        }}
        .whatsapp-button {{
            display: inline-block;
            background-color: #25D366;
            color: white;
            padding: 12px 24px;
            border-radius: 50px;
            text-decoration: none;
            font-weight: bold;
            margin: 15px 0;
            transition: all 0.3s;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}
        .whatsapp-button:hover {{
            background-color: #128C7E;
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.3);
        }}
        .signature {{
            margin-top: 5px;
            text-align: center;
            color: #04ecd4;
            font-size: 14px;
        }}
        .info-box {{
            background-color: #f2f9f9;
            border-left: 5px solid #029687;
            padding: 15px 20px;
            margin: 20px 0;
            border-radius: 6px;
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
            .content p {{
                font-size: 14px;
            }}
            .whatsapp-button {{
                padding: 10px 18px;
                font-size: 14px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://i.imgur.com/M4fVy4y.png" alt="Polos Tecnologia" class="logo">
            <h2 style="margin: 0; font-size: 22px;">⚠️ Alerta de Armazenamento</h2>
            <p style="margin: 5px 0 0;">Servidor PACS - {unidade}</p>
        </div>

        <div class="content">
            <div class="alert-title">
                <p style="margin: 0; font-size: 16px;">
                    <strong>Este e um alerta automatico do servidor PACS {unidade}</strong>
                </p>
            </div>

            <p>Atencao! O uso do HD principal esta em <span class="important">{uso_principal}%</span> e esta acima do limite de {limite_uso_hd_principal}%!</p>

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
                        <td>HD Principal</td>
                        <td>{tamanho_total_principal / (1024 ** 3):.2f} GB</td>
                        <td>{tamanho_usado_principal / (1024 ** 3):.2f} GB</td>
                        <td>{tamanho_livre_principal / (1024 ** 3):.2f} GB</td>
                        <td>{uso_principal}%</td>
                    </tr>
                    <tr>
                        <td>HD de Backup</td>
                        <td>{tamanho_total_backup / (1024 ** 3):.2f} GB</td>
                        <td>{tamanho_usado_backup / (1024 ** 3):.2f} GB</td>
                        <td>{tamanho_livre_backup / (1024 ** 3):.2f} GB</td>
                        <td>{uso_backup}%</td>
                    </tr>
                </tbody>
            </table>

            <div class="info-box">
                <p style="margin: 0; font-size: 16px;">
                    <strong>⚠️ Situacao do Backup:</strong><br>
                    {f"O backup possui {tamanho_livre_backup / (1024 ** 3):.2f} GB livres" if caminho_hd_backup else "Backup nao configurado"}
                    {f", abaixo do limite de seguranca de {limite_livre_backup / (1024 ** 3):.0f} GB" if caminho_hd_backup and tamanho_livre_backup < limite_livre_backup else ""}
                </p>
            </div>

            <p class="important">Por favor, entre em contato com a equipe da Polos o mais rapido possivel.</p>
            <p><strong>Recomendamos considerar a expansao do armazenamento com um HD de 6TB.</strong></p>
        </div>

        <div class="footer">
            <a href="https://wa.me/559833024038?text=Ola,%20gostaria%20de%20falar%20sobre%20o%20alerta%20do%20HD%20do%20servidor%20PACS%20{unidade}%20que%20esta%20com%20{uso_principal}%25%20de%20uso." class="whatsapp-button" target="_blank">
                📱 Entrar em contato pelo WhatsApp
            </a>
            <p>© {datetime.now().year} Polos Tecnologia - Todos os direitos reservados</p>
            <div class="signature">
                Desenvolvido por Celio Nora Junior - Analista de Suporte Tecnico
            </div>
        </div>
    </div>
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
        logging.error("Falha ao enviar o email: {}".format(e))
        print("Falha ao enviar o email: {}".format(e))
else:
    print("Condicoes para envio de alerta nao foram atendidas.")
    print("HD Principal: {}% | Backup livre: {:.2f} GB".format(uso_principal, tamanho_livre_backup / (1024 ** 3)))