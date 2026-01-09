import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import pyodbc
import logging
from typing import List, Dict
import os
from dotenv import load_dotenv

# # Carrega variáveis de ambiente
load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)

# ===== CONFIGURAÇÕES DO BANCO DE DADOS =====
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
    
    print(f"\nString de conexão: {conn_str}")
    
    try:
        print("Tentando conectar ao banco de dados...")
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        print("✓ Conexão bem sucedida!")
        
        # Tabela de execuções
        '''print("\nVerificando tabela 'execucoes_scraper'...")
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='execucoes_scraper' AND xtype='U')
            CREATE TABLE execucoes_scraper (
                id INT IDENTITY(1,1) PRIMARY KEY,
                data_execucao DATETIME NOT NULL,
                status VARCHAR(50) NOT NULL,
                total_produtos INT,
                total_erros INT,
                mensagem VARCHAR(MAX)
            )
        """)
        print("✓ Tabela 'execucoes_scraper' verificada/criada")
        
        # Tabela de produtos
        print("Verificando tabela 'produtos_endsupport'...")
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='produtos_endsupport' AND xtype='U')
            CREATE TABLE produtos_endsupport (
                id INT IDENTITY(1,1) PRIMARY KEY,
                ano INT NOT NULL,
                nome_produto VARCHAR(500) NOT NULL,
                data_fim_suporte VARCHAR(100),
                url VARCHAR(500),
                data_coleta DATETIME NOT NULL,
                CONSTRAINT UK_produto_ano UNIQUE(nome_produto, ano, data_coleta)
            )
        """)
        print("✓ Tabela 'produtos_endsupport' verificada/criada")
        
        conn.commit()
        print("\n✓ Tabelas criadas/verificadas com sucesso")
        '''
    except Exception as e:
        print(f"\n✗ ERRO ao conectar/criar tabelas: {e}")
        print(f"Tipo do erro: {type(e).__name__}")
        logging.error(f"Erro ao criar tabelas: {e}")
        raise
    finally:

        if conn:
            conn.close()
            print("Conexão fechada")

