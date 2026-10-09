"""Tes SQL guard DuckDB (Architecture.md 5.2). Ditulis, belum dijalankan."""

import pytest

from app.infra.motherduck import SqlRejected, check_readonly_sql


def test_allows_select_on_allowlisted_mart_and_adds_limit():
    out = check_readonly_sql("SELECT ticker, close FROM finrag.mart.mart_ohlcv_1d WHERE ticker = 'BTC'")
    assert "LIMIT 500" in out.upper()


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE finrag.mart.mart_ohlcv_1d",
        "SELECT 1; SELECT 2",
        "SELECT * FROM read_parquet('s3://bucket/x.parquet')",
        "SELECT * FROM finrag.raw.raw_ohlcv",
        "SELECT * FROM 'https://example.com/x.csv'",
        "SELECT getenv('MOTHERDUCK_TOKEN')",
        "COPY finrag.mart.mart_ohlcv_1d TO '/tmp/x.csv'",
        "ATTACH 'md:other' AS o",
    ],
)
def test_rejects_unsafe_sql(sql):
    with pytest.raises(SqlRejected):
        check_readonly_sql(sql)
