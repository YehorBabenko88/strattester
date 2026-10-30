"""Render an independently pinned result as read-only Terminan review HTML."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strattester.research.history_terminan import render_review

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True);p.add_argument('--receipt-pin',required=True);p.add_argument('--output',required=True)
    a=p.parse_args()
    with Path(a.input).open('rb') as f:raw=f.read(8*1024*1024+1)
    if len(raw)>8*1024*1024:raise ValueError('RESULT_LIMIT')
    document=render_review(json.loads(raw),a.receipt_pin)
    with Path(a.output).open('x',encoding='utf8') as f:f.write(document)

if __name__=='__main__':main()
