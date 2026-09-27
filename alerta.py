#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Envia alerta crítico quando o armazenamento do PACS exige atenção imediata."""

import logging
import json
import os
import smtplib
import ssl
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import psutil
from dotenv import load_dotenv


ENV_FILE = "/root/.env"
LOG_FILE = "/var/log/alerta.log"


class ConfigurationError(Exception):
    """Indica uma configuração ausente ou inválida."""


class StorageError(Exception):
    """Indica que não foi possível consultar um armazenamento."""


class DiskUsage(object):
    def __init__(self, percent, total, used, free):
        self.percent = percent
        self.total = total
        self.used = used
        self.free = free


class Settings(object):
    def __init__(
        self,
        unit_name,
        principal_path,
        backup_path,
        sender,
        password,
        smtp_host,
        smtp_port,
        recipients,
        principal_limit,
        backup_limit,
        backup_status_file,
    ):
        self.unit_name = unit_name
        self.principal_path = principal_path
        self.backup_path = backup_path
        self.sender = sender
        self.password = password
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.recipients = recipients
        self.principal_limit = principal_limit
        self.backup_limit = backup_limit
        self.backup_status_file = backup_status_file


def configure_logging():
    try:
        logging.basicConfig(
            filename=LOG_FILE,
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
    except (IOError, OSError):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        logging.warning("Não foi possível escrever em %s; usando saída padrão.", LOG_FILE)


def required_env(name):
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ConfigurationError("Variável obrigatória ausente: {}".format(name))
    return value.strip()


def read_limit(name):
    raw_value = required_env(name)
    try:
        value = int(raw_value)
    except ValueError:
        raise ConfigurationError("{} deve ser um número inteiro".format(name))
    if not 0 <= value <= 100:
        raise ConfigurationError("{} deve estar entre 0 e 100".format(name))
    return value


def load_settings():
    load_dotenv(ENV_FILE)
    recipients = [item.strip() for item in required_env("EMAIL_DESTINATARIOS_2").split(",") if item.strip()]
    if not recipients:
        raise ConfigurationError("EMAIL_DESTINATARIOS_2 não possui destinatários válidos")
    try:
        smtp_port = int(required_env("EMAIL_SMTP_PORT"))
    except ValueError:
        raise ConfigurationError("EMAIL_SMTP_PORT deve ser um número inteiro")
    return Settings(
        unit_name=required_env("UNIDADE"),
        principal_path=required_env("HD_PRINCIPAL"),
        backup_path=(os.getenv("HD_BACKUP") or "").strip(),
        sender=required_env("EMAIL_REMETENTE"),
        password=required_env("EMAIL_SENHA"),
        smtp_host=required_env("EMAIL_SMTP_HOST"),
        smtp_port=smtp_port,
        recipients=recipients,
        principal_limit=read_limit("LIMITE_USO_HD_PRINCIPAL"),
        backup_limit=read_limit("LIMITE_USO_HD_BACKUP"),
        backup_status_file=(os.getenv("BACKUP_STATUS_FILE") or "/root/ultimo_backup_sucesso.json").strip(),
    )


def is_mounted(path):
    try:
        return any(part.mountpoint == path for part in psutil.disk_partitions(all=True))
    except Exception as error:
        raise StorageError("Não foi possível verificar a montagem de {}: {}".format(path, error))


def get_disk_usage(path):
    try:
        usage = psutil.disk_usage(path)
        return DiskUsage(usage.percent, usage.total, usage.used, usage.free)
    except Exception as error:
        raise StorageError("Não foi possível consultar {}: {}".format(path, error))


def format_size(value):
    if value >= 1024 ** 4:
        return "{:.2f} TB".format(value / float(1024 ** 4))
    return "{:.2f} GB".format(value / float(1024 ** 3))


def get_last_backup_status(path):
    if not os.path.exists(path):
        return "missing", None
    try:
        with open(path, "r") as status_file:
            status = json.load(status_file)
    except (IOError, OSError, ValueError) as error:
        logging.error("Não foi possível ler o status do último backup: %s", error)
        return "invalid", None

    if not isinstance(status, dict):
        logging.error("Status do último backup inválido em %s", path)
        return "invalid", None
    completed_at = status.get("completed_at")
    if status.get("status") != "success" or not completed_at:
        logging.error("Status do último backup inválido em %s", path)
        return "invalid", None
    return "success", completed_at


def build_email_html(settings, principal, backup_state, backup_usage, reason, last_backup_status):
    if backup_state == "not_configured":
        backup_message = "HD de backup não configurado."
        backup_details = "Não há armazenamento de backup definido no arquivo de configuração."
    elif backup_state == "unmounted":
        backup_message = "HD de backup configurado, porém não está montado ou disponível no servidor."
        backup_details = "O ponto de montagem configurado é: <strong>{}</strong>.".format(settings.backup_path)
    elif backup_state == "error":
        backup_message = "Não foi possível consultar o HD de backup."
        backup_details = "O armazenamento de backup deve ser verificado no servidor."
    else:
        backup_message = "HD de backup acima do limite configurado ({}%).".format(settings.backup_limit)
        backup_details = "O backup também atingiu o limite de segurança."

    status_kind, completed_at = last_backup_status
    if status_kind == "success":
        backup_status_card = """<div style="border-left:4px solid #029687;background:#f0fdfa;padding:15px;margin-bottom:20px;font-size:15px;line-height:22px;"><strong style="color:#04546c;">Status do último backup automático</strong><br>Último backup concluído com sucesso em <strong>{}</strong>.</div>""".format(completed_at)
    elif status_kind == "missing":
        backup_status_card = """<div style="border-left:4px solid #d99a00;background:#fff8e7;padding:15px;margin-bottom:20px;font-size:15px;line-height:22px;"><strong style="color:#8a5a00;">Status do último backup automático</strong><br>Não há registro de backup automático concluído com sucesso.</div>"""
    else:
        backup_status_card = """<div style="border-left:4px solid #d99a00;background:#fff8e7;padding:15px;margin-bottom:20px;font-size:15px;line-height:22px;"><strong style="color:#8a5a00;">Status do último backup automático</strong><br>Não foi possível consultar o registro do último backup.</div>"""

    return """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f3f6f8;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f3f6f8;"><tr><td align="center" style="padding:20px 12px;">
    <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:600px;background:#ffffff;border:1px solid #dbe4ea;border-radius:12px;overflow:hidden;">
      <tr><td align="center" style="padding:18px 16px;background:#9b1c1c;color:#ffffff;"><img src="https://i.imgur.com/M4fVy4y.png" alt="Polos Tecnologia" width="80" style="display:block;width:80px;max-width:100%;height:auto;border:0;margin:0 auto 10px;"><div style="font-size:11px;letter-spacing:0.7px;text-transform:uppercase;font-weight:bold;">Alerta crítico de armazenamento</div><div style="font-size:20px;line-height:25px;font-weight:bold;margin-top:5px;">Servidor PACS — {unit}</div></td></tr>
      <tr><td style="padding:24px;">
        <div style="border-left:4px solid #b42318;background:#fef3f2;padding:16px;margin-bottom:22px;"><div style="font-size:18px;line-height:25px;font-weight:bold;color:#8a1c16;">Ação imediata necessária</div><div style="font-size:15px;line-height:22px;margin-top:6px;">{reason}</div></div>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border:1px solid #dbe4ea;border-radius:8px;margin-bottom:20px;"><tr><td style="padding:16px;background:#f8fafc;font-size:16px;font-weight:bold;color:#17324d;">HD principal</td></tr><tr><td style="padding:16px;"><div style="font-size:34px;line-height:38px;font-weight:bold;color:#b42318;">{percent}% usado</div><div style="font-size:14px;color:#5b6773;margin-top:5px;">Limite configurado: {limit}%</div><div style="font-size:15px;line-height:24px;margin-top:14px;">Total: <strong>{total}</strong><br>Utilizado: <strong>{used}</strong><br>Livre: <strong>{free}</strong></div></td></tr></table>
        <div style="font-size:16px;font-weight:bold;color:#17324d;margin:0 0 10px;">Situação do backup</div><div style="border-left:4px solid #b42318;background:#fff8f7;padding:15px;margin-bottom:20px;font-size:15px;line-height:22px;"><strong>{backup_message}</strong><br>{backup_details}</div>
        {backup_status_card}
        <p style="font-size:15px;line-height:22px;margin:22px 0 0;">Verifique o armazenamento e contate a equipe responsável para evitar indisponibilidade do PACS.</p>
      </td></tr><tr><td style="padding:18px 24px;background:#17324d;color:#dbeafe;font-size:12px;line-height:18px;">Mensagem automática do monitoramento do servidor PACS · © {year} Polos Tecnologia</td></tr>
    </table>
  </td></tr></table>
</body></html>""".format(unit=settings.unit_name, reason=reason, percent=principal.percent, limit=settings.principal_limit, total=format_size(principal.total), used=format_size(principal.used), free=format_size(principal.free), backup_message=backup_message, backup_details=backup_details, backup_status_card=backup_status_card, year=datetime.now().year)


def send_email(settings, html):
    message = MIMEMultipart("alternative")
    message["From"] = settings.sender
    message["To"] = ", ".join(settings.recipients)
    message["Subject"] = "ALERTA CRÍTICO: armazenamento do PACS {}".format(settings.unit_name)
    message.attach(MIMEText(html, "html", "utf-8"))
    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        server.starttls(context=context)
        server.login(settings.sender, settings.password)
        server.sendmail(settings.sender, settings.recipients, message.as_string())


def main():
    configure_logging()
    try:
        settings = load_settings()
        if not is_mounted(settings.principal_path):
            raise StorageError("HD principal não está montado: {}".format(settings.principal_path))
        principal = get_disk_usage(settings.principal_path)
    except (ConfigurationError, StorageError) as error:
        logging.error("Não foi possível avaliar o alerta: %s", error)
        print("Erro: {}".format(error), file=sys.stderr)
        return 1
    if principal.percent < settings.principal_limit:
        logging.info("Nenhum alerta: HD principal em %s%% (limite %s%%).", principal.percent, settings.principal_limit)
        print("HD principal dentro do limite: {}%".format(principal.percent))
        return 0

    backup_usage = None
    if not settings.backup_path:
        backup_state = "not_configured"
        reason = "O HD principal atingiu o limite e não há HD de backup configurado."
    else:
        try:
            mounted = is_mounted(settings.backup_path)
        except StorageError as error:
            backup_state = "error"
            reason = "O HD principal atingiu o limite e ocorreu erro ao verificar o HD de backup."
            logging.error("Falha ao verificar o backup: %s", error)
        else:
            if not mounted:
                backup_state = "unmounted"
                reason = "O HD principal atingiu o limite e o HD de backup não está disponível no servidor."
            else:
                try:
                    backup_usage = get_disk_usage(settings.backup_path)
                except StorageError as error:
                    backup_state = "error"
                    reason = "O HD principal atingiu o limite e ocorreu erro ao consultar o HD de backup."
                    logging.error("Falha ao consultar o backup: %s", error)
                else:
                    if backup_usage.percent < settings.backup_limit:
                        logging.info("Sem alerta crítico: backup disponível em %s%%.", backup_usage.percent)
                        print("Backup disponível; o aviso preventivo é responsabilidade do verifica_hd.py.")
                        return 0
                    backup_state = "full"
                    reason = "O HD principal e o HD de backup atingiram os limites configurados."
    try:
        last_backup_status = get_last_backup_status(settings.backup_status_file)
        send_email(settings, build_email_html(settings, principal, backup_state, backup_usage, reason, last_backup_status))
    except Exception as error:
        logging.exception("Falha ao enviar alerta crítico: %s", error)
        print("Falha ao enviar alerta crítico: {}".format(error), file=sys.stderr)
        return 1
    logging.warning("Alerta crítico enviado: %s", reason)
    print("Alerta crítico enviado com sucesso.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
