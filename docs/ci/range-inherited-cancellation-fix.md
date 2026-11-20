# Inherited cancellation defect retained as failed evidence

First fa8b40ac414fa46694b43bea934dc2c6aec96c99 artifact run: Python3.11 had648PASS/1FAIL at the existing cancellation/admission regression; Python3.12 had649PASS. Exact failed log remains private .proof/artifact-311-FAILED.log. The new range-audit decisions were not the failing component, and no full qualification is claimed for that historical wheel.

The pre-fix collector Git blob was verified identical to parent983. This branch now reuses the exact collector.py and four regression cases from accepted cancellation fix01c64a188ee4e7020b4620583efb8c89f3a2baea, rather than implementing another cancellation policy. Parent aggregate/CI pins are unchanged. The parent already owns those same bytes; the independent future semantic delta remains the four-scenario range audit.

The first inherited-fix949 artifact scope passed653 cases onPython3.11; Python3.12 recorded650PASS/3FAIL. Two rotation/service failures matched the parent644 discovery: Python3.12 wait_for executes cancelled raw cleanup inline. This branch now reuses the exact cf9e2397c67041add9e8f16afd011395d44908b5 collector and one added valid-admission cleanup regression. The additional observed[] book-silence assertion from that earlier run remains preserved with causal attributionUNKNOWN; no silent fixture or timeout relaxation.
