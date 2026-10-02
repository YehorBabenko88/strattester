from dataclasses import dataclass
from statistics import mean

@dataclass(frozen=True)
class Wall:
    price:float; size:float; multiple:float; first_seen:int; last_seen:int

@dataclass(frozen=True)
class L2Absorption:
    level:float; side:str; known_at:int; executed_at_level:float; replenished:float; wall_multiple:float

class L2Book:
    def __init__(self,*,tick_size:float,wall_multiple:float=3):
        self.tick_size=tick_size; self.wall_multiple=wall_multiple
        self.bids={}; self.asks={}; self.first_seen={}; self.removed=[]; self.now=0
    def snapshot(self,ts,bids,asks):
        self.bids={float(p):float(q) for p,q in bids}; self.asks={float(p):float(q) for p,q in asks}; self.now=ts
        for side,levels in (('bid',self.bids),('ask',self.asks)):
            for p in levels:self.first_seen[(side,p)]=ts
    def delta(self,ts,*,bids,asks):
        self.now=ts
        for side,levels,updates in (('bid',self.bids,bids),('ask',self.asks,asks)):
            for p,q in updates:
                p=float(p); q=float(q)
                if q==0:
                    if p in levels:self.removed.append((ts,side,p))
                    levels.pop(p,None); self.first_seen.pop((side,p),None)
                else:
                    if p not in levels:self.first_seen[(side,p)]=ts
                    levels[p]=q
    def wall_at(self,price,side,*,now,min_persistence_ms=0):
        levels=self.bids if side=='bid' else self.asks; price=float(price)
        if price not in levels:return None
        others=[q for p,q in levels.items() if p!=price]
        baseline=mean(others) if others else 0
        multiple=levels[price]/baseline if baseline>0 else float('inf')
        first=self.first_seen.get((side,price),now)
        if multiple<self.wall_multiple or now-first<min_persistence_ms:return None
        return Wall(price,levels[price],multiple,first,now)
    def was_removed(self,price,side,*,since):
        return any(ts>=since and s==side and p==float(price) for ts,s,p in self.removed)

class L2AbsorptionDetector:
    def __init__(self,*,tick_size,wall_multiple=3):
        self.book=L2Book(tick_size=tick_size,wall_multiple=wall_multiple); self.trades=[]; self.replenishment={}
    def on_snapshot(self,ts,bids,asks):self.book.snapshot(ts,bids,asks)
    def on_trade(self,ts,price,size,side):self.trades.append((ts,float(price),float(size),side))
    def on_delta(self,ts,*,bids,asks):
        before=dict(self.book.bids)
        self.book.delta(ts,bids=bids,asks=asks)
        for p,q in bids:
            p=float(p); q=float(q); old=before.get(p,0)
            executed=sum(sz for _,px,sz,side in self.trades if px==p and side=='Sell')
            expected=max(0,old-executed)
            self.replenishment[p]=self.replenishment.get(p,0)+max(0,q-expected)
    def signal(self,*,level,side,now,min_executed,min_replenishment):
        book_side='bid' if side=='long' else 'ask'
        wall=self.book.wall_at(level,book_side,now=now)
        if wall is None or self.book.was_removed(level,book_side,since=wall.first_seen):return None
        aggressor='Sell' if side=='long' else 'Buy'
        executed=sum(sz for ts,p,sz,s in self.trades if ts>=wall.first_seen and p==level and s==aggressor)
        repl=self.replenishment.get(level,0)
        if executed<min_executed or repl<min_replenishment:return None
        return L2Absorption(level,side,now,executed,repl,wall.multiple)
