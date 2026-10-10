from __future__ import annotations
class TelegramController:
    def __init__(self,allowed_chat_ids,service_manager,status_provider,confirmations,inspection=None):
        self.allowed={str(x) for x in allowed_chat_ids}; self.services=service_manager; self.status_provider=status_provider; self.confirmations=confirmations; self.inspection=inspection
    def handle(self,chat_id,text):
        if str(chat_id) not in self.allowed:return None
        cmd=text.strip().split()[0].lower()
        actions={'/start':('start','STARTED'),'/stop':('stop','STOPPED'),
                 '/restart':('restart','RESTARTED'),'/drain':('drain','DRAINING')}
        if cmd in actions:
            action,message=actions[cmd]
            return self._lifecycle(cmd,getattr(self.services,action),message)
        if cmd=='/status': return self.status_provider()
        if cmd=='/results':
            if self.inspection is None:return 'RESULTS UNAVAILABLE'
            parts=text.split()
            if len(parts)!=3:return 'USAGE /results SYMBOL STRATEGY'
            row=self.inspection.results(parts[1],parts[2])
            return str(row) if row else 'NO RESULT'
        if cmd=='/resources':
            return str(self.inspection.resources()) if self.inspection else 'RESOURCES UNAVAILABLE'
        if cmd=='/db':
            return str(self.inspection.database()) if self.inspection else 'DATABASE STATUS UNAVAILABLE'
        if cmd=='/health':
            return str(self.inspection.health()) if self.inspection else 'HEALTH UNAVAILABLE'
        if cmd=='/errors':
            if self.inspection is None:return 'ERROR INSPECTION UNAVAILABLE'
            parts=text.split()
            try: lines=int(parts[1]) if len(parts)>1 else 100
            except ValueError:return 'INVALID LINE COUNT'
            rows=self.inspection.errors(lines)
            return '\n'.join(str(x) for x in rows) if rows else 'NO ERRORS'
        if cmd in ('/jobs','/progress'):
            if self.inspection is None:return 'PROGRESS UNAVAILABLE'
            return str(self.inspection.jobs())
        if cmd=='/logs':
            if self.inspection is None:return 'LOG INSPECTION UNAVAILABLE'
            parts=text.split(); component=parts[1] if len(parts)>1 else 'worker'
            try: lines=int(parts[2]) if len(parts)>2 else 100
            except ValueError:return 'INVALID LINE COUNT'
            try: rows=self.inspection.tail_log(component,lines)
            except ValueError:return 'INVALID COMPONENT'
            return '\n'.join(rows) if rows else 'NO LOGS'
        if cmd=='/remove':
            c=self.confirmations.create('remove-worker'); return f'CONFIRM /confirm_remove {c.nonce}'
        if cmd=='/confirm_remove':
            parts=text.split()
            if len(parts)!=2:return 'INVALID CONFIRMATION'
            c=self.confirmations.consume(parts[1])
            if not c or c.action!='remove-worker':return 'CONFIRMATION EXPIRED'
            return self._lifecycle(cmd,self.services.remove_worker,'WORKER REMOVED; DATA PRESERVED')
        return 'UNKNOWN COMMAND'

    @staticmethod
    def _lifecycle(command,operation,success):
        try:
            operation()
        except Exception as exc:
            return f'FAILED {command}: {exc}'
        return success
