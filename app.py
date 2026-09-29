from __future__ import annotations

from typing import BinaryIO

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st


st.set_page_config(page_title="Fintech | Monitor de transações", page_icon="📊", layout="wide")

RISK_BY_CLIENT = {
    "C100": "Baixo",
    "C101": "Alto",
    "C102": "Médio",
    "C103": "Alto",
    "C104": "Baixo",
}
TRANSACTION_COLUMNS = {"id_cliente", "data_transacao", "valor", "origem", "estado_cliente"}
QUOTE_COLUMNS = {"data", "cotacao_usd", "volume_negociado"}


def read_csv(source: BinaryIO, encoding: str) -> pd.DataFrame:
    """Read a CSV upload using its expected legacy or UTF-8 encoding."""
    return pd.read_csv(source, encoding=encoding)


def process_data(transactions: pd.DataFrame, quotes: pd.DataFrame) -> dict[str, pd.DataFrame]:
    missing = TRANSACTION_COLUMNS.difference(transactions.columns)
    if missing:
        raise ValueError(f"Colunas ausentes em transacoes.csv: {', '.join(sorted(missing))}")
    missing_quotes = QUOTE_COLUMNS.difference(quotes.columns)
    if missing_quotes:
        raise ValueError(f"Colunas ausentes em cotacoes.csv: {', '.join(sorted(missing_quotes))}")

    tx = transactions.copy()
    tx["valor"] = pd.to_numeric(tx["valor"], errors="coerce")
    tx["data_transacao"] = pd.to_datetime(tx["data_transacao"], errors="coerce")
    if tx["data_transacao"].isna().any():
        raise ValueError("Há datas inválidas ou vazias em data_transacao.")
    if tx["data_transacao"].dt.tz is None:
        tx["data_transacao"] = tx["data_transacao"].dt.tz_localize("America/Sao_Paulo")
    else:
        tx["data_transacao"] = tx["data_transacao"].dt.tz_convert("America/Sao_Paulo")

    tx["valor"] = tx["valor"].fillna(tx.groupby("estado_cliente")["valor"].transform("median"))
    tx["plataforma"] = "Mobile"
    tx["dia_semana"] = tx["data_transacao"].dt.day_name()
    tx["mes"] = tx["data_transacao"].dt.month
    tx = tx.drop_duplicates(keep="first").reset_index(drop=True)
    tx["nivel_risco"] = tx["id_cliente"].map(RISK_BY_CLIENT).fillna("Não mapeado")

    setembro_sp_rj = tx.loc[
        (tx["mes"] == 9)
        & ((tx["estado_cliente"] == "SP") | (tx["estado_cliente"] == "RJ"))
        & (tx["valor"] > 5000)
    ].copy()
    pivot = pd.pivot_table(
        tx,
        index="mes",
        columns="nivel_risco",
        values="valor",
        aggfunc="sum",
        margins=True,
        margins_name="Total",
        fill_value=0,
    )

    state_stats = tx.groupby("estado_cliente")["valor"]
    std = state_stats.transform("std").replace(0, np.nan)
    tx["z_score"] = (tx["valor"] - state_stats.transform("mean")) / std
    anomalies = tx.loc[tx["z_score"] > 2.5].copy()

    daily = tx.set_index("data_transacao").resample("D")["valor"].sum().rename("total_diario").to_frame()
    daily["media_movel_7d"] = daily["total_diario"].rolling(7, min_periods=1).mean()

    q = quotes.copy()
    q["data"] = pd.to_datetime(q["data"], errors="coerce").dt.normalize()
    q["data"] = q["data"].dt.tz_localize("America/Sao_Paulo")
    q["cotacao_usd"] = pd.to_numeric(q["cotacao_usd"], errors="coerce")
    q["volume_negociado"] = pd.to_numeric(q["volume_negociado"], errors="coerce")
    q = q.dropna(subset=["data"]).drop_duplicates(subset=["data"], keep="first")
    daily = daily.join(q.set_index("data")[["cotacao_usd", "volume_negociado"]], how="left")

    return {
        "transacoes": tx,
        "filtro_setembro": setembro_sp_rj,
        "pivot_risco": pivot,
        "anomalias": anomalies,
        "diario": daily,
    }


