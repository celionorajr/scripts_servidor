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
PYTHON_PIP_PACKAGES=("psutil")

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

msg_info "Configurando SSH para usar porta ${SSH_PORT} ${EMOJI_SSH}..."
sudo sed -i "s/#Port 22/Port $SSH_PORT/" /etc/ssh/sshd_config
sudo systemctl restart sshd
msg_success "Serviço SSH reiniciado."

msg_success "🎉 CONFIGURAÇÃO CONCLUÍDA! Seu servidor está pronto! 🎉"
