"""Offline ZIP integrity inspection; never authorizes physical execution."""
import hashlib
import io
import re
import zipfile

SHA256 = re.compile(r"^[0-9a-f]{64}$")


def inspect_zip_bytes(payload, *, expected_sha256, max_archive=32_000_000,
                      max_entries=128, max_uncompressed=64_000_000):
    issues = []
    if (any(type(x) is not int or x <= 0 for x in (max_archive, max_entries, max_uncompressed))):
        return {"status": "BLOCKED", "issues": ["invalid_limits"]}
    if (type(payload) is not bytes or len(payload) > max_archive
            or type(expected_sha256) is not str or not SHA256.fullmatch(expected_sha256)):
        return {"status": "BLOCKED", "issues": ["invalid_input"]}
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected_sha256:
        issues.append("archive_digest_mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = archive.infolist()
            if not members or len(members) > max_entries:
                issues.append("entry_count")
            names = set()
            total = 0
            for entry in members:
                name = entry.filename
                if (not name or name.startswith(("/", "\\"))
                        or "\\" in name or ":" in name or
                        any(part in ("", ".", "..") for part in name.rstrip("/").split("/"))):
                    issues.append("unsafe_entry_name")
                components = name.rstrip("/").split("/")
                reserved = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
                reserved.update("COM" + str(n) for n in range(1, 10))
                reserved.update("LPT" + str(n) for n in range(1, 10))
                if (name.endswith("//") or any(
                    not part or part.endswith((" ", ".")) or
                    any(ord(c) < 32 or c in '<>:"|?*' for c in part) or
                    part.split(".")[0].upper() in reserved
                    for part in components
                )):
                    issues.append("unsafe_windows_entry")
                canonical = name.rstrip("/").casefold()
                if canonical in names:
                    issues.append("duplicate_entry_name")
                names.add(canonical)
                if entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    issues.append("unsupported_compression")
                if entry.flag_bits & 0x1:
                    issues.append("encrypted_entry")
                if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    issues.append("symlink_entry")
                if entry.file_size > max_uncompressed:
                    issues.append("oversized_member")
                if entry.file_size and entry.compress_size == 0:
                    issues.append("invalid_compressed_size")
                total += entry.file_size
                if total > max_uncompressed:
                    issues.append("uncompressed_limit")
                    break
            if not issues:
                for entry in members:
                    with archive.open(entry) as stream:
                        read = 0
                        while chunk := stream.read(65536):
                            read += len(chunk)
                            if read > entry.file_size or read > max_uncompressed:
                                issues.append("entry_size_mismatch")
                                break
                    if read != entry.file_size:
                        issues.append("entry_size_mismatch")
    except (zipfile.BadZipFile, EOFError, OSError, RuntimeError, ValueError):
        issues.append("malformed_zip")
    return {"status": "BLOCKED", "archive_sha256": actual,
            "zip_structure_valid": not issues,
            "issues": sorted(set(issues)) or ["junit_and_signed_provenance_not_verified"]}
