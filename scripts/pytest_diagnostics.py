"""Bounded, redacted JUnit attributes for ordinary GitHub check annotations.

This diagnostic never changes pytest's exit status and never emits trace bodies.
"""
import os
from pathlib import Path
import re
import stat
import sys
import xml.etree.ElementTree as ET

MAX_BYTES = 16 * 1024 * 1024
URL = re.compile(r'(?i)\b(?:[a-z][a-z0-9+.-]*://|www\.)[^\s<>"\']+')
AUTH = re.compile(r'(?i)\b(?:bearer|basic)\s+[^\s,;]+')
LABELLED = re.compile(r'''(?ix)
    \b(password|passwd|pwd|token|secret|api[_ -]?key|authorization|credential|
       access[_ -]?key|client[_ -]?secret|dsn)\b[\"\']?
    \s*(?:[:=]\s*|\s+)(?:"[^"]*"|'[^']*'|[^\s,;]+)
''')
TOKEN = re.compile(r'\b(?:(?:gh[pousr]_|github_pat_|sk-(?:proj-)?)[A-Za-z0-9_-]{8,}|(?:AKIA|ASIA)[A-Z0-9]{16})\b')


def safe_text(value, limit):
    value = URL.sub('[REDACTED]', value)
    value = AUTH.sub('authorization=[REDACTED]', value)
    value = LABELLED.sub(lambda match: match.group(1) + '=[REDACTED]', value)
    value = TOKEN.sub('[REDACTED]', value)
    value = value[:limit].encode('ascii', errors='backslashreplace').decode('ascii')
    return value.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')


def warn(reason):
    print('::warning title=pytest diagnostics::JUnit diagnostics unavailable (' + reason + ')')


def read_report(path):
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0)
    if path.is_symlink():
        raise ValueError('REPORT_UNSAFE')
    fd = os.open(path, flags)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('REPORT_UNSAFE')
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('REPORT_TOO_LARGE')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeError:
        raise ValueError('XML_ENCODING_UNSAFE') from None
    if '\x00' in text or re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b', text, re.I):
        raise ValueError('XML_UNSAFE')
    try:
        return ET.fromstring(text)
    except (ET.ParseError, ValueError):
        raise ValueError('XML_INVALID') from None


def annotate(path):
    try:
        root = read_report(path)
    except FileNotFoundError:
        warn('REPORT_MISSING')
        return
    except OSError:
        warn('REPORT_UNREADABLE')
        return
    except ValueError as error:
        # Only our fixed reason codes are emitted; parser text/input is private.
        warn(str(error))
        return
    failures = 0
    for case in root.iter('testcase'):
        problem = next((child for child in case if child.tag in ('failure', 'error')), None)
        if problem is None:
            continue
        failures += 1
        if failures > 10:
            continue
        identity = '::'.join(value for value in (case.get('classname', ''), case.get('name', '')) if value)
        message = problem.get('message') or problem.get('type') or 'No short message attribute'
        print('::error title=pytest failure::' + safe_text(identity or 'Unnamed JUnit testcase', 1024)
              + ' | ' + safe_text(message, 320))
    print('::notice title=pytest diagnostics::Reported failing tests: ' + str(failures)
          + '; annotated: ' + str(min(10, failures)) + '; trace bodies omitted')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        warn('REPORT_ARGUMENT_REQUIRED')
    else:
        annotate(Path(sys.argv[1]))
