"""Wrap inert joint/replay exports for opt-in display; never launches Math."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strattester.research.grid_math_history import canonical
from strattester.research.history_joint_display import joint_display_packet, LIMIT

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('history','joint-result','joint-receipt-pin','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--joint-request',help='Required only for older joint exports without a captured joint_request')
    p.add_argument('--joint-published-at-ms',type=int,required=True)
    a=p.parse_args()
    def read(path):
        with Path(path).open('rb') as f:raw=f.read(LIMIT+1)
        if len(raw)>LIMIT:raise ValueError('DISPLAY_LIMIT')
        def pairs(items):
            d={}
            for k,v in items:
                if k in d:raise ValueError('DUPLICATE_KEY')
                d[k]=v
            return d
        return json.loads(raw,object_pairs_hook=pairs)
    result=read(a.joint_result)
    request=read(a.joint_request) if a.joint_request else result.get('joint_request')
    packet=joint_display_packet(read(a.history),request,result,
        a.joint_receipt_pin,joint_published_at_ms=a.joint_published_at_ms)
    with Path(a.output).open('xb') as f:f.write(canonical(packet))
    print(json.dumps({'packet_sha256':packet['packet_sha256'],'qualification':'NOT_QUALIFIED','source_authenticity':'UNATTESTED'}))
if __name__=='__main__':main()
