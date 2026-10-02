from strattester.strategies.builtin.legacy_grid import BacktestConfig,BacktestEngine,LevelSeed,MinuteCandle

def C(t,o,h,l,c): return MinuteCandle(t,o,h,l,c,1,1)

def test_high_level_strict_break_and_tp():
    e=BacktestEngine('X',BacktestConfig(taker_fee=0))
    e.add_level(LevelSeed('1H','HIGH',100,0,0))
    e.process_minute(C(60_000,99,99.6,98.9,99.5))
    assert len(e.open_positions)==1
    e.process_minute(C(120_000,99.5,100.0,99.2,99.8))
    assert not next(iter(e.levels.values())).broken
    e.process_minute(C(180_000,99.8,101.1,99.7,100.8))
    assert next(iter(e.levels.values())).broken
    assert e.closed_trades[0].exit_reason=='TP'

def test_stop_rearms_unbroken_level():
    e=BacktestEngine('X',BacktestConfig(taker_fee=0))
    e.add_level(LevelSeed('1H','HIGH',100,0,0))
    e.process_minute(C(60_000,99,99.6,98.9,99.5))
    e.process_minute(C(120_000,99.4,99.6,98.0,98.4))
    assert e.closed_trades[-1].exit_reason=='SL'
    e.process_minute(C(180_000,98.4,99.6,98.2,99.5))
    assert len(e.open_positions)==1

def test_intrabar_entry_cannot_exit_same_minute():
    e=BacktestEngine('X',BacktestConfig(taker_fee=0))
    e.add_level(LevelSeed('1H','HIGH',100,0,0))
    e.process_minute(C(60_000,99.0,101.0,97.0,99.0))
    assert len(e.open_positions)==1
    assert e.closed_trades==[]

def test_gap_stop_uses_worse_open_fill():
    e=BacktestEngine('X',BacktestConfig(taker_fee=0))
    e.add_level(LevelSeed('1H','HIGH',100,0,0))
    e.process_minute(C(60_000,99.5,99.6,99.4,99.5))
    trade=next(iter(e.open_positions.values()))
    e.process_minute(C(120_000,98.0,99.0,97.8,98.5))
    assert e.closed_trades[0].exit_reason=='SL'
    assert e.closed_trades[0].exit_price==98.0
    assert e.closed_trades[0].exit_price<trade.stop_loss

def test_reversal_high_can_open_short():
    e=BacktestEngine('X',BacktestConfig(allowed_level_types=('HIGH',),high_direction='SHORT',taker_fee=0))
    e.add_level(LevelSeed('1H','HIGH',100,0,0))
    e.process_minute(C(60_000,99.0,99.6,98.9,99.5))
    assert next(iter(e.open_positions.values())).direction=='SHORT'
