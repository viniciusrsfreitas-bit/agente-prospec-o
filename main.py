import os
import time
import json
import requests
import unicodedata
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from openai import OpenAI

# Carrega as chaves do seu arquivo .env
load_dotenv()

client_openai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
API_KEY_GOOGLE = os.environ.get("GOOGLE_CUSTOM_SEARCH_KEY")
SEARCH_ENGINE_ID = "e0c02c422fb02448d"

# NOVO ID DA PLANILHA ATUALIZADO
SPREADSHEET_ID_LEADS = os.environ.get("SPREADSHEET_ID")
SPREADSHEET_ID_CRONOGRAMA = os.environ.get("SPREADSHEET_ID_CRONOGRAMA")

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
path_credentials = 'credentials.json'

def obtener_servico_sheets():
    credenciais = Credentials.from_service_account_file(path_credentials, scopes=SCOPES)
    return build('sheets', 'v4', credentials=credenciais).spreadsheets()


# 🕵️‍♂️ AGENTE 1: ORQUESTRADOR / PLANEJADOR COGNITIVO
class AgentePlanejador:
    def __init__(self, sheets_client):
        self.sheets = sheets_client
        self.backstory = """
        Você é o Diretor de Operações de IA da Foco Fiscal. Sua função é analisar as linhas de dados brutos 
        de uma planilha de planejamento semanal. Você deve interpretar as datas informadas, cruzá-las de forma 
        inteligente com o contexto de execução atual (Segunda-feira) e extrair os perfis e abas de destino 
        das tarefas que precisam ser processadas.
        """

    def analisar_cronograma_da_semana(self):
        print("📅 [Agente 1 - Planejador] Acessando o cronograma no Google Sheets...")
        
        # 1. DEFINE O NOME EXATO DA ABA AQUI (Garanta que no navegador está igualzinho)
        NOME_ABA_CRONOGRAMA = "Página1" 
        
    def analisar_cronograma_da_semana(self):
        print("📅 [Agente 1 - Planejador] Acessando o cronograma no Google Sheets...")
        
    def analisar_cronograma_da_semana(self):
        print("📅 [Agente 1 - Planejador] Acessando o cronograma no Google Sheets...")
        
        try:
            # 1. Busca os metadados - Certifique-se de que o nome da variável está idêntico ao do topo
            metadados = self.sheets.get(spreadsheetId=SPREADSHEET_ID_CRONOGRAMA).execute()
            nome_real_da_aba = metadados.get('sheets', [])[0]['properties']['title']
            
            range_dinamico = f"'{nome_real_da_aba}'!A1:E30"
            print(f"🔍 [Agente 1] Aba identificada automaticamente: {range_dinamico}")
            
            # 2. Busca os valores usando a variável correta do Cronograma
            resultado = self.sheets.values().get(
                spreadsheetId=SPREADSHEET_ID_CRONOGRAMA, 
                range=range_dinamico
            ).execute()
            
            linhas = resultado.get('values', [])
        except Exception as e:
            print(f"❌ Erro ao acessar a planilha: {e}")
            return []

        if not linhas or len(linhas) <= 1:
            print("💡 Nenhuma linha encontrada na planilha.")
            return []

        # Pega o dia da semana atual por extenso em português
        dias_semana = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
        dia_semana_hoje = dias_semana[datetime.now().weekday()]
        print(f"⏱️ [Agente 1 - Planejador] Dia da semana atual: {dia_semana_hoje}")

        print("🧠 [Agente 1 - Planejador] Enviando dados para o LLM interpretar o cronograma colado...")
        
        # O prompt agora usa o nome que foi descoberto em tempo de execução
        prompt = f"""
        Dia da Semana de Hoje: {dia_semana_hoje}
        
        Aqui estão as linhas de dados brutos extraídas da nossa aba de planejamento ({nome_real_da_aba}):
        {json.dumps(linhas, ensure_ascii=False)}
        
        Atenção: Os dias da semana na coluna 'Dia semana' podem estar colados/agrupados (Exemplo: 'Segunda-feiraTerça-feiraQuarta-feira...').
        
        Sua tarefa inteligente:
        1. Avalie a coluna de dias da semana de cada linha.
        2. Identifique se o 'Dia da Semana de Hoje' ({dia_semana_hoje}) está incluído dentro daquele texto colado e se a linha possui um 'Perfil Desejado' preenchido.
        3. Se o dia de hoje estiver contido no texto, extraia o 'Perfil Desejado' e a 'Aba' destino dessa linha.
        
        Retorne APENAS um JSON no formato:
        {{
            "tarefas": [
                {{"perfil": "Nome do Perfil", "aba_destino": "Nome da Aba"}}
            ]
        }}
        """
        
        resposta = client_openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": self.backstory},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        dados_finais = json.loads(resposta.choices[0].message.content)
        tarefas = dados_finais.get("tarefas", [])
        
        print(f"🎯 [Agente 1] Interpretação concluída. {len(tarefas)} ordens de busca validadas para {dia_semana_hoje}.")
        return tarefas

