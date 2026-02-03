# Microsoft End of Support Scraper 🚀

Este projeto é um **web scraper automatizado** desenvolvido em **Python** para coletar informações sobre o **fim do ciclo de vida (End of Support)** de produtos Microsoft diretamente da **documentação oficial**.  
Os dados coletados são processados, versionados e armazenados em um **banco de dados SQL Server**, garantindo rastreabilidade e histórico de execuções.

---

## 📋 Funcionalidades

- **Scraping Inteligente**  
  Coleta produtos Microsoft que perderão suporte nos **próximos 5 anos**.

- **Persistência em SQL Server**  
  Armazena os dados de forma estruturada.

- **Controle de Versão**  
  Identifica se um produto já existe no banco e atualiza apenas quando há mudança na data de fim de suporte.

- **Logs Detalhados**  
  Geração de logs em arquivo (`scraper.log`) e no console para monitoramento de execução e erros.

- **Rastreabilidade**  
  Tabela de execuções para auditar quando o scraper rodou e quantos registros foram processados.

---

## 🛠️ Tecnologias Utilizadas

- Python 3.x  
- **BeautifulSoup4** – Parsing de HTML  
- **Requests** – Requisições HTTP  
- **PyODBC** – Conexão com SQL Server  
- **Python-dotenv** – Gerenciamento de variáveis de ambiente  

---

## ⚙️ Configuração e Instalação

### 1️⃣ Pré-requisitos

- Python instalado  
- Driver ODBC para SQL Server  
  - Exemplo: **Microsoft ODBC Driver 17 for SQL Server**
- Banco de dados SQL Server disponível

---

### 2️⃣ Instalação das Dependências

```bash
pip install requests beautifulsoup4 pyodbc python-dotenv
```

## 3️⃣ Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com as credenciais do banco de dados:

```env
DB_SERVER=seu_servidor
DB_NAME=seu_banco_de_dados
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
DB_DRIVER={ODBC Driver 17 for SQL Server}
```

## 🗄️ Estrutura do Banco de Dados

O projeto utiliza duas tabelas principais para **persistência** e **auditoria** das execuções do scraper.

---

### 🔹 `execucoes_scraper`

Responsável pelo controle e rastreabilidade das execuções do scraper:

- Data e hora da execução  
- Status da execução (sucesso ou erro)  
- Total de registros processados  

---

### 🔹 `produtos_endsupport`

Armazena as informações referentes ao fim de suporte dos produtos Microsoft:

- Nome do produto  
- Ano de referência  
- Data exata do fim do suporte  
- Identificador da execução relacionada  

> ⚠️ **Importante**  
> Na primeira execução, descomente o bloco de criação de tabelas dentro da função `criar_tabelas()`  
> ou crie as tabelas manualmente conforme a estrutura definida no código.

---

## 🚀 Como Executar

Execute o script principal do projeto:

```bash
python main.py
```

Durante a execução, o scraper irá:

1. Validar a conexão com o SQL Server  
2. Percorrer as páginas oficiais da Microsoft referentes aos próximos 5 anos  
3. Comparar os dados coletados com os registros existentes  
4. Inserir ou atualizar somente os registros alterados  
5. Registrar a execução e exibir um resumo no console  

---

## 📝 Logs e Monitoramento

Os logs são gerados automaticamente em dois formatos:

### 🔹 Console
- Acompanhamento em tempo real da execução  

### 🔹 Arquivo (`scraper.log`)
- Histórico completo de erros, warnings e informações  
- Ideal para auditoria e depuração  

---

## 📈 Boas Práticas e Recomendações

- Executar o scraper via:
  - Task Scheduler (Windows)
  - Cron (Linux)
  - Azure Automation / Data Factory

- Integrar os dados com:
  - Power BI
  - Data Warehouse
  - Processos de governança de TI

- Versionar alterações no scraper junto com:
  - Mudanças de layout da documentação da Microsoft
  - Ajustes de regras de negócio

---

## 📄 Licença

Projeto de uso **interno / educacional**.
