"""Pure proposed DTO conversion. Caller owns profile admission; no execution paths."""
import copy
import hashlib
import json
import re

INPUT_FIELDS={'schema','raw_pnl','fees','slippage','funding','currency','unit','profile_sha256','calculation_basis','provenance'}
PROFILE_FIELDS={'schema','profile_id','currency','unit','decimal_places','max_digits'}
PROVENANCE_FIELDS={'source_head','source_tree','input_manifest_sha256','strategy_id','strategy_version','fidelity','mode'}

def require(condition,reason):
    if not condition: raise ValueError(reason)

def closed(value,fields,name):
    require(type(value) is dict and set(value)==fields,name+' fields mismatch')

def convert(record,profile,admitted_profile_digests):
    """Return new gross/net DTO; reject legacy floats and unadmitted unit profiles.

    admitted_profile_digests must come from the owning admission seam, never
    inferred from the record. This pure function does not authenticate that seam.
    No profile is built in and no runtime endpoint is provided.
    """
    closed(record,INPUT_FIELDS,'input');closed(profile,PROFILE_FIELDS,'profile')
    require(record['schema']=='agent7.financial-input.v2','input version')
    require(profile['schema']=='agent7.financial-unit-profile.v2','profile version')
    def code(value,limit):
        return type(value) is str and 0<len(value)<=limit and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/+-]*',value) is not None
    require(code(profile['profile_id'],128),'profile identity')
    for key in ('currency','unit'):
        require(code(profile[key],64),'profile unit')
        require(record[key]==profile[key],'unit binding mismatch')
    scale=profile['decimal_places'];limit=profile['max_digits']
    require(type(scale) is int and 0<=scale<=18,'decimal scale')
    require(type(limit) is int and scale<limit<=78,'digit bound')
    pin=record['profile_sha256']
    require(type(pin) is str and re.fullmatch('[0-9a-f]{64}',pin) is not None,'profile digest')
    require(type(admitted_profile_digests) in (set,frozenset),'admission digest set required')
    require(all(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None for value in admitted_profile_digests),'malformed admission digest')
    actual=hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
    require(actual==pin and pin in admitted_profile_digests,'unadmitted profile or digest mismatch')
    provenance=record['provenance'];closed(provenance,PROVENANCE_FIELDS,'provenance')
    for key,width in (('source_head',40),('source_tree',40),('input_manifest_sha256',64)):
        require(type(provenance[key]) is str and re.fullmatch('[0-9a-f]{'+str(width)+'}',provenance[key]) is not None,'provenance pin')
    for key in ('strategy_id','strategy_version'):
        require(code(provenance[key],128),'strategy identity')
    require(provenance['fidelity'] in ('PAPER_FIXTURE','PAPER_SIMULATION'),'unsupported fidelity')
    require(provenance['mode'] in ('HISTORICAL','LIVE_PAPER'),'unsupported mode')
    def integer(value):
        require(type(value) is str and len(value)<=limit+2,'monetary string required')
        pattern=r'-?(0|[1-9][0-9]*)'+(r'\.[0-9]{'+str(scale)+'}' if scale else '')
        require(re.fullmatch(pattern,value) is not None,'noncanonical monetary value')
        digits=value.lstrip('-').replace('.','')
        require(len(digits)<=limit,'monetary digit bound')
        result=int(digits)*(-1 if value.startswith('-') else 1)
        require(result!=0 or not value.startswith('-'),'negative zero')
        return result
    pnl=integer(record['raw_pnl']);fees=integer(record['fees']);slippage=integer(record['slippage']);funding=integer(record['funding'])
    require(fees>=0 and slippage>=0,'negative fee/slippage cost')
    cost=fees+slippage+funding
    basis=record['calculation_basis']
    if basis=='GROSS_MINUS_SIGNED_COSTS': gross,net=pnl,pnl-cost
    elif basis=='NET_INCLUDES_SIGNED_COSTS': gross,net=pnl+cost,pnl
    else: raise ValueError('unknown calculation basis')
    def formatted(value):
        digits=str(abs(value));require(len(digits)<=limit,'result digit bound')
        if scale:
            digits=digits.zfill(scale+1);digits=digits[:-scale]+'.'+digits[-scale:]
        return ('-' if value<0 else '')+digits
    output=copy.deepcopy(record);del output['raw_pnl']
    output.update(schema='agent7.financial-calculation.v2',gross_pnl=formatted(gross),net_pnl=formatted(net))
    return output
