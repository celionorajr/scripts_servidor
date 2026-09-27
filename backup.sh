#!/bin/bash

# Backup mensal do PACS. As configurações ficam em /root/.env.

ENV_FILE="${ENV_FILE:-/root/.env}"
if [ ! -r "$ENV_FILE" ]; then
    echo "Arquivo de configuração não encontrado ou sem leitura: $ENV_FILE" >&2
    exit 1
fi

read_env_value() {
    local key="$1"
    local value
    value=$(sed -n "s/^${key}=//p" "$ENV_FILE" | tail -n 1)
    value=${value%$'\r'}
    case "$value" in
        \"*\") value=${value#\"}; value=${value%\"} ;;
        \'*\') value=${value#\'}; value=${value%\'} ;;
    esac
    printf '%s' "$value"
}

HD_PRINCIPAL=$(read_env_value "HD_PRINCIPAL")
HD_BACKUP=$(read_env_value "HD_BACKUP")
BACKUP_LOG_DIR=$(read_env_value "BACKUP_LOG_DIR")
BACKUP_LOCK_FILE=$(read_env_value "BACKUP_LOCK_FILE")
BACKUP_STATUS_FILE=$(read_env_value "BACKUP_STATUS_FILE")

if [ -z "${HD_PRINCIPAL:-}" ] || [ -z "${HD_BACKUP:-}" ]; then
    echo "HD_PRINCIPAL e HD_BACKUP devem estar configurados em $ENV_FILE" >&2
    exit 1
fi

ANO=$(date +%Y)
MES=$(date +%m)
MES=${MES#0}

DIR_ORIGEM="$HD_PRINCIPAL/$ANO/$MES"
DIR_DESTINO="$HD_BACKUP/$ANO"
LOG_DIR="${BACKUP_LOG_DIR:-/home/polos/backup_logs}"
LOG_FILE="$LOG_DIR/rsync_backup_${ANO}-${MES}.log"
LOCK_FILE="${BACKUP_LOCK_FILE:-/tmp/backup_pacs.lock}"
STATUS_FILE="${BACKUP_STATUS_FILE:-/root/ultimo_backup_sucesso.json}"

mkdir -p "$LOG_DIR" || {
    echo "Não foi possível criar o diretório de logs: $LOG_DIR" >&2
    exit 1
}

if ! command -v flock >/dev/null 2>&1; then
    echo "O comando flock é necessário para evitar backups concorrentes." >> "$LOG_FILE"
    exit 1
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "Backup já está em execução; nova execução ignorada: $(date)" >> "$LOG_FILE"
    exit 0
fi

echo "Iniciando backup: $(date)" >> "$LOG_FILE"

if ! mountpoint -q "$HD_PRINCIPAL"; then
    echo "HD principal não está montado: $HD_PRINCIPAL" >> "$LOG_FILE"
    exit 1
fi

if ! mountpoint -q "$HD_BACKUP"; then
    echo "HD de backup não está montado: $HD_BACKUP" >> "$LOG_FILE"
    exit 1
fi

if [ ! -d "$DIR_ORIGEM" ]; then
    echo "Origem não encontrada: $DIR_ORIGEM" >> "$LOG_FILE"
    exit 1
fi

if [ ! -d "$DIR_DESTINO" ]; then
    echo "Destino não encontrado: $DIR_DESTINO" >> "$LOG_FILE"
    exit 1
fi

if rsync -havPuz --partial "$DIR_ORIGEM" "$DIR_DESTINO" >> "$LOG_FILE" 2>&1; then
    STATUS_DIR=$(dirname "$STATUS_FILE")
    STATUS_TEMP_FILE="${STATUS_FILE}.tmp.$$"
    if ! mkdir -p "$STATUS_DIR" || ! (umask 077; printf '{\n  "status": "success",\n  "completed_at": "%s"\n}\n' "$(date '+%d/%m/%Y às %H:%M')" > "$STATUS_TEMP_FILE" && mv "$STATUS_TEMP_FILE" "$STATUS_FILE"); then
        rm -f "$STATUS_TEMP_FILE"
        echo "Backup concluído, mas não foi possível atualizar o status: $STATUS_FILE" >> "$LOG_FILE"
        exit 1
    fi
    echo "Backup concluído com sucesso: $(date)" >> "$LOG_FILE"
else
    echo "Erro no backup: $(date)" >> "$LOG_FILE"
    exit 1
fi
