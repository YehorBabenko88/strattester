"""Static local prediction reports. No strategy performance is implied."""
import csv
import html
import io
import math
import os
from pathlib import Path
import tempfile
from .financial_snapshot import reject_linked_path,canonical_bytes
from .financial_session import check_cancel

def export_report(result,output_dir,*,cancel=lambda:False):
    check_cancel(cancel)
    p=result['prediction'];mu=p['mu'];scale=p['scale']
    if not all(type(v) in (int,float) and math.isfinite(v) for v in (mu,scale)) or scale<=0:raise ValueError('finite prediction required')
    target=Path(output_dir);root=reject_linked_path(target.parent)
    if target.exists() or target.is_symlink():raise FileExistsError('report destination exists')
    label=html.escape(str(p['instrument']['symbol']),quote=True)
    points=' '.join(f'{20+i*4:.2f},{180-140*math.exp(-.5*((i-50)/16)**2):.2f}' for i in range(101))
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 440 220"><title>{label}: predicted return distribution</title><rect width="440" height="220" fill="white"/><polyline points="{points}" fill="none" stroke="navy"/><text x="20" y="210">mu={mu:.6g}; scale={scale:.6g}</text></svg>'
    stream=io.StringIO(newline='');writer=csv.writer(stream);writer.writerow(['symbol','origin_ns','available_ns','horizon_ns','mu','scale'])
    symbol=str(p['instrument']['symbol']);symbol="'"+symbol if symbol.startswith(('=','+','-','@','\t','\r')) else symbol
    writer.writerow([symbol,*[p[k] for k in ('origin_ns','available_ns','horizon_ns','mu','scale')]])
    document=f'<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; img-src &#39;self&#39;"><title>Research prediction</title></head><body><h1>{label}</h1><p>Research prediction only. Trading: NO-GO. Physical G1: NOT_AUTHORIZED. Native resource caps: NOT_ENFORCED.</p><p>No profitability or calibration claim.</p>{svg}<h2>Provenance</h2><pre>{html.escape(canonical_bytes(result["provenance"]).decode())}</pre></body></html>'
    with tempfile.TemporaryDirectory(prefix='.report-',dir=root) as stage:
        for name,data in {'report.html':document.encode(),'distribution.svg':svg.encode(),'prediction.csv':stream.getvalue().encode(),'provenance.json':canonical_bytes(result['provenance'])}.items():
            check_cancel(cancel);(Path(stage)/name).write_bytes(data)
        check_cancel(cancel)
        if target.exists():raise FileExistsError('report destination exists')
        os.rename(stage,target)
    return {'status':'PUBLISHED','files':['report.html','distribution.svg','prediction.csv','provenance.json']}
