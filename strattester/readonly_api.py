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
    def __init__(self, source_path=None):
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
                data['reason'] = self._source_reason()
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
