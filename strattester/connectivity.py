from __future__ import annotations
from dataclasses import dataclass
import requests
from .marketdata.bybit_client import BybitClient

@dataclass(frozen=True)
class ConnectivityResult:
    ok:bool; detail:str

def check_bybit(client=None):
    client=client or BybitClient()
    try:
        rows=client.fetch_linear_instruments()
        return ConnectivityResult(bool(rows),f'{len(rows)} instrument(s) visible')
    except Exception as exc:
        return ConnectivityResult(False,f'{type(exc).__name__}: {exc}')

def check_telegram(token,session=None):
    if not token:return ConnectivityResult(False,'token not configured')
    session=session or requests.Session()
    try:
        r=session.get(f'https://api.telegram.org/bot{token}/getMe',timeout=15)
        r.raise_for_status(); data=r.json()
        return ConnectivityResult(bool(data.get('ok')),'bot authenticated' if data.get('ok') else 'telegram rejected token')
    except requests.RequestException as exc:
        return ConnectivityResult(False,f'{type(exc).__name__}: {exc}')
