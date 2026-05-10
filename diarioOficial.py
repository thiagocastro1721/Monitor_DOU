#!/usr/bin/env python3
"""
Monitor de Editais DOU - FUB 25
Versão otimizada que usa requisições HTTP e só abre navegador quando necessário

AGENDAMENTOS DE TAREFAS

Observação:
Para o meu notebook só funciona se ele estiver ligado na tomada e não desconectar, mesmo que por 1 minuto.
A tampa deve estar aberta.

DESPOIS QUE TUDO ESTIVER CONFIGURADO O COMPUTADOR DEVE SE COMPORTAR DA SEGUINTE FORMA:

1 O usuário fará o primeiro agendamento manual.
2 O computador inicia o boot na hora programada, às 8h50.
3 O script do diário oficial é executado às 9h graças à programação do crontab.
4 O script do diario oficial terá 50 minutos para executar.
5 O computador desliga às 9h50 graças à programação do crontab.
6 Antes de desligar o serviço invoca o script de agendamento e agenda para hoje ou amanhã às 08h50, dependendo da hora do desligamento.
7 O notebook ficará ligado por 1h, para que a bateria assuma caso necessário.
8 O ciclo se repete.

Faça as configurações 1 e 2 na ordem abaixo:

1 CONFIGURAÇÃO PARA EXECUTAR SCRIPT DO DOU E DESLIGAR:

Observação: Caso queira que o computador execute o script, aguarde 120 segundos e depois desligue, então descomente quase no final deste 
script as linhas abaixo dos comentários:
        #Aguarda 120 segundos (linha 651) e #Desliga o computador (linha 654). Desative o desligamento pelo cron.

Configuração do crontab para executar o script e depois desligar computador todos os dias:
O comando shutdown e a execução do script de agendamento do próximo boot necessitam de acesso root para o usuário.
A configuração abaixo fará com que não seja solicidata a senha ao usuário quando o crontab executar
o shutdown e o script de agendamento de boot.

Edite o sudoers:

sudo visudo



Adicione ao fim do arquivo visudo:

thiago ALL=(ALL) NOPASSWD: /sbin/shutdown
thiago ALL=(ALL) NOPASSWD: /usr/local/bin/agendar_boot.sh




A configuração a seguir irá executar script do diário oficial às 9h e depois iŕá desligar o computador ás 9h50.

Digite o comando abaixo para editar o arquivo de agendamento:

crontab -e



Cole no arquivo o texto a seguir:

0 9 * * * DISPLAY=:0 qterminal -e /usr/bin/python3 /home/thiago/Desktop/diarioOficial5.py
50 9 * * * sudo /sbin/shutdown -h now



2 CONFIGURAR SCRIPT DE AGENDAMENTO DE BOOT E SERVIÇO DE AGENDAMENTO:

Crie o script:

sudo nano /usr/local/bin/agendar_boot.sh



Cole no arquivo o texto a seguir:

#!/bin/bash

# Limpa qualquer agendamento anterior
echo 0 > /sys/class/rtc/rtc0/wakealarm 2>/dev/null || true
sleep 1

# ============================================
# CONFIGURAÇÃO: Defina apenas o horário UTC desejado
# ============================================
HORA_UTC=8        # Hora em UTC (0-23)
MINUTO_UTC=50      # Minuto (0-59)

# ============================================
# LÓGICA SIMPLES
# ============================================

# Pega a hora LOCAL atual do sistema (RTC) em minutos
HORA_RTC=$(date +%H)
MINUTO_RTC=$(date +%M)
RTC_MINUTOS=$(( (10#$HORA_RTC * 60) + 10#$MINUTO_RTC ))

# Converte o horário UTC desejado em minutos
UTC_MINUTOS=$(( (HORA_UTC * 60) + MINUTO_UTC ))

# REGRA SIMPLES:
# Se RTC >= UTC, então usa tomorrow
# Caso contrário, usa today
if [ $RTC_MINUTOS -ge $UTC_MINUTOS ]; then
    # Calcula a data de amanhã no horário LOCAL
    DATA=$(date -d "tomorrow" +%Y-%m-%d)
else
    # Usa hoje
    DATA=$(date -d "today" +%Y-%m-%d)
fi

# Monta o horário completo em UTC
HORARIO_BOOT_UTC="$DATA $(printf '%02d:%02d' $HORA_UTC $MINUTO_UTC) UTC"

# DEBUG
echo "=========================================="
echo "DEBUG:"
echo "  Hora LOCAL atual (RTC): $(printf '%02d:%02d' $HORA_RTC $MINUTO_RTC) = $RTC_MINUTOS minutos"
echo "  Hora UTC desejada: $(printf '%02d:%02d' $HORA_UTC $MINUTO_UTC) = $UTC_MINUTOS minutos"
echo "  Regra: $RTC_MINUTOS >= $UTC_MINUTOS? $([ $RTC_MINUTOS -ge $UTC_MINUTOS ] && echo 'SIM (usa tomorrow)' || echo 'NÃO (usa today)')"
echo "  Data calculada: $DATA"
echo "  String final: $HORARIO_BOOT_UTC"
echo "=========================================="

# Calcula o timestamp UTC
TIMESTAMP_UTC=$(date -d "$HORARIO_BOOT_UTC" +%s)

echo "  Timestamp calculado: $TIMESTAMP_UTC"
echo "  Data UTC: $(date -u -d @$TIMESTAMP_UTC '+%d/%m/%Y %H:%M:%S UTC')"
echo "  Data Local: $(date -d @$TIMESTAMP_UTC '+%d/%m/%Y %H:%M:%S %Z')"
echo ""

# Grava no RTC
echo $TIMESTAMP_UTC > /sys/class/rtc/rtc0/wakealarm 2>&1

# Verifica se gravou
sleep 1
VALOR_GRAVADO=$(cat /sys/class/rtc/rtc0/wakealarm 2>/dev/null)

if [ "$VALOR_GRAVADO" = "$TIMESTAMP_UTC" ]; then
    PROXIMA_DATA_UTC=$(date -u -d @$TIMESTAMP_UTC "+%d/%m/%Y às %H:%M:%S UTC")
    PROXIMA_DATA_LOCAL=$(date -d @$TIMESTAMP_UTC "+%d/%m/%Y às %H:%M:%S %Z")
    
    {
        echo ""
        echo "=========================================="
        echo "  ✓ PRÓXIMO BOOT AGENDADO PARA:"
        echo "    Horário UTC:   $PROXIMA_DATA_UTC"
        echo "    Horário Local: $PROXIMA_DATA_LOCAL"
        echo "=========================================="
        echo ""
    } | tee /dev/console /dev/tty1 2>/dev/null || true
    
    logger -t agendar-boot "✓ Próximo boot: $PROXIMA_DATA_UTC (Local: $PROXIMA_DATA_LOCAL)"
    
    sleep 2
    exit 0
else
    echo "✗ ERRO: Agendamento não persistiu!"
    echo "  Esperado: $TIMESTAMP_UTC"
    echo "  Gravado:  $VALOR_GRAVADO"
    logger -t agendar-boot "✗ ERRO: Agendamento não persistiu"
    exit 1
fi
# Fim do script



Crie o serviço:

sudo nano /etc/systemd/system/agendar-boot.service

Cole no arquivo o texto a seguir:

[Unit]
Description=Agenda boot RTC para o dia seguinte
DefaultDependencies=no
Before=shutdown.target
[Service]
Type=oneshot
ExecStart=/usr/local/bin/agendar_boot.sh
StandardOutput=journal+console
StandardError=journal+console
TTYPath=/dev/console
[Install]
WantedBy=halt.target poweroff.target

#Fim do serviço. Não copie esta linha nem a linha em branco acima.

Conceda permissão ao script:

sudo chmod +x /usr/local/bin/agendar_boot.sh

Recarregue e ative os serviços:

sudo systemctl daemon-reload
sudo systemctl enable agendar-boot.service

Faça o primeiro agendamento executando o script:

sudo /usr/local/bin/agendar_boot.sh

Valide o agendamento: 

Lembre-se de que a data aparecerá em horário local RTC, Relógio de Tempo Real (Real-Time Clock),
o que está tudo certo, pois para o meu notebook vale o agendamento UTC, Tempo Universal Coordenado (Coordinated Universal Time).
O script agenda em UTC. Faça testes para saber se irá funcionar na sua máquina também. :)
Se aparecer a data, então o agendamento foi feito com sucesso.
Execute o comando abaixo para validar o agendamento:

date -d @$(sudo cat /sys/class/rtc/rtc0/wakealarm) 2>/dev/null || echo "Nenhum agendamento ativo"


Quando oportuno, desligue o computador:

sudo shutdown -h now

"""

import requests
import time
import subprocess
import smtplib
import select
import sys
import json
import os
import tkinter as tk
from tkinter import filedialog
from email.message import EmailMessage
from datetime import datetime, timedelta
from pathlib import Path
import re

# ============================================================================
# RELATÓRIO DE EXECUÇÃO (acumulado ao longo do script)
# ============================================================================

_relatorio = {
    'inicio_execucao': None,     # datetime de início do script
    'buscas': [],                # lista de dicts por rodada/pessoa
    'musicas_tocadas': {},       # nome_pessoa → int (quantas vezes tocou)
    'emails_enviados': [],       # lista de dicts {nome, tipo, horario}
    'novidades_encontradas': [], # lista de nomes com novidade
}


