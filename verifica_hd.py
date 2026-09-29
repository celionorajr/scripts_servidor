#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Envia aviso preventivo quando há espaço disponível no backup do PACS."""

import logging
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
LOG_FILE = "/var/log/verifica_hd.log"


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
        principal_mount,
        backup_path,
        backup_mount,
        sender,
        password,
        smtp_host,
        smtp_port,
        recipients,
        principal_limit,
        backup_limit,
    ):
        self.unit_name = unit_name
        self.principal_path = principal_path
        self.principal_mount = principal_mount
        self.backup_path = backup_path
        self.backup_mount = backup_mount
        self.sender = sender
        self.password = password
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.recipients = recipients
        self.principal_limit = principal_limit
        self.backup_limit = backup_limit


def configure_logging():
    try:
        logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    except (IOError, OSError):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        logging.warning("Não foi possível escrever em %s; usando saída padrão.", LOG_FILE)


def required_env(name):
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ConfigurationError("Variável obrigatória ausente: {}".format(name))
    return value.strip()


def read_limit(name):
    try:
        value = int(required_env(name))
    except ValueError:
        raise ConfigurationError("{} deve ser um número inteiro".format(name))
    if not 0 <= value <= 100:
        raise ConfigurationError("{} deve estar entre 0 e 100".format(name))
    return value


def load_settings():
    load_dotenv(ENV_FILE)
    recipients = [item.strip() for item in required_env("EMAIL_DESTINATARIOS").split(",") if item.strip()]
    if not recipients:
        raise ConfigurationError("EMAIL_DESTINATARIOS não possui destinatários válidos")
    try:
        smtp_port = int(required_env("EMAIL_SMTP_PORT"))
    except ValueError:
        raise ConfigurationError("EMAIL_SMTP_PORT deve ser um número inteiro")
    return Settings(
        unit_name=required_env("UNIDADE"),
        principal_path=required_env("HD_PRINCIPAL"),
        principal_mount=(os.getenv("HD_PRINCIPAL_MOUNT") or required_env("HD_PRINCIPAL")).strip(),
        backup_path=(os.getenv("HD_BACKUP") or "").strip(),
        backup_mount=(os.getenv("HD_BACKUP_MOUNT") or os.getenv("HD_BACKUP") or "").strip(),
        sender=required_env("EMAIL_REMETENTE"),
        password=required_env("EMAIL_SENHA"),
        smtp_host=required_env("EMAIL_SMTP_HOST"),
        smtp_port=smtp_port,
        recipients=recipients,
        principal_limit=read_limit("LIMITE_USO_HD_PRINCIPAL"),
        backup_limit=read_limit("LIMITE_USO_HD_BACKUP"),
    )


def is_mounted(path):
    try:
        expected_path = os.path.normpath(path)
        return any(os.path.normpath(part.mountpoint) == expected_path for part in psutil.disk_partitions(all=True))
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


