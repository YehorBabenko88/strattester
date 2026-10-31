"""Opt-in WSGI boundary. Does not bind sockets or launch research/workers.

The legacy store cannot establish immutable dataset identity. Until its producer
can seal that identity, result routes deliberately disclose no research data.
"""
import json
from pathlib import Path
import re
import sqlite3
import stat
import time
from urllib.parse import parse_qs


class ReadOnlyResultsApp:
    def __init__(self, source_path=None, *, trusted_sources=(), trusted_receipts=()):
        self.trusted_sources = frozenset(tuple(x) for x in trusted_sources)
        self.trusted_receipts = frozenset(tuple(x) for x in trusted_receipts)
        from strattester.research.financial_executable_inventory import _local_path
        self.source_path = None
        if source_path is not None:
            try:
                # Lexical admission only: resolving can probe UNC/reparse targets.
                self.source_path = Path(_local_path(source_path))
            except (OSError, TypeError, ValueError):
                pass

    def _source_reason(self):
        if self.source_path is None:
            return 'SOURCE_UNAVAILABLE'
        try:
            from strattester.research.financial_snapshot import reject_linked_path
            # Preserve lexical ancestors until checked. These portable checks
            # do not provide native confinement against namespace races.
            source = reject_linked_path(self.source_path)
            info = source.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                return 'SOURCE_UNAVAILABLE'
            # Metadata-only main-file probe: ignore WAL, never create sidecars.
            # This cannot qualify source freshness or consume a live snapshot.
            con = sqlite3.connect(source.as_uri() + '?mode=ro&immutable=1', uri=True, timeout=0.1)
            try:
                deadline = time.monotonic() + 0.1
                con.set_progress_handler(lambda: int(time.monotonic() >= deadline), 100)
                con.execute('PRAGMA query_only=ON')
                row = con.execute("SELECT type FROM sqlite_master WHERE name='research_results' LIMIT 1").fetchone()
                if row != ('table',):
                    return 'SOURCE_UNAVAILABLE'
            finally:
                con.close()
        except (sqlite3.Error, OSError, ValueError):
            return 'SOURCE_UNAVAILABLE'
        return 'SOURCE_PROVENANCE_UNQUALIFIED'

    def _qualified(self, path, query):
        from strattester.research.provenance import validate
        if not self.trusted_sources: return None, 'SOURCE_TRUST_UNCONFIGURED'
        if self.source_path is None: return None, 'SOURCE_UNAVAILABLE'
        try:
            from strattester.research.financial_snapshot import reject_linked_path, unique_object
            source = reject_linked_path(self.source_path)
            info = source.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                return None, 'SOURCE_UNAVAILABLE'
            # A live WAL is read only with its existing regular sidecars. A
            # checkpointed main file uses immutable mode to avoid new sidecars.
            wal = source.with_name(source.name + '-wal')
            shm = source.with_name(source.name + '-shm')
            live_wal = wal.exists()
            if live_wal:
                for sidecar in (wal, shm):
                    sidecar = reject_linked_path(sidecar)
                    sideinfo = sidecar.lstat()
                    if not stat.S_ISREG(sideinfo.st_mode) or sideinfo.st_nlink != 1:
                        return None, 'SOURCE_UNAVAILABLE'
            uri = source.as_uri() + ('?mode=ro' if live_wal else '?mode=ro&immutable=1')
            con=sqlite3.connect(uri,uri=True,timeout=0.1)
            try:
                deadline=time.monotonic()+0.1
                con.set_progress_handler(lambda: int(time.monotonic()>=deadline),100)
                con.execute('PRAGMA query_only=ON'); con.execute('BEGIN')
                if path=='/internal/v1/runs':
                    rows=con.execute("SELECT run_id,state,CASE WHEN length(CAST(record AS BLOB))<=900000 THEN record ELSE NULL END FROM owned_runs WHERE state='COMPLETE' ORDER BY run_id LIMIT ? OFFSET ?",(int(query.get('limit',['50'])[0]),int(query.get('offset',['0'])[0])))
                else:
                    rows=con.execute("SELECT run_id,state,CASE WHEN length(CAST(record AS BLOB))<=900000 THEN record ELSE NULL END FROM owned_runs WHERE run_id=?",(path.split('/')[-2],))
                records=[]; total_bytes=0
                for run_id,state,raw in rows:
                    if state!='COMPLETE': return None,'RUN_INCOMPLETE'
                    if raw is None: return None,'ARTIFACT_SIZE_UNAVAILABLE'
                    if not isinstance(raw,str): return None,'RECORD_INVALID'
                    total_bytes+=len(raw.encode('utf-8'))
                    if total_bytes>900_000: return None,'ARTIFACT_SIZE_UNAVAILABLE'
                    if time.monotonic()>=deadline: return None,'SOURCE_TIMEOUT'
                    record=json.loads(raw,object_pairs_hook=unique_object)
                    reason=validate(record)
                    if reason: return None,reason
                    if record['run_id']!=run_id: return None,'RUN_ID_MISMATCH'
                    if (record['producer_identity'],record['source_revision'],record['dataset']['source_identity']) not in self.trusted_sources: return None,'SOURCE_IDENTITY_UNTRUSTED'
                    if (record['producer_identity'],record['source_revision'],run_id,record['completion_receipt']) not in self.trusted_receipts: return None,'SOURCE_RECEIPT_UNTRUSTED'
                    if time.monotonic()>=deadline: return None,'SOURCE_TIMEOUT'
                    records.append(record)
                return (records,None) if records else (None,'RUN_UNAVAILABLE')
            finally: con.close()
        except (sqlite3.Error,OSError,ValueError,TypeError,KeyError,AttributeError,RecursionError): return None,'SOURCE_PROVENANCE_UNQUALIFIED'

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        method = environ.get('REQUEST_METHOD', '')
        data = {'api_version': {'major': 1, 'minor': 0}, 'producer': 'strattester', 'read_only': True,
                'provenance': 'UNAVAILABLE'}
        status = 503
        if method != 'GET':
            status, data['reason'] = 405, 'METHOD_NOT_ALLOWED'
        elif path == '/internal/v1/capabilities':
            status = 200
            data['capabilities'] = {'historical_research': False, 'runs': False, 'run_metrics': False}
        elif path in ('/internal/v1/health', '/internal/v1/runs') or re.fullmatch(
                r'/internal/v1/runs/[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}/metrics', path):
            try:
                raw = environ.get('QUERY_STRING', '')
                if len(raw) > 256:
                    raise ValueError('query too long')
                query = parse_qs(raw, keep_blank_values=True, strict_parsing=True, max_num_fields=2)
                allowed = {'limit', 'offset'} if path == '/internal/v1/runs' else set()
                if set(query) - allowed or any(len(v) != 1 for v in query.values()):
                    raise ValueError('unknown or repeated query')
                for key, default, low, high in (('limit', '50', 1, 100), ('offset', '0', 0, 10000)):
                    value = query.get(key, [default])[0]
                    if not re.fullmatch(r'[0-9]{1,5}', value) or not low <= int(value) <= high:
                        raise ValueError('unbounded query')
            except ValueError:
                status, data['reason'] = 400, 'INVALID_QUERY'
            else:
                if path == '/internal/v1/health' or not self.trusted_sources:
                    data['reason'] = self._source_reason()
                else:
                    records, reason = self._qualified(path, query)
                    if reason:
                        data['reason'] = reason
                    else:
                        status = 200
                        data.update(provenance='QUALIFIED',mode='HISTORICAL',execution_authority=False,
                                    runs=records,freshness='HISTORICAL',data_quality='COMPLETE',
                                    source_authenticity='OWNER_POLICY_ADMITTED',physical_attestation='UNVERIFIED',
                                    listing_policy='COMPLETE_ONLY',unfinished_runs='UNAVAILABLE_BY_ID')
        else:
            status, data['reason'] = 404, 'NOT_FOUND'
        data['status'] = 'AVAILABLE' if status == 200 else 'UNAVAILABLE'
        body = json.dumps(data, sort_keys=True, allow_nan=False).encode('utf-8')
        labels = {200: 'OK', 400: 'Bad Request', 404: 'Not Found', 405: 'Method Not Allowed', 503: 'Service Unavailable'}
        headers = [('Content-Type', 'application/json'), ('Content-Length', str(len(body))), ('Cache-Control', 'no-store')]
        if status == 405:
            headers.append(('Allow', 'GET'))
        start_response(f'{status} {labels[status]}', headers)
        return [body]
