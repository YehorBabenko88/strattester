"""Adversarial shape admission tests; no GPU or network required."""
import pytest
from strattester.research.alphafold_security import admit_pair_shape, PairBudget

@pytest.mark.parametrize("shape", [(0, 10, 8), (-1, 10, 8), (1, 1025, 8), (9, 10, 8), (True, 10, 8)])
def test_reject_invalid_or_oversized(shape):
    with pytest.raises(ValueError):
        admit_pair_shape(*shape)

def test_quadratic_memory_growth():
    a = admit_pair_shape(1, 16, 8)
    b = admit_pair_shape(1, 32, 8)
    assert b == 4 * a

def test_budget_fails_closed():
    with pytest.raises(ValueError):
        admit_pair_shape(1, 256, 32, budget=PairBudget(max_pair_bytes=1024))

@pytest.mark.parametrize('budget', [PairBudget(max_pair_bytes=-1), PairBudget(max_tokens=0), PairBudget(activation_multiplier=0)])
def test_invalid_policy_is_rejected(budget):
    with pytest.raises(ValueError):
        admit_pair_shape(1, 8, 8, budget=budget)


def test_sqlite_uri_escaping(tmp_path):
    import sqlite3
    from strattester.research.protein_geometry_snapshot import readonly_candles
    db = tmp_path / 'candles #1?.sqlite'
    con = sqlite3.connect(db)
    con.execute('CREATE TABLE candles (symbol TEXT, timeframe TEXT, open_time INTEGER, close REAL, complete INTEGER)')
    con.execute("INSERT INTO candles VALUES ('BTCUSDT','1m',1000,12.5,1)")
    con.commit()
    con.close()
    with readonly_candles(db, 'BTCUSDT') as rows:
        assert rows == ((1000, 12.5),)


def test_dataset_rejects_duplicate_and_reverse_timestamps():
    from strattester.research.financial_structure_dataset import make_samples
    for timestamps in ((1, 2, 2, 4, 5, 6, 7, 8), (1, 3, 2, 4, 5, 6, 7, 8)):
        with pytest.raises(ValueError, match='timestamps'):
            make_samples('BTCUSDT', '1m', timestamps, [100.0] * len(timestamps), window=3, horizon=2)
