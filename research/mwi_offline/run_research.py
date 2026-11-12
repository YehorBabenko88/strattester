"""Run with an explicit isolated Python: -I -S -B run_research.py ..."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mwi_offline.run import main
if __name__=='__main__':main()
