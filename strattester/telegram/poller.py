from __future__ import annotations
import requests,time
class TelegramPoller:
    def __init__(self,token,controller,session=None):
        self.token=token;self.controller=controller;self.session=session or requests.Session();self.offset=None
    def poll_once(self):
        url=f'https://api.telegram.org/bot{self.token}/getUpdates'
        r=self.session.get(url,params={'timeout':25,'offset':self.offset},timeout=35);r.raise_for_status()
        count=0
        for u in r.json().get('result',[]):
            self.offset=u['update_id']+1
            m=u.get('message') or {}; chat=(m.get('chat') or {}).get('id'); text=m.get('text')
            if chat is None or not text: continue
            reply=self.controller.handle(chat,text)
            if reply:
                self.session.post(f'https://api.telegram.org/bot{self.token}/sendMessage',json={'chat_id':chat,'text':reply},timeout=15).raise_for_status()
            count+=1
        return count
    def run(self):
        while True:
            try:self.poll_once()
            except requests.RequestException:time.sleep(5)
