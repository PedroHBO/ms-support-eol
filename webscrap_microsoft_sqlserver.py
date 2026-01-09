import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import pyodbc
import logging
from typing import List, Dict
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)

DB_CONFIG = {
    'server': os.getenv('DB_SERVER'),
    'database': os.getenv('DB_NAME'),
    'username': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'driver': os.getenv('DB_DRIVER', '{ODBC Driver 17 for SQL Server}')
}

def criar_tabelas():
    """Cria as tabelas necessárias no SQL Server se não existirem."""
    conn_str = (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']}"
    )
    
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        # Se tiver acesso de CRIAR TABELAS pode descomentar.
        #
        # Tabela de execuções
        # cursor.execute("""
        #     IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='execucoes_scraper' AND xtype='U')
        #     CREATE TABLE execucoes_scraper (
        #         id INT IDENTITY(1,1) PRIMARY KEY,
        #         data_execucao DATETIME NOT NULL,
        #         status VARCHAR(50) NOT NULL,
        #         total_inseridos INT DEFAULT 0,
        #         total_atualizados INT DEFAULT 0,
        #         total_existentes INT DEFAULT 0,
        #         total_erros INT DEFAULT 0,
        #         mensagem VARCHAR(MAX)
        #     )
        # """)
        
        # # Tabela de produtos
        # cursor.execute("""
        #     IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='produtos_endsupport' AND xtype='U')
        #     CREATE TABLE produtos_endsupport (
        #         id INT IDENTITY(1,1) PRIMARY KEY,
        #         ano SMALLINT NOT NULL,
        #         nome_produto VARCHAR(500) NOT NULL,
        #         data_fim_suporte VARCHAR(100),
        #         execucao_id INT NULL,
        #         data_coleta DATETIME NOT NULL,
        #         FOREIGN KEY (execucao_id) REFERENCES execucoes_scraper(id)
        #     )
        # """)
        
        conn.commit()
        logging.info("Tabelas verificadas/criadas com sucesso")
        
    except Exception as e:
        logging.error(f"Erro ao criar tabelas: {e}")
        raise
    finally:
        if conn:
            conn.close()

def scrape_microsoft_endsupport(ano: int) -> Dict:
    """Faz o scraping da página de End of Support da Microsoft."""
    url = f"https://learn.microsoft.com/en-us/lifecycle/end-of-support/end-of-support-{ano}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        
        titulo_tag = soup.find("h1")
        titulo = titulo_tag.get_text(strip=True) if titulo_tag else "Não encontrado"
        
        dados = {
            "ano": ano,
            "url": url,
            "titulo": titulo,
            "produtos": []
        }
        
        for tabela in soup.find_all("table"):
            for linha in tabela.select("tbody tr"):
                colunas = linha.find_all("td")
                
                if len(colunas) < 2:
                    continue
                
                data_fim = colunas[1].get_text(strip=True)
                produtos = colunas[0].find_all("a", attrs={"data-linktype": "absolute-path"})
                
                for a in produtos:
                    nome_produto = a.get_text(strip=True)
                    href = a.get("href")
                    dados["produtos"].append({
                        "nome": nome_produto,
                        "data_fim_suporte": data_fim,
                        "url_produto": f"https://learn.microsoft.com{href}" if href else None
                    })
        
        logging.info(f"Ano {ano}: {len(dados['produtos'])} produtos encontrados")
        return dados
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao acessar {url}: {e}")
        return {
            "ano": ano,
            "url": url,
            "erro": str(e),
            "produtos": []
        }

