import hashlib
import io
import unittest
import zipfile
from physical_zip_integrity import inspect_zip_bytes


def archive(entries):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as z:
        for name, value in entries:
            z.writestr(name, value)
    return data.getvalue()


def inspect(payload, **kwargs):
    return inspect_zip_bytes(payload, expected_sha256=hashlib.sha256(payload).hexdigest(), **kwargs)


class ZipIntegrityTests(unittest.TestCase):
    def test_valid_archive_still_blocked(self):
        result = inspect(archive([("test.xml", b"<testsuite/>")]))
        self.assertTrue(result["zip_structure_valid"])
        self.assertEqual(result["status"], "BLOCKED")

    def test_hash_mismatch(self):
        data = archive([("a", b"x")])
        self.assertIn("archive_digest_mismatch",
                      inspect_zip_bytes(data, expected_sha256="0"*64)["issues"])

    def test_traversal(self):
        self.assertIn("unsafe_entry_name", inspect(archive([("../escape", b"x")]))["issues"])

    def test_casefold_duplicate(self):
        self.assertIn("duplicate_entry_name", inspect(archive([("A", b"x"), ("a", b"y")]))["issues"])

    def test_bomb_budget(self):
        self.assertIn("uncompressed_limit", inspect(archive([("big", b"x"*10000)]),
                                                   max_uncompressed=100)["issues"])

    def test_malformed_zip(self):
        self.assertIn("malformed_zip", inspect(b"not a zip")["issues"])


if __name__ == "__main__":
    unittest.main()
