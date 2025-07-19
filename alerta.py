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
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Alerta Polos - Servidor PACS {unidade}</title>
</head>
<body style="font-family: Arial, sans-serif; background-color: #f9f9f9; margin: 0; padding: 0;">
    <div style="max-width: 600px; margin: 20px auto; background-color: #fff; border: 1px solid #ccc; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1);">
        
        <div style="background-image: url('https://i.imgur.com/oGNaMki.jpeg'); background-size: cover; background-position: center; height: 150px; border-radius: 10px 10px 0 0;">
        </div>
        
        <div style="padding: 20px;">
            <p><strong>Este é um alerta automático do servidor PACS {unidade}</strong></p>
            <p>Atenção! O uso do HD principal está em <span style="font-weight: bold; color: #d9534f; font-size: 18px;">{uso_principal}%</span> e está acima do limite de {limite_uso_hd_principal}%!</p>
            
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <thead>
                    <tr>
                        <th style="border: 1px solid #ddd; padding: 10px; background-color: #f8f9fa;">Disco</th>
                        <th style="border: 1px solid #ddd; padding: 10px; background-color: #f8f9fa;">Tamanho Total</th>
                        <th style="border: 1px solid #ddd; padding: 10px; background-color: #f8f9fa;">Espaço Usado</th>
                        <th style="border: 1px solid #ddd; padding: 10px; background-color: #f8f9fa;">Espaço Livre</th>
                        <th style="border: 1px solid #ddd; padding: 10px; background-color: #f8f9fa;">Uso (%)</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 10px;">HD Principal</td>
                        <td style="border: 1px solid #ddd; padding: 10px;">{tamanho_total_principal / (1024 ** 3):.2f} GB</td>
                        <td style="border: 1px solid #ddd; padding: 10px;">{tamanho_usado_principal / (1024 ** 3):.2f} GB</td>
                        <td style="border: 1px solid #ddd; padding: 10px;">{tamanho_livre_principal / (1024 ** 3):.2f} GB</td>
                        <td style="border: 1px solid #ddd; padding: 10px;">{uso_principal}%</td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 10px;">HD de Backup</td>
                        <td style="border: 1px solid #ddd; padding: 10px;">{tamanho_total_backup / (1024 ** 3):.2f} GB</td>
                        <td style="border: 1px solid #ddd; padding: 10px;">{tamanho_usado_backup / (1024 ** 3):.2f} GB</td>
                        <td style="border: 1px solid #ddd; padding: 10px;">{tamanho_livre_backup / (1024 ** 3):.2f} GB</td>
                        <td style="border: 1px solid #ddd; padding: 10px;">{uso_backup}%</td>
                    </tr>
                </tbody>
            </table>

            <p style="font-weight: bold; color: #d9534f; font-size: 16px;">Por favor, entre em contato com a equipe da Polos o mais rápido possível.</p>
            <p><strong>Recomendamos considerar a expansão do armazenamento com um HD de 6TB.</strong></p>
        </div>

        <div style="background-color: #f1f1f1; text-align: center; padding: 20px; border-top: 1px solid #ccc; border-radius: 0 0 10px 10px;">
            <p>Atenciosamente,</p>
            <p><strong>Suporte Polos</strong></p>
            <p><a href="https://wa.me/9833024038" target="_blank" style="color: #0275d8; text-decoration: none;">Entre em contato pelo WhatsApp</a></p>
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
        logging.error(f"Falha ao enviar o email: {e}")
        print(f"Falha ao enviar o email: {e}")
else:
    print("Condições para envio de alerta não foram atendidas.")