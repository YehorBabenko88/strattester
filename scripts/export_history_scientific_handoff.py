"""Export a separately reviewed synthetic history handoff for Terminan read-only import."""
import argparse
import json
from pathlib import Path
from strattester.research.history_terminan import review_packet
from strattester.research.history_scientific_handoff import handoff_packet

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",required=True)
    parser.add_argument("--receipt-pin",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    source=Path(args.input)
    if source.stat().st_size>8*1024*1024:raise ValueError("INPUT_LIMIT")
    result=json.loads(source.read_text(encoding="utf-8"))
    packet=handoff_packet(review_packet(result,args.receipt_pin))
    target=Path(args.output)
    if target.exists():raise ValueError("OUTPUT_EXISTS")
    if not target.parent.is_dir():raise ValueError("OUTPUT_PARENT_MISSING")
    data=json.dumps(packet,sort_keys=True,separators=(",",":"),allow_nan=False)
    if len(data.encode("utf-8"))>2*1024*1024:raise ValueError("HANDOFF_FILE_LIMIT")
    # Exclusive creation: never replace prior evidence.
    with target.open("x",encoding="utf-8",newline="\n") as output:
        output.write(data+"\n")
    print(json.dumps({"state":"SYNTHETIC_HANDOFF_CREATED","output":str(target),
                      "handoff_sha256":packet["handoff_sha256"],
                      "source_authenticity":"UNATTESTED",
                      "execution_authority":False}))

if __name__=="__main__":main()
