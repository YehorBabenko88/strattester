import pytest
from research.independent_asof_revisions import select_asof_revisions

def test_future_revision_does_not_rewrite_past():
    rows=[('trade',0,10,20,'a'*64),('trade',1,10,100,'b'*64)]
    assert select_asof_revisions(rows,50)['trade'][0] == 0
    assert select_asof_revisions(rows,100)['trade'][0] == 1

def test_ingestion_order_invariance():
    rows=[('trade',0,10,20,'a'*64),('trade',1,10,40,'b'*64)]
    assert select_asof_revisions(rows,50)==select_asof_revisions(list(reversed(rows)),50)

def test_duplicate_revision_rejected():
    row=('trade',0,10,20,'a'*64)
    with pytest.raises(ValueError):
        select_asof_revisions([row,row],50)