# 🤖 AGENTE 2: EXECUTOR DE MINERAÇÃO E ENRIQUECIMENTO DE DADOS
class AgenteExecutor:
    def __init__(self, sheets_client):
        self.sheets = sheets_client
        self.diretrizes_qualificacao = {
            "Advogados": {
                "obrigatorio": ["tributaria", "tributario", "tributacao", "fiscal", "tax", "imposto"],
                "cargos": ["socio", "socia", "partner", "diretor", "proprietario", "associado", "titular"],
                "bloqueado": ["civil", "familia", "trabalhista", "criminal", "previdenciario"]
            },
            "Contadores": {
                "obrigatorio": ["contador", "contadora", "contabilidade"],
                "cargos": ["socio", "dono", "proprietario", "partner"],
                "bloqueado": []
            },
            "BPO": {
                "obrigatorio": ["bpo financeiro", "gestao financeira", "terceirizacao financeira", "consultoria financeira"],
                "cargos": ["socio", "socia", "proprietario", "proprietaria", "dono", "dona", "diretor", "diretora", "gerente", "founder", "partner"],
                "bloqueado": ["analista", "assistente", "auxiliar", "estagiario"]
            }
        }

    def _normalizar_texto(self, texto):
        if not texto: return ""
        return unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii").lower()

    def _validar_lead(self, item, categoria_perfil):
        texto_lead = self._normalizar_texto(item.get("title", "") + " " + item.get("snippet", ""))
        diretriz = self.diretrizes_qualificacao.get(categoria_perfil)
        
        if not diretriz:
            return False

        sinal_area = any(x in texto_lead for x in diretriz["obrigatorio"])
        sinal_cargo = any(x in texto_lead for x in diretriz["cargos"])
        contem_sujeira = any(x in texto_lead for x in diretriz["bloqueado"])

        if categoria_perfil == "Advogados" and contem_sujeira and sinal_area:
            contem_sujeira = False

        return sinal_area and sinal_cargo and not contem_sujeira

    def executar_prospeccao(self, perfil_alvo, aba_destino, cidade_alvo="Campinas"):
        print(f"🚀 [Agente 2 - Executor] Iniciando prospecção para salvar na aba '{aba_destino}'...")

        categoria = "BPO" if "BPO" in aba_destino else ("Advogados" if "Advogado" in aba_destino else "Contadores")
        
        if categoria == "Advogados":
            query = f'site:linkedin.com/in/ "tributário" "sócio" OR "partner" "{cidade_alvo}"'
        elif categoria == "Contadores":
            query = f'site:linkedin.com/in/ "contador" "sócio" OR "dono" "{cidade_alvo}"'
        else:
            query = f'site:linkedin.com/in/ "BPO Financeiro" OR "Terceirização Financeira" "sócio" OR "diretor" OR "gerente" "{cidade_alvo}"'

        links_existentes = set()
        try:
            res_aba = self.sheets.values().get(spreadsheetId=SPREADSHEET_ID_LEADS, range=f'{aba_destino}!B2:B5000').execute()
            valores_aba = res_aba.get('values', [])
            links_existentes = {str(item[0]).strip() for item in valores_aba if item}
        except Exception:
            pass

        novos_leads = []
        for i in range(10):
            start_index = (i * 10) + 1
            url = "https://www.googleapis.com/customsearch/v1"
            params = {"key": API_KEY_GOOGLE, "cx": SEARCH_ENGINE_ID, "q": query, "start": start_index}
            
            try:
                res = requests.get(url, params=params, timeout=20)
                if res.status_code != 200: break
                items = res.json().get("items", [])
                if not items: break

                for item in items:
                    if self._validar_lead(item, categoria):
                        link = item.get("link", "").strip()
                        if link not in links_existentes:
                            titulo = item.get("title", "").strip()
                            nome = titulo.split(" - ")[0].split(" | ")[0].strip()
                            novos_leads.append([nome, link, cidade_alvo, "Novo"])
                            links_existentes.add(link)
                time.sleep(1.2)
            except Exception:
                break

        # Linha aproximada 163 (Inserção dos novos leads):
        if novos_leads:
            body = {'values': novos_leads}
            self.sheets.values().append(
                spreadsheetId=SPREADSHEET_ID_LEADS,
                range=f'{aba_destino}!A1',
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            print(f"✅ [Agente 2] {len(novos_leads)} leads novos inseridos com sucesso na aba '{aba_destino}'!")
        else:
            print(f"💡 [Agente 2] Nenhum lead novo inédito para a aba '{aba_destino}'.")


# 🔄 EXECUÇÃO DO SISTEMA MULTI-AGENTE
if __name__ == "__main__":
    try:
        print("🤖 [Sistema] Inicializando a esteira de Multi-Agentes Foco Fiscal...")
        sheets_service = obtener_servico_sheets()
        
        planejador = AgentePlanejador(sheets_service)
        executor = AgenteExecutor(sheets_service)
        
        # O Agente 1 entra na planilha nova, lê as datas e decide o plano
        plano_trabalho = planejador.analisar_cronograma_da_semana()
        
        if plano_trabalho:
            for tarefa in plano_trabalho:
                print(f"\n────────────────────────────────────────────────────────")
                perfil = tarefa.get("perfil")
                aba = tarefa.get("aba_destino")
                
                if perfil and aba:
                    # O Agente 2 executa a prospecção alimentando a aba correta online
                    executor.executar_prospeccao(perfil_alvo=perfil, aba_destino=aba, cidade_alvo="Campinas")
            print("\n✨ [Sistema] Esteira finalizada com sucesso!")
        else:
            print("\n⚠️ [Sistema] Nenhuma tarefa correspondente encontrada para esta semana.")

    except Exception as e:
        print(f"\n❌ Erro na execução global do sistema: {e}")