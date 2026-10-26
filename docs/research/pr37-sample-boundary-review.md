# PR37 supervised sample boundary review

Reviewed exact PR37 head `5541afa3e37781642406fb7774d2fbc09ac6fc1d`
against root `f3dfee421cdadce39df1c3aba107f623ceeb0b55` and the unchanged
sample implementation at baseline `c09592be649d249c6b082a5e21cbeea2800a0049`.
No PR37 implementation or workflow is imported.

The PR changes the exclusive loop stop from `n - horizon` to
`n - horizon + 1`. The extra origin is `n - horizon`; adding its horizon
addresses element `n`, beyond the final legal index `n - 1`. The baseline
already emits the last legal target. Existing tests cover a longer history;
the new regression covers the exact minimum accepted history for three
window/horizon combinations: `(2,2)`, `(4,3)`, `(5,7)`.

Exact source provenance:

| PR37 path | Git blob |
| --- | --- |
| strattester/research/financial_structure_dataset.py | 44a34558ae39588ff77895447492d0af778852cd |
| research/test_independent_system_math_20261026.py | e20e1c0d6ec6e1540b85772a372ff1aeeef3a3a4 |
| research/independent_resampling_oracle_20261026.py | c7a50e6b99b5fd4472a113775a7f8f970e435d70 |
| research/test_independent_resampling_oracle_20261026.py | 4a47e1095b0469341c26578a364179698fa15d9c |

The new test is independently written from the index boundary, not copied
from the PR. To check sensitivity, the exact PR37 dataset module was read
with `git show`, compiled in memory under its real package name, and the
new real-API regression invoked for each pair. All three produced the
expected RED: `IndexError: tuple index out of range`. No source file was
modified for this demonstration.

With the baseline implementation, existing-venv command:

```text
-m pytest tests/research/test_financial_structure_dataset.py -q --basetemp=../grid-pr37-boundary-green-20261026
9 passed in 0.13s
```

Separately, all 16 PR37 independent system math tests passed with the root
sample implementation. With the PR sample implementation, 13 passed and
three failed with IndexError (target alignment and two future-mutation
cases). Thus those tests are useful evidence against importing its fix,
not evidence that root lacks the last valid sample.

The PR37 standalone resampling oracle's three tests passed when executed
from exact Git source. They validate that oracle itself; they do not call
a product candle-resampling implementation. No production resampling or
source-data qualification follows. No native or physical code was executed.
