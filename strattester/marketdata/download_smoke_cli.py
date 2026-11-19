import argparse,json

def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',default='.'); p.add_argument('--minutes',type=int,default=10)
    a=p.parse_args()
    # This legacy CLI is intentionally inert until Unified/Grid supply an
    # authenticated, source-verified read interface. Never open Bybit directly.
    print(json.dumps({'ok':False,'detail':'GRID_SOURCE_REQUIRED'},indent=2))
    return 2
if __name__=='__main__': raise SystemExit(main())
