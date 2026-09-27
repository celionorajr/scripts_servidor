#!/bin/bash

#--------------------------------------------------------
# SCRIPT DE CONFIGURAÇÃO INICIAL DE SERVIDOR UBUNTU
# DESENVOLVIDO POR CÉLIO
#--------------------------------------------------------

# ------- CONFIGURAÇÕES VARIÁVEIS ---------

LOCALE="pt_BR.UTF-8"
TIMEZONE="America/Sao_Paulo"
SSH_PORT=2070
PACKAGES=("bridge-utils" "ifenslave" "net-tools" "python3-pip")
PYTHON_PIP_PACKAGES=("psutil" "matplotlib")
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_TO_INSTALL=("alerta.py" "verifica_hd.py" "monitorar.py" "backup.sh" "backup_pacsdb.sh")

# ------- CORES E EMOJIS ---------
RED="\e[31m"
GREEN="\e[32m"
YELLOW="\e[33m"
CYAN="\e[36m"
BOLD="\e[1m"
RESET="\e[0m"

EMOJI_CHECK="✅"
EMOJI_INFO="ℹ️"
EMOJI_WARN="⚠️"
EMOJI_SSH="🔐"
EMOJI_TIME="⏰"
EMOJI_PACK="📦"
EMOJI_GLOBE="🌐"

# ------- FUNÇÕES DE MENSAGEM ---------

function msg_info {
    echo -e "${CYAN}${EMOJI_INFO} $1${RESET}"
    sleep 2
}

function msg_success {
    echo -e "${GREEN}${EMOJI_CHECK} $1${RESET}"
    sleep 1
}

function msg_warn {
    echo -e "${YELLOW}${EMOJI_WARN} $1${RESET}"
    sleep 2
}

function msg_title {
    clear
    echo -e "${BOLD}${CYAN}"
    echo "==========================================="
    echo "    INICIANDO CONFIGURAÇÃO DO SERVIDOR     "
    echo "==========================================="
    echo -e "${RESET}"
}

# ------- INÍCIO DO SCRIPT ---------

msg_title

msg_info "Atualizando lista de pacotes..."
sudo apt update -y && msg_success "Lista de pacotes atualizada."

msg_info "Atualizando pacotes instalados..."
sudo apt upgrade -y && msg_success "Pacotes atualizados com sucesso."

msg_info "Instalando pacotes essenciais ${EMOJI_PACK}..."
sudo apt install -y "${PACKAGES[@]}" && msg_success "Pacotes essenciais instalados."

msg_info "Configurando localidade para ${LOCALE} ${EMOJI_GLOBE}..."
sudo locale-gen "$LOCALE"
sudo localectl set-locale LANG="$LOCALE"
sudo update-locale LANG="$LOCALE" LC_ALL="$LOCALE" LANGUAGE="pt_BR:pt:en"
msg_success "Localidade configurada."

msg_info "Configurando fuso horário para ${TIMEZONE} ${EMOJI_TIME}..."
sudo timedatectl set-timezone "$TIMEZONE"
msg_success "Fuso horário definido."

msg_info "Configurando servidores NTP no systemd-timesyncd ${EMOJI_TIME}..."
sudo sed -i 's/#NTP=/NTP=a.st1.ntp.br/' /etc/systemd/timesyncd.conf
sudo sed -i 's/#FallbackNTP=/FallbackNTP=a.ntp.br/' /etc/systemd/timesyncd.conf
sudo systemctl restart systemd-timesyncd.service
msg_success "Serviço timesyncd reiniciado."

msg_info "Exibindo data e hora atuais..."
timedatectl
sleep 5
clear

msg_info "Instalando pacotes Python via pip3..."
for pkg in "${PYTHON_PIP_PACKAGES[@]}"; do
    pip3 install "$pkg"
done
msg_success "Pacotes Python instalados."

# === INSTALAR DEPENDÊNCIA PYTHON PARA .env ===
msg_info "Instalando suporte ao carregamento de arquivos .env com python-dotenv..."
pip3 install python-dotenv && msg_success "python-dotenv instalado."

# === CRIAR ARQUIVO .env PADRÃO ===
ENV_FILE="/root/.env"
if [ ! -f "$ENV_FILE" ]; then
    msg_info "Criando arquivo .env padrão em $ENV_FILE..."

    cat <<EOF > "$ENV_FILE"
# === Identificação da Unidade ===
UNIDADE=Hospital ABC

# === Caminhos dos HDs ===
HD_PRINCIPAL=/mnt/storage0
HD_BACKUP=

