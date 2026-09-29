# Análise de transações

Aplicação em Streamlit para processar os arquivos `transacoes.csv` e `cotacoes.csv` do exercício.

## Como executar

Use Python 3.10 ou mais recente:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python criar_dados.py
streamlit run app.py
```

Depois, carregue os dois arquivos gerados na barra lateral. O arquivo de transações é lido em Latin-1; o de cotações, em UTF-8.

O painel remove duplicatas, preenche valores ausentes pela mediana do estado, ajusta as datas para `America/Sao_Paulo`, calcula a pivot table por risco e destaca registros com Z-Score acima de 2,5. Também mostra o total diário e a média móvel de sete dias.

Os níveis de risco usados no exemplo estão no dicionário `RISK_BY_CLIENT` em `app.py` e podem ser atualizados conforme os dados disponíveis.
