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
import pyautogui
import time
import subprocess
import smtplib
from email.message import EmailMessage
import os
import glob
from datetime import datetime
import re

# ============================================================================
# CONFIGURAÇÕES
# ============================================================================

PESSOAS = {
    'Fulano': {
        'url': 'https://www.in.gov.br/consulta/-/buscar/dou?q=%22FULANO+DE+TALS%22&s=todos&exactDate=all&sortType=0',
        'numero_de_editais_com_o_padrao_de_data_no_titulo': 3,
        'numero_de_editais_encontrados_na_pesquisa_do_site': 9,
        'fav_x': 59,
        'fav_y': 121,
        'edital_referencia': 'EDITAL Nº 8 - FUB, DE 19 DE SETEMBRO DE 2025',
        'data_referencia': datetime(2025, 9, 19)
    },
    'Beltrano': {
        'url': 'https://www.in.gov.br/consulta/-/buscar/dou?q=%22BELTRANO+DE+TALS%22&s=todos&exactDate=all&sortType=0',
        'numero_de_editais_com_o_padrao_de_data_no_titulo': 5,
        'numero_de_editais_encontrados_na_pesquisa_do_site': 7,
        'fav_x': 157,
        'fav_y': 121,
        'edital_referencia': 'EDITAL Nº 5 - FUB, DE 10 DE OUTUBRO DE 2025',
        'data_referencia': datetime(2025, 10, 10)
    }
}
#print(PESSOAS['Thiago']['url'])


EMAIL_CONFIG = {
    'remetente': 'email@gmail.com',
    'destinatario': 'email@gmail.com',
    'senha': 'xxxx xxxx xxxx xxxx'
}

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
    """Extrai o número de resultados da busca do padrão 'X resultados para <strong>\"Nome\"</strong>'"""
    
    # Tenta vários padrões possíveis, do mais específico ao mais genérico
    padroes = [
        # Padrão 1: Com aspas duplas literais no HTML
        r'(\d+)\s+resultados?\s+para\s+<strong>"[^"]*"</strong>',
        
        # Padrão 2: Com aspas simples
        r"(\d+)\s+resultados?\s+para\s+<strong>'[^']*'</strong>",
        
        # Padrão 3: Sem aspas
        r'(\d+)\s+resultados?\s+para\s+<strong>[^<]+</strong>',
        
        # Padrão 4: Mais genérico, captura qualquer coisa depois de "resultados para"
        r'(\d+)\s+resultados?\s+para\s+<strong>',
        
        # Padrão 5: Versão HTML escapada
        r'(\d+)\s+resultados?\s+para\s+&lt;strong&gt;',
    ]
    
    for i, padrao in enumerate(padroes, 1):
        match = re.search(padrao, html, re.IGNORECASE)
        if match:
            numero = int(match.group(1))
            print(f"  Número de resultados encontrados: {numero} (padrão {i})")
            return numero
    
    # Se nenhum padrão funcionou, tenta buscar especificamente pelo nome
    # Escapa caracteres especiais do nome para uso em regex
    nome_escapado = re.escape(nome)
    padrao_com_nome = rf'(\d+)\s+resultados?\s+para.*?{nome_escapado}'
    match = re.search(padrao_com_nome, html, re.IGNORECASE | re.DOTALL)
    if match:
        numero = int(match.group(1))
        print(f"  Número de resultados encontrados: {numero} (busca por nome)")
        return numero
    
    # Debug: Mostra trechos do HTML que contêm "resultados para"
    print(f"  ⚠️  Não foi possível encontrar o número de resultados no HTML")
    print(f"  Debug: Procurando por 'resultados para' no HTML...")
    
    # Busca ocorrências de "resultados para" para debug
    debug_matches = re.finditer(r'.{0,50}resultados?\s+para.{0,100}', html, re.IGNORECASE)
    for idx, match in enumerate(debug_matches, 1):
        if idx <= 3:  # Mostra apenas as 3 primeiras ocorrências
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
            except:
                pass
    
    return None, None


def analisar_editais_html(html, nome):
    """Analisa o HTML e retorna informações sobre os editais"""
    if not html:
        return None
    
    # Extrai o número de resultados da busca
    num_resultados = extrair_numero_resultados(html, nome)
    
    # Procura por títulos de editais no JSON
    padrao_titulo = r'"title":"([^"]*DE \d{1,2} DE [A-ZÇÃÕ]+ DE \d{4}[^"]*)"'
    titulos = re.findall(padrao_titulo, html, re.IGNORECASE)
    
    total_editais = len(titulos)
    editais_com_data = []
    
    # Extrai datas dos editais
    for titulo in titulos:
        data_str, data_obj = extrair_data_edital(titulo)
        if data_str and data_obj:
            editais_com_data.append({
                'titulo': titulo,
                'data_obj': data_obj
            })
    
    # Ordena por data (mais recente primeiro)
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

