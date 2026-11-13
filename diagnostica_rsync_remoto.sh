#!/bin/bash
# Monitora um destino rsync sobre SSH e registra falhas de conectividade.
# A autenticacao deve ser por chave SSH; senha interativa nao e suportada.

set -u
set -o pipefail

PROGRAMA=$(basename "$0")
REMOTE_USER_HOST=""
REMOTE_PATH=""
SSH_PORT=22
IDENTITY_FILE=""
DURATION_MINUTES=240
INTERVAL_SECONDS=60
MAX_FAILURES=3
CONNECT_TIMEOUT_SECONDS=15
LOG_DIR="/root/diagnostico_rsync_remoto"

uso() {
    cat <<EOF
Uso:
  $PROGRAMA --remote USUARIO@HOST --path /diretorio/remoto [opcoes]

Opcoes:
  --port N                 Porta SSH (padrao: 22).
  --identity-file ARQUIVO  Chave privada SSH a usar.
  --duration-minutes N     Duracao maxima do teste (padrao: 240).
  --interval-seconds N     Intervalo entre verificacoes (padrao: 60).
  --max-failures N         Falhas a registrar antes de encerrar (padrao: 3).
  --log-dir CAMINHO        Diretorio dos relatorios.
  -h, --help               Exibe esta ajuda.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --remote) REMOTE_USER_HOST="$2"; shift 2 ;;
        --path) REMOTE_PATH="$2"; shift 2 ;;
        --port) SSH_PORT="$2"; shift 2 ;;
        --identity-file) IDENTITY_FILE="$2"; shift 2 ;;
        --duration-minutes) DURATION_MINUTES="$2"; shift 2 ;;
        --interval-seconds) INTERVAL_SECONDS="$2"; shift 2 ;;
        --max-failures) MAX_FAILURES="$2"; shift 2 ;;
        --log-dir) LOG_DIR="$2"; shift 2 ;;
        -h|--help) uso; exit 0 ;;
        *) echo "Opcao desconhecida: $1" >&2; uso >&2; exit 2 ;;
    esac
done

numero_positivo() {
    case "$1" in
        ''|*[!0-9]*) return 1 ;;
        *) [ "$1" -gt 0 ] ;;
    esac
}

if [ "$(id -u)" -ne 0 ]; then
    echo "Execute como root." >&2
    exit 1
fi

if [ -z "$REMOTE_USER_HOST" ] || [ -z "$REMOTE_PATH" ]; then
    echo "Informe --remote e --path." >&2
    uso >&2
    exit 2
fi

