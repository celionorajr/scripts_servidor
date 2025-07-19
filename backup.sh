#!/bin/bash
set -a
source /root/.env
set +a

ANO=$(date +%Y)
MES=$(date +%m)
if [ ${MES:0:1} == "0" ]; then MES=${MES:1}; fi

DIR_ORIGEM="$HD_PRINCIPAL/$ANO/$MES"
DIR_DESTINO="$HD_BACKUP/$ANO"
LOG_DIR="/home/polos/backup_logs"
LOG_FILE="$LOG_DIR/rsync_backup_${ANO}-${MES}.log"

mkdir -p "$LOG_DIR"
echo "Iniciando backup: $(date)" >> "$LOG_FILE"

if [ ! -d "$DIR_ORIGEM" ]; then
    echo "Origem não encontrada: $DIR_ORIGEM" >> "$LOG_FILE"
    exit 1
fi

if [ ! -d "$DIR_DESTINO" ]; then
    echo "Destino não encontrado: $DIR_DESTINO" >> "$LOG_FILE"
    exit 1
fi

sudo rsync -havPuz --partial "$DIR_ORIGEM" "$DIR_DESTINO" &>> "$LOG_FILE"

if [ $? -eq 0 ]; then
    echo "Backup concluído com sucesso: $(date)" >> "$LOG_FILE"
else
    echo "Erro no backup: $(date)" >> "$LOG_FILE"
fi