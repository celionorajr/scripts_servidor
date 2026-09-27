#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Avisa por e-mail quando o servidor PACS é reiniciado."""

import fcntl
import logging
import smtplib
import ssl
import sys
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

ENV_FILE = "/root/.env"
LOG_FILE = "/root/monitorar.log"


def load_env_file(path):
    values = {}
    try:
        with open(path, "r") as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    except (IOError, OSError) as error:
        raise RuntimeError("Não foi possível ler {}: {}".format(path, error))
    return values


def required(values, name):
    value = values.get(name, "").strip()
    if not value:
        raise RuntimeError("Variável obrigatória ausente: {}".format(name))
    return value


def configure_logging():
    try:
        logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    except (IOError, OSError):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def load_settings():
    values = load_env_file(ENV_FILE)
    try:
        port = int(required(values, "EMAIL_SMTP_PORT"))
        interval = int(required(values, "TEMPO_MINIMO_ENVIO"))
    except ValueError:
        raise RuntimeError("EMAIL_SMTP_PORT e TEMPO_MINIMO_ENVIO devem ser números inteiros")
    recipients = [item.strip() for item in required(values, "EMAIL_DESTINATARIOS_2").split(",") if item.strip()]
    if not recipients:
        raise RuntimeError("EMAIL_DESTINATARIOS_2 não possui destinatários válidos")
    return {
        "host": required(values, "EMAIL_SMTP_HOST"), "port": port,
        "sender": required(values, "EMAIL_REMETENTE"), "password": required(values, "EMAIL_SENHA"),
        "recipients": recipients, "unit": required(values, "UNIDADE"),
        "control": values.get("CONTROLE_ARQUIVO", "/root/ultimo_envio.txt").strip() or "/root/ultimo_envio.txt",
        "interval": interval, "lock": values.get("LOCK_FILE", "/tmp/monitor_lock").strip() or "/tmp/monitor_lock",
    }


def build_email_html(unit, data_hora):
    return """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f3f6f8;font-family:Arial,Helvetica,sans-serif;color:#1f2937;"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f3f6f8;"><tr><td align="center" style="padding:20px 12px;"><table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:600px;background:#ffffff;border:1px solid #dbe4ea;border-radius:12px;overflow:hidden;">
<tr><td align="center" style="padding:18px 16px;background:#04546c;color:#ffffff;"><img src="https://i.imgur.com/M4fVy4y.png" alt="Polos Tecnologia" width="80" style="display:block;width:80px;max-width:100%;height:auto;border:0;margin:0 auto 10px;"><div style="font-size:11px;letter-spacing:0.7px;text-transform:uppercase;font-weight:bold;">Monitoramento do servidor</div><div style="font-size:20px;line-height:25px;font-weight:bold;margin-top:5px;">Servidor PACS — {unit}</div></td></tr>
<tr><td style="padding:24px;"><div style="border-left:4px solid #029687;background:#f0fdfa;padding:16px;margin-bottom:20px;"><div style="font-size:18px;line-height:25px;font-weight:bold;color:#04546c;">Aviso de reinicialização</div><div style="font-size:15px;line-height:22px;margin-top:6px;">O servidor PACS foi reiniciado. Este é um aviso automático para conferência da operação após o reboot.</div></div><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border:1px solid #dbe4ea;border-radius:8px;margin-bottom:20px;"><tr><td style="padding:16px;background:#f8fafc;font-size:16px;font-weight:bold;color:#17324d;">Data e hora do reinício</td></tr><tr><td style="padding:16px;"><div style="font-size:23px;line-height:29px;font-weight:bold;color:#04546c;">{time}</div></td></tr></table><div style="border-left:4px solid #d99a00;background:#fff8e7;padding:16px;margin-bottom:20px;font-size:15px;line-height:22px;"><strong style="color:#8a5a00;">Ação recomendada</strong><br>Confirme que os serviços essenciais voltaram a operar normalmente após a reinicialização.</div><div style="font-size:16px;font-weight:bold;color:#17324d;margin:0 0 10px;">Checklist de conferência</div><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border:1px solid #dbe4ea;border-radius:8px;background:#ffffff;font-size:15px;line-height:23px;"><tr><td style="padding:16px;"><span style="color:#029687;font-weight:bold;">•</span> Serviço PACS em execução<br><span style="color:#029687;font-weight:bold;">•</span> Banco de dados operacional<br><span style="color:#029687;font-weight:bold;">•</span> Conexões de rede estabelecidas<br><span style="color:#029687;font-weight:bold;">•</span> Storage montado e acessível<br><span style="color:#029687;font-weight:bold;">•</span> Aplicações auxiliares funcionando</td></tr></table></td></tr>
<tr><td style="padding:18px 24px;background:#04546c;color:#dbeafe;font-size:12px;line-height:18px;">Desenvolvido por Celio Nora Junior — Analista de Suporte Técnico<br>Monitoramento automático · © {year} Polos Tecnologia</td></tr></table></td></tr></table></body></html>""".format(unit=unit, time=data_hora, year=datetime.now().year)


def was_sent_recently(settings):
    try:
        with open(settings["control"], "r") as control_file:
            return (time.time() - float(control_file.read().strip())) < settings["interval"]
    except (IOError, OSError, ValueError):
        return False


def send_email(settings):
    message = MIMEMultipart("alternative")
    message["Subject"] = "Aviso: Servidor Reiniciado - {}".format(settings["unit"])
    message["From"] = settings["sender"]
    message["To"] = ", ".join(settings["recipients"])
    data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
    message.attach(MIMEText(build_email_html(settings["unit"], data_hora), "html", "utf-8"))
    context = ssl.create_default_context()
    with smtplib.SMTP(settings["host"], settings["port"], timeout=30) as server:
        server.starttls(context=context)
        server.login(settings["sender"], settings["password"])
        server.sendmail(settings["sender"], settings["recipients"], message.as_string())
    with open(settings["control"], "w") as control_file:
        control_file.write(str(time.time()))


def main():
    configure_logging()
    try:
        settings = load_settings()
        lock_file = open(settings["lock"], "w")
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            print("Monitoramento já está em execução.")
            return 0
        try:
            if was_sent_recently(settings):
                print("Já foi enviado recentemente; nenhum novo aviso será enviado.")
                return 0
            send_email(settings)
            logging.info("Aviso de reinicialização enviado para %s", settings["unit"])
            print("Email de reinicialização enviado com sucesso.")
            return 0
        finally:
            lock_file.close()
    except Exception as error:
        logging.exception("Falha no monitoramento de reinicialização: %s", error)
        print("Erro: {}".format(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