def scrape_microsoft_endsupport(ano: int) -> Dict:
    """
    Faz o scraping da página de End of Support da Microsoft
    tratando corretamente múltiplos produtos por linha.
    """
    url = f"https://learn.microsoft.com/en-us/lifecycle/end-of-support/end-of-support-{ano}"

    print(f"\n{'='*60}")
    print(f"SCRAPING ANO: {ano}")
    print(f"URL: {url}")
    print(f"{'='*60}")

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

        # Percorre todas as tabelas da página
        for tabela in soup.find_all("table"):
            for linha in tabela.select("tbody tr"):
                colunas = linha.find_all("td")

                # Precisa ter pelo menos produto + data
                if len(colunas) < 2:
                    continue

                data_fim = colunas[1].get_text(strip=True)

                # Cada <a> representa um produto
                produtos = colunas[0].find_all(
                    "a",
                    attrs={"data-linktype": "absolute-path"}
                )

                for a in produtos:
                    nome_produto = a.get_text(strip=True)
                    href = a.get("href")

                    dados["produtos"].append({
                        "nome": nome_produto,
                        "data_fim_suporte": data_fim,
                        "url_produto": f"https://learn.microsoft.com{href}" if href else None
                    })

        print(f"✓ Produtos encontrados em {ano}: {len(dados['produtos'])}")
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
    
    total_produtos = 0
    total_erros = 0
    data_execucao = datetime.now()
    
    print(f"\n{'='*80}")
    print("INICIANDO PROCESSO DE SALVAR NO BANCO")
    print(f"Data/Hora: {data_execucao}")
    print(f"Total de anos processados: {len(resultados)}")
    print(f"{'='*80}")
    
    # Primeiro, apenas mostra o que seria inserido
    print("\nPRÉVIA DOS DADOS PARA INSERÇÃO:")
    
    for idx, resultado in enumerate(resultados, 1):
        ano = resultado['ano']
        url = resultado['url']
        
        print(f"\n[{idx}] ANO {ano}:")
        print(f"   URL: {url}")
        
        if 'erro' in resultado:
            print(f"   ✗ ERRO: {resultado['erro']}")
            total_erros += 1
            continue
        
        print(f"   ✓ Título: {resultado['titulo']}")
        print(f"   ✓ Produtos encontrados: {len(resultado['produtos'])}")
        
        # Mostra os primeiros 3 produtos como exemplo
        for i, produto in enumerate(resultado['produtos'][:3], 1):
            print(f"      Exemplo {i}: {produto['nome'][:60]}... | {produto['data_fim_suporte']}")
        
        if len(resultado['produtos']) > 3:
            print(f"      ... e mais {len(resultado['produtos']) - 3} produtos")
    
    print(f"\n{'='*80}")
    print("RESUMO PARA INSERÇÃO:")
    print(f"Total de anos processados: {len(resultados)}")
    print(f"Total de produtos para inserir: {sum(len(r['produtos']) for r in resultados if 'erro' not in r)}")
    print(f"Total de erros: {sum(1 for r in resultados if 'erro' in r)}")
    
    # Pergunta se deve realmente inserir
    resposta = input("\nDeseja realmente inserir no banco? (s/n): ").lower().strip()
    
    if resposta != 's':
        print("Inserção cancelada pelo usuário.")
        return 0, 0
    
    print("\nIniciando inserção no banco...")
    
    try:
        print("Conectando ao banco...")
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        print("✓ Conexão estabelecida")
        
        for resultado in resultados:
            ano = resultado['ano']
            url = resultado['url']
            
            if 'erro' in resultado:
                total_erros += 1
                print(f"\n✗ Pulando ano {ano} devido a erro: {resultado['erro']}")
                continue
            
            print(f"\nProcessando ano {ano} ({len(resultado['produtos'])} produtos):")
            
            for produto in resultado['produtos']:
                try:
                    # Mostra o que está sendo inserido
                    print(f"  → Produto: {produto['nome'][:50]}...")
                    print(f"    Data Fim: {produto['data_fim_suporte']}")
                    
                    cursor.execute("""
                        INSERT INTO produtos_endsupport (ano, nome_produto, data_fim_suporte, url, data_coleta)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        ano,
                        produto['nome'],
                        produto['data_fim_suporte'],
                        url,
                        data_execucao
                    ))

                    total_produtos += 1
                    
                except pyodbc.IntegrityError:
                    print(f"    ⚠ Produto já existe, ignorando...")
                except Exception as e:
                    print(f"    ✗ Erro ao inserir: {e}")
        
        # Registra a execução
        print(f"\nRegistrando execução na tabela 'execucoes_scraper'...")
        cursor.execute("""
            INSERT INTO execucoes_scraper (data_execucao, status, total_produtos, total_erros, mensagem)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data_execucao,
            'SUCESSO' if total_erros == 0 else 'SUCESSO_COM_ERROS',
            total_produtos,
            total_erros,
            f'Processados {len(resultados)} anos'
        ))
        
        conn.commit()
        
        print(f"\n✓ Simulação concluída!")
        print(f"✓ Produtos que seriam inseridos: {total_produtos}")
        print(f"✓ Erros: {total_erros}")
        
        return total_produtos, total_erros
        
    except Exception as e:
        print(f"\n✗ ERRO ao conectar/salvar no banco: {e}")
        print(f"Tipo do erro: {type(e).__name__}")
        logging.error(f"Erro ao salvar no banco: {e}")
        
        raise
    finally:
        if conn:
            conn.close()
            print("Conexão com o banco fechada")

def executar_scraping():
    """Função principal que executa todo o processo."""
    print("=" * 80)
    print("MICROSOFT END OF SUPPORT - SCRAPER TOOL")
    print("=" * 80)
    
    logging.info("=" * 60)
    logging.info("Iniciando scraping...")
    
    try:
        print("\nETAPA 1: Verificando/Criando tabelas no banco")
        print("-" * 60)
        criar_tabelas()
        
        print("\n\nETAPA 2: Coletando dados do site da Microsoft")
        print("-" * 60)
        
        # Define período (próximos 5 anos)
        ano_atual = datetime.now().year
        anos = list(range(ano_atual, ano_atual + 5))
        
        print(f"Anos que serão processados: {anos}")
        
        resultados = []
        
        for ano in anos:
            print(f"\nProcessando ano {ano}...")
            dados = scrape_microsoft_endsupport(ano)
            resultados.append(dados)
            
            if 'erro' not in dados:
                print(f"✓ Concluído: {len(dados['produtos'])} produtos encontrados")
            else:
                print(f"✗ Falhou: {dados['erro']}")
            
            # Pausa entre requisições (para não sobrecarregar o servidor)
            if ano != anos[-1]:
                print("Aguardando 2 segundos...")
                time.sleep(2)
        
        print("\n\nETAPA 3: Salvando dados no banco")
        print("-" * 60)
        total_produtos, total_erros = salvar_no_banco(resultados)
        
        print("\n" + "=" * 80)
        print("RESUMO FINAL DA EXECUÇÃO")
        print("=" * 80)
        print(f"Total de anos processados: {len(resultados)}")
        print(f"Produtos coletados: {total_produtos}")
        print(f"Erros encontrados: {total_erros}")

        
    except Exception as e:
        print(f"\n✗ ERRO FATAL: {e}")
        print("=" * 80)
        logging.error(f"Erro fatal na execução: {e}")
        raise

if __name__ == "__main__":
    executar_scraping()
