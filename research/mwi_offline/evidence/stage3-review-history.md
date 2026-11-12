# Stage3 independent review and negative evidence

Base PR82 `bd6224331310724e0497285ecec4dd22957d4535` is preserved. ROOT approved only the contained research namespace, existing MWI research doc and new MWI Learning Lab proposal/fixture paths. Existing workflows/core source and other repositories are unchanged.

TDD first observed missing modules, then passing contained contract tests. Independent reviews found and reproduced the following failures before correction:

- Search refusal containing NaN failed during canonical serialization; shared subtree traversal lacked a total work bound. Noncanonical input is now rejected before batch identity, with finite/safe-integer limits and a4096 node budget. Bounded valid JSON declarations still retain validation, duplicate and budget refusal records.
- Finite feedback evaluated a repeated candidate twice (4 rather than3 in the regression). It now admits batches through semantic deduplication and persists the decisions.
- Completed resume accepted deletion of a search-artifact plus its inventory entry. It now requires the initial search and, for iteration2, the next-version search. The fixed frozen-policy control artifact is also mandatory.
- Control interruption had no retained control-failure artifact. It now saves typed failure after selection and before any fresh holdout access, then rethrows.
- Learning Lab accepted impossible/inconsistent metric summaries and holdout trades outside declared temporal windows. It now checks multiclass Brier bounds, reliability summary consistency, episode/latency/horizon/window joins. It accepts actual native SL_GAP/TP_GAP exits and refuses unknown enums.
- Confidence-bin mean rounding could reject native mean0.6999999999999998 in bin7. The validator uses the bin interval with declared1e-12 tolerance and retains wrong-bin refusal.
- The exact fixture/source pin test correctly refused a stale projection-module raw hash after source fixes and owned LF normalization. Unpublished intermediate manifests are retained in the local readiness packet. The fixture bytes themselves and preserved original negative PnL were unchanged. No admitted source snapshot or prior PR was rewritten.

Detailed original RED/GREEN outputs, independent repros and review dispositions live in the companion local `outputs/MWI-STAGE3` readiness packet. A historically named `learning-lab-bin-boundary-green.txt` contains an expected intermediate stale-pin failure; the packet also labels it `learning-lab-bin-boundary-intermediate-stale-pin.txt`. It is not final PASS evidence.

This review is contained source/test evidence, not A8 acceptance. Math source review is conditional and execution remains blocked. Grid/Unified native lanes, real-data authentication/admission and Terminan viewer adoption remain unavailable. No production DB/provider/native Math execution or deployment was performed.
