#!/bin/bash
# Transfere meses PACS para destino rsync sobre SSH.
# Nao usa --delete: nunca remove arquivos da origem ou do destino.
# Em falha de rede, repete o rsync ate a conexao voltar.

set -u
set -o pipefail

# Ajuste por variaveis de ambiente quando necessario:
# ANO=2026 MESES="4 5 6" /root/transferir_nuvem_recuperavel.sh
ANO="${ANO:-2026}"
MESES="${MESES:-4 5 6 7 8 9 10}"
ORIGEM_BASE="${ORIGEM_BASE:-/mnt/storage02/$ANO}"
REMOTE_USER_HOST="${REMOTE_USER_HOST:-polosbackup@177.66.114.35}"
SSH_PORT="${SSH_PORT:-45222}"
SSH_IDENTITY_FILE="${SSH_IDENTITY_FILE:-/root/.ssh/id_ed25519_polosbackup}"
DESTINO_REMOTO="${DESTINO_REMOTO:-/srv/polos/dados/storage02/$ANO}"
LOG_DIR="${LOG_DIR:-/home/polos/backup_logs}"
RETRY_SECONDS="${RETRY_SECONDS:-60}"
LOCK_FILE="${LOCK_FILE:-/tmp/transferir_nuvem_recuperavel.lock}"

numero_positivo() {
    case "$1" in
        ''|*[!0-9]*) return 1 ;;
        *) [ "$1" -gt 0 ] ;;
    esac
}

registrar() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

if [ "$(id -u)" -ne 0 ]; then
    echo "Execute como root." >&2
    exit 1
fi

for VALOR in "$ANO" "$SSH_PORT" "$RETRY_SECONDS"; do
    if ! numero_positivo "$VALOR"; then
        echo "ANO, SSH_PORT e RETRY_SECONDS devem ser inteiros positivos." >&2
        exit 2
    fi
done

if [ ! -r "$SSH_IDENTITY_FILE" ]; then
    echo "Chave SSH inexistente ou sem leitura: $SSH_IDENTITY_FILE" >&2
    exit 2
fi

if ! command -v rsync >/dev/null 2>&1 || ! command -v flock >/dev/null 2>&1; then
    echo "rsync e flock devem estar instalados." >&2
    exit 1
fi

mkdir -p "$LOG_DIR" || exit 1
LOG_FILE="$LOG_DIR/backup_nuvem_$ANO_meses_$(printf '%s' "$MESES" | tr ' ' '-')_$(date +%F_%H-%M-%S).log"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    registrar "Outra transferencia recuperavel ja esta em execucao. Nenhuma nova copia foi iniciada."
    exit 0
fi

ORIGENS=()
for MES in $MESES; do
    ORIGEM="$ORIGEM_BASE/$MES"
    if [ ! -d "$ORIGEM" ]; then
        registrar "ERRO: origem inexistente: $ORIGEM"
        exit 2
    fi
    ORIGENS+=("$ORIGEM")
done

if ! ssh \
    -i "$SSH_IDENTITY_FILE" \
    -o IdentitiesOnly=yes \
    -o BatchMode=yes \
    -o ConnectTimeout=15 \
    -p "$SSH_PORT" \
    "$REMOTE_USER_HOST" \
    "test -d '$DESTINO_REMOTO' && test -w '$DESTINO_REMOTO'"; then
    registrar "Aviso: destino remoto indisponivel no inicio. O rsync tentara novamente ate recuperar."
fi

registrar "Transferencia iniciada. Origem: $ORIGEM_BASE | Meses: $MESES | Destino: $REMOTE_USER_HOST:$DESTINO_REMOTO"
registrar "Sem --delete: arquivos existentes nunca serao removidos."

trap 'registrar "Transferencia interrompida manualmente."; exit 130' INT TERM

TENTATIVA=0
while true; do
    TENTATIVA=$((TENTATIVA + 1))
    registrar "Iniciando rsync, tentativa $TENTATIVA."

    if rsync \
        -avhP \
        --partial \
        --no-owner \
        --no-group \
        --no-perms \
        --stats \
        --log-file="$LOG_FILE" \
        -e "ssh -i $SSH_IDENTITY_FILE -o IdentitiesOnly=yes -o BatchMode=yes -p $SSH_PORT -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=3" \
        "${ORIGENS[@]}" \
        "$REMOTE_USER_HOST:$DESTINO_REMOTO/"; then
        registrar "Transferencia concluida com sucesso na tentativa $TENTATIVA."
        exit 0
    else
        STATUS=$?
    fi

    registrar "Falha do rsync (codigo $STATUS). Nenhum arquivo foi removido; nova tentativa em $RETRY_SECONDS segundos."
    sleep "$RETRY_SECONDS"
done