# === Configurações de E-mail ===
EMAIL_REMETENTE=suporte@polos.tec.br
EMAIL_SENHA=*S1spolos#
EMAIL_SMTP_HOST=smtp.hostinger.com
EMAIL_SMTP_PORT=587
EMAIL_DESTINATARIOS=suporte@polos.tec.br,cnoraj@gmail.com
EMAIL_DESTINATARIOS_2=suporte@polos.tec.br,cnoraj@gmail.com

# === Limites para alerta ===
LIMITE_USO_HD_PRINCIPAL=80
LIMITE_USO_HD_BACKUP=80

# === Controle do monitoramento ===
CONTROLE_ARQUIVO=/root/ultimo_envio.txt
LOCK_FILE=/tmp/monitor_lock
TEMPO_MINIMO_ENVIO=300

# === Controle do backup de imagens ===
BACKUP_LOG_DIR=/home/polos/backup_logs
BACKUP_LOCK_FILE=/tmp/backup_pacs.lock

# === Backup do banco PACS ===
PACSDB_NAME=pacsdb
PACSDB_LOCAL_DIR=/tmp
PACSDB_BACKUP_MOUNT=/mnt/storage40T
PACSDB_BACKUP_SUBDIR=bkp_pacsdb
PACSDB_RETENTION_DAYS=7

EOF

    msg_success "Arquivo .env criado com valores padrão."
else
    msg_warn "Arquivo .env já existe. Nenhuma modificação feita."
fi

msg_info "⚙️  Você pode editar o arquivo /root/.env para ajustar os dados da unidade."

# === INSTALAR SCRIPTS OPERACIONAIS EM /root ===
msg_info "Copiando scripts operacionais para /root..."
for script in "${SCRIPTS_TO_INSTALL[@]}"; do
    if [ ! -f "$SCRIPT_DIR/$script" ]; then
        echo "Arquivo não encontrado para instalação: $SCRIPT_DIR/$script" >&2
        exit 1
    fi
    sudo install -m 700 "$SCRIPT_DIR/$script" "/root/$script"
done
msg_success "Scripts instalados em /root. O clone original foi preservado para futuras atualizações."

### CRIAÇÃO DOS CRONJOBS NO CRON DO ROOT

msg_info "Configurando entradas no cron (comentadas)..."

# Exporta o crontab atual para edição
crontab -l 2>/dev/null > /tmp/cron_jobs || touch /tmp/cron_jobs

# Adiciona as tarefas ao cron (comentadas)
echo "# ───── CRONJOBS AUTOMÁTICOS ─────"                                >> /tmp/cron_jobs
echo "# Alerta: Segunda e sexta as 10h"                                >> /tmp/cron_jobs
echo "# 0 10 * * 1,5 /usr/bin/python3 /root/alerta.py >> /var/log/alerta.log 2>&1" >> /tmp/cron_jobs

echo "# Verifica HD: Segunda e sexta as 9h"                            >> /tmp/cron_jobs
echo "# 0 9 * * 1,5 /usr/bin/python3 /root/verifica_hd.py >> /var/log/verifica_hd.log 2>&1" >> /tmp/cron_jobs

echo "# Backup: Diariamente a meia-noite"                             >> /tmp/cron_jobs
echo "# 0 0 * * * /root/backup.sh >> /var/log/backup.log 2>&1"        >> /tmp/cron_jobs

echo "# Monitoramento: Executa apos reboot do sistema"               >> /tmp/cron_jobs
echo "# @reboot /usr/bin/python3 /root/monitorar.py >> /var/log/monitorar.log 2>&1" >> /tmp/cron_jobs

echo "# banco de dados pacs" >> /tmp/cron_jobs
echo "# 0 2 * * 1 /bin/bash /root/backup_pacsdb.sh >> /var/log/backup_pacsdb.log 2>&1" >> /tmp/cron_jobs


# Restaura o crontab do root com as entradas comentadas
crontab /tmp/cron_jobs && rm /tmp/cron_jobs

msg_success "Entradas do cron adicionadas (comentadas). Edite com 'crontab -e' para ativar."


msg_info "Configurando SSH para usar porta ${SSH_PORT} ${EMOJI_SSH}..."
sudo sed -i "s/#Port 22/Port $SSH_PORT/" /etc/ssh/sshd_config
sudo systemctl restart sshd
msg_success "Serviço SSH reiniciado."

msg_success "🎉 CONFIGURAÇÃO CONCLUÍDA! Seu servidor está pronto! 🎉"