def money(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


st.title("Análise de transações")
st.caption("Tratamento dos registros, volume diário e transações fora do padrão.")

with st.sidebar:
    st.header("Dados de entrada")
    transaction_file = st.file_uploader("transacoes.csv (Latin-1)", type="csv", key="tx")
    quote_file = st.file_uploader("cotacoes.csv (UTF-8)", type="csv", key="quotes")
    st.divider()
    st.caption("Gere os dois CSVs com `python criar_dados.py` e selecione-os aqui.")

if not transaction_file or not quote_file:
    st.info("Para começar, carregue os arquivos transacoes.csv e cotacoes.csv na barra lateral.")
    st.markdown(
        "**Formato esperado**  \n"
        "Transações: `id_cliente`, `data_transacao`, `valor`, `origem`, `estado_cliente`.  \n"
        "Cotações: `data`, `cotacao_usd`, `volume_negociado`."
    )
    st.stop()

try:
    raw_tx = read_csv(transaction_file, "latin1")
    raw_quotes = read_csv(quote_file, "utf-8")
    result = process_data(raw_tx, raw_quotes)
except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
    st.error(f"Não foi possível processar os arquivos: {exc}")
    st.stop()

tx = result["transacoes"]
daily = result["diario"]
total = tx["valor"].sum()
median = tx["valor"].median()
anomaly_count = len(result["anomalias"])

k1, k2, k3, k4 = st.columns(4)
k1.metric("Transações válidas", f"{len(tx):,}".replace(",", "."))
k2.metric("Volume processado", money(total))
k3.metric("Ticket mediano", money(median))
k4.metric("Sinais Z-Score > 2,5", f"{anomaly_count}")

    st.subheader("Movimentação por dia")
fig, ax = plt.subplots(figsize=(12, 4.5))
ax.plot(daily.index, daily["total_diario"], label="Total diário", color="#2374AB", linewidth=1.8)
ax.plot(daily.index, daily["media_movel_7d"], label="Média móvel de 7 dias", color="#F18F01", linewidth=2)
ax.set_ylim(bottom=0)
ax.set_title("Volume transacionado por dia")
ax.set_ylabel("Valor (R$)")
ax.set_xlabel("Data")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
ax.grid(axis="y", alpha=0.25)
ax.legend()
fig.tight_layout()
st.pyplot(fig, use_container_width=True)
plt.close(fig)

left, right = st.columns(2)
with left:
    st.subheader("Soma por mês e nível de risco")
    st.dataframe(result["pivot_risco"].style.format(money), use_container_width=True)
with right:
    st.subheader("Cruzamento com cotações")
    quote_view = daily.dropna(subset=["cotacao_usd"])[["cotacao_usd", "volume_negociado"]]
    if quote_view.empty:
        st.caption("Não há datas de cotação coincidentes com as transações.")
    else:
        st.dataframe(quote_view.style.format({"cotacao_usd": "R$ {:.4f}", "volume_negociado": "{:,.0f}"}), use_container_width=True)

tab1, tab2, tab3 = st.tabs(["Filtro de setembro", "Anomalias", "Dados tratados"])
with tab1:
    st.caption("Setembro, SP ou RJ e valor acima de R$ 5.000,00.")
    st.dataframe(result["filtro_setembro"], use_container_width=True, hide_index=True)
with tab2:
    st.caption("Z-Score calculado dentro de cada estado; registros acima de 2,5 são exibidos.")
    st.dataframe(result["anomalias"], use_container_width=True, hide_index=True)
with tab3:
    st.caption("Dados deduplicados, imputados por mediana estadual, com fuso America/Sao_Paulo e risco mapeado.")
    st.dataframe(tx, use_container_width=True, hide_index=True)

csv_bytes = tx.to_csv(index=False).encode("utf-8-sig")
st.download_button("Baixar transações tratadas (CSV)", data=csv_bytes, file_name="transacoes_tratadas.csv", mime="text/csv")
