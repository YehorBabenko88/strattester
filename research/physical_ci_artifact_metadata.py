"""Independent offline CI artifact metadata verifier. Never grants G1."""
import re

SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
REQUIRED = frozenset({"core", "data", "training", "security", "math", "cpu",
                      "integration", "native-component-proof", "acceptance"})


def verify_artifact_metadata(items, *, head, run_id):
    """Validate GitHub API metadata only, not downloaded ZIP bytes."""
    errors = []
    if type(head) is not str or not SHA.fullmatch(head):
        errors.append("invalid_head")
    if type(run_id) is not int or run_id <= 0:
        errors.append("invalid_run_id")
    if type(items) is not list:
        return {"status": "BLOCKED", "errors": errors + ["invalid_artifacts"]}
    seen = set()
    artifact_ids = set()
    for index, item in enumerate(items):
        if type(item) is not dict:
            errors.append(f"invalid_item_{index}")
            continue
        name = item.get("name")
        if type(name) is not str or not name.endswith("-" + head):
            errors.append(f"name_{index}")
            continue
        prefix = name[:-(len(head) + 1)]
        expected_names = {("native-component-proof" if kind == "native-component-proof" else "financial-" + kind): kind for kind in REQUIRED}
        if prefix not in expected_names:
            errors.append(f"unknown_or_duplicate_{index}")
            continue
        prefix = expected_names[prefix]
        if prefix in seen:
            errors.append(f"unknown_or_duplicate_{index}")
        seen.add(prefix)
        artifact_id = item.get("id")
        if type(artifact_id) is not int or artifact_id <= 0 or artifact_id in artifact_ids:
            errors.append(f"artifact_id_{index}")
        else:
            artifact_ids.add(artifact_id)
        digest = item.get("digest")
        if type(digest) is not str or not DIGEST.fullmatch(digest):
            errors.append(f"digest_{index}")
        if type(item.get("size_in_bytes")) is not int or item["size_in_bytes"] <= 0:
            errors.append(f"size_{index}")
        if item.get("expired") is not False:
            errors.append(f"expired_{index}")
        run = item.get("workflow_run")
        if type(run) is not dict or type(run.get("id")) is not int or run["id"] != run_id or run.get("head_sha") != head:
            errors.append(f"provenance_{index}")
    if seen != REQUIRED:
        errors.append("missing_required_artifacts")
    # Metadata alone can never attest ZIP content, JUnit, run attempt, or signing.
    return {"status": "BLOCKED", "metadata_valid": not errors,
            "errors": errors or ["zip_bytes_junit_attempt_and_signature_unverified"]}