def obter_caminho_desktop():
    """Retorna o caminho para a pasta Desktop"""
    return os.path.join(os.path.expanduser('~'), 'Desktop')


def capturar_screenshot(pasta, prefixo=''):
    """Captura screenshot e salva na pasta especificada"""
    try:
        os.makedirs(pasta, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d%H%M')
        screenshot_path = os.path.join(pasta, f'{prefixo}{timestamp}.png')
        pyautogui.screenshot(screenshot_path)
        print(f"  ✓ Screenshot salvo em: {screenshot_path}")
        return screenshot_path
    except Exception as e:
        print(f"  ✗ Erro ao capturar screenshot: {e}")
        return None


def limpar_screenshots_antigos(pasta, limite=10):
    """Remove screenshots antigos se houver mais que o limite"""
    arquivos = sorted(glob.glob(f'{pasta}/*.png'), key=os.path.getmtime)
    while len(arquivos) > limite:
        arquivo_remover = arquivos.pop(0)
        try:
            os.remove(arquivo_remover)
            print(f"  ✓ Screenshot antigo removido: {os.path.basename(arquivo_remover)}")
        except Exception as e:
            print(f"  ✗ Erro ao remover arquivo: {e}")


def sendEmail(nome, novidade, erro, detalhes='', screenshot_path=None):
    """Envia email com as informações do script"""
    cfg = EMAIL_CONFIG
    
    if erro == 1:
        assunto = f"Erro no script do {nome}"
        mensagem = f"Ocorreu um erro ao verificar os editais.\n\nDetalhes:\n{detalhes}\n\nAcesse o DOU:\n{PESSOAS[nome]['url']}"
        
    elif novidade == 0:
        assunto = 'DOU 25 sem novidades'
        mensagem = f"{nome}, continue acreditando!\nDeus é fiel!\n\n{detalhes}\n\nAcesse o DOU:\n{PESSOAS[nome]['url']}"
    elif novidade == 1:
        assunto = 'ATENÇÃO! NOVIDADE DOU! VEJA O DOU!'
        assunto = f'⚠️ {assunto} ⚠️'
        mensagem = f"Novidade para {nome}!\n\n{detalhes}\n\nAcesse o DOU:\n{PESSOAS[nome]['url']}\n\nVerifique o screenshot anexo."
    
    msg = EmailMessage()
    msg['From'] = cfg['remetente']
    msg['To'] = cfg['destinatario']
    msg['Subject'] = assunto
    msg.set_content(mensagem)
    
    # Anexar screenshot se houver
    if screenshot_path and os.path.exists(screenshot_path):
        with open(screenshot_path, 'rb') as f:
            img_data = f.read()
            filename = f'{nome}_{"novidade" if novidade == 1 else "erro"}.png'
            msg.add_attachment(img_data, maintype='image', subtype='png', filename=filename)
    
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as email:
            email.login(cfg['remetente'], cfg['senha'])
            email.send_message(msg)
        print(f"  ✓ Email enviado com sucesso!")
    except Exception as e:
        print(f"  ✗ Erro ao enviar email: {e}")

# ============================================================================
# FUNÇÕES DE NAVEGADOR (BACKUP)
# ============================================================================

def abrir_navegador_e_capturar(nome, fav_x, fav_y):
    """Abre o navegador e captura screenshot (usado quando há novidade)"""
    print(f"  → Abrindo navegador para capturar screenshot...")
    
    screenWidth, screenHeight = pyautogui.size()
    print(f"  Resolução da tela: {screenWidth}x{screenHeight}")
    
    # Abrir Firefox
    pyautogui.moveTo(210, 751)
    time.sleep(4)
    pyautogui.click()
    time.sleep(60)
    
    # Nova aba
    pyautogui.hotkey('ctrl', 't')
    time.sleep(60)
    
    # Clica no favorito
    pyautogui.moveTo(fav_x, fav_y)
    time.sleep(8)
    pyautogui.click()
    time.sleep(60)
    
    # Scroll para mostrar conteúdo
    pyautogui.scroll(-5)
    time.sleep(60)
    
    # Captura screenshot
    desktop_path = obter_caminho_desktop()
    pasta_novidades = os.path.join(desktop_path, 'DOU_2025_novidades')
    screenshot_path = capturar_screenshot(pasta_novidades, f'{nome}_')
    
    # Fecha a aba
    time.sleep(20)
    pyautogui.hotkey('ctrl', 'w')
    time.sleep(20)
    pyautogui.hotkey('ctrl', 'w')

    
    return screenshot_path

# ============================================================================
# FUNÇÃO PRINCIPAL DE ANÁLISE
# ============================================================================

def verificar_pessoa(nome, config):
    """Verifica os editais de uma pessoa"""
    print("\n" + "="*80)
    print(f"VERIFICANDO EDITAIS PARA: {nome}")
    print("="*80)

    # Referências individuais por pessoa
    edital_referencia = config['edital_referencia']
    data_referencia   = config['data_referencia']

    # 1. Captura o HTML
    html = capturar_html(config['url'])
    
    if not html:
        print(f"  ✗ Não foi possível acessar o site para {nome}")
        desktop_path = obter_caminho_desktop()
        pasta_erros = os.path.join(desktop_path, 'prints_dos_erros_do_script')
        screenshot_path = capturar_screenshot(pasta_erros, f'{nome}_erro_conexao_')
        sendEmail(nome, 0, 1, "Falha ao acessar o site do DOU", screenshot_path)
        return
    
    # 2. Analisa os editais
    resultado = analisar_editais_html(html, nome)
    
    if not resultado:
        print(f"  ✗ Não foi possível analisar os editais para {nome}")
        desktop_path = obter_caminho_desktop()
        pasta_erros = os.path.join(desktop_path, 'prints_dos_erros_do_script')
        screenshot_path = capturar_screenshot(pasta_erros, f'{nome}_erro_analise_')
        sendEmail(nome, 0, 1, "Erro ao analisar os editais", screenshot_path)
        return
    
    total          = resultado['total_editais']
    esperado       = config['numero_de_editais_com_o_padrao_de_data_no_titulo']
    num_resultados = resultado['num_resultados']
    numero_de_editais_encontrados_na_pesquisa_do_site = config['numero_de_editais_encontrados_na_pesquisa_do_site']
    mais_recente   = resultado['edital_mais_recente']
    
    print(f"\n  Total de editais com data encontrados: {total}")
    print(f"  Total de editais com data esperados: {esperado}")
    
    if num_resultados is not None:
        print(f"  Número de resultados no site: {num_resultados}")
        print(f"  Número de resultados esperados no site : {numero_de_editais_encontrados_na_pesquisa_do_site}")
    
    if mais_recente:
        print(f"  Edital mais recente: {mais_recente['titulo'][:80]}...")
        print(f"  Data: {mais_recente['data_obj'].strftime('%d/%m/%Y')}")
    
    # 3. Verifica se há novidades
    tem_novidade = False
    motivo = []
    
    if total != esperado:
        tem_novidade = True
        motivo.append(f"Número de editais mudou: {esperado} → {total}")
    
    if num_resultados is not None and num_resultados != numero_de_editais_encontrados_na_pesquisa_do_site:
        tem_novidade = True
        motivo.append(f"Número de resultados no site mudou: {numero_de_editais_encontrados_na_pesquisa_do_site} → {num_resultados}")
    
    if mais_recente:
        if mais_recente['data_obj'] > data_referencia:
            tem_novidade = True
            motivo.append(f"Novo edital mais recente: {mais_recente['data_obj'].strftime('%d/%m/%Y')}")
            motivo.append(f"Título: {mais_recente['titulo'][:80]}...")
        elif edital_referencia not in mais_recente['titulo']:
            tem_novidade = True
            motivo.append("Edital de referência não é o mais recente")
    
    # 4. Age conforme o resultado
    if tem_novidade:
        print(f"\n  ⚠️  NOVIDADE DETECTADA!")
        for m in motivo:
            print(f"      - {m}")
        
        # Abre navegador e captura screenshot
        screenshot_path = abrir_navegador_e_capturar(nome, config['fav_x'], config['fav_y'])
        
        # Limpa screenshots antigos
        desktop_path = obter_caminho_desktop()
        pasta_novidades = os.path.join(desktop_path, 'DOU_2025_novidades')
        limpar_screenshots_antigos(pasta_novidades, 20)
        
        # Envia email
        detalhes = f"Total de títulos com data: {total} (esperado: {esperado})\n"
        if num_resultados is not None:
            detalhes += f"Número de resultados no site: {num_resultados} (esperado: {numero_de_editais_encontrados_na_pesquisa_do_site})\n"
        detalhes += "\n".join(motivo)
        sendEmail(nome, 1, 0, detalhes, screenshot_path)
        
    else:
        print(f"\n  ✓ SEM NOVIDADES")
        print(f"      - {total} editais com data encontrados (conforme esperado)")
        if num_resultados is not None:
            print(f"      - {num_resultados} resultados de editais encontrados no site (conforme esperado)")
        print(f"      - Edital de referência continua o mais recente")
        
        detalhes = f"Editais com data: {total}\n"
        if num_resultados is not None:
            detalhes += f"Número de resultados no site: {num_resultados}\n"
        detalhes += f"Edital mais recente: {edital_referencia}"
        sendEmail(nome, 0, 0, detalhes)

# ============================================================================
# EXECUÇÃO PRINCIPAL
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("MONITOR DE EDITAIS DOU")
    print(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("="*80)
    
    try:
        # Verifica cada pessoa
        for nome, config in PESSOAS.items():
            verificar_pessoa(nome, config)
            time.sleep(10)  # Pausa entre verificações
        
        print("\n" + "="*80)
        print("VERIFICAÇÃO CONCLUÍDA COM SUCESSO!")
        print("="*80 + "\n")
        
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
