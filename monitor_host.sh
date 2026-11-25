#!/bin/bash
# Monitoramento do HOST Proxmox - Picos Imagem / TI
# SOMENTE LEITURA: nao altera VMs, discos nem configuracoes.
# Uso (no Shell do no, pelo painel do Proxmox):
#   bash monitor_host.sh [horas] [intervalo_segundos]
#   ex.: nohup bash monitor_host.sh 10 30 >/dev/null 2>&1 &
# Saida em /root/monitor_<host>_<data>/ : snapshot.txt, host.csv, discos.csv, vms.csv, ping.csv

HORAS=${1:-10}
INT=${2:-30}
ALVOS="172.16.255.1 172.16.255.185 172.16.255.183 172.16.255.254"
D="/root/monitor_$(hostname)_$(date +%Y%m%d_%H%M)"
mkdir -p "$D"
FIM=$(( $(date +%s) + $(awk "BEGIN{printf \"%d\", $HORAS*3600}") ))

# ------------------------------------------------------------------ foto inicial
{
  echo "=== $(date)  host: $(hostname)"
  echo; echo "=== versao";        pveversion 2>/dev/null
  echo; echo "=== uptime";        uptime
  echo; echo "=== CPU";           lscpu | grep -E 'Model name|^CPU\(s\)|Socket|Thread'
  echo; echo "=== memoria";       free -h
  echo; echo "=== discos (df)";   df -hT | grep -vE 'tmpfs|udev'
  echo; echo "=== armazenamentos Proxmox"; pvesm status 2>/dev/null
  echo; echo "=== ZFS pools";     zpool list 2>/dev/null
  echo; echo "=== ZFS saude";     zpool status 2>/dev/null
  echo; echo "=== ZFS ARC (cache em RAM)"; grep -E '^(size|c_max|c_min) ' /proc/spl/kstat/zfs/arcstats 2>/dev/null
  echo; echo "=== LVM";           vgs 2>/dev/null; lvs -a 2>/dev/null
  echo; echo "=== RAID software"; cat /proc/mdstat 2>/dev/null
  echo; echo "=== discos fisicos"; lsblk -d -o NAME,MODEL,SIZE,ROTA,TYPE 2>/dev/null
  for d in /dev/sd? /dev/nvme?n1; do
    [ -e "$d" ] || continue
    echo; echo "--- SMART $d"
    smartctl -H -A "$d" 2>/dev/null | grep -Ei 'overall|result|Reallocated|Pending|Uncorrect|Wear|Percentage Used|Media_Wearout|Temperature|Power_On_Hours|CRC'
  done
  echo; echo "=== VMs";           qm list 2>/dev/null
  for id in $(qm list 2>/dev/null | awk 'NR>1{print $1}'); do
    echo; echo "--- VM $id"
    qm config "$id" 2>/dev/null | grep -E '^(name|memory|balloon|cores|sockets|cpu|scsihw|scsi[0-9]|virtio[0-9]|sata[0-9]|ide[0-9]|net[0-9]):'
  done
  echo; echo "=== erros recentes do kernel (disco, I/O, travamentos)"
  dmesg -T 2>/dev/null | grep -Ei 'error|fail|timeout|reset|blocked for more|hung|I/O|abort|degrad' | tail -80
} > "$D/snapshot.txt" 2>&1

# ------------------------------------------------------------------ cabecalhos
echo "DataHora;Load1;CPU_uso_%;CPU_iowait_%;RAM_disponivel_MB;Swap_usado_MB" > "$D/host.csv"
echo "DataHora;Disco;Leituras_s;Gravacoes_s;Leitura_ms;Gravacao_ms;Ocupado_%" > "$D/discos.csv"
echo "DataHora;VMID;Nome;CPU_%;RAM_MB" > "$D/vms.csv"
echo "DataHora;Alvo;Ping_ms" > "$D/ping.csv"

DISKRE='^(sd[a-z]+|nvme[0-9]+n[0-9]+|vd[a-z]+)$'
declare -A NOME
for id in $(qm list 2>/dev/null | awk 'NR>1{print $1}'); do
  NOME[$id]=$(qm config "$id" 2>/dev/null | awk -F': ' '/^name:/{print $2}')
