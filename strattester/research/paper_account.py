"""Paper-only cash admission around the existing native quote research ledger.

PaperLedger remains the sole fill/fee/slippage/funding/PnL calculator. This
module records conservative fully collateralized LONG reservations and durable
close intents. A native trade without a matching recorded intent blocks the
entire account; no foreign trade is adopted as spendable cash. Cross-database
commit is NOT atomic: uncertainty retains collateral, and reconciliation may
settle only an already verified native result for its exact recorded request.

The caller admits a private parent, immutable owner policy and live kernel gate.
Ownership values below are consistency capabilities to keep externally protected,
not JSON authentication, distributed consensus or hostile administrator isolation.
"""
from contextlib import closing, contextmanager
from dataclasses import dataclass
from decimal import Decimal
from functools import wraps
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import uuid
from . import quote_paper as native

MAX_DECISIONS, MAX_CLOSED, MAX_EVENTS = 512, 200, 4096
MAX_RECORD_BYTES, MAX_DATABASE_BYTES = 300000, 64*1024*1024
SCHEMA = 'stratt.paper.account.v1'
STATUS = frozenset(('DENIED','RESERVED','DECIDED','ENTRY_SELECTED','EXIT_DECIDED','CLOSE_READY','SETTLED','UNCERTAIN'))
CODES = frozenset(('ACCOUNT_INPUT_REJECTED','ACCOUNT_POLICY_REJECTED','ACCOUNT_OWNERSHIP_REJECTED',
    'ACCOUNT_REVOKED','ACCOUNT_UNAVAILABLE','ACCOUNT_CORRUPT','ACCOUNT_FOREIGN_NATIVE_TRADE',
    'ACCOUNT_NATIVE_CAPACITY','ACCOUNT_CAPACITY','ACCOUNT_COLLISION','ACCOUNT_CLOCK_REJECTED',
    'ACCOUNT_ENTRY_REJECTED','ACCOUNT_CLOSE_REJECTED'))
UNCERTAINTY = frozenset(('SOURCE_GAP','FUNDING_CHANGED','RESTART','REVOKED','QUOTE_TIMEOUT'))
RISK_REASONS = frozenset(('APPROVED','LONG_ONLY','QUOTE_UNAVAILABLE','STALE_QUOTE','SPREAD_LIMIT',
                         'FUNDING_UNPROVEN','SYMBOL_RESERVED','POSITION_LIMIT','RESERVATION_LIMIT',
                         'INSUFFICIENT_CASH','DRAWDOWN_LIMIT','LEDGER_CAPACITY'))
POLICY_FIELDS = frozenset(('schema','mode','long_only','initial_cash_usdt','notional_usdt',
    'max_reserved_usdt','max_positions','max_drawdown_fraction','max_quote_age_ms',
    'max_spread_bps','fee_bps','slippage_bps','latency_ms','entry_wait_ms','exit_wait_ms','hold_ms'))


class AccountBlocked(ValueError):
    def __init__(self, code='ACCOUNT_UNAVAILABLE'):
        self.code = code if code in CODES else 'ACCOUNT_UNAVAILABLE'
        super().__init__(self.code)


def need(value, code='ACCOUNT_INPUT_REJECTED'):
    if not value: raise AccountBlocked(code)


def closed_errors(fn):
    @wraps(fn)
    def call(*args, **kwargs):
        try: return fn(*args, **kwargs)
        except AccountBlocked: raise
        except Exception: raise AccountBlocked() from None
    return call


def _number(value, minimum, maximum):
    return type(value) in (int,float) and math.isfinite(value) and minimum <= value <= maximum


def _policy(value):
    need(type(value) is dict and set(value)==POLICY_FIELDS, 'ACCOUNT_POLICY_REJECTED')
    need(value['schema']=='stratt.paper.account-policy.v1' and value['mode']=='LAB_SIMULATION'
         and value['long_only'] is True, 'ACCOUNT_POLICY_REJECTED')
    for name in ('initial_cash_usdt','notional_usdt','max_reserved_usdt'):
        need(_number(value[name], .000001, 1e9), 'ACCOUNT_POLICY_REJECTED')
    need(value['notional_usdt']<=value['max_reserved_usdt']<=value['initial_cash_usdt'], 'ACCOUNT_POLICY_REJECTED')
    need(type(value['max_positions']) is int and 1<=value['max_positions']<=10, 'ACCOUNT_POLICY_REJECTED')
    need(_number(value['max_drawdown_fraction'], .000001, .999999), 'ACCOUNT_POLICY_REJECTED')
    need(_number(value['max_spread_bps'], .000001, 1000), 'ACCOUNT_POLICY_REJECTED')
    for name in ('fee_bps','slippage_bps'): need(_number(value[name],0,1000), 'ACCOUNT_POLICY_REJECTED')
    for name in ('latency_ms','max_quote_age_ms','entry_wait_ms','exit_wait_ms','hold_ms'):
        need(type(value[name]) is int and 1<=value[name]<=3600000, 'ACCOUNT_POLICY_REJECTED')
    need(value['latency_ms']<value['entry_wait_ms'] and value['latency_ms']<value['exit_wait_ms']
         and value['hold_ms']+value['exit_wait_ms']<=3600000, 'ACCOUNT_POLICY_REJECTED')
    return copy.deepcopy(value)


