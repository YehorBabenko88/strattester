from strattester.telegram.commands import ConfirmationStore
def test_confirmation_expires():
    s=ConfirmationStore(ttl=10); c=s.create('delete',now=1)
    assert s.consume(c.nonce,now=12) is None
