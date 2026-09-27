#!/bin/bash

# ==== CONFIGURAÇÕES ====
ENV_FILE="${ENV_FILE:-/root/.env}"
if [ ! -r "$ENV_FILE" ]; then
    echo "[ERRO] Arquivo de configuração não encontrado ou sem leitura: ${ENV_FILE}"
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

# Valores padrão preservam o comportamento anterior quando as variáveis ainda
# não foram adicionadas ao .env.
DB_NAME="$(read_env_value "PACSDB_NAME")"
DB_NAME="${DB_NAME:-pacsdb}"
LOCAL_DIR="$(read_env_value "PACSDB_LOCAL_DIR")"
LOCAL_DIR="${LOCAL_DIR:-/tmp}"
REMOTE_MOUNT="$(read_env_value "PACSDB_BACKUP_MOUNT")"
REMOTE_MOUNT="${REMOTE_MOUNT:-/mnt/storage40T}"
REMOTE_SUBDIR="$(read_env_value "PACSDB_BACKUP_SUBDIR")"
REMOTE_SUBDIR="${REMOTE_SUBDIR:-bkp_pacsdb}"
REMOTE_DIR="${REMOTE_MOUNT}/${REMOTE_SUBDIR}"
RETENTION_DAYS="$(read_env_value "PACSDB_RETENTION_DAYS")"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
DATA=$(date +%Y%m%d_%H%M)
ARQUIVO="pacsdb_${DATA}.sql.gz"
LOCAL_ARQ="${LOCAL_DIR}/${ARQUIVO}"
REMOTE_ARQ="${REMOTE_DIR}/${ARQUIVO}"

# ==== CONFIGURAÇÃO DE PERMISSÕES E AMBIENTE ====
# Mudar para diretório com permissões adequadas
cd /tmp

# ==== VERIFICAÇÕES INICIAIS ====
echo "[INFO] Iniciando backup do banco ${DB_NAME} em $(date)..."

# Verificar se o ponto de montagem está ativo
if ! mountpoint -q "${REMOTE_MOUNT}"; then
    echo "[ERRO] Ponto de montagem não está montado: ${REMOTE_MOUNT}"
    exit 1
fi

# Verificar se a pasta de backup existe, se não, criar
if [ ! -d "${REMOTE_DIR}" ]; then
    echo "[INFO] Criando diretório de backup: ${REMOTE_DIR}"
    mkdir -p "${REMOTE_DIR}"
    if [ $? -ne 0 ]; then
        echo "[ERRO] Falha ao criar diretório: ${REMOTE_DIR}"
        exit 1
    fi
fi

# Verificar permissões de escrita no diretório remoto
if [ ! -w "${REMOTE_DIR}" ]; then
    echo "[ERRO] Sem permissão de escrita em: ${REMOTE_DIR}"
    exit 1
fi

# Verificar espaço em disco no diretório temporário
AVAILABLE_SPACE_KB=$(df "${LOCAL_DIR}" | awk 'NR==2 {print $4}')
if [ "${AVAILABLE_SPACE_KB}" -lt 1048576 ]; then  # Menos de 1GB
    echo "[ERRO] Espaço insuficiente em ${LOCAL_DIR}. Disponível: ${AVAILABLE_SPACE_KB}KB"
    exit 1
fi

# Verificar espaço em disco no ponto de montagem
AVAILABLE_SPACE_REMOTE_KB=$(df "${REMOTE_MOUNT}" | awk 'NR==2 {print $4}')
if [ "${AVAILABLE_SPACE_REMOTE_KB}" -lt 1048576 ]; then  # Menos de 1GB
    echo "[ERRO] Espaço insuficiente em ${REMOTE_MOUNT}. Disponível: ${AVAILABLE_SPACE_REMOTE_KB}KB"
    exit 1
fi

# ==== BACKUP LOCAL ====
echo "[INFO] Criando backup do banco ${DB_NAME}..."
sudo -u postgres pg_dump "${DB_NAME}" | gzip > "${LOCAL_ARQ}"

# Verifica se o backup foi criado com sucesso
if [ $? -eq 0 ] && [ -s "${LOCAL_ARQ}" ]; then
    BACKUP_SIZE=$(du -h "${LOCAL_ARQ}" | cut -f1)
    echo "[OK] Backup local criado: ${LOCAL_ARQ} (Tamanho: ${BACKUP_SIZE})"
else
    echo "[ERRO] Falha ao gerar backup local ou arquivo vazio. Abortando."
    # Limpar arquivo corrompido se existir
    [ -f "${LOCAL_ARQ}" ] && rm -f "${LOCAL_ARQ}"
    exit 1
fi

# ==== MOVER PARA O DIRETÓRIO REMOTO ====
echo "[INFO] Movendo backup para diretório remoto..."
if mv "${LOCAL_ARQ}" "${REMOTE_ARQ}"; then
    echo "[OK] Backup movido para: ${REMOTE_ARQ}"
else
    echo "[ERRO] Falha ao mover o arquivo para ${REMOTE_DIR}"
    # Manter backup local em caso de falha
    echo "[INFO] Backup local mantido em: ${LOCAL_ARQ}"
    exit 1
fi

# ==== LIMPEZA DE BACKUPS ANTIGOS (MAIS DE 7 DIAS) ====
echo "[INFO] Iniciando limpeza de backups antigos (mais de ${RETENTION_DAYS} dias)..."

# Listar arquivos que serão removidos (para logging)
OLD_BACKUPS_COUNT=$(find "${REMOTE_DIR}" -type f -name "pacsdb_*.sql.gz" -mtime +${RETENTION_DAYS} | wc -l)
OLD_BACKUPS=$(find "${REMOTE_DIR}" -type f -name "pacsdb_*.sql.gz" -mtime +${RETENTION_DAYS})

if [ "${OLD_BACKUPS_COUNT}" -gt 0 ]; then
    echo "[INFO] ${OLD_BACKUPS_COUNT} backup(s) antigo(s) será(ão) removido(s):"
    echo "${OLD_BACKUPS}"

    # Remover backups antigos
    find "${REMOTE_DIR}" -type f -name "pacsdb_*.sql.gz" -mtime +${RETENTION_DAYS} -exec rm -f {} \;

    if [ $? -eq 0 ]; then
        echo "[OK] Limpeza de backups antigos concluída com sucesso"
    else
        echo "[ERRO] Falha durante a limpeza de backups antigos"
    fi
else
    echo "[INFO] Nenhum backup antigo para remover"
fi

# ==== VERIFICAÇÃO FINAL ====
# Listar backups atuais
echo "[INFO] Backups atuais em ${REMOTE_DIR}:"
CURRENT_BACKUPS_COUNT=$(find "${REMOTE_DIR}" -type f -name "pacsdb_*.sql.gz" | wc -l)
if [ "${CURRENT_BACKUPS_COUNT}" -gt 0 ]; then
    find "${REMOTE_DIR}" -type f -name "pacsdb_*.sql.gz" -exec ls -lh {} \; | sort -k6,7
    echo "[INFO] Total de backups: ${CURRENT_BACKUPS_COUNT}"
else
    echo "[INFO] Nenhum backup encontrado no diretório"
fi

echo "[INFO] Backup do banco ${DB_NAME} finalizado com sucesso em $(date)."