def _safe(path, *, directory=False, absent=False):
    path=Path(path)
    need(path.is_absolute() and '..' not in path.parts and not str(path).startswith(('\\\\','//')),
         'ACCOUNT_OWNERSHIP_REJECTED')
    need(':' not in str(path)[len(path.drive):], 'ACCOUNT_OWNERSHIP_REJECTED')
    for part in (*reversed(path.parents),path):
        try: info=part.lstat()
        except FileNotFoundError:
            need(absent and part==path, 'ACCOUNT_OWNERSHIP_REJECTED'); continue
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400,
             'ACCOUNT_OWNERSHIP_REJECTED')
        if part!=path or directory: need(stat.S_ISDIR(info.st_mode), 'ACCOUNT_OWNERSHIP_REJECTED')
        else: need(stat.S_ISREG(info.st_mode) and info.st_nlink==1, 'ACCOUNT_OWNERSHIP_REJECTED')
    return path


def _identity(path, *, directory=False):
    info=_safe(path,directory=directory).lstat(); return info.st_dev, info.st_ino


def _json(raw):
    need(type(raw) is str and 0<len(raw.encode('utf-8'))<=MAX_RECORD_BYTES,'ACCOUNT_CORRUPT')
    def pairs(items):
        out={}
        for key,value in items: need(key not in out,'ACCOUNT_CORRUPT');out[key]=value
        return out
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'ACCOUNT_CORRUPT'))
    need(native.canonical(value).decode()==raw,'ACCOUNT_CORRUPT'); return value


def _decimal(value): return Decimal(str(value))


@dataclass(frozen=True)
class AccountOwnership:
    account_id: str
    root_identity: tuple
    account_identity: tuple
    ledger_identity: tuple
    policy_sha256: str


