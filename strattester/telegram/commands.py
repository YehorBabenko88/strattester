from dataclasses import dataclass
import secrets,time
@dataclass
class Confirmation:
    action:str; nonce:str; expires:float
class ConfirmationStore:
    def __init__(self,ttl=60): self.ttl=ttl; self._items={}
    def create(self,action,now=None):
        now=time.time() if now is None else now; c=Confirmation(action,secrets.token_urlsafe(8),now+self.ttl); self._items[c.nonce]=c; return c
    def consume(self,nonce,now=None):
        now=time.time() if now is None else now; c=self._items.pop(nonce,None)
        return c if c and c.expires>=now else None