def salvar_no_banco(resultados: List[Dict]) -> tuple:
    """Salva os resultados no SQL Server."""
    conn_str = (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']}"
    )
    
    total_inseridos = 0
    total_atualizados = 0
    total_existentes = 0
    total_erros = 0
    data_execucao = datetime.now()
    execucao_id = None
    
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Registra a execução primeiro para obter o ID
        cursor.execute("""
            INSERT INTO execucoes_scraper (data_execucao, status, mensagem)
            VALUES (?, 'EM_ANDAMENTO', 'Processando...')
        """, (data_execucao,))
        
        cursor.execute("SELECT @@IDENTITY")
        execucao_id = cursor.fetchone()[0]
        conn.commit()
        
        for resultado in resultados:
            ano = resultado['ano']
            
            if 'erro' in resultado:
                total_erros += 1
                continue
            
            for produto in resultado['produtos']:
                try:
                    # Verifica se o produto já existe
                    cursor.execute("""
                        SELECT id, data_fim_suporte 
                        FROM produtos_endsupport 
                        WHERE nome_produto = ? AND ano = ?
                    """, (produto['nome'], ano))
                    
                    registro_existente = cursor.fetchone()
                    
                    if registro_existente:
                        # Verifica se houve mudança na data
                        if registro_existente[1] != produto['data_fim_suporte']:
                            cursor.execute("""
                                UPDATE produtos_endsupport
                                SET data_fim_suporte = ?,
                                    execucao_id = ?,
                                    data_coleta = GETDATE()
                                WHERE id = ?
                            """, (produto['data_fim_suporte'], execucao_id, registro_existente[0]))
                            total_atualizados += 1
                        else:
                            total_existentes += 1
                    else:
                        # Insere novo registro
                        cursor.execute("""
                            INSERT INTO produtos_endsupport 
                            (nome_produto, ano, data_fim_suporte, execucao_id, data_coleta)
                            VALUES (?, ?, ?, ?, GETDATE())
                        """, (produto['nome'], ano, produto['data_fim_suporte'], execucao_id))
                        total_inseridos += 1
                        
                except Exception as e:
                    logging.error(f"Erro ao processar produto '{produto['nome']}': {e}")
                    total_erros += 1
        
        # Atualiza o registro de execução com os totais
        status = 'SUCESSO' if total_erros == 0 else 'SUCESSO_COM_ERROS'
        cursor.execute("""
            UPDATE execucoes_scraper
            SET status = ?,
                total_inseridos = ?,
                total_atualizados = ?,
                total_existentes = ?,
                total_erros = ?,
                mensagem = ?
            WHERE id = ?
        """, (
            status,
            total_inseridos,
            total_atualizados,
            total_existentes,
            total_erros,
            f'Processados {len(resultados)} anos',
            execucao_id
        ))
        
        conn.commit()
        
        return total_inseridos, total_atualizados, total_existentes, total_erros
        
    except Exception as e:
        logging.error(f"Erro ao salvar no banco: {e}")
        raise
    finally:
        if conn:
            conn.close()

def executar_scraping():
    """Função principal que executa todo o processo."""
    logging.info("="*60)
    logging.info("Iniciando Microsoft End of Support Scraper")
    logging.info("="*60)
    
    try:
        criar_tabelas()
        
        # Scraping dos próximos 5 anos
        ano_atual = datetime.now().year
        anos = list(range(ano_atual, ano_atual + 5))
        
        logging.info(f"Coletando dados dos anos: {anos}")
        
        resultados = []
        for ano in anos:
            dados = scrape_microsoft_endsupport(ano)
            resultados.append(dados)
            
            if ano != anos[-1]:
                time.sleep(2)
        
        # Salva no banco
        total_inseridos, total_atualizados, total_existentes, total_erros = salvar_no_banco(resultados)
        
        # Resumo final
        logging.info("="*60)
        logging.info("RESUMO DA EXECUÇÃO")
        logging.info("="*60)
        logging.info(f"Novos produtos inseridos: {total_inseridos}")
        logging.info(f"Produtos atualizados: {total_atualizados}")
        logging.info(f"Produtos já existentes (sem alteração): {total_existentes}")
        logging.info(f"Erros encontrados: {total_erros}")
        logging.info(f"Total processado: {total_inseridos + total_atualizados + total_existentes}")
        logging.info("="*60)
        
    except Exception as e:
        logging.error(f"Erro fatal na execução: {e}")
        raise

if __name__ == "__main__":
    executar_scraping()