done

cpu_snap()  { awk '/^cpu /{print $2+$3+$4+$5+$6+$7+$8+$9, $6}' /proc/stat; }   # total iowait
disk_snap() { awk -v re="$DISKRE" '$3 ~ re {print $3, $4, $7, $8, $11, $13}' /proc/diskstats; }

read T1 W1 < <(cpu_snap); I1=$(awk '/^cpu /{print $5}' /proc/stat)
disk_snap > "$D/.d1"; S1=$(date +%s.%N)

echo "Monitorando ate $(date -d @$FIM). Arquivos em $D"

while [ "$(date +%s)" -lt "$FIM" ]; do
  sleep "$INT"
  TS=$(date '+%d/%m/%Y %H:%M:%S')
  S2=$(date +%s.%N)
  DT=$(awk "BEGIN{print $S2-$S1}")

  # CPU e memoria
  read T2 W2 < <(cpu_snap); I2=$(awk '/^cpu /{print $5}' /proc/stat)
  awk -v t1="$T1" -v t2="$T2" -v w1="$W1" -v w2="$W2" -v i1="$I1" -v i2="$I2" -v ts="$TS" \
      -v l="$(cut -d' ' -f1 /proc/loadavg)" \
      -v ma="$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)" \
      -v su="$(awk '/SwapTotal/{t=$2}/SwapFree/{f=$2}END{print int((t-f)/1024)}' /proc/meminfo)" \
      'BEGIN{dt=t2-t1; if(dt<=0)dt=1; printf "%s;%s;%.0f;%.1f;%s;%s\n", ts, l, 100*(1-(i2-i1)/dt), 100*(w2-w1)/dt, ma, su}' \
      | tr '.' ',' >> "$D/host.csv"
  T1=$T2; W1=$W2; I1=$I2

  # discos fisicos: latencia media por operacao e % ocupado
  disk_snap > "$D/.d2"
  awk -v ts="$TS" -v dt="$DT" 'NR==FNR{r[$1]=$2; rm[$1]=$3; w[$1]=$4; wm[$1]=$5; io[$1]=$6; next}
       ($1 in r){dr=$2-r[$1]; dw=$4-w[$1];
         printf "%s;%s;%.1f;%.1f;%.1f;%.1f;%.0f\n", ts, $1, dr/dt, dw/dt,
           (dr>0?($3-rm[$1])/dr:0), (dw>0?($5-wm[$1])/dw:0), 100*($6-io[$1])/(dt*1000)}' \
       "$D/.d1" "$D/.d2" | tr '.' ',' >> "$D/discos.csv"
  mv "$D/.d2" "$D/.d1"; S1=$S2

  # CPU e RAM por VM (uso atual, medido em 1 s)
  for pf in /var/run/qemu-server/*.pid; do
    [ -e "$pf" ] || continue
    id=$(basename "$pf" .pid); pid=$(cat "$pf")
    top -b -n2 -d1 -p "$pid" 2>/dev/null | awk -v ts="$TS" -v id="$id" -v nm="${NOME[$id]}" \
      '/^ *[0-9]+ /{c=$9; m=$6} END{gsub(",", ".", c); if (m ~ /g$/) m=m*1024; else if (m ~ /m$/) m=m+0; else m=m/1024;
        printf "%s;%s;%s;%.0f;%.0f\n", ts, id, nm, c, m}' | tr '.' ',' >> "$D/vms.csv" &
  done
  wait

  # ping a partir do host
  for a in $ALVOS; do
    v=$(ping -c 2 -W 1 -q "$a" 2>/dev/null | awk -F'/' '/^rtt/{print $6}')
    echo "$TS;$a;${v:-PERDA}" | tr '.' ',' | sed "s/;$(echo "$a" | tr '.' ',');/;$a;/" >> "$D/ping.csv"
  done
done

rm -f "$D/.d1"
echo "Fim: $(date)" >> "$D/snapshot.txt"
echo "Concluido. Arquivos em $D"