def build_email_html(settings, principal, backup):
    return """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f3f6f8;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f3f6f8;"><tr><td align="center" style="padding:20px 12px;">
    <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:600px;background:#ffffff;border:1px solid #dbe4ea;border-radius:12px;overflow:hidden;">
      <tr><td align="center" style="padding:18px 16px;background:#0f766e;color:#ffffff;"><img src="https://i.imgur.com/M4fVy4y.png" alt="Polos Tecnologia" width="80" style="display:block;width:80px;max-width:100%;height:auto;border:0;margin:0 auto 10px;"><div style="font-size:11px;letter-spacing:0.7px;text-transform:uppercase;font-weight:bold;">Aviso preventivo de armazenamento</div><div style="font-size:20px;line-height:25px;font-weight:bold;margin-top:5px;">Servidor PACS — {unit}</div></td></tr>
      <tr><td style="padding:24px;">
        <div style="border-left:4px solid #0f766e;background:#f0fdfa;padding:16px;margin-bottom:22px;"><div style="font-size:18px;line-height:25px;font-weight:bold;color:#115e59;">Gestão de espaço necessária</div><div style="font-size:15px;line-height:22px;margin-top:6px;">O armazenamento principal atingiu o limite configurado, porém existe espaço disponível no HD de backup para apoiar a gestão ou migração dos dados.</div></div>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border:1px solid #dbe4ea;border-radius:8px;margin-bottom:20px;"><tr><td style="padding:16px;background:#f8fafc;font-size:16px;font-weight:bold;color:#17324d;">HD principal</td></tr><tr><td style="padding:16px;"><div style="font-size:34px;line-height:38px;font-weight:bold;color:#b45309;">{principal_percent}% usado</div><div style="font-size:14px;color:#5b6773;margin-top:5px;">Limite configurado: {principal_limit}%</div><div style="font-size:15px;line-height:24px;margin-top:14px;">Total: <strong>{principal_total}</strong><br>Utilizado: <strong>{principal_used}</strong><br>Livre: <strong>{principal_free}</strong></div></td></tr></table>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border:1px solid #dbe4ea;border-radius:8px;margin-bottom:20px;"><tr><td style="padding:16px;background:#f8fafc;font-size:16px;font-weight:bold;color:#17324d;">HD de backup disponível</td></tr><tr><td style="padding:16px;"><div style="font-size:34px;line-height:38px;font-weight:bold;color:#0f766e;">{backup_percent}% usado</div><div style="font-size:14px;color:#5b6773;margin-top:5px;">Limite configurado: {backup_limit}%</div><div style="font-size:15px;line-height:24px;margin-top:14px;">Total: <strong>{backup_total}</strong><br>Utilizado: <strong>{backup_used}</strong><br>Livre: <strong>{backup_free}</strong></div></td></tr></table>
        <p style="font-size:15px;line-height:22px;margin:22px 0 0;">Planeje a gestão do espaço para preservar a operação normal do servidor PACS.</p>
      </td></tr><tr><td style="padding:18px 24px;background:#17324d;color:#dbeafe;font-size:12px;line-height:18px;">Mensagem automática do monitoramento do servidor PACS · © {year} Polos Tecnologia</td></tr>
    </table>
  </td></tr></table>
</body></html>""".format(unit=settings.unit_name, principal_percent=principal.percent, principal_limit=settings.principal_limit, principal_total=format_size(principal.total), principal_used=format_size(principal.used), principal_free=format_size(principal.free), backup_percent=backup.percent, backup_limit=settings.backup_limit, backup_total=format_size(backup.total), backup_used=format_size(backup.used), backup_free=format_size(backup.free), year=datetime.now().year)


def send_email(settings, html):
    message = MIMEMultipart("alternative")
    message["From"] = settings.sender
    message["To"] = ", ".join(settings.recipients)
    message["Subject"] = "Aviso preventivo: gestão de HD requerida - {}".format(settings.unit_name)
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
        if not is_mounted(settings.principal_mount):
            raise StorageError("Ponto de montagem do HD principal não está disponível: {}".format(settings.principal_mount))
        principal = get_disk_usage(settings.principal_path)
    except (ConfigurationError, StorageError) as error:
        logging.error("Não foi possível avaliar o aviso preventivo: %s", error)
        print("Erro: {}".format(error), file=sys.stderr)
        return 1
    if principal.percent < settings.principal_limit:
        logging.info("Nenhum aviso: HD principal em %s%% (limite %s%%).", principal.percent, settings.principal_limit)
        print("HD principal dentro do limite: {}%".format(principal.percent))
        return 0
    if not settings.backup_path:
        logging.info("Sem aviso preventivo: backup não configurado; alerta.py deve tratar o cenário crítico.")
        print("Backup não configurado; nenhum aviso preventivo será enviado.")
        return 0
    try:
        if not is_mounted(settings.backup_mount):
            logging.warning("Sem aviso preventivo: backup não montado em %s.", settings.backup_path)
            print("Backup configurado, mas não montado; nenhum aviso preventivo será enviado.")
            return 0
        backup = get_disk_usage(settings.backup_path)
    except StorageError as error:
        logging.error("Sem aviso preventivo: erro ao consultar backup: %s", error)
        print("Erro ao consultar backup; nenhum aviso preventivo será enviado.", file=sys.stderr)
        return 1
    if backup.percent >= settings.backup_limit:
        logging.info("Sem aviso preventivo: backup em %s%% (limite %s%%).", backup.percent, settings.backup_limit)
        print("Backup atingiu o limite; o cenário crítico é responsabilidade do alerta.py.")
        return 0
    try:
        send_email(settings, build_email_html(settings, principal, backup))
    except Exception as error:
        logging.exception("Falha ao enviar aviso preventivo: %s", error)
        print("Falha ao enviar aviso preventivo: {}".format(error), file=sys.stderr)
        return 1
    logging.warning("Aviso preventivo enviado: principal %s%%, backup %s%%.", principal.percent, backup.percent)
    print("Aviso preventivo enviado com sucesso.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
