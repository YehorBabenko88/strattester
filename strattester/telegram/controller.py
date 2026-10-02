from __future__ import annotations
class TelegramController:
    def __init__(self,allowed_chat_ids,service_manager,status_provider,confirmations):
        self.allowed={str(x) for x in allowed_chat_ids}; self.services=service_manager; self.status_provider=status_provider; self.confirmations=confirmations
    def handle(self,chat_id,text):
        if str(chat_id) not in self.allowed:return None
        cmd=text.strip().split()[0].lower()
        if cmd=='/start': self.services.start(); return 'STARTED'
        if cmd=='/stop': self.services.stop(); return 'STOPPED'
        if cmd=='/restart': self.services.restart(); return 'RESTARTED'
        if cmd=='/drain': self.services.drain(); return 'DRAINING'
        if cmd=='/status': return self.status_provider()
        if cmd=='/remove':
            c=self.confirmations.create('remove-worker'); return f'CONFIRM /confirm_remove {c.nonce}'
        if cmd=='/confirm_remove':
            parts=text.split()
            if len(parts)!=2:return 'INVALID CONFIRMATION'
            c=self.confirmations.consume(parts[1])
            if not c or c.action!='remove-worker':return 'CONFIRMATION EXPIRED'
            self.services.remove_worker(); return 'WORKER REMOVED; DATA PRESERVED'
        return 'UNKNOWN COMMAND'