class PaperAccount:
    @classmethod
    @closed_errors
    def create(cls, root, policy, *, require_current):
        policy=_policy(policy); need(callable(require_current),'ACCOUNT_REVOKED')
        need(require_current() is True,'ACCOUNT_REVOKED')
        root=_safe(root,directory=True,absent=True)
        root.mkdir(mode=0o700,exist_ok=False)
        ledger=native.PaperLedger.create(root/'paper.sqlite')
        path=root/'account.sqlite';fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        identity=uuid.uuid4().hex;pin=native.digest(policy)
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute('PRAGMA journal_mode=DELETE');connection.execute('PRAGMA synchronous=FULL')
            connection.execute('CREATE TABLE meta(id INTEGER PRIMARY KEY CHECK(id=1),account_id TEXT NOT NULL,policy TEXT NOT NULL)')
            connection.execute('CREATE TABLE reservations(id TEXT PRIMARY KEY,body TEXT NOT NULL)')
            connection.execute('CREATE TABLE events(sequence INTEGER PRIMARY KEY,body TEXT NOT NULL,digest TEXT NOT NULL)')
            connection.execute('INSERT INTO meta VALUES(1,?,?)',(identity,native.canonical(policy).decode()))
        ownership=AccountOwnership(identity,_identity(root,directory=True),_identity(path),_identity(ledger.path),pin)
        return cls.open(root,policy,ownership=ownership,require_current=require_current)

    @classmethod
    @closed_errors
    def open(cls, root, policy, *, ownership, require_current):
        # Never infer ownership from a file's own self-declared marker/schema.
        need(type(ownership) is AccountOwnership,'ACCOUNT_OWNERSHIP_REJECTED')
        result=cls();result.root=Path(root);result.policy=_policy(policy)
        result.ownership=ownership;result.require_current=require_current
        result.account_path=result.root/'account.sqlite';result.ledger_path=result.root/'paper.sqlite'
        result._guard();result._ledger=native.PaperLedger(result.ledger_path)
        with result._transaction(write=False) as connection:
            records,_=result._read(connection);result._native(records)
        return result

    @property
    def execution_policy(self):
        p=self.policy
        return dict(notional=p['notional_usdt'],fee_bps=p['fee_bps'],slippage_bps=p['slippage_bps'],
            latency_ms=p['latency_ms'],max_quote_age_ms=p['max_quote_age_ms'],
            max_hold_ms=p['hold_ms']+p['exit_wait_ms'])

    def _guard(self):
        need(callable(self.require_current) and self.require_current() is True,'ACCOUNT_REVOKED')
        need(type(self.ownership) is AccountOwnership and native.digest(_policy(self.policy))==self.ownership.policy_sha256,
             'ACCOUNT_OWNERSHIP_REJECTED')
        need(_identity(self.root,directory=True)==self.ownership.root_identity
             and _identity(self.account_path)==self.ownership.account_identity
             and _identity(self.ledger_path)==self.ownership.ledger_identity,'ACCOUNT_OWNERSHIP_REJECTED')
        need(self.account_path.stat().st_size<=MAX_DATABASE_BYTES,'ACCOUNT_CAPACITY')
        for path in (self.account_path,self.ledger_path):
            for suffix in ('-journal','-wal','-shm'):
                side=Path(str(path)+suffix)
                if side.exists() or side.is_symlink(): _safe(side)

    @contextmanager
    def _transaction(self, *, write=True):
        self._guard()
        with closing(sqlite3.connect(self.account_path,timeout=3)) as connection:
            connection.execute('PRAGMA synchronous=FULL')
            need(connection.execute('PRAGMA journal_mode').fetchone()[0]=='delete','ACCOUNT_CORRUPT')
            connection.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            try:
                yield connection
                self._guard()
                connection.commit() if write else connection.rollback()
            except BaseException: connection.rollback();raise

    def _read(self, connection):
        need({r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
             =={'meta','reservations','events'},'ACCOUNT_CORRUPT')
        row=connection.execute('SELECT account_id,policy FROM meta WHERE id=1').fetchone()
        need(row==(self.ownership.account_id,native.canonical(self.policy).decode()),'ACCOUNT_CORRUPT')
        need(connection.execute('SELECT count(*) FROM events').fetchone()[0]<=MAX_EVENTS
             and connection.execute('SELECT count(*) FROM reservations').fetchone()[0]<=MAX_DECISIONS,'ACCOUNT_CAPACITY')
        for table in ('events','reservations'):
            need(connection.execute('SELECT count(*) FROM '+table+" WHERE typeof(body)!='text' OR length(CAST(body AS BLOB)) NOT BETWEEN 1 AND ?",(MAX_RECORD_BYTES,)).fetchone()[0]==0,'ACCOUNT_CORRUPT')
        records={};previous='0'*64;last_clock=0
        transitions={None:{'DENIED','RESERVED'},'RESERVED':{'DECIDED','UNCERTAIN'},'DECIDED':{'ENTRY_SELECTED','UNCERTAIN'},
                     'ENTRY_SELECTED':{'EXIT_DECIDED','UNCERTAIN'},'EXIT_DECIDED':{'CLOSE_READY','UNCERTAIN'},'CLOSE_READY':{'SETTLED','UNCERTAIN'},
                     'UNCERTAIN':{'SETTLED'},'SETTLED':set(),'DENIED':set()}
        for expected,(sequence,raw,digest) in enumerate(connection.execute('SELECT sequence,body,digest FROM events ORDER BY sequence'),1):
            value=_json(raw)
            need(type(sequence) is int and sequence==expected and type(value) is dict
                 and set(value)=={'sequence','at_ms','previous_sha256','record'}
                 and value['sequence']==sequence and value['previous_sha256']==previous
                 and native.digest(value)==digest,'ACCOUNT_CORRUPT')
            native.clock(value['at_ms']);need(value['at_ms']>=last_clock,'ACCOUNT_CLOCK_REJECTED');last_clock=value['at_ms']
            record=value['record'];self._record(record);old=records.get(record['id'])
            need(record['status'] in transitions[None if old is None else old['status']],'ACCOUNT_CORRUPT')
            if old:
                immutable=set(old)-{'status','decision','entry_quote','close_decision','request','admitted_ms','result_sha256','uncertainty'}
                need(all(record[key]==old[key] for key in immutable),'ACCOUNT_CORRUPT')
                for key in ('decision','entry_quote','close_decision','request','admitted_ms','result_sha256'):
                    if old[key] is not None: need(record[key]==old[key],'ACCOUNT_CORRUPT')
            records[record['id']]=record;previous=digest
        stored={ident:_json(raw) for ident,raw in connection.execute('SELECT id,body FROM reservations')}
        need(stored==records,'ACCOUNT_CORRUPT')
        return records,last_clock

    def _record(self, record):
        fields={'id','signal','strategy','strategy_revision','evidence_class','reference_quote','funding',
                'collateral','status','risk_receipt','decision','entry_quote','close_decision','request','admitted_ms','result_sha256','uncertainty'}
        need(type(record) is dict and set(record)==fields and record['status'] in STATUS,'ACCOUNT_CORRUPT')
        native.label(record['id']);native.label(record['strategy'])
        need(re.fullmatch('[a-f0-9]{40}',record['strategy_revision']) is not None
             and record['evidence_class'] in ('SYNTHETIC','HISTORICAL','LIVE'),'ACCOUNT_CORRUPT')
        native.receipt(record['signal'],('decision_ms','observed_ms','expires_ms','side'))
        for key in ('decision_ms','observed_ms','expires_ms'):native.clock(record['signal'][key])
        need(record['signal']['observed_ms']<=record['signal']['decision_ms']<record['signal']['expires_ms']
             and record['signal']['expires_ms']-record['signal']['decision_ms']==self.policy['entry_wait_ms'],'ACCOUNT_CORRUPT')
        need(record['collateral']==str(_decimal(record['collateral'])) and _decimal(record['collateral'])>=0,'ACCOUNT_CORRUPT')
        receipt=record['risk_receipt']
        need(type(receipt) is dict and set(receipt)=={'schema','reservation_id','accepted','reason','policy_sha256',
             'candidate_sha256','ledger_sha256','cash_usdt','reserved_usdt','collateral_usdt','decision_ms','mode',
             'execution_authority','trading_authorized'} and receipt['schema']=='stratt.paper.account-risk.v1'
             and receipt['policy_sha256']==self.ownership.policy_sha256 and receipt['reservation_id']==record['id']
             and type(receipt['accepted']) is bool and receipt['reason'] in RISK_REASONS
             and receipt['accepted']==(receipt['reason']=='APPROVED') and receipt['mode']=='LAB_SIMULATION'
             and receipt['execution_authority'] is False and receipt['trading_authorized'] is False,'ACCOUNT_CORRUPT')
        candidate={key:record[key] for key in ('id','signal','strategy','strategy_revision','evidence_class','reference_quote','funding')}
        need(receipt['candidate_sha256']==native.digest(candidate) and native.HEX.fullmatch(receipt['ledger_sha256'])
             and receipt['decision_ms']==record['signal']['decision_ms'],'ACCOUNT_CORRUPT')
        for key in ('cash_usdt','reserved_usdt','collateral_usdt'):
            need(_number(receipt[key],-1e18,1e18),'ACCOUNT_CORRUPT')
        need((record['status']=='DENIED')==(receipt['accepted'] is False),'ACCOUNT_CORRUPT')
        need(record['uncertainty'] is None or record['uncertainty'] in UNCERTAINTY,'ACCOUNT_CORRUPT')
        if record['reference_quote'] is not None:self._quote(record['reference_quote'])
        if record['funding'] is not None:
            native.receipt(record['funding'],('kind','observed_ms','previous_ms','next_ms','interval_ms','events'))
        if receipt['accepted']:
            collateral=_decimal(self.policy['notional_usdt'])*(1+_decimal(self.policy['fee_bps'])/10000)
            need(_decimal(record['collateral'])==collateral and receipt['collateral_usdt']==float(collateral)
                 and record['signal']['side']=='long' and record['reference_quote'] is not None
                 and self._funding(record['funding'],record['signal'])
                 and record['reference_quote']['symbol']==record['signal']['symbol']
                 and record['reference_quote']['observed_ms']<=record['signal']['decision_ms']
                 and record['signal']['decision_ms']-record['reference_quote']['event_ms']<=self.policy['max_quote_age_ms'],'ACCOUNT_CORRUPT')
        else:need(record['collateral']=='0' and receipt['collateral_usdt']==0,'ACCOUNT_CORRUPT')
        if record['entry_quote'] is not None: self._quote(record['entry_quote'])
        if record['decision'] is not None:
            decision=record['decision'];native.receipt(decision,('decision_ms','observed_ms','expires_ms','side'))
            for key in ('decision_ms','observed_ms','expires_ms'):native.clock(decision[key])
            need(decision['source_id']=='STRATT_PAPER_RISK_DECISION'
                 and decision['symbol']==record['signal']['symbol'] and decision['side']==record['signal']['side']
                 and decision['decision_ms']>=record['signal']['decision_ms']
                 and record['signal']['observed_ms']<=decision['observed_ms']<=decision['decision_ms']
                 and decision['expires_ms']==record['signal']['expires_ms']
                 and decision['decision_ms']+self.policy['latency_ms']<=decision['expires_ms']
                 and self._funding(record['funding'],decision)
                 and decision['raw_sha256']==native.digest(dict(schema='stratt.paper.risk-decision-input.v1',
                     proposal_sha256=record['signal']['sha256'],risk_sha256=native.digest(receipt))),'ACCOUNT_CORRUPT')
        if record['close_decision'] is not None:
            decision=record['close_decision'];native.receipt(decision,('decision_ms','observed_ms','expires_ms'))
            for key in ('decision_ms','observed_ms','expires_ms'):native.clock(decision[key])
            need(record['decision'] is not None and record['entry_quote'] is not None
                 and decision['source_id']=='STRATT_PAPER_CLOSE_DECISION' and decision['symbol']==record['signal']['symbol']
                 and record['entry_quote']['observed_ms']+self.policy['hold_ms']<=decision['observed_ms']<=decision['decision_ms']
                 and decision['expires_ms']==decision['decision_ms']+self.policy['exit_wait_ms']
                 and decision['expires_ms']<record['funding']['next_ms']
                 and decision['raw_sha256']==native.digest(dict(schema='stratt.paper.close-decision-input.v1',
                     opening_decision_sha256=record['decision']['sha256'],entry_quote_sha256=record['entry_quote']['sha256'],
                     risk_sha256=native.digest(receipt),hold_ms=self.policy['hold_ms'])),'ACCOUNT_CORRUPT')
        if record['entry_quote'] is not None:
            quote=record['entry_quote'];decision=record['decision'];prior=record['reference_quote']
            need(decision is not None and quote['symbol']==record['signal']['symbol']
                 and quote['epoch']==prior['epoch'] and quote['source_id']==prior['source_id'] and quote['sequence']>prior['sequence']
                 and decision['decision_ms']+self.policy['latency_ms']<=quote['event_ms']<=quote['observed_ms']<=decision['expires_ms']
                 and quote['observed_ms']-quote['event_ms']<=self.policy['max_quote_age_ms'],'ACCOUNT_CORRUPT')
        if record['request'] is not None:
            native.clock(record['admitted_ms']);need(type(record['request']) is dict,'ACCOUNT_CORRUPT')
        if record['result_sha256'] is not None: need(native.HEX.fullmatch(record['result_sha256']) is not None,'ACCOUNT_CORRUPT')
        if record['status'] in ('ENTRY_SELECTED','EXIT_DECIDED','CLOSE_READY','SETTLED'):need(record['entry_quote'] is not None,'ACCOUNT_CORRUPT')
        if record['status'] in ('DECIDED','ENTRY_SELECTED','EXIT_DECIDED','CLOSE_READY','SETTLED'):need(record['decision'] is not None,'ACCOUNT_CORRUPT')
        if record['status'] in ('EXIT_DECIDED','CLOSE_READY','SETTLED'):need(record['close_decision'] is not None,'ACCOUNT_CORRUPT')
        if record['status'] in ('CLOSE_READY','SETTLED'):need(record['request'] is not None,'ACCOUNT_CORRUPT')
        if record['status']=='SETTLED':need(record['result_sha256'] is not None,'ACCOUNT_CORRUPT')
        if record['status'] in ('DENIED','RESERVED'):
            need(all(record[key] is None for key in ('decision','entry_quote','close_decision','request','admitted_ms','result_sha256','uncertainty')),'ACCOUNT_CORRUPT')
        if record['status']=='DECIDED':
            need(all(record[key] is None for key in ('entry_quote','close_decision','request','admitted_ms','result_sha256','uncertainty')),'ACCOUNT_CORRUPT')
        if record['status']=='ENTRY_SELECTED':
            need(all(record[key] is None for key in ('close_decision','request','admitted_ms','result_sha256','uncertainty')),'ACCOUNT_CORRUPT')
        if record['status']=='EXIT_DECIDED':
            need(all(record[key] is None for key in ('request','admitted_ms','result_sha256','uncertainty')),'ACCOUNT_CORRUPT')
        if record['status']=='CLOSE_READY':need(record['result_sha256'] is None and record['uncertainty'] is None,'ACCOUNT_CORRUPT')
        if record['status']=='UNCERTAIN':need(record['uncertainty'] is not None and record['result_sha256'] is None,'ACCOUNT_CORRUPT')
        if record['request'] is not None:
            request=record['request']
            need(request['request_id']==record['id'] and request['signal']==record['decision']
                 and request['quotes'][0]==record['entry_quote'] and request['close_signal']==record['close_decision'] and request['funding']==record['funding']
                 and request['strategy']==record['strategy'] and request['strategy_revision']==record['strategy_revision']
                 and request['evidence_class']==record['evidence_class'] and request['symbol']==record['signal']['symbol']
                 and request['policy']==self.execution_policy,'ACCOUNT_CORRUPT')
            native.evaluate(request,now_ms=record['admitted_ms'])

    def _event(self, connection, record, now_ms):
        self._record(record);native.clock(now_ms)
        prior=connection.execute('SELECT sequence,digest FROM events ORDER BY sequence DESC LIMIT 1').fetchone()
        sequence=1 if prior is None else prior[0]+1;need(sequence<=MAX_EVENTS,'ACCOUNT_CAPACITY')
        value=dict(sequence=sequence,at_ms=now_ms,previous_sha256='0'*64 if prior is None else prior[1],record=record)
        raw=native.canonical(value).decode();need(len(raw.encode())<=MAX_RECORD_BYTES,'ACCOUNT_CAPACITY')
        connection.execute('INSERT INTO events VALUES(?,?,?)',(sequence,raw,native.digest(value)))
        connection.execute('INSERT INTO reservations VALUES(?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',
                           (record['id'],native.canonical(record).decode()))

    def _native(self, records):
        packet=self._ledger.snapshot(limit=MAX_CLOSED,max_bytes=4*1024*1024,validation_seconds=10.)
        need(packet['validated_count']==packet['returned_count'] and packet['has_more'] is False,'ACCOUNT_NATIVE_CAPACITY')
        rows={row['request_id']:row for row in packet['rows']}
        for ident,row in rows.items():
            record=records.get(ident)
            need(record is not None and record['request'] is not None
                 and record['status'] in ('CLOSE_READY','UNCERTAIN','SETTLED')
                 and native.digest(record['request'])==row['request_sha256'],'ACCOUNT_FOREIGN_NATIVE_TRADE')
            need(record['result_sha256'] in (None,row['result_sha256']),'ACCOUNT_FOREIGN_NATIVE_TRADE')
        for ident,record in records.items():
            if record['status']=='SETTLED': need(ident in rows,'ACCOUNT_FOREIGN_NATIVE_TRADE')
        return packet,rows

    def _balances(self, connection, records, rows):
        cash=peak=_decimal(self.policy['initial_cash_usdt'])
        # Realization order is the verified journal's causal SETTLED order,
        # never caller-declared native admission clocks (which can be backdated).
        settled=set()
        for (raw,) in connection.execute('SELECT body FROM events ORDER BY sequence'):
            record=_json(raw)['record']
            if record['status']=='SETTLED':
                ident=record['id'];need(ident not in settled and ident in rows,'ACCOUNT_CORRUPT')
                settled.add(ident);cash+=_decimal(rows[ident]['result']['pnl']);peak=max(peak,cash)
        # Native commits awaiting causal reconciliation remain verified cash;
        # they acquire their realization position only when SETTLED is journalled.
        cash+=sum((_decimal(row['result']['pnl']) for ident,row in rows.items() if ident not in settled),Decimal(0))
        reserved=sum((_decimal(r['collateral']) for r in records.values() if r['status'] not in ('DENIED','SETTLED')),Decimal(0))
        return cash,peak,reserved

    def _reconcile(self, connection, records, rows, now_ms):
        for ident,row in rows.items():
            old=records[ident]
            if old['status']!='SETTLED':
                record=copy.deepcopy(old);record.update(status='SETTLED',result_sha256=row['result_sha256'])
                self._event(connection,record,now_ms);records[ident]=record

    @staticmethod
    def _quote(value):
        native.receipt(value,('epoch','sequence','event_ms','observed_ms','bid','ask'))
        native.label(value['epoch']);native.clock(value['sequence'])
        native.clock(value['event_ms']);native.clock(value['observed_ms'])
        native.num(value['bid'],1e-12);native.num(value['ask'],1e-12)
        need(value['bid']<=value['ask'] and value['event_ms']<=value['observed_ms'])

    def _funding(self, funding, signal):
        if funding is None:return False
        native.receipt(funding,('kind','observed_ms','previous_ms','next_ms','interval_ms','events'))
        for key in ('observed_ms','previous_ms','next_ms','interval_ms'):native.clock(funding[key])
        return (funding['symbol']==signal['symbol'] and funding['kind']=='COMPLETE_INTERVAL' and funding['events']==[]
                and 0<funding['interval_ms']<=86400000 and funding['next_ms']-funding['previous_ms']==funding['interval_ms']
                and funding['observed_ms']<=signal['decision_ms']
                and funding['previous_ms']<=signal['decision_ms']
                and signal['expires_ms']+self.policy['hold_ms']+self.policy['exit_wait_ms']<funding['next_ms'])

    @closed_errors
    def reserve(self, request_id, *, signal, strategy, strategy_revision, evidence_class, reference_quote, funding, now_ms):
        native.label(request_id);native.label(strategy);native.clock(now_ms)
        native.receipt(signal,('decision_ms','observed_ms','expires_ms','side'))
        need(signal['symbol'] in native.SYMBOLS and signal['side'] in ('long','short'))
        need(type(strategy_revision) is str and re.fullmatch('[a-f0-9]{40}',strategy_revision)
             and evidence_class in ('SYNTHETIC','HISTORICAL','LIVE'))
        for key in ('decision_ms','observed_ms','expires_ms'):native.clock(signal[key])
        need(signal['observed_ms']<=signal['decision_ms']<=now_ms<signal['expires_ms']
             and signal['expires_ms']-signal['decision_ms']==self.policy['entry_wait_ms'])
        if reference_quote is not None:self._quote(reference_quote)
        candidate=dict(id=request_id,signal=copy.deepcopy(signal),strategy=strategy,strategy_revision=strategy_revision,
                       evidence_class=evidence_class,reference_quote=copy.deepcopy(reference_quote),funding=copy.deepcopy(funding))
        with self._transaction() as connection:
            records,last=self._read(connection);packet,rows=self._native(records)
            if request_id in records:
                old=records[request_id];need(all(old[k]==v for k,v in candidate.items()),'ACCOUNT_COLLISION')
                return copy.deepcopy(old['risk_receipt'])
            need(now_ms>=last,'ACCOUNT_CLOCK_REJECTED');need(len(records)<MAX_DECISIONS,'ACCOUNT_CAPACITY')
            self._reconcile(connection,records,rows,now_ms);cash,peak,reserved=self._balances(connection,records,rows)
            live=[r for r in records.values() if r['status'] not in ('DENIED','SETTLED')]
            collateral=_decimal(self.policy['notional_usdt'])*(1+_decimal(self.policy['fee_bps'])/10000)
            reason='APPROVED'
            if signal['side']!='long':reason='LONG_ONLY'
            elif reference_quote is None:reason='QUOTE_UNAVAILABLE'
            elif (reference_quote['symbol']!=signal['symbol'] or reference_quote['observed_ms']>signal['decision_ms']
                  or now_ms-reference_quote['event_ms']>self.policy['max_quote_age_ms']):reason='STALE_QUOTE'
            elif (reference_quote['ask']/reference_quote['bid']-1)*10000>self.policy['max_spread_bps']:reason='SPREAD_LIMIT'
            elif not self._funding(funding,signal):reason='FUNDING_UNPROVEN'
            elif any(r['signal']['symbol']==signal['symbol'] for r in live):reason='SYMBOL_RESERVED'
            elif len(rows)+len(live)>=MAX_CLOSED:reason='LEDGER_CAPACITY'
            elif len(live)>=self.policy['max_positions']:reason='POSITION_LIMIT'
            elif reserved+collateral>_decimal(self.policy['max_reserved_usdt']):reason='RESERVATION_LIMIT'
            elif cash-reserved<collateral:reason='INSUFFICIENT_CASH'
            elif cash-reserved-collateral<peak*(1-_decimal(self.policy['max_drawdown_fraction'])):reason='DRAWDOWN_LIMIT'
            accepted=reason=='APPROVED'
            receipt=dict(schema='stratt.paper.account-risk.v1',reservation_id=request_id,accepted=accepted,reason=reason,
                policy_sha256=self.ownership.policy_sha256,candidate_sha256=native.digest(candidate),ledger_sha256=native.digest(packet),
                cash_usdt=float(cash),reserved_usdt=float(reserved),collateral_usdt=float(collateral) if accepted else 0.,
                decision_ms=signal['decision_ms'],mode='LAB_SIMULATION',execution_authority=False,trading_authorized=False)
            record=dict(candidate,collateral=str(collateral) if accepted else '0',status='RESERVED' if accepted else 'DENIED',
                risk_receipt=receipt,decision=None,entry_quote=None,close_decision=None,request=None,admitted_ms=None,result_sha256=None,uncertainty=None)
            self._event(connection,record,now_ms);return copy.deepcopy(receipt)

    @closed_errors
    def record_decision(self, request_id, decision, *, now_ms):
        """Persist the risk-bound decision before any later quote can be selected."""
        native.clock(now_ms);native.receipt(decision,('decision_ms','observed_ms','expires_ms','side'))
        with self._transaction() as connection:
            records,last=self._read(connection);self._native(records)
            old=records[request_id]
            if old['decision'] is not None:
                need(old['decision']==decision,'ACCOUNT_COLLISION');return copy.deepcopy(old)
            need(now_ms>=last,'ACCOUNT_CLOCK_REJECTED')
            need(old['status']=='RESERVED' and decision['decision_ms']==now_ms
                 and old['signal']['decision_ms']<=decision['observed_ms']<=now_ms
                 and decision['expires_ms']==old['signal']['expires_ms']
                 and now_ms+self.policy['latency_ms']<=old['signal']['expires_ms']
                 and now_ms-old['reference_quote']['event_ms']<=self.policy['max_quote_age_ms']
                 and self._funding(old['funding'],decision),'ACCOUNT_ENTRY_REJECTED')
            record=copy.deepcopy(old);record.update(status='DECIDED',decision=copy.deepcopy(decision))
            self._event(connection,record,now_ms);return copy.deepcopy(record)

    @closed_errors
    def record_entry(self, request_id, quote, *, now_ms):
        self._quote(quote);native.clock(now_ms)
        with self._transaction() as connection:
            records,last=self._read(connection);self._native(records)
            old=records[request_id]
            if old['entry_quote'] is not None:
                need(old['entry_quote']==quote,'ACCOUNT_COLLISION');return copy.deepcopy(old)
            need(now_ms>=last,'ACCOUNT_CLOCK_REJECTED')
            signal=old['decision'];prior=old['reference_quote']
            need(old['status']=='DECIDED' and quote['symbol']==signal['symbol'] and quote['epoch']==prior['epoch']
                 and quote['source_id']==prior['source_id'] and quote['sequence']>prior['sequence']
                 and signal['decision_ms']+self.policy['latency_ms']<=quote['event_ms']<=quote['observed_ms']<=now_ms
                 and signal['expires_ms']==old['signal']['expires_ms']
                 and now_ms<=old['signal']['expires_ms'] and now_ms-quote['event_ms']<=self.policy['max_quote_age_ms'], 'ACCOUNT_ENTRY_REJECTED')
            need(quote['event_ms']<old['funding']['next_ms'],'ACCOUNT_ENTRY_REJECTED')
            record=copy.deepcopy(old);record.update(status='ENTRY_SELECTED',entry_quote=copy.deepcopy(quote))
            self._event(connection,record,now_ms);return copy.deepcopy(record)

    def _after_native_commit(self): pass # Injection seam for crash-boundary verification only.

    @closed_errors
    def record_exit_decision(self, request_id, decision, *, now_ms):
        native.clock(now_ms);native.receipt(decision,('decision_ms','observed_ms','expires_ms'))
        with self._transaction() as connection:
            records,last=self._read(connection);self._native(records)
            old=records[request_id]
            if old['close_decision'] is not None:
                need(old['close_decision']==decision,'ACCOUNT_COLLISION');return copy.deepcopy(old)
            need(now_ms>=last,'ACCOUNT_CLOCK_REJECTED')
            need(old['status']=='ENTRY_SELECTED' and decision['decision_ms']==now_ms
                 and old['entry_quote']['observed_ms']+self.policy['hold_ms']<=decision['observed_ms']<=now_ms
                 and decision['expires_ms']==now_ms+self.policy['exit_wait_ms']
                 and decision['expires_ms']<old['funding']['next_ms'],'ACCOUNT_CLOSE_REJECTED')
            record=copy.deepcopy(old);record.update(status='EXIT_DECIDED',close_decision=copy.deepcopy(decision))
            self._event(connection,record,now_ms);return copy.deepcopy(record)

    @closed_errors
    def close_trade(self, request, *, now_ms):
        request=copy.deepcopy(request);native.clock(now_ms)
        with self._transaction() as connection:
            records,last=self._read(connection);packet,rows=self._native(records)
            old=records[request['request_id']]
            if old['status']=='SETTLED':
                need(native.digest(request)==rows[old['id']]['request_sha256'],'ACCOUNT_COLLISION')
                return copy.deepcopy(rows[old['id']]['result'])
            need(now_ms>=last,'ACCOUNT_CLOCK_REJECTED')
            if old['status']=='CLOSE_READY':need(request==old['request'],'ACCOUNT_COLLISION')
            else:
                need(old['status']=='EXIT_DECIDED' and request['signal']==old['decision']
                    and request['close_signal']==old['close_decision']
                    and request['quotes'][0]==old['entry_quote'] and request['funding']==old['funding']
                    and request['policy']==self.execution_policy
                    and request['strategy']==old['strategy'] and request['strategy_revision']==old['strategy_revision']
                    and request['evidence_class']==old['evidence_class'] and request['symbol']==old['signal']['symbol']
                    and request['close_signal']['decision_ms']>=old['entry_quote']['observed_ms']+self.policy['hold_ms'], 'ACCOUNT_CLOSE_REJECTED')
                native.evaluate(request,now_ms=now_ms) # Reuse actual producer-owned financial/causal validation.
                record=copy.deepcopy(old);record.update(status='CLOSE_READY',request=request,admitted_ms=now_ms)
                self._event(connection,record,now_ms)
        # Separate native transaction. A failure/crash retains the above intent.
        with self._transaction() as connection:
            records,last=self._read(connection);packet,rows=self._native(records);record=records[request['request_id']]
            need(record['request']==request and record['status'] in ('CLOSE_READY','SETTLED'),'ACCOUNT_CLOSE_REJECTED')
            need(record['id'] in rows or len(rows)<MAX_CLOSED,'ACCOUNT_NATIVE_CAPACITY')
            self._guard()
            result=self._ledger.append(request,now_ms=record['admitted_ms'])
            self._after_native_commit()
            packet,rows=self._native(records);self._reconcile(connection,records,rows,max(now_ms,last))
            return result

    @closed_errors
    def mark_uncertain(self, request_id, reason, *, now_ms):
        need(reason in UNCERTAINTY);native.clock(now_ms)
        with self._transaction() as connection:
            records,last=self._read(connection);self._native(records);need(now_ms>=last,'ACCOUNT_CLOCK_REJECTED')
            old=records[request_id]
            if old['status']=='UNCERTAIN':return
            need(old['status'] not in ('DENIED','SETTLED'))
            record=copy.deepcopy(old);record.update(status='UNCERTAIN',uncertainty=reason)
            self._event(connection,record,now_ms)

    @closed_errors
    def reconcile(self, *, now_ms):
        native.clock(now_ms)
        with self._transaction() as connection:
            records,last=self._read(connection);packet,rows=self._native(records)
            need(now_ms>=last,'ACCOUNT_CLOCK_REJECTED');self._reconcile(connection,records,rows,now_ms)

    @closed_errors
    def verified_paper_snapshot(self):
        with self._transaction(write=False) as connection:
            records,_=self._read(connection);packet,_=self._native(records);return packet

    @closed_errors
    def snapshot(self):
        with self._transaction(write=False) as connection:
            records,_=self._read(connection);packet,rows=self._native(records)
            cash,peak,reserved=self._balances(connection,records,rows)
            return dict(schema=SCHEMA,mode='LAB_SIMULATION',account_id=self.ownership.account_id,
                policy_sha256=self.ownership.policy_sha256,cash_usdt=float(cash),reserved_usdt=float(reserved),
                available_usdt=float(cash-reserved),realized_peak_usdt=float(peak),closed_count=len(rows),
                open_positions=[dict(reservation_id=r['id'],symbol=r['signal']['symbol'],entry_quote=copy.deepcopy(r['entry_quote']),status=r['status'])
                    for r in records.values() if r['entry_quote'] is not None and r['status']!='SETTLED'],
                reservations=[copy.deepcopy(r) for r in records.values()],unrealized_pnl=None,
                ledger_accounting='NATIVE_QUOTE_PAPER_LEDGER',balance_basis='VERIFIED_CLOSED_NATIVE_RESULTS',
                source_authenticity='NOT_EVALUATED',receipt_provenance='CALLER_DECLARED',
                durability='NODE_LOCAL_NOT_DISTRIBUTED_CONSENSUS_OR_FAILOVER',execution_authority=False,trading_authorized=False)
