# Independent Ed25519 key admission before signature assurance

Baseline593cf92b1cfbfb6a04961dd7f260349c01459cc0/tree08bbe80d13324f03b858dfe13c0e3ff48a5b4114.
PR56 source4108b9f24c309f09c2beef4c14ab26121a2934ec correctly identifies identity-key
forgery as unresolved P2: pinned identity public I=01+31zero bytes and R=I,S=0
can produce signatures_verifiedTrue without private-key possession. External
provisioning of the weak key was required; no unchanged-pin or G0/G1 bypass.

Before this change was integrated, an independent reviewer reproduced genuine
OpenSSL3.5.7 acceptance on593 for two arbitrary messages and independently checked
PyNaCl1.6.2 against affine Edwards arithmetic in a test-only oracle.306point
controls agree:8torsion,38noncanonical-y,2forbidden signs,128offcurve and112mixed
order rejected;16normal/RFCpublic/R points accepted. RFC8032 signature and8normal
signing controls pass. No handwritten curve implementation enters production.

Production trust-store intake and direct OpenSSLVerifier now validate public
points through PyNaCl/libsodium before signature assurance. Per-call capability
controls require valid RFCpoint,invalid identity and independently derived order8L
point98519eadf35b995233b51b5cd23e9cc5a28b639b5a4af0ec903cb960d81b7819.
Unavailable,alwaysTrue/False,integer-returning or old mixed-order semantics fail
closed without fallback. Key validation is not authority/possession/history/replay
or physical qualification. Native sandbox code/stage unchanged; native key-policy
qualification is not claimed by this Python-consumer fix.

Primary sources:
- https://github.com/jedisct1/libsodium/blob/master/src/libsodium/crypto_core/ed25519/core_ed25519.c
- https://doc.libsodium.org/advanced/point-arithmetic
- https://raw.githubusercontent.com/pyca/pynacl/main/CHANGELOG.rst
- https://pypi.org/pypi/PyNaCl/1.6.2/json

Version nuance: upstream documents mixed-order problems in older1.0.20 builds.
PyNaCl1.6.2 bundles patched1.0.20-stable2025-12-31 forCVE-2025-69277; do not infer
patch identity from sodium_version_string alone. Independent vectors and capability
checks are required. Version pinned1.6.2 in dev/research extras; ordinary nonresearch
imports do not load validator. Offline wheels and licenses checked against primary
PyPI SHA256/size and advisory snapshot (not a vulnerability-free guarantee).
PyNaCl Apache2,libsodium ISC,cffi MIT,pycparser BSD licenses retained in delivery.

RED9failed/1passed on existing production entrypoints; GREEN83passed including
signature,receipt,owner consumers and14new key/backend controls. Independent
candidate review subsequently tested all306points through both predicate and
trust-store intake,6broken-backend and7malformed controls,actual forged receipt
rejection before OpenSSL and genuine RFC verification. Accepted before integration.

Independent baseline confirmation SHA256:
43ad1a8c4f6b7ccc244149e745e2dd1d78b67695ae2b95ed39f7065303df74a6.
Independent candidate review SHA256:
330f0c9ec5f8c76d3f2939ba796b43b6760b193ccb30072ad59a7c14596868dc.
Evidence manifest SHA256:
5665f77347b15be36e5b6db27bf711fe8051233ba1f60648957e8ad40aa2a3e2.
Raw candidate module SHA256848fc8d866694084214b8b9ef6b13c818377a0edb7b100c6db28709c0c24bd9d
is workstation bytes; canonical Git blob/newline bindings are separately recorded.
Self-signature of software evidence is integrity only,not owner/provider identity.

P0:newconfirmednone. P2:Python key-assurance flaw corrected. P1physical/trust/time/
replay/namespace/executable identity/native isolation/source/OOS prerequisites
remainBLOCKED. No physical collection,production operation,VM provisioning,G1
Execute/Cleanup,deployment or trading. No real trusted secrets created.