case "$REMOTE_PATH" in
    /*) ;;
    *) echo "O caminho remoto deve ser absoluto." >&2; exit 2 ;;
esac

for VALOR in "$SSH_PORT" "$DURATION_MINUTES" "$INTERVAL_SECONDS" "$MAX_FAILURES"; do
    if ! numero_positivo "$VALOR"; then
        echo "Porta, duracao, intervalo e numero de falhas devem ser inteiros positivos." >&2
        exit 2
    fi
done

if ! command -v timeout >/dev/null 2>&1; then
    echo "O comando timeout e necessario." >&2
    exit 1
fi

if [ -n "$IDENTITY_FILE" ] && [ ! -r "$IDENTITY_FILE" ]; then
    echo "Chave SSH inexistente ou sem leitura: $IDENTITY_FILE" >&2
    exit 2
fi

REMOTE_HOST=$(printf '%s' "$REMOTE_USER_HOST" | sed 's/^[^@]*@//')
if [ "$REMOTE_HOST" = "$REMOTE_USER_HOST" ]; then
    echo "Use --remote no formato usuario@host." >&2
    exit 2
fi

mkdir -p "$LOG_DIR" || exit 1
RUN_ID=$(date '+%Y%m%d_%H%M%S')
LOG_FILE="$LOG_DIR/relatorio_$RUN_ID.log"
SAIDA_REMOTA="$LOG_DIR/saida_remota_$RUN_ID.tmp"
LOCK_FILE="/tmp/$PROGRAMA.lock"
REMOTE_TEST_FILE=".diagnostico_$RUN_ID.$$"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "Ja existe um diagnostico em execucao: $LOCK_FILE" >&2
    exit 1
fi

registrar() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

registrar_bloco() {
    {
        printf '\n===== %s =====\n' "$1"
        shift
        "$@"
        printf '[codigo de saida: %s]\n' "$?"
    } >> "$LOG_FILE" 2>&1
}

teste_remoto() {
    SSH_IDENTITY_ARGS=()
    if [ -n "$IDENTITY_FILE" ]; then
        SSH_IDENTITY_ARGS=(-i "$IDENTITY_FILE" -o IdentitiesOnly=yes)
    fi

    timeout "$((CONNECT_TIMEOUT_SECONDS + 20))" \
        ssh \
            -p "$SSH_PORT" \
            "${SSH_IDENTITY_ARGS[@]}" \
            -o BatchMode=yes \
            -o ConnectTimeout="$CONNECT_TIMEOUT_SECONDS" \
            -o ConnectionAttempts=1 \
            -o ServerAliveInterval=15 \
            -o ServerAliveCountMax=3 \
            "$REMOTE_USER_HOST" \
            bash -s -- "$REMOTE_PATH" "$REMOTE_TEST_FILE" <<'REMOTE'
set -u
remote_path="$1"
test_name="$2"
test_file="$remote_path/$test_name"

test -d "$remote_path"
test -r "$remote_path"
test -w "$remote_path"
touch "$test_file"
rm -f "$test_file"

printf 'HOSTNAME=%s\n' "$(hostname)"
printf 'UTC=%s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
df -h "$remote_path"
REMOTE
}

coletar_contexto_local() {
    registrar "Coletando contexto local da falha."
    registrar_bloco "rota para remoto" ip route get "$REMOTE_HOST"
    registrar_bloco "interfaces" ip -br link
    registrar_bloco "enderecos" ip -br address
    registrar_bloco "ping remoto" ping -c 3 -W 2 "$REMOTE_HOST"
    registrar_bloco "teste TCP SSH" bash -c "exec 3<>/dev/tcp/$REMOTE_HOST/$SSH_PORT"

    if command -v journalctl >/dev/null 2>&1; then
        registrar_bloco "kernel recente" journalctl -k --since "$CONTEXTO_DESDE" --no-pager
        {
            printf '\n===== mensagens de rede recentes =====\n'
            journalctl --since "$CONTEXTO_DESDE" --no-pager 2>&1 | \
                grep -Ei 'network|route|link is down|connection timed out|connection reset|ssh|rsync' || true
        } >> "$LOG_FILE"
    fi
}

INICIO_EPOCH=$(date +%s)
FIM_EPOCH=$((INICIO_EPOCH + DURATION_MINUTES * 60))
FALHAS=0
CHECAGENS=0
RECUPERACOES=0
ESTADO_ANTERIOR="desconhecido"
CONTEXTO_DESDE=$(date '+%Y-%m-%d %H:%M:%S')

registrar "Diagnostico iniciado."
registrar "Remoto: $REMOTE_USER_HOST | Porta: $SSH_PORT | Diretorio: $REMOTE_PATH"
registrar "Duracao: $DURATION_MINUTES min | Intervalo: $INTERVAL_SECONDS s | Maximo de falhas: $MAX_FAILURES"
registrar "Relatorio: $LOG_FILE"
registrar "A autenticacao deve ocorrer por chave SSH; senha interativa nao e suportada."

while [ "$(date +%s)" -lt "$FIM_EPOCH" ] && [ "$FALHAS" -lt "$MAX_FAILURES" ]; do
    CHECAGENS=$((CHECAGENS + 1))

    if teste_remoto > "$SAIDA_REMOTA" 2>&1; then
        if [ "$ESTADO_ANTERIOR" != "ok" ]; then
            registrar "Destino remoto acessivel e com escrita confirmada."
            cat "$SAIDA_REMOTA" >> "$LOG_FILE"
        fi
        if [ "$ESTADO_ANTERIOR" = "falha" ]; then
            RECUPERACOES=$((RECUPERACOES + 1))
            registrar "Conexao recuperada sem intervencao local."
        fi
        ESTADO_ANTERIOR="ok"
    else
        FALHAS=$((FALHAS + 1))
        registrar "FALHA $FALHAS/$MAX_FAILURES ao acessar o destino remoto."
        {
            printf '\n===== saida SSH da falha =====\n'
            cat "$SAIDA_REMOTA"
        } >> "$LOG_FILE"
        coletar_contexto_local
        ESTADO_ANTERIOR="falha"
    fi

    CONTEXTO_DESDE=$(date '+%Y-%m-%d %H:%M:%S')
    sleep "$INTERVAL_SECONDS"
done

rm -f "$SAIDA_REMOTA"
registrar "Diagnostico finalizado. Checagens: $CHECAGENS | Falhas registradas: $FALHAS | Recuperacoes: $RECUPERACOES"
registrar "Relatorio final: $LOG_FILE"

if [ "$FALHAS" -gt 0 ]; then
    exit 1
fi

exit 0
