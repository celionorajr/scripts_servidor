# Pacote específico — Socorrão I

Este pacote deve ser instalado diretamente em `/root`. Ele não usa
`/home/polos`: os logs e os arquivos de controle ficam em `/root`.

O terminal fornecido identifica o servidor como **Ubuntu 16.04.7 LTS**, apesar
de a unidade ter sido descrita como Debian. Os três scripts Python deste pacote
leem o `.env` sem `python-dotenv` e não utilizam sintaxe exclusiva do Python
3.6; assim, permanecem compatíveis com o Python 3.5 padrão dessa versão.

## Arquivos e destinos

| Arquivo | Destino no servidor |
| --- | --- |
| `alerta.py` | `/root/alerta.py` |
| `verifica_hd.py` | `/root/verifica_hd.py` |
| `monitorar.py` | `/root/monitorar.py` |
| `backup.sh` | `/root/backup.sh` |
| `backup_pacsdb.sh` | `/root/backup_pacsdb.sh` |
| `.env.exemplo` | Referência para `/root/.env` |

Os caminhos configurados para a unidade são:

- Produção: `/mnt/storage3`
- Backup dos exames e do banco: `/mnt/ExamesAntigos2`
- Banco: `/mnt/ExamesAntigos2/bkp_pacsdb`
- Log do backup de exames: `/root/backup_logs/rsync_backup_AAAA-M.log`
- Log sugerido do backup do banco: `/root/backup_pacsdb.log`
- Logs Python: `/root/alerta.log`, `/root/verifica_hd.log`, `/root/monitorar.log`
- Registro do último backup dos exames: `/root/ultimo_backup_sucesso.json`

## Instalação e validação

Antes de substituir os arquivos operacionais, faça uma cópia local dos arquivos
atuais no próprio servidor. Em seguida, copie os cinco scripts para `/root`,
preserve o `/root/.env` existente e complete nele as chaves de backup que
constam no arquivo de exemplo.

```bash
cd /root
chmod 700 alerta.py verifica_hd.py monitorar.py backup.sh backup_pacsdb.sh
python3 -m py_compile alerta.py verifica_hd.py monitorar.py
bash -n backup.sh
bash -n backup_pacsdb.sh
python3 -c "import psutil; print('psutil OK')"
```

O backup do banco já foi identificado no armazenamento remoto, porém esta
instalação deve confirmar que `/mnt/ExamesAntigos2` continua montado antes de
executar qualquer rotina.

## Agendamento sugerido

Os agendamentos abaixo são apenas referência; devem ser adicionados ao
`crontab -e` do root quando a validação manual terminar.

```cron
# Backup do banco PACS, segunda-feira às 02:00
0 2 * * 1 /bin/bash /root/backup_pacsdb.sh >> /root/backup_pacsdb.log 2>&1

# Backup de exames; ajuste o horário e mantenha comentado até validar
# 0 1 * * * /bin/bash /root/backup.sh
```

Para acompanhar:

```bash
tail -f /root/backup_pacsdb.log
tail -f /root/backup_logs/rsync_backup_$(date +\%Y)-$((10#$(date +\%m))).log
cat /root/ultimo_backup_sucesso.json
```
