from strattester.telegram.poller import TelegramPoller
class Resp:
    def raise_for_status(self):pass
    def json(self):return {'result':[{'update_id':5,'message':{'chat':{'id':1},'text':'/status'}}]}
class Session:
    def __init__(self):self.posts=[]
    def get(self,*a,**k):return Resp()
    def post(self,*a,**k):self.posts.append((a,k));return Resp()
class Controller:
    def handle(self,chat,text):return 'OK'
def test_poller_advances_offset_and_replies():
    s=Session();p=TelegramPoller('secret',Controller(),s)
    assert p.poll_once()==1 and p.offset==6 and len(s.posts)==1