def _relatorio_iniciar() -> None:
    """Marca o início da execução."""
    _relatorio['inicio_execucao'] = datetime.now()


def _relatorio_registrar_busca(nome: str, rodada: int, horario: datetime,
                                tem_novidade: bool, motivos: list) -> None:
    """Registra uma busca realizada."""
    _relatorio['buscas'].append({
        'nome': nome,
        'rodada': rodada,
        'horario': horario,
        'tem_novidade': tem_novidade,
        'motivos': list(motivos),
    })
    if tem_novidade and nome not in _relatorio['novidades_encontradas']:
        _relatorio['novidades_encontradas'].append(nome)


def _relatorio_registrar_musica(nome: str, repeticoes: int, caminho: str = '') -> None:
    """Registra que a música foi tocada para uma pessoa."""
    entrada = _relatorio['musicas_tocadas'].get(nome, {'vezes': 0, 'arquivo': ''})
    _relatorio['musicas_tocadas'][nome] = {
        'vezes': entrada['vezes'] + repeticoes,
        'arquivo': os.path.basename(caminho) if caminho else entrada['arquivo'],
    }



def _relatorio_registrar_email(nome: str, tipo: str) -> None:
    """Registra o envio de um e-mail. tipo: 'novidade' | 'sem_resultado' | 'erro'"""
    _relatorio['emails_enviados'].append({
        'nome': nome,
        'tipo': tipo,
        'horario': datetime.now(),
    })


