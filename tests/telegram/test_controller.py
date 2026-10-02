from strattester.telegram.controller import TelegramController
from strattester.telegram.commands import ConfirmationStore
class S:
    def __init__(self):self.calls=[]
    def __getattr__(self,n):return lambda:self.calls.append(n)
def test_unknown_chat_ignored():
    s=S(); c=TelegramController(['1'],s,lambda:'OK',ConfirmationStore())
    assert c.handle('2','/start') is None and not s.calls
def test_controller_operates_when_worker_stopped():
    s=S(); c=TelegramController(['1'],s,lambda:'worker stopped',ConfirmationStore())
    assert c.handle('1','/status')=='worker stopped'
    assert c.handle('1','/start')=='STARTED'
def test_remove_requires_nonce():
    s=S(); cs=ConfirmationStore(); c=TelegramController(['1'],s,lambda:'OK',cs)
    reply=c.handle('1','/remove'); nonce=reply.split()[-1]
    assert 'remove_worker' not in s.calls
    assert c.handle('1',f'/confirm_remove {nonce}').startswith('WORKER REMOVED')
    assert 'remove_worker' in s.calls

def test_logs_command_is_read_only_and_bounded():
    class P:
        def tail_log(self,component,lines): return ['x','y']
    s=S(); c=TelegramController(['1'],s,lambda:'OK',ConfirmationStore(),inspection=P())
    assert c.handle('1','/logs worker 2')=='x\ny'
