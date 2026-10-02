from strattester.marketdata.l2_recorder import L2Book,L2AbsorptionDetector

def test_wall_requires_relative_depth_and_persistence():
    book=L2Book(tick_size=.01,wall_multiple=3)
    book.snapshot(100,[['100.00','50'],['99.99','10'],['99.98','12']],[['100.01','8']])
    book.delta(200,bids=[['100.00','48']],asks=[])
    wall=book.wall_at(100.00,'bid',now=200,min_persistence_ms=100)
    assert wall is not None and wall.multiple>=3

def test_removed_wall_is_marked_spoof_candidate():
    book=L2Book(tick_size=.01,wall_multiple=3)
    book.snapshot(100,[['100.00','50'],['99.99','10'],['99.98','10']],[['100.01','8']])
    book.delta(150,bids=[['100.00','0']],asks=[])
    assert book.was_removed(100.00,'bid',since=100)

def test_true_l2_absorption_needs_wall_trade_hits_and_replenishment():
    d=L2AbsorptionDetector(tick_size=.01,wall_multiple=3)
    d.on_snapshot(100,[['100.00','50'],['99.99','10'],['99.98','10']],[['100.01','10']])
    d.on_trade(110,100.00,15,'Sell')
    d.on_delta(120,bids=[['100.00','45']],asks=[])
    d.on_trade(130,100.00,15,'Sell')
    x=d.signal(level=100.00,side='long',now=140,min_executed=20,min_replenishment=10)
    assert x is not None
    assert x.executed_at_level>=30
    assert x.replenished>=10
