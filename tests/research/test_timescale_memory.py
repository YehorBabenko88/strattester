from strattester.research.timescale_memory import MultiTimescaleMemory

def test_short_memory_reacts_without_becoming_long_term():
    m=MultiTimescaleMemory()
    m.add("a",1,"HIGH")
    x=m.state("a","HIGH")
    assert x.short_signal==1 and x.long_samples==1
    assert m.consolidation_candidate("a","HIGH") is None

def test_regime_memories_are_separate():
    m=MultiTimescaleMemory()
    for _ in range(5):m.add("a",1,"HIGH")
    for _ in range(5):m.add("a",-1,"LOW")
    assert m.state("a","HIGH").regime_signal>0
    assert m.state("a","LOW").regime_signal<0

def test_reactive_modifier_is_bounded():
    m=MultiTimescaleMemory()
    for _ in range(20):m.add("a",100,"HIGH")
    assert m.reactive_modifier("a","HIGH",cap=.2)==.2

def test_long_term_candidate_requires_enough_history():
    m=MultiTimescaleMemory()
    for _ in range(15):m.add("a",1,"HIGH")
    assert m.consolidation_candidate("a","HIGH",min_long_samples=16) is None
    m.add("a",1,"HIGH")
    assert m.consolidation_candidate("a","HIGH",min_long_samples=16)>0

def test_regime_lifetime_disagreement_blocks_consolidation():
    m=MultiTimescaleMemory(regime_decay=0,long_decay=.99)
    for _ in range(20):m.add("a",1,"HIGH")
    for _ in range(20):m.add("a",-1,"LOW")
    assert m.consolidation_candidate("a","LOW",min_long_samples=16,agreement_tolerance=.1) is None