def _gerar_texto_relatorio(nome_pessoa: str, caminho_musica: str = '') -> str:
    """
    Gera o bloco de texto do mini relatório para inserir nos e-mails,
    filtrando apenas os dados da pessoa indicada (privacidade).
    """
    agora = datetime.now()
    inicio = _relatorio['inicio_execucao'] or agora
    duracao = agora - inicio
    total_min = int(duracao.total_seconds() // 60)
    total_seg = int(duracao.total_seconds() % 60)

    linhas = [
        '',
        '─' * 50,
        '📊 RELATÓRIO DE EXECUÇÃO',
        '─' * 50,
        f'Início da execução  : {inicio.strftime("%d/%m/%Y às %H:%M:%S")}',
        f'Horário deste e-mail: {agora.strftime("%d/%m/%Y às %H:%M:%S")}',
        f'Duração total       : {total_min}min {total_seg}s',
    ]

    # ── Buscas realizadas — apenas desta pessoa ───────────────────────────
    buscas_pessoa = [b for b in _relatorio['buscas'] if b['nome'] == nome_pessoa]
    linhas.append(f'\nBuscas realizadas: {len(buscas_pessoa)}')

    if buscas_pessoa:
        horarios = [b['horario'].strftime('%H:%M:%S') for b in buscas_pessoa]
        linhas.append(f'Horários das buscas: {", ".join(horarios)}')
        com_novidade = [b for b in buscas_pessoa if b['tem_novidade']]
        if com_novidade:
            linhas.append(
                f'⚠️ Novidade detectada em: '
                f'{", ".join(b["horario"].strftime("%H:%M:%S") for b in com_novidade)}'
            )
            for b in com_novidade:
                for motivo in b['motivos']:
                    linhas.append(f'   • {motivo}')

    # ── Novidade ──────────────────────────────────────────────────────────
    if nome_pessoa in _relatorio['novidades_encontradas']:
        linhas.append('\n⚠️ Novidade encontrada nesta execução.')
    else:
        linhas.append('\nNenhuma novidade encontrada no período.')

    # ── Música — apenas desta pessoa ──────────────────────────────────────
    if caminho_musica:
        linhas.append(f'Música: "{os.path.basename(caminho_musica)}".')
    else:
        linhas.append('Música: não tocada.')

    # ── E-mails enviados — apenas desta pessoa ────────────────────────────
    emails_pessoa = [e for e in _relatorio['emails_enviados'] if e['nome'] == nome_pessoa]
    linhas.append(f'\nE-mails enviados para você nesta sessão: {len(emails_pessoa)}')
    for em in emails_pessoa:
        linhas.append(
            f'  [{em["horario"].strftime("%H:%M:%S")}] tipo: {em["tipo"]}'
        )

    linhas.append('─' * 50)
    return '\n'.join(linhas)


# ============================================================================
# CONTROLE DE VOLUME DO SISTEMA
# ============================================================================

def _obter_volume_sistema() -> int | None:
    """
    Obtém o volume atual do sistema via amixer (ALSA) ou pactl (PulseAudio/PipeWire).
    Retorna o volume como inteiro 0-100, ou None se não conseguir detectar.
    """
    # Tenta PulseAudio/PipeWire primeiro (pactl)
    try:
        saida = subprocess.check_output(
            ['pactl', 'get-sink-volume', '@DEFAULT_SINK@'],
            stderr=subprocess.DEVNULL, text=True
        )
        match = re.search(r'(\d+)%', saida)
        if match:
            return int(match.group(1))
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # Tenta ALSA (amixer)
    try:
        saida = subprocess.check_output(
            ['amixer', 'sget', 'Master'],
            stderr=subprocess.DEVNULL, text=True
        )
        match = re.search(r'\[(\d+)%\]', saida)
        if match:
            return int(match.group(1))
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    return None


def _definir_volume_sistema(volume: int) -> bool:
    """
    Define o volume do sistema via pactl ou amixer.
    Retorna True se conseguiu alterar, False caso contrário.
    """
    vol = max(0, min(100, volume))

    # Tenta PulseAudio/PipeWire (pactl)
    try:
        subprocess.run(
            ['pactl', 'set-sink-volume', '@DEFAULT_SINK@', f'{vol}%'],
            check=True, stderr=subprocess.DEVNULL
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # Tenta ALSA (amixer)
    try:
        subprocess.run(
            ['amixer', 'sset', 'Master', f'{vol}%'],
            check=True, stderr=subprocess.DEVNULL
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    return False


# ============================================================================
# CAMINHO DO ARQUIVO DE CONFIGURAÇÃO JSON
# ============================================================================

# O arquivo config_editais.json deve estar na mesma pasta que este script.
# Você pode alterar o caminho abaixo se preferir outra localização.
CONFIG_PATH = Path(__file__).parent / 'config_editais.json'

# Campos obrigatórios de cada pessoa no JSON
CAMPOS_PESSOA = [
    'nome_dou',
    'numero_de_editais_com_o_padrao_de_data_no_titulo',
    'numero_de_editais_encontrados_na_pesquisa_do_site',
    'edital_referencia',
    'data_referencia',
    'destinatarios',
]

# Campos obrigatórios da seção de e-mail no JSON
CAMPOS_EMAIL = ['remetente', 'senha']

# Campos obrigatórios da seção de agendamento no JSON
CAMPOS_AGENDAMENTO = ['multiplas_execucoes']

# ============================================================================
# ASSISTENTE INTERATIVO DE CONFIGURAÇÃO
# ============================================================================

def _selecionar_musica() -> str | None:
    """
    Abre uma janela de seleção de arquivo para o usuário escolher uma música.
    Retorna o caminho absoluto do arquivo selecionado, ou None se cancelar.
    """
    root = tk.Tk()
    root.withdraw()          # oculta a janela principal
    root.attributes('-topmost', True)  # garante que o diálogo aparece na frente
    caminho = filedialog.askopenfilename(
        title="Selecione a música a tocar ao encontrar novidade",
        filetypes=[
            ("Áudio", "*.mp3 *.wav *.ogg *.flac *.aac *.m4a *.wma *.opus"),
            ("Todos os arquivos", "*.*"),
        ]
    )
    root.destroy()
    return caminho if caminho else None


def _tocar_musica(caminho: str, repeticoes: int = 1, volume: int = 100) -> None:
    """
    Toca a música do 'caminho' usando ffplay (já disponível via ffmpeg).
    Repete 'repeticoes' vezes e respeita o volume de 0 a 100.
    Ajusta o volume do sistema para o valor configurado antes de tocar e
    restaura o volume original ao terminar todas as reproduções.
    Bloqueia até o fim de todas as reproduções.
    """
    if not caminho or not os.path.isfile(caminho):
        print(f"  ⚠️  Arquivo de música não encontrado: {caminho}")
        return

    # ── Salva e ajusta volume do sistema ─────────────────────────────────────
    vol_original = _obter_volume_sistema()
    vol_sistema_alterado = False

    if vol_original is not None:
        if vol_original != volume:
            print(f"  🔊 Ajustando volume do sistema: {vol_original}% → {volume}%")
            if _definir_volume_sistema(volume):
                vol_sistema_alterado = True
            else:
                print("  ⚠️  Não foi possível ajustar o volume do sistema.")
        else:
            print(f"  🔊 Volume do sistema já está em {volume}%. Nenhuma alteração necessária.")
    else:
        print("  ⚠️  Não foi possível detectar o volume atual do sistema.")

    # ── Reprodução ────────────────────────────────────────────────────────────
    # ffplay aceita volume de 0 a 100 via -volume (ajusta ganho interno do player)
    vol_ffplay = max(0, min(100, volume))
    try:
        for i in range(repeticoes):
            if repeticoes > 1:
                print(f"\n  🎵 Tocando ({i + 1}/{repeticoes}): {os.path.basename(caminho)}")
            else:
                print(f"\n  🎵 Tocando: {os.path.basename(caminho)}")
            try:
                subprocess.run(
                    ['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet',
                     '-volume', str(vol_ffplay), caminho],
                    check=True
                )
            except FileNotFoundError:
                print("  ⚠️  'ffplay' não encontrado. Instale o ffmpeg para tocar músicas.")
                return
            except subprocess.CalledProcessError as e:
                print(f"  ⚠️  Erro ao tocar a música: {e}")
                return
    finally:
        # ── Restaura volume original sempre (mesmo em caso de erro) ───────────
        if vol_sistema_alterado and vol_original is not None:
            print(f"  🔊 Restaurando volume do sistema: {volume}% → {vol_original}%")
            if not _definir_volume_sistema(vol_original):
                print(f"  ⚠️  Não foi possível restaurar o volume. Defina manualmente para {vol_original}%.")


def _ler(prompt: str, obrigatorio: bool = True) -> str:
    """Lê uma linha do terminal. Se 'obrigatorio', repete até o usuário digitar algo."""
    while True:
        valor = input(prompt).strip()
        if valor or not obrigatorio:
            return valor
        print("  ⚠️  Este campo é obrigatório. Por favor, preencha.")


def _ler_inteiro(prompt: str) -> int:
    """Lê um inteiro do terminal, repetindo até obter um valor válido."""
    while True:
        texto = input(prompt).strip()
        try:
            return int(texto)
        except ValueError:
            print("  ⚠️  Digite apenas números inteiros (ex.: 3).")


def _ler_hora_hhmm(prompt: str) -> tuple[int, int]:
    """
    Lê um horário no formato HH:MM (ex: 09:00, 9:30, 14:45).
    Retorna uma tupla (hora, minuto), ambos inteiros.
    """
    while True:
        texto = input(prompt).strip()
        partes = texto.replace('h', ':').split(':')
        try:
            if len(partes) == 2:
                hora   = int(partes[0])
                minuto = int(partes[1])
            elif len(partes) == 1:
                hora   = int(partes[0])
                minuto = 0
            else:
                raise ValueError
            if 0 <= hora <= 23 and 0 <= minuto <= 59:
                return hora, minuto
            print("  ⚠️  Hora deve ser entre 0 e 23 e minutos entre 0 e 59.")
        except ValueError:
            print("  ⚠️  Formato inválido. Use HH:MM (ex: 09:00, 14:30).")


def _ler_data(prompt: str) -> datetime:
    """Lê uma data no formato DD/MM/AAAA e devolve um objeto datetime."""
    while True:
        texto = input(prompt).strip()
        for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(texto, fmt)
            except ValueError:
                pass
        print("  ⚠️  Formato inválido. Use DD/MM/AAAA (ex.: 19/09/2025).")


def gerar_url(nome_dou: str) -> str:
    """
    Gera a URL de busca no DOU a partir do nome completo para pesquisa.
    Exemplo: 'FULANO DE TALS' ->
      https://www.in.gov.br/consulta/-/buscar/dou?q=%22FULANO+DE+TALS%22&s=todos&exactDate=all&sortType=0
    """
    from urllib.parse import quote
    nome_encoded = quote(nome_dou.upper(), safe='')
    # O DOU usa '+' para espaços dentro das aspas — substituímos %20 por +
    nome_encoded = nome_encoded.replace('%20', '+')
    return (
        f"https://www.in.gov.br/consulta/-/buscar/dou"
        f"?q=%22{nome_encoded}%22&s=todos&exactDate=all&sortType=0"
    )


def _perguntar_email(dados: dict) -> None:
    """Pede as credenciais de e-mail ao usuário e preenche dados['email']."""
    sep = "-" * 60
    print(f"\n{sep}")
    print("  CONFIGURAÇÃO DE E-MAIL")
    print(sep)
    print("  Informe os dados da conta Gmail que enviará os alertas.")
    print("  A senha deve ser uma 'Senha de App' do Google (16 caracteres).")
    print(sep)

    email = dados.setdefault('email', {})
    if not email.get('remetente'):
        email['remetente'] = _ler("  E-mail remetente : ")
    if not email.get('senha'):
        email['senha']     = _ler("  Senha de App     : ")


# ============================================================================
# ASSISTENTE DE AGENDAMENTO
# ============================================================================

def _perguntar_agendamento(dados: dict) -> None:
    """
    Pergunta ao usuário as preferências de agendamento de múltiplas execuções
    e preenche dados['agendamento'] com as respostas.

    Campos gerados:
      multiplas_execucoes      : bool
      hora_inicio              : int   (somente se multiplas_execucoes)
      hora_limite              : int   (somente se multiplas_execucoes)
      intervalo_minutos        : int   (somente se multiplas_execucoes; 30 ou 60)
      desligar_ao_encontrar    : bool  (somente se multiplas_execucoes)
      email_sem_resultado      : bool
    """
    sep = "-" * 60
    print(f"\n{sep}")
    print("  CONFIGURAÇÃO DE AGENDAMENTO DE EXECUÇÕES")
    print(sep)

    ag = dados.setdefault('agendamento', {})

    # ── 1. Múltiplas execuções? ───────────────────────────────────────────────
    if ag.get('multiplas_execucoes') is None:
        resp = input("  1. Deseja que o script pesquise mais de uma vez os nomes na mesma execução com intervalos pré-definidos? [s/N] → ").strip().lower()
        ag['multiplas_execucoes'] = resp in ('s', 'sim', 'y', 'yes')

    if ag['multiplas_execucoes']:

        # ── 2. Hora de início ─────────────────────────────────────────────────
        if ag.get('hora_inicio') is None or ag.get('minuto_inicio') is None:
            print("\n  2. Qual o horário de início das verificações?")
            print("     Use o formato HH:MM  (ex: 09:00, 03:30)")
            hora, minuto = _ler_hora_hhmm("     Horário de início: ")
            ag['hora_inicio']   = hora
            ag['minuto_inicio'] = minuto

        # ── 3. Hora limite ────────────────────────────────────────────────────
        if ag.get('hora_limite') is None or ag.get('minuto_limite') is None:
            print("\n  3. Qual o horário limite para as verificações?")
            print("     Use o formato HH:MM  (ex: 09:50, 14:00)")
            while True:
                hora, minuto = _ler_hora_hhmm("     Horário limite   : ")
                inicio_total = ag['hora_inicio'] * 60 + ag.get('minuto_inicio', 0)
                limite_total = hora * 60 + minuto
                if limite_total > inicio_total:
                    ag['hora_limite']   = hora
                    ag['minuto_limite'] = minuto
                    break
                h_i = ag['hora_inicio']
                m_i = ag.get('minuto_inicio', 0)
                print(f"  ⚠️  O horário limite ({hora:02d}:{minuto:02d}) deve ser "
                      f"posterior ao horário de início ({h_i:02d}:{m_i:02d}).")

        # ── 3b. Executar uma vez após o horário limite? ───────────────────────
        if ag.get('executar_apos_limite') is None:
            print("\n  3b. Deseja executar uma vez após o horário limite?")
            print("      (Útil quando o script atrasa e perde o intervalo final.)")
            resp = input("      [s/N] → ").strip().lower()
            ag['executar_apos_limite'] = resp in ('s', 'sim', 'y', 'yes')

        # ── 4. Intervalo ──────────────────────────────────────────────────────
        if ag.get('intervalo_minutos') is None:
            print("\n  4. Defina o intervalo entre cada verificação no formato HH:MM.")
            print("     Exemplos: 00:30 → 30 minutos | 01:00 → 1 hora | 00:15 → 15 minutos")
            while True:
                hora, minuto = _ler_hora_hhmm("     Intervalo: ")
                total = hora * 60 + minuto
                if total >= 1:
                    ag['intervalo_minutos'] = total
                    break
                print("  ⚠️  O intervalo deve ser de pelo menos 1 minuto.")

        # ── 5. Desligar ao encontrar novidade? ────────────────────────────────
        if ag.get('desligar_ao_encontrar') is None:
            print("\n  5. Ao encontrar alguma novidade, deseja enviar os e-mails de todas as")
            print("     pessoas e depois desligar o computador?")
            resp = input("     [s/N] → ").strip().lower()
            ag['desligar_ao_encontrar'] = resp in ('s', 'sim', 'y', 'yes')

        # ── 5b. Desligar ao finalizar sem novidade? ───────────────────────────
        if ag.get('desligar_ao_finalizar') is None:
            print("\n  5b. Ao finalizar todas as verificações sem encontrar novidade,")
            print("      deseja desligar o computador?")
            resp = input("      [s/N] → ").strip().lower()
            ag['desligar_ao_finalizar'] = resp in ('s', 'sim', 'y', 'yes')

    else:
        # Sem múltiplas execuções: garante que os campos opcionais não existam
        # ou fiquem como None/False para não causar erro depois
        ag.setdefault('hora_inicio', None)
        ag.setdefault('minuto_inicio', None)
        ag.setdefault('hora_limite', None)
        ag.setdefault('minuto_limite', None)
        ag.setdefault('intervalo_minutos', None)
        ag.setdefault('desligar_ao_encontrar', False)
        ag.setdefault('executar_apos_limite', False)

    # ── 6. E-mail de confirmação mesmo sem resultado? ─────────────────────────
    if ag.get('email_sem_resultado') is None:
        print("\n  6. Deseja receber um e-mail de confirmação mesmo quando não há novidade,")
        print("     ao atingir o horário limite (ou ao encerrar a única execução)?")
        resp = input("     [s/N] → ").strip().lower()
        ag['email_sem_resultado'] = resp in ('s', 'sim', 'y', 'yes')

    # ── 7. Desligar ao finalizar? (vale para ambos os modos) ──────────────────
    if ag.get('desligar_ao_finalizar') is None:
        print("\n  7. Ao finalizar todas as verificações, deseja desligar o computador")
        print("     (mesmo que nenhuma novidade tenha sido encontrada)?")
        resp = input("     [s/N] → ").strip().lower()
        ag['desligar_ao_finalizar'] = resp in ('s', 'sim', 'y', 'yes')

    # Resumo
    sep2 = "-" * 60
    print(f"\n{sep2}")
    print("  RESUMO DO AGENDAMENTO:")
    print(f"    Múltiplas execuções    : {'Sim' if ag['multiplas_execucoes'] else 'Não'}")
    if ag['multiplas_execucoes']:
        h_i = ag['hora_inicio']
        m_i = ag.get('minuto_inicio', 0)
        h_l = ag['hora_limite']
        m_l = ag.get('minuto_limite', 0)
        print(f"    Horário de início      : {h_i:02d}:{m_i:02d}")
        print(f"    Horário limite         : {h_l:02d}:{m_l:02d}")
        intv = ag['intervalo_minutos']
        print(f"    Intervalo              : {intv // 60:02d}:{intv % 60:02d} ({intv} min)")
        print(f"    Desligar ao encontrar  : {'Sim' if ag['desligar_ao_encontrar'] else 'Não'}")
        print(f"    Exec. após limite      : {'Sim' if ag.get('executar_apos_limite') else 'Não'}")
    print(f"    Desligar ao finalizar  : {'Sim' if ag.get('desligar_ao_finalizar') else 'Não'}")
    print(f"    E-mail sem novidade    : {'Sim' if ag['email_sem_resultado'] else 'Não'}")
    print(sep2)


def _busca_preliminar(nome_dou: str, url: str) -> dict | None:
    """
    Faz uma busca no DOU e retorna os dados encontrados para uso na
    configuração inicial: total de editais, número de resultados,
    edital mais recente e sua data.
    Retorna None se a busca falhar.
    """
    print(f"\n  🔍 Realizando busca preliminar no DOU para: {nome_dou}")
    print(f"     URL: {url}")
    html = capturar_html(url, max_tentativas=5)
    if not html:
        return None
    return analisar_editais_html(html, nome_dou)


def _perguntar_pessoa(nome: str, cfg: dict) -> None:
    """
    Preenche interativamente os campos ausentes/inválidos de uma pessoa.
    Pede apenas nome no DOU e coordenadas do favorito; os demais campos
    são obtidos automaticamente via busca preliminar no site do DOU.
    Modifica 'cfg' in-place.
    """
    sep = "-" * 60
    print(f"\n{sep}")
    print(f"  CONFIGURAÇÃO DA PESSOA: {nome}")
    print(sep)

    # ── Nome para pesquisa no DOU ─────────────────────────────────────────────
    if not cfg.get('nome_dou'):
        print("  Nome completo para pesquisa no DOU.")
        print("  Informe exatamente como aparece nos editais.")
        print("  Será convertido para maiúsculas automaticamente.")
        print("  Exemplo: FULANO DE TALS")
        cfg['nome_dou'] = _ler("  Nome no DOU: ").upper()
    else:
        cfg['nome_dou'] = cfg['nome_dou'].upper()
    cfg['url'] = gerar_url(cfg['nome_dou'])
    print(f"  ✓ URL gerada: {cfg['url']}")

    # ── Destinatários do e-mail para esta pessoa ─────────────────────────────
    if not cfg.get('destinatarios'):
        print("\n  E-mails destinatários para alertas desta pessoa.")
        print("  Digite um endereço por linha. Linha vazia encerra.")
        lista = []
        while True:
            addr = input(f"  Destinatário {len(lista)+1}: ").strip()
            if not addr:
                if not lista:
                    print("  ⚠️  Informe ao menos um destinatário.")
                    continue
                break
            lista.append(addr)
            print(f"  ✓ {addr} adicionado.")
        cfg['destinatarios'] = lista

    # ── Música ao encontrar novidade ──────────────────────────────────────────
    if cfg.get('musica_novidade') is None:
        print("\n  Ao encontrar alguma novidade para esta pessoa, deseja tocar uma música?")
        resp = input("  [s/N] → ").strip().lower()
        if resp in ('s', 'sim', 'y', 'yes'):
            print("  Abrindo seletor de arquivo... (uma janela pode aparecer na barra de tarefas)")
            caminho = _selecionar_musica()
            if caminho:
                cfg['musica_novidade'] = caminho
                print(f"  ✓ Música selecionada: {os.path.basename(caminho)}")

                # Quantas vezes tocar
                while True:
                    try:
                        vezes = input("  Quantas vezes deseja que a música toque? [1]: ").strip()
                        vezes = int(vezes) if vezes else 1
                        if vezes >= 1:
                            cfg['musica_repeticoes'] = vezes
                            break
                        print("  ⚠️  Digite um número maior ou igual a 1.")
                    except ValueError:
                        print("  ⚠️  Digite um número inteiro válido.")

                # Volume
                while True:
                    try:
                        vol = input("  Volume da música (0 a 100)? [100]: ").strip()
                        vol = int(vol) if vol else 100
                        if 0 <= vol <= 100:
                            cfg['musica_volume'] = vol
                            break
                        print("  ⚠️  O volume deve estar entre 0 e 100.")
                    except ValueError:
                        print("  ⚠️  Digite um número inteiro válido.")
            else:
                cfg['musica_novidade']    = None
                cfg['musica_repeticoes']  = 1
                cfg['musica_volume']      = 100
                print("  ⚠️  Nenhum arquivo selecionado. Nenhuma música será tocada.")
        else:
            cfg['musica_novidade']   = None
            cfg['musica_repeticoes'] = 1
            cfg['musica_volume']     = 100

    # ── Busca preliminar para preencher os demais campos automaticamente ──────
    chave_editais    = 'numero_de_editais_com_o_padrao_de_data_no_titulo'
    chave_resultados = 'numero_de_editais_encontrados_na_pesquisa_do_site'

    campos_auto_faltando = (
        cfg.get(chave_editais)    is None or
        cfg.get(chave_resultados) is None or
        not cfg.get('edital_referencia') or
        not cfg.get('data_referencia')
    )

    if campos_auto_faltando:
        resultado = _busca_preliminar(cfg['nome_dou'], cfg['url'])

        if resultado:
            sep2 = "-" * 60
            print(f"\n{sep2}")
            print("  RESULTADO DA BUSCA PRELIMINAR")
            print(sep2)

            total        = resultado['total_editais']
            num_res      = resultado['num_resultados']
            mais_recente = resultado['edital_mais_recente']

            print(f"  Editais com padrão de data no título : {total}")
            if num_res is not None:
                print(f"  Total de resultados no site          : {num_res}")
            if mais_recente:
                print(f"  Edital mais recente encontrado       : {mais_recente['titulo']}")
                print(f"  Data do edital mais recente          : {mais_recente['data_obj'].strftime('%d/%m/%Y')}")
            print(sep2)

            # Confirma ou corrige cada valor encontrado
            print("\n  Confirme os valores encontrados (Enter = aceitar, ou digite para corrigir):")

            if cfg.get(chave_editais) is None:
                resp = input(f"  Editais com data [{total}]: ").strip()
                cfg[chave_editais] = int(resp) if resp else total

            if cfg.get(chave_resultados) is None:
                if num_res is not None:
                    resp = input(f"  Total de resultados no site [{num_res}]: ").strip()
                    cfg[chave_resultados] = int(resp) if resp else num_res
                else:
                    print("  ⚠️  Não foi possível detectar o total de resultados.")
                    cfg[chave_resultados] = _ler_inteiro("  Digite manualmente: ")

            if not cfg.get('edital_referencia'):
                if mais_recente:
                    resp = input(f"  Edital de referência [{mais_recente['titulo'][:60]}]: ").strip()
                    cfg['edital_referencia'] = resp if resp else mais_recente['titulo']
                else:
                    print("  ⚠️  Não foi possível detectar o edital mais recente.")
                    print("  Título do edital mais recente conhecido. Exemplo: EDITAL Nº 8 - FUB, DE 19 DE SETEMBRO DE 2025")
                    cfg['edital_referencia'] = _ler("  Título: ")

            if not cfg.get('data_referencia'):
                if mais_recente:
                    data_str = mais_recente['data_obj'].strftime('%d/%m/%Y')
                    resp = input(f"  Data de referência [{data_str}]: ").strip()
                    if not resp:
                        cfg['data_referencia'] = mais_recente['data_obj']
                    else:
                        data_convertida = None
                        for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
                            try:
                                data_convertida = datetime.strptime(resp, fmt)
                                break
                            except ValueError:
                                pass
                        if data_convertida:
                            cfg['data_referencia'] = data_convertida
                        else:
                            print("  ⚠️  Formato inválido. Use DD/MM/AAAA (ex.: 19/09/2025).")
                            cfg['data_referencia'] = _ler_data("  Data de referência (DD/MM/AAAA): ")
                else:
                    print("  ⚠️  Não foi possível detectar a data do edital mais recente.")
                    cfg['data_referencia'] = _ler_data("  Data de referência (DD/MM/AAAA): ")

        else:
            # Busca falhou — pede manualmente como fallback
            print("  ⚠️  Busca preliminar falhou. Preencha os campos manualmente.")

            if cfg.get(chave_editais) is None:
                print("\n  Quantos editais com padrão de data no título existem na busca?")
                print("  (Títulos no formato: '... DE DD DE MÊS DE AAAA')")
                cfg[chave_editais] = _ler_inteiro("  Número: ")

            if cfg.get(chave_resultados) is None:
                print("\n  Quantos resultados totais o site exibe para essa busca?")
                cfg[chave_resultados] = _ler_inteiro("  Número: ")

            if not cfg.get('edital_referencia'):
                print("\n  Título do edital mais recente conhecido.")
                print("  Exemplo: EDITAL Nº 8 - FUB, DE 19 DE SETEMBRO DE 2025")
                cfg['edital_referencia'] = _ler("  Título: ")

            if not cfg.get('data_referencia'):
                print("\n  Data do edital de referência (DD/MM/AAAA):")
                cfg['data_referencia'] = _ler_data("  Data: ")


def _assistente_configuracao(dados: dict) -> dict:
    """
    Verifica todos os campos obrigatórios do dicionário 'dados'.
    Para cada campo ausente ou inválido, pergunta ao usuário no terminal.
    Ao final, retorna o dicionário completo e atualizado.
    """
    sep = "=" * 60
    print(f"\n{sep}")
    print("  ASSISTENTE DE CONFIGURAÇÃO — MONITOR DE EDITAIS DOU")
    print(f"{sep}")
    print("  Alguns dados estão ausentes. Por favor, preencha abaixo.")
    print("  As informações serão salvas em config_editais.json")
    print(f"{sep}")

    # ── Seção e-mail ─────────────────────────────────────────────────────────
    email_incompleto = any(
        not dados.get('email', {}).get(c) for c in CAMPOS_EMAIL
    )
    if email_incompleto:
        _perguntar_email(dados)

    # ── Seção agendamento ─────────────────────────────────────────────────────
    ag = dados.get('agendamento', {})
    agendamento_incompleto = ag.get('multiplas_execucoes') is None or ag.get('email_sem_resultado') is None
    if agendamento_incompleto:
        _perguntar_agendamento(dados)

    # ── Seção pessoas ─────────────────────────────────────────────────────────
    if not dados.get('pessoas'):
        print("\n  Nenhuma pessoa cadastrada. Vamos adicionar a primeira.")
        print("  Informe o nome exatamente como aparece nos editais do DOU.")
        print("  Use letras maiúsculas. Exemplo: FULANO DE TALS")
        nome_dou_inicial = _ler("\n  Nome no DOU: ").upper()
        dados['pessoas'] = {nome_dou_inicial: {'nome_dou': nome_dou_inicial}}

    # Percorre pessoas existentes e completa campos faltantes
    for nome, cfg in dados['pessoas'].items():
        campos_faltando = [
            c for c in CAMPOS_PESSOA
            if cfg.get(c) is None or cfg.get(c) == ''
        ]
        if campos_faltando:
            print(f"\n  ⚠️  Campos ausentes para '{nome}': {', '.join(campos_faltando)}")
            _perguntar_pessoa(nome, cfg)

    # Verifica se o usuário quer adicionar mais pessoas
    while True:
        print("\n" + "-" * 60)
        resp = input("  Deseja adicionar outra pessoa para monitorar? [s/N] → ").strip().lower()
        if resp not in ('s', 'sim', 'y', 'yes'):
            break
        print("  Informe o nome exatamente como aparece nos editais do DOU.")
        print("  Use letras maiúsculas. Exemplo: FULANO DE TALS")
        novo_nome = _ler("  Nome no DOU: ").upper()
        if novo_nome in dados['pessoas']:
            print(f"  ⚠️  '{novo_nome}' já está cadastrado.")
        else:
            dados['pessoas'][novo_nome] = {'nome_dou': novo_nome}
            _perguntar_pessoa(novo_nome, dados['pessoas'][novo_nome])

    return dados

# ============================================================================
# CARREGAMENTO DA CONFIGURAÇÃO
# ============================================================================

def carregar_configuracao(caminho: Path) -> dict:
    """
    Tenta ler o arquivo JSON de configuração.
    - Se não existir ou estiver vazio: cria uma estrutura base vazia.
    - Se tiver JSON inválido: avisa e parte de uma estrutura vazia.
    - Chama o assistente interativo para preencher qualquer campo faltante.
    - Ao final, salva e devolve o dicionário completo com datas como datetime.
    """
    dados: dict = {'email': {}, 'agendamento': {}, 'pessoas': {}}
    assistente_necessario = False

    # ── Tenta ler o arquivo ───────────────────────────────────────────────────
    if not caminho.exists():
        print(f"\n  Arquivo de configuração não encontrado: {caminho.name}")
        print(    "  Um novo arquivo será criado após o preenchimento das informações.")
        assistente_necessario = True

    else:
        conteudo = caminho.read_text(encoding='utf-8').strip()

        if not conteudo:
            print(f"\n  ⚠️  O arquivo {caminho.name} está vazio.")
            assistente_necessario = True

        else:
            try:
                dados = json.loads(conteudo)
            except json.JSONDecodeError as e:
                print(f"\n  ⚠️  O arquivo {caminho.name} tem JSON inválido: {e}")
                print(    "  O arquivo será reconfigurado do zero.")
                dados = {'email': {}, 'agendamento': {}, 'pessoas': {}}
                assistente_necessario = True

            # Garante que as seções obrigatórias existem
            dados.setdefault('email', {})
            dados.setdefault('agendamento', {})
            dados.setdefault('pessoas', {})

            # Verifica se algum campo está faltando
            email_ok = all(dados['email'].get(c) for c in CAMPOS_EMAIL)
            ag = dados.get('agendamento', {})
            agendamento_ok = ag.get('multiplas_execucoes') is not None and ag.get('email_sem_resultado') is not None
            pessoas_ok = bool(dados['pessoas']) and all(
                all(p.get(c) is not None and p.get(c) != '' for c in CAMPOS_PESSOA)
                for p in dados['pessoas'].values()
            )
            if not email_ok or not agendamento_ok or not pessoas_ok:
                assistente_necessario = True

    # ── Chama o assistente se necessário ─────────────────────────────────────
    if assistente_necessario:
        dados = _assistente_configuracao(dados)
        salvar_configuracao(caminho, dados)
        print(f"\n  ✓ Configuração salva em: {caminho}")

    # ── (Re)gera URL a partir de nome_dou e persiste no JSON ─────────────────
    url_atualizada = False
    for cfg in dados['pessoas'].values():
        if cfg.get('nome_dou'):
            nova_url = gerar_url(cfg['nome_dou'])
            if cfg.get('url') != nova_url:
                cfg['url'] = nova_url
                url_atualizada = True
    if url_atualizada and not assistente_necessario:
        salvar_configuracao(caminho, dados)

    # ── Converte data_referencia → datetime ───────────────────────────────────
    for nome, cfg in dados['pessoas'].items():
        dr = cfg.get('data_referencia')
        if isinstance(dr, datetime):
            pass  # já convertido (veio do assistente)
        elif isinstance(dr, str):
            try:
                cfg['data_referencia'] = datetime.strptime(dr[:10], '%Y-%m-%d')
            except ValueError:
                print(f"\n  ⚠️  'data_referencia' inválida para '{nome}': '{dr}'")
                print(    "  Por favor, corrija no assistente.")
                cfg['data_referencia'] = _ler_data(f"  Nova data para '{nome}' (DD/MM/AAAA): ")
                salvar_configuracao(caminho, dados)
        else:
            print(f"\n  ⚠️  'data_referencia' ausente para '{nome}'.")
            cfg['data_referencia'] = _ler_data(f"  Data de referência para '{nome}' (DD/MM/AAAA): ")
            salvar_configuracao(caminho, dados)

    return dados


def salvar_configuracao(caminho: Path, dados: dict) -> None:
    """
    Grava o dicionário de configuração de volta no arquivo JSON.
    Converte datetime → string 'YYYY-MM-DD' antes de salvar.
    """
    dados_para_salvar = json.loads(json.dumps(dados, default=str))

    for cfg in dados_para_salvar['pessoas'].values():
        dr = cfg.get('data_referencia')
        if isinstance(dr, str):
            cfg['data_referencia'] = dr[:10]  # garante só YYYY-MM-DD

    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(dados_para_salvar, f, ensure_ascii=False, indent=2)


# ============================================================================
# FUNÇÕES DE CAPTURA WEB
# ============================================================================

def capturar_html(url, max_tentativas=10):
    """Captura o HTML de uma URL com múltiplas tentativas"""
    for tentativa in range(1, max_tentativas + 1):
        try:
            print(f"  Tentativa {tentativa}/{max_tentativas}: Buscando dados...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            resposta = requests.get(url, headers=headers, timeout=180)
            resposta.raise_for_status()
            
            print(f"  ✓ Sucesso! Status: {resposta.status_code}")
            return resposta.text
            
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Erro na tentativa {tentativa}: {e}")
            if tentativa < max_tentativas:
                time.sleep(4)
            else:
                print("  ✗ Todas as tentativas falharam.")
                return None
        except Exception as e:
            print(f"  ✗ Erro inesperado: {e}")
            return None


def extrair_numero_resultados(html, nome):
    """Extrai o número de resultados da busca do padrão 'X resultados para <strong>"Nome"</strong>'"""
    
    padroes = [
        r'(\d+)\s+resultados?\s+para\s+<strong>"[^"]*"</strong>',
        r"(\d+)\s+resultados?\s+para\s+<strong>'[^']*'</strong>",
        r'(\d+)\s+resultados?\s+para\s+<strong>[^<]+</strong>',
        r'(\d+)\s+resultados?\s+para\s+<strong>',
        r'(\d+)\s+resultados?\s+para\s+&lt;strong&gt;',
    ]
    
    for i, padrao in enumerate(padroes, 1):
        match = re.search(padrao, html, re.IGNORECASE)
        if match:
            numero = int(match.group(1))
            print(f"  Número de resultados encontrados: {numero} (padrão {i})")
            return numero
    
    nome_escapado = re.escape(nome)
    padrao_com_nome = rf'(\d+)\s+resultados?\s+para.*?{nome_escapado}'
    match = re.search(padrao_com_nome, html, re.IGNORECASE | re.DOTALL)
    if match:
        numero = int(match.group(1))
        print(f"  Número de resultados encontrados: {numero} (busca por nome)")
        return numero
    
    print(f"  ⚠️  Não foi possível encontrar o número de resultados no HTML")
    print(f"  Debug: Procurando por 'resultados para' no HTML...")
    
    debug_matches = re.finditer(r'.{0,50}resultados?\s+para.{0,100}', html, re.IGNORECASE)
    for idx, match in enumerate(debug_matches, 1):
        if idx <= 3:
            trecho = match.group(0).replace('\n', ' ').strip()
            print(f"  Ocorrência {idx}: ...{trecho}...")
    
    return None


def extrair_data_edital(texto):
    """Extrai a data do edital no formato 'DE DD DE MMMM DE AAAA'"""
    padrao = r'DE\s+(\d{1,2})\s+DE\s+([A-ZÇÃÕ]+)\s+DE\s+(\d{4})'
    match = re.search(padrao, texto, re.IGNORECASE)
    
    if match:
        dia = match.group(1)
        mes_nome = match.group(2).upper()
        ano = match.group(3)
        
        meses = {
            'JANEIRO': 1, 'FEVEREIRO': 2, 'MARÇO': 3, 'ABRIL': 4,
            'MAIO': 5, 'JUNHO': 6, 'JULHO': 7, 'AGOSTO': 8,
            'SETEMBRO': 9, 'OUTUBRO': 10, 'NOVEMBRO': 11, 'DEZEMBRO': 12
        }
        
        mes = meses.get(mes_nome)
        if mes:
            try:
                data_obj = datetime(int(ano), mes, int(dia))
                return texto, data_obj
            except Exception:
                pass
    
    return None, None


def analisar_editais_html(html, nome):
    """Analisa o HTML e retorna informações sobre os editais"""
    if not html:
        return None
    
    num_resultados = extrair_numero_resultados(html, nome)
    
    padrao_titulo = r'"title":"([^"]*DE \d{1,2} DE [A-ZÇÃÕ]+ DE \d{4}[^"]*)"'
    titulos = re.findall(padrao_titulo, html, re.IGNORECASE)
    
    total_editais = len(titulos)
    editais_com_data = []
    
    for titulo in titulos:
        data_str, data_obj = extrair_data_edital(titulo)
        if data_str and data_obj:
            editais_com_data.append({
                'titulo': titulo,
                'data_obj': data_obj
            })
    
    editais_com_data.sort(key=lambda x: x['data_obj'], reverse=True)
    
    edital_mais_recente = editais_com_data[0] if editais_com_data else None
    
    return {
        'total_editais': total_editais,
        'num_resultados': num_resultados,
        'edital_mais_recente': edital_mais_recente,
        'todos_editais': editais_com_data
    }

# ============================================================================
# FUNÇÕES DE SCREENSHOT E EMAIL
# ============================================================================


def nome_curto(nome: str) -> str:
    """
    Retorna primeiro + último nome da pessoa.
    Exemplos:
      'Fulano'              -> 'Fulano'
      'Fulano Reis'         -> 'Fulano Reis'
      'Fulano Guedes Reis'  -> 'Fulano Reis'
    """
    partes = nome.strip().split()
    if len(partes) <= 2:
        return nome.strip()
    return f"{partes[0]} {partes[-1]}"


def sendEmail(nome, novidade, erro, email_config, cfg_pessoa, url, detalhes=''):
    """Envia email com as informações do script"""
    cfg        = email_config
    nome_fmt   = nome.title()           # ex: FULANO DE TALS → Fulano De Tals
    nc         = nome_curto(nome_fmt)   # ex: Fulano Tals
    primeiro   = nome_fmt.split()[0]    # ex: Fulano

    if erro == 1:
        tipo_email = 'erro'
        assunto  = f"DOU. Erro para {nc}."
        corpo    = f"Ocorreu um erro ao verificar os editais de\n {nome}.\n\nDetalhes:\n{detalhes}\n\nAcesse o DOU:\n{url}"
    elif novidade == 0:
        tipo_email = 'sem_resultado'
        assunto  = f"DOU inalterado para {nc}."
        corpo    = f"{nome},\ncontinue acreditando!\nDeus é fiel!\n\n{detalhes}\n\nAcesse o DOU:\n{url}"
    elif novidade == 1:
        tipo_email = 'novidade'
        assunto  = f"⚠️Novidade DOU para {primeiro}!⚠️"
        corpo    = f"Novidade para {nome}!\n\n{detalhes}\n\nAcesse o DOU:\n{url}"

    # Registra o envio no relatório e acrescenta o mini relatório ao corpo
    _relatorio_registrar_email(nome, tipo_email)
    caminho_musica = cfg_pessoa.get('musica_novidade') or ''
    mensagem = corpo + _gerar_texto_relatorio(nome, caminho_musica)

    # destinatarios vem da configuração da pessoa (lista de 1 ou mais endereços)
    destinatarios = cfg_pessoa.get('destinatarios', [])
    if isinstance(destinatarios, str):
        destinatarios = [destinatarios]  # compatibilidade com JSONs antigos
    if not destinatarios:
        print(f"  ⚠️  Nenhum destinatário configurado para '{nome}'. E-mail não enviado.")
        return

    msg = EmailMessage()
    msg['From']    = cfg['remetente']
    msg['To']      = ', '.join(destinatarios)
    msg['Subject'] = assunto
    msg.set_content(mensagem)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as email:
            email.login(cfg['remetente'], cfg['senha'])
            email.send_message(msg)
        print(f"  ✓ E-mail enviado para: {', '.join(destinatarios)}")
    except Exception as e:
        print(f"  ✗ Erro ao enviar e-mail: {e}")

# ============================================================================
# CONFIRMAÇÃO INTERATIVA DE NOVO NORMAL
# ============================================================================

TIMEOUT_CONFIRMACAO = 60  # segundos disponíveis para o usuário responder


def _input_com_timeout(prompt: str, timeout: int) -> str | None:
    """
    Exibe 'prompt' e aguarda entrada do usuário por até 'timeout' segundos.
    Retorna a string digitada ou None se o tempo esgotar.
    Funciona apenas em sistemas Unix/Linux (usa select).
    """
    print(prompt, end='', flush=True)
    leitura, _, _ = select.select([sys.stdin], [], [], timeout)
    if leitura:
        return sys.stdin.readline().strip()
    print()  # quebra de linha após o timeout
    return None


def _barra_regressiva(segundos: int) -> None:
    """Exibe uma contagem regressiva de segundos no mesmo terminal."""
    for restante in range(segundos, 0, -1):
        print(f"\r  ⏳ Tempo restante: {restante:>3}s  ", end='', flush=True)
        time.sleep(1)
    print("\r" + " " * 40 + "\r", end='', flush=True)


def confirmar_novo_normal(nome: str, motivos: list[str], resultado: dict, config: dict) -> bool:
    """
    Mostra as alterações detectadas e pergunta ao usuário (por 60 s) se deseja
    reconhecê-las como o novo normal.

    Retorna True  → usuário confirmou: atualiza o JSON e NÃO envia e-mail.
    Retorna False → usuário recusou ou tempo esgotou: envia e-mail normalmente.
    """
    separador = "=" * 70

    print(f"\n{separador}")
    print(f"  ⚠️  NOVIDADE DETECTADA PARA: {nome}")
    print(separador)
    print("  Alterações encontradas:")
    for m in motivos:
        print(f"    • {m}")
    print()

    mais_recente = resultado.get('edital_mais_recente')
    if mais_recente:
        print(f"  Edital mais recente encontrado:")
        print(f"    Título : {mais_recente['titulo']}")
        print(f"    Data   : {mais_recente['data_obj'].strftime('%d/%m/%Y')}")
    print()

    print(f"  Você tem {TIMEOUT_CONFIRMACAO} segundos para responder.")
    print("  Se não responder, o e-mail de novidade será enviado automaticamente.")
    print(separador)

    resposta = _input_com_timeout(
        "\n  Reconhecer como novo normal e NÃO enviar e-mail? [s/N] → ",
        TIMEOUT_CONFIRMACAO
    )

    if resposta is None:
        print("  ⏰ Tempo esgotado. Enviando e-mail de novidade...")
        return False

    if resposta.strip().lower() in ('s', 'sim', 'y', 'yes'):
        print("\n  ✅ Novo normal reconhecido! Atualizando configuração...")
        _atualizar_config_novo_normal(nome, resultado, config)
        return True
    else:
        print("\n  📧 Confirmação recusada. Enviando e-mail de novidade...")
        return False


def _atualizar_config_novo_normal(nome: str, resultado: dict, config: dict) -> None:
    """
    Atualiza em memória (dict config) os campos de referência para a pessoa
    com os valores recém-detectados, e persiste no arquivo JSON.
    """
    cfg_pessoa = config['pessoas'][nome]

    total          = resultado['total_editais']
    num_resultados = resultado['num_resultados']
    mais_recente   = resultado['edital_mais_recente']

    # Atualiza contadores
    cfg_pessoa['numero_de_editais_com_o_padrao_de_data_no_titulo'] = total

    if num_resultados is not None:
        cfg_pessoa['numero_de_editais_encontrados_na_pesquisa_do_site'] = num_resultados

    # Atualiza edital e data de referência
    if mais_recente:
        cfg_pessoa['edital_referencia'] = mais_recente['titulo']
        cfg_pessoa['data_referencia']   = mais_recente['data_obj']

    # Persiste no arquivo JSON
    salvar_configuracao(CONFIG_PATH, config)

    print(f"  ✓ Configuração atualizada para '{nome}':")
    print(f"      editais com data : {total}")
    if num_resultados is not None:
        print(f"      resultados no site: {num_resultados}")
    if mais_recente:
        print(f"      edital referência: {mais_recente['titulo']}")
        print(f"      data referência  : {mais_recente['data_obj'].strftime('%d/%m/%Y')}")

# ============================================================================
# FUNÇÃO PRINCIPAL DE ANÁLISE
# ============================================================================

def verificar_pessoa(nome: str, config: dict) -> bool:
    """
    Verifica os editais de uma pessoa usando a configuração carregada do JSON.

    Retorna True se foi encontrada uma novidade (e o e-mail foi enviado),
    False caso contrário.
    """

    cfg_pessoa = config['pessoas'][nome]
    email_cfg  = config['email']

    edital_referencia = cfg_pessoa['edital_referencia']
    data_referencia   = cfg_pessoa['data_referencia']
    url               = cfg_pessoa['url']

    print("\n" + "=" * 80)
    print(f"VERIFICANDO EDITAIS PARA: {nome}")
    print("=" * 80)

    # 1. Captura o HTML
    html = capturar_html(url)

    if not html:
        print(f"  ✗ Não foi possível acessar o site para {nome}")
        sendEmail(nome, 0, 1, email_cfg, cfg_pessoa, url, "Falha ao acessar o site do DOU")
        return False

    # 2. Analisa os editais
    resultado = analisar_editais_html(html, nome)

    if not resultado:
        print(f"  ✗ Não foi possível analisar os editais para {nome}")
        sendEmail(nome, 0, 1, email_cfg, cfg_pessoa, url, "Erro ao analisar os editais")
        return False

    total                                            = resultado['total_editais']
    esperado                                         = cfg_pessoa['numero_de_editais_com_o_padrao_de_data_no_titulo']
    num_resultados                                   = resultado['num_resultados']
    numero_de_editais_encontrados_na_pesquisa_do_site = cfg_pessoa['numero_de_editais_encontrados_na_pesquisa_do_site']
    mais_recente                                     = resultado['edital_mais_recente']

    print(f"\n  Total de editais com data encontrados: {total}")
    print(f"  Total de editais com data esperados:   {esperado}")

    if num_resultados is not None:
        print(f"  Número de resultados no site:         {num_resultados}")
        print(f"  Número de resultados esperados:       {numero_de_editais_encontrados_na_pesquisa_do_site}")

    if mais_recente:
        print(f"  Edital mais recente: {mais_recente['titulo'][:80]}")
        print(f"  Data: {mais_recente['data_obj'].strftime('%d/%m/%Y')}")

    # 3. Verifica se há novidades
    tem_novidade = False
    motivo = []

    if total != esperado:
        tem_novidade = True
        motivo.append(f"Número de editais mudou: {esperado} → {total}")

    if num_resultados is not None and num_resultados != numero_de_editais_encontrados_na_pesquisa_do_site:
        tem_novidade = True
        motivo.append(
            f"Número de resultados no site mudou: "
            f"{numero_de_editais_encontrados_na_pesquisa_do_site} → {num_resultados}"
        )

    if mais_recente:
        if mais_recente['data_obj'] > data_referencia:
            tem_novidade = True
            motivo.append(f"Novo edital mais recente: {mais_recente['data_obj'].strftime('%d/%m/%Y')}")
            motivo.append(f"Título: {mais_recente['titulo'][:80]}")
        elif edital_referencia not in mais_recente['titulo']:
            tem_novidade = True
            motivo.append("Edital de referência não é o mais recente")

    # Registra esta busca no relatório de execução
    rodada_atual = len(_relatorio['buscas']) + 1
    _relatorio_registrar_busca(nome, rodada_atual, datetime.now(), tem_novidade, motivo)

    # 4. Age conforme o resultado
    if tem_novidade:
        # ── Pergunta ao usuário se é o novo normal ───────────────────────────
        novo_normal_confirmado = confirmar_novo_normal(nome, motivo, resultado, config)

        if novo_normal_confirmado:
            print(f"\n  ✓ Monitoramento atualizado para '{nome}'. Nenhum e-mail enviado.")
            return False  # não considera novidade para efeito de desligamento

        # ── Usuário não confirmou: envia e-mail ──────────────────────────────
        detalhes  = f"Total de títulos com data: {total} (esperado: {esperado})\n"
        if num_resultados is not None:
            detalhes += (
                f"Número de resultados no site: {num_resultados} "
                f"(esperado: {numero_de_editais_encontrados_na_pesquisa_do_site})\n"
            )
        detalhes += "\n".join(motivo)
        sendEmail(nome, 1, 0, email_cfg, cfg_pessoa, url, detalhes)

        # ── Toca música se configurada ────────────────────────────────────────
        musica = cfg_pessoa.get('musica_novidade')
        if musica:
            repeticoes_musica = cfg_pessoa.get('musica_repeticoes', 1)
            _tocar_musica(
                musica,
                repeticoes=repeticoes_musica,
                volume=cfg_pessoa.get('musica_volume', 100),
            )
            _relatorio_registrar_musica(nome, repeticoes_musica, musica)

        return True  # novidade confirmada e e-mail enviado

    else:
        print(f"\n  ✓ SEM NOVIDADES")
        print(f"      - {total} editais com data encontrados (conforme esperado)")
        if num_resultados is not None:
            print(f"      - {num_resultados} resultados de editais encontrados no site (conforme esperado)")
        print(f"      - Edital de referência continua o mais recente")
        return False


def _enviar_email_sem_resultado(config: dict, rodada: int, hora_limite: int, minuto_limite: int = 0) -> None:
    """
    Envia um e-mail de confirmação para cada pessoa informando que o horário
    limite foi atingido sem novidade.
    """
    email_cfg = config['email']
    for nome, cfg_pessoa in config['pessoas'].items():
        url      = cfg_pessoa['url']
        detalhes = (
            f"Horário limite ({hora_limite:02d}:{minuto_limite:02d}) atingido após {rodada} verificação(ões).\n"
            f"Nenhuma novidade detectada no DOU para {nome}."
        )
        sendEmail(nome, 0, 0, email_cfg, cfg_pessoa, url, detalhes)


# ============================================================================
# LOOP DE MÚLTIPLAS EXECUÇÕES
# ============================================================================

def _aguardar_hora_inicio(hora_inicio: int, minuto_inicio: int = 0) -> None:
    """
    Fica em espera até que o relógio local atinja 'hora_inicio:minuto_inicio'.
    Exibe uma mensagem a cada 5 minutos enquanto aguarda.
    """
    agora = datetime.now()
    alvo  = agora.replace(hour=hora_inicio, minute=minuto_inicio, second=0, microsecond=0)

    if agora >= alvo:
        return  # já passou da hora de início, executa imediatamente

    print(f"\n  ⏰ Aguardando horário de início ({hora_inicio:02d}:{minuto_inicio:02d})...")
    print(f"     Início em: {alvo.strftime('%H:%M:%S')}  |  Agora: {agora.strftime('%H:%M:%S')}")

    while True:
        agora = datetime.now()
        if agora >= alvo:
            break
        restante = (alvo - agora).total_seconds()
        print(f"\r  ⏳ Faltam {int(restante // 60):02d}min {int(restante % 60):02d}s para o início...   ",
              end='', flush=True)
        time.sleep(min(300, restante))  # verifica a cada 5 min ou quando restar < 5 min

    print("\r" + " " * 70 + "\r", end='', flush=True)
    print(f"\n  ✓ Horário de início atingido! Iniciando verificações.")


def executar_com_agendamento(config: dict) -> None:
    """
    Controla o loop de execuções conforme a configuração de agendamento.

    Modos de operação:
      - multiplas_execucoes = False → executa uma única vez para cada pessoa
        e encerra (comportamento original).
      - multiplas_execucoes = True  → aguarda a hora de início, depois repete
        a verificação em intervalos até atingir a hora limite.
        • Se desligar_ao_encontrar = True e houver novidade: desliga.
        • Se email_sem_resultado = True e o limite for atingido: envia e-mail.
    """
    ag = config.get('agendamento', {})
    multiplas     = ag.get('multiplas_execucoes', False)
    email_sem_res = ag.get('email_sem_resultado', False)

    # ── Modo único (comportamento original) ───────────────────────────────────
    if not multiplas:
        for nome in config['pessoas']:
            verificar_pessoa(nome, config)
            time.sleep(10)

        if email_sem_res:
            # No modo único, o "horário limite" não existe formalmente,
            # então enviamos após a única rodada se o usuário quiser.
            _enviar_email_sem_resultado(config, rodada=1, hora_limite=0, minuto_limite=0)

        print("\n" + "=" * 80)
        print("VERIFICAÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 80 + "\n")

        if ag.get('desligar_ao_finalizar', False):
            print("  🔌 Desligando o computador...")
            time.sleep(5)
            subprocess.run(['sudo', '/sbin/shutdown', '-h', 'now'], check=True)
        return

    # ── Modo múltiplo ─────────────────────────────────────────────────────────
    hora_inicio      = ag['hora_inicio']
    minuto_inicio    = ag.get('minuto_inicio', 0)
    hora_limite      = ag['hora_limite']
    minuto_limite    = ag.get('minuto_limite', 0)
    intervalo_min    = ag['intervalo_minutos']
    desligar_ao_enc  = ag.get('desligar_ao_encontrar', False)
    desligar_ao_fin  = ag.get('desligar_ao_finalizar', False)
    exec_apos_limite = ag.get('executar_apos_limite', False)

    # Converte limites para minutos do dia para facilitar comparações
    inicio_minutos = hora_inicio * 60 + minuto_inicio
    limite_minutos = hora_limite * 60 + minuto_limite

    print(f"\n  📋 Modo múltiplas execuções ativado:")
    print(f"     Início   : {hora_inicio:02d}:{minuto_inicio:02d}")
    print(f"     Limite   : {hora_limite:02d}:{minuto_limite:02d}")
    print(f"     Intervalo: {intervalo_min // 60:02d}:{intervalo_min % 60:02d} ({intervalo_min} min)")
    print(f"     Desligar ao encontrar       : {'Sim' if desligar_ao_enc else 'Não'}")
    print(f"     Desligar ao finalizar       : {'Sim' if desligar_ao_fin else 'Não'}")
    print(f"     Executar uma vez após limite: {'Sim' if exec_apos_limite else 'Não'}")
    print(f"     E-mail sem novidade no limite: {'Sim' if email_sem_res else 'Não'}")

    # Aguarda hora de início (caso o script tenha sido iniciado antes)
    _aguardar_hora_inicio(hora_inicio, minuto_inicio)

    rodada         = 0
    novidade_geral = False
    exec_pos_feita = False  # controla se a execução pós-limite já foi realizada

    while True:
        agora = datetime.now()
        agora_minutos = agora.hour * 60 + agora.minute

        # ── Verifica se passou do horário limite ──────────────────────────────
        if agora_minutos >= limite_minutos:
            # Execução extra após o limite (se configurada e ainda não feita)
            if exec_apos_limite and not exec_pos_feita:
                exec_pos_feita = True
                print(f"\n  🔁 Horário limite atingido — executando verificação extra "
                      f"(executar_apos_limite = Sim)...")
                rodada += 1
                print(f"\n{'=' * 80}")
                print(f"  RODADA {rodada} (EXTRA)  |  {agora.strftime('%d/%m/%Y %H:%M:%S')}")
                print(f"{'=' * 80}")
                for nome in config['pessoas']:
                    encontrou = verificar_pessoa(nome, config)
                    if encontrou:
                        novidade_geral = True
                    time.sleep(10)
                # Após a rodada extra, encerra normalmente
                print(f"\n  🔔 Rodada extra concluída. Encerrando verificações.")
            else:
                print(f"\n  🔔 Horário limite ({hora_limite:02d}:{minuto_limite:02d}) atingido. Encerrando verificações.")

            if email_sem_res and not novidade_geral:
                print("  📧 Enviando e-mail de confirmação (sem novidade no período)...")
                _enviar_email_sem_resultado(config, rodada, hora_limite, minuto_limite)
            break

        rodada += 1
        print(f"\n{'=' * 80}")
        print(f"  RODADA {rodada}  |  {agora.strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"{'=' * 80}")

        # ── Verifica cada pessoa ──────────────────────────────────────────────
        novidade_nesta_rodada = False
        pessoas_com_novidade  = set()
        for nome in config['pessoas']:
            encontrou = verificar_pessoa(nome, config)
            if encontrou:
                novidade_nesta_rodada = True
                novidade_geral        = True
                pessoas_com_novidade.add(nome)
            time.sleep(10)

        # ── Novidade encontrada → desliga se configurado ──────────────────────
        if novidade_nesta_rodada and desligar_ao_enc:
            email_cfg = config['email']
            for nome, cfg_pessoa in config['pessoas'].items():
                if nome not in pessoas_com_novidade:
                    url      = cfg_pessoa['url']
                    detalhes = (
                        f"Horário limite ({hora_limite:02d}:{minuto_limite:02d}) atingido após {rodada} verificação(ões).\n"
                        f"Nenhuma novidade detectada no DOU para {nome}."
                    )
                    sendEmail(nome, 0, 0, email_cfg, cfg_pessoa, url, detalhes)
            print(f"\n  ⚠️  Novidade detectada! E-mails enviados. Desligando o computador...")
            time.sleep(5)
            subprocess.run(['sudo', '/sbin/shutdown', '-h', 'now'], check=True)
            return  # nunca alcançado após o shutdown, mas por clareza

        # ── Calcula próxima execução ──────────────────────────────────────────
        proxima = datetime.now() + timedelta(minutes=intervalo_min)
        proxima_minutos = proxima.hour * 60 + proxima.minute

        # Se a próxima execução já ultrapassaria o limite e não há exec extra,
        # verifica se ainda vale a pena aguardar ou se deve encerrar direto
        if proxima_minutos >= limite_minutos and not exec_apos_limite:
            print(f"\n  🔔 Próxima verificação seria após o horário limite "
                  f"({hora_limite:02d}:{minuto_limite:02d}). Encerrando.")
            if email_sem_res and not novidade_geral:
                print("  📧 Enviando e-mail de confirmação (sem novidade no período)...")
                _enviar_email_sem_resultado(config, rodada, hora_limite, minuto_limite)
            break

        # ── Aguarda até a próxima execução ────────────────────────────────────
        print(f"\n  ⏳ Próxima verificação: {proxima.strftime('%H:%M:%S')}  "
              f"(em {intervalo_min // 60:02d}:{intervalo_min % 60:02d})")

        segundos_espera = intervalo_min * 60
        inicio_espera   = time.time()
        while True:
            decorrido = time.time() - inicio_espera
            if decorrido >= segundos_espera:
                break
            restante = segundos_espera - decorrido
            print(f"\r  ⏳ Próxima rodada em {int(restante // 60):02d}min {int(restante % 60):02d}s...   ",
                  end='', flush=True)
            time.sleep(30)

        print("\r" + " " * 70 + "\r", end='', flush=True)

    print("\n" + "=" * 80)
    print("CICLO DE VERIFICAÇÕES CONCLUÍDO!")
    print("=" * 80 + "\n")

    if desligar_ao_fin:
        print("  🔌 Desligando o computador...")
        time.sleep(5)
        subprocess.run(['sudo', '/sbin/shutdown', '-h', 'now'], check=True)


# ============================================================================
# EXECUÇÃO PRINCIPAL
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("MONITOR DE EDITAIS DOU")
    print(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 80)

    # Inicia o rastreador de relatório de execução
    _relatorio_iniciar()

    # Carrega configuração do JSON (cria/completa interativamente se necessário)
    config = carregar_configuracao(CONFIG_PATH)
    print(f"\n✓ Configuração carregada: {CONFIG_PATH}")
    print(f"  Pessoas monitoradas : {', '.join(config['pessoas'].keys())}")

    try:
        executar_com_agendamento(config)

        #Aguarda 120 segundos
        #time.sleep(120)

        #Desliga o computador
        #subprocess.run(['sudo', '/sbin/shutdown', '-h', 'now'], check=True)

    except KeyboardInterrupt:
        print("\n\n✗ Execução interrompida pelo usuário.")
    except Exception as e:
        print(f"\n\n✗ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
