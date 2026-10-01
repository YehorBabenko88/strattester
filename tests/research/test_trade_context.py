from strattester.research.trade_context import attach_entry_context
from strattester.research.volatility import VolatilitySnapshot,VolatilityRegime
from strattester.research.volume_profile import VolumeProfileSnapshot,POCMode

def test_entry_context_uses_latest_snapshot_known_at_entry():
    vols=[
      VolatilitySnapshot(0,60,.01,.01,.01,.02,1,1,.5,VolatilityRegime.NORMAL,'v1'),
      VolatilitySnapshot(60,120,.02,.02,.02,.03,2,2,.9,VolatilityRegime.EXTREME,'v1'),
    ]
    profiles=[
      VolumeProfileSnapshot(100,102,98,60,POCMode.TRADE_POC,4),
      VolumeProfileSnapshot(110,112,108,180,POCMode.TRADE_POC,4),
    ]
    m=attach_entry_context(entry_time=120,metadata={},volatility=vols,profiles=profiles)
    assert m['volatility_regime']=='EXTREME'
    assert m['volatility_version']=='v1'
    assert m['poc']==100
    assert m['poc_mode']=='TRADE_POC'

def test_future_context_is_never_attached():
    v=[VolatilitySnapshot(60,180,.02,.02,.02,.03,2,2,.9,VolatilityRegime.EXTREME,'v1')]
    m=attach_entry_context(entry_time=120,metadata={'coverage':'COMPLETE_HISTORY'},volatility=v,profiles=[])
    assert 'volatility_regime' not in m
    assert m['coverage']=='COMPLETE_HISTORY'
