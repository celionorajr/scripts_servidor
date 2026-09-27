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
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'Aviso: Servidor Reiniciado - {UNIDADE}'
    msg['From'] = EMAIL_USER
    msg['To'] = ', '.join(DESTINATARIOS)

    current_year = datetime.now().year
    data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")

    html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f3f6f8;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f3f6f8;"><tr><td align="center" style="padding:20px 12px;">
    <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:600px;background:#ffffff;border:1px solid #dbe4ea;border-radius:12px;overflow:hidden;">
      <tr><td align="center" style="padding:18px 16px;background:#04546c;color:#ffffff;"><img src="https://i.imgur.com/M4fVy4y.png" alt="Polos Tecnologia" width="80" style="display:block;width:80px;max-width:100%;height:auto;border:0;margin:0 auto 10px;"><div style="font-size:11px;letter-spacing:0.7px;text-transform:uppercase;font-weight:bold;">Monitoramento do servidor</div><div style="font-size:20px;line-height:25px;font-weight:bold;margin-top:5px;">Servidor PACS — {UNIDADE}</div></td></tr>
      <tr><td style="padding:24px;">
        <div style="border-left:4px solid #029687;background:#f0fdfa;padding:16px;margin-bottom:20px;"><div style="font-size:18px;line-height:25px;font-weight:bold;color:#04546c;">Aviso de reinicialização</div><div style="font-size:15px;line-height:22px;margin-top:6px;">O servidor PACS foi reiniciado. Este é um aviso automático para conferência da operação após o reboot.</div></div>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border:1px solid #dbe4ea;border-radius:8px;margin-bottom:20px;"><tr><td style="padding:16px;background:#f8fafc;font-size:16px;font-weight:bold;color:#17324d;">Data e hora do reinício</td></tr><tr><td style="padding:16px;"><div style="font-size:23px;line-height:29px;font-weight:bold;color:#04546c;">{data_hora}</div></td></tr></table>
        <div style="border-left:4px solid #d99a00;background:#fff8e7;padding:16px;margin-bottom:20px;font-size:15px;line-height:22px;"><strong style="color:#8a5a00;">Ação recomendada</strong><br>Confirme que os serviços essenciais voltaram a operar normalmente após a reinicialização.</div>
        <div style="font-size:16px;font-weight:bold;color:#17324d;margin:0 0 10px;">Checklist de conferência</div>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border:1px solid #dbe4ea;border-radius:8px;background:#ffffff;font-size:15px;line-height:23px;"><tr><td style="padding:16px;"><span style="color:#029687;font-weight:bold;">•</span> Serviço PACS em execução<br><span style="color:#029687;font-weight:bold;">•</span> Banco de dados operacional<br><span style="color:#029687;font-weight:bold;">•</span> Conexões de rede estabelecidas<br><span style="color:#029687;font-weight:bold;">•</span> Storage montado e acessível<br><span style="color:#029687;font-weight:bold;">•</span> Aplicações auxiliares funcionando</td></tr></table>
        <p style="font-size:14px;line-height:21px;color:#5b6773;margin:20px 0 0;">Caso o reinício não tenha sido planejado, investigue a causa conforme o procedimento da unidade.</p>
      </td></tr>
      <tr><td style="padding:18px 24px;background:#04546c;color:#dbeafe;font-size:12px;line-height:18px;">Desenvolvido por Celio Nora Junior — Analista de Suporte Técnico<br>Monitoramento automático · © {current_year} Polos Tecnologia</td></tr>
    </table>
  </td></tr></table>
</body></html>"""
    msg.attach(MIMEText(html, 'html', 'utf-8'))

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
