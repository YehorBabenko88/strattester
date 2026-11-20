# Closed-map resource rejection fix

Independent consumer review confirmed Data98 da80e53 builds set(packet) before rejecting wrong cardinality. Own reproduction: 100000-field invalid dict peak 4195847 bytes; eight nested/public closed-map paths also built input-sized key sets. Nine tests were RED before the fix.

All closed packet/request/context/availability/row/evidence/proof maps now check exact dict type and O1 cardinality before any iteration; then require exact string keys of at most64 characters and membership in the small fixed contract. Funding evidence fields use bounded subset cardinality and fixed membership. No input-sized key set is constructed. Valid schema, hashes, financial logic and distinct clock-domain policy are unchanged.

497 scoped source tests pass with reviewed Math d88. Source scope only until independent artifact/reviewer evidence; real provider/PG/native NOT_RUN. The invalid100000-field input is constructed before tracemalloc starts; regression enforces transient rejection peak below256KiB.
