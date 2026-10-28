"""Read-only pinned file-byte inventory; no execution or admission proof."""
import os
from pathlib import Path
import re
from .financial_contract import integer,digest
from .financial_snapshot import verified_bytes,bounded_json


def _local_path(path):
    text=os.fspath(path)
    if (type(text) is not str or len(text)>1024 or text.replace('\\','/').startswith('//') or '\x00' in text
        or not Path(text).is_absolute() or '..' in Path(text).parts):
        raise ValueError('absolute local executable inventory path required')
    drive=2 if re.match(r'^[A-Za-z]:[\\/]',text) else 0
    if ':' in text[drive:]:raise ValueError('device/alternate-stream path rejected')
    for component in text.replace('\\','/').split('/'):
        stem=component.split('.')[0].rstrip(' ').upper()
        if (component.endswith((' ','.')) or stem in ('CON','PRN','AUX','NUL','CONIN$','CONOUT$')
            or re.fullmatch(r'(COM|LPT)[1-9¹²³]',stem)):
            raise ValueError('noncanonical/device path component rejected')
    return text


def verify_executable_inventory(manifest_path,manifest_sha256,*,cancel=lambda:False):
    from .financial_session import check_cancel
    check_cancel(cancel)
    payload=bounded_json(verified_bytes(_local_path(manifest_path),manifest_sha256,64*1024))
    if (set(payload)!={'version','files'} or type(payload['version']) is not int or payload['version']!=1
        or type(payload['files']) is not list or not 1<=len(payload['files'])<=32):
        raise ValueError('executable inventory schema/budget')
    names=set();paths=set();total=0
    for row in payload['files']:
        if type(row) is not dict or set(row)!={'logical_name','absolute_path','sha256','size_bytes'}:
            raise ValueError('executable entry schema')
        name=row['logical_name'];path=row['absolute_path']
        if type(name) is not str or re.fullmatch('[a-z][a-z0-9_-]{0,63}',name) is None:
            raise ValueError('executable logical identity')
        if type(path) is not str:raise ValueError('executable path type')
        _local_path(path)
        lexical=os.path.normcase(os.path.abspath(path))
        if name in names or lexical in paths:raise ValueError('duplicate executable identity/path')
        names.add(name);paths.add(lexical);digest(row['sha256']);integer(row['size_bytes'],'executable bytes',1)
        total+=row['size_bytes']
        if row['size_bytes']>64*1024*1024 or total>128*1024*1024:
            raise ValueError('executable inventory byte budget')
    # Validate the complete requested roster/budget before reading any target.
    results=[]
    for row in payload['files']:
        check_cancel(cancel)
        data=verified_bytes(row['absolute_path'],row['sha256'],row['size_bytes'])
        if len(data)!=row['size_bytes']:raise ValueError('executable byte count mismatch')
        results.append({k:row[k] for k in ('logical_name','sha256','size_bytes')})
        del data
    check_cancel(cancel)
    return dict(status='FILES_VERIFIED_ONLY',manifest_sha256=manifest_sha256,files=results,
        execution_binding='UNQUALIFIED',dependency_closure='NOT_PROVEN',native_enforcement=False,
        physical_g1='NOT_AUTHORIZED',trading='NO-GO')
