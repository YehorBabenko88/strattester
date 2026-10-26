import unittest
from physical_ci_artifact_metadata import REQUIRED, verify_artifact_metadata

HEAD = "4f3a4bbb9a2f6c0cc3e87fbb0af4fed1dfcc3fd7"
RUN = 40350796074


def fixtures():
    result = []
    for index, name in enumerate(sorted(REQUIRED), start=1):
        prefix = name if name == "native-component-proof" else "financial-" + name
        result.append(dict(id=index, name=prefix + "-" + HEAD, digest="sha256:" + "a"*64,
                           size_in_bytes=100, expired=False,
                           workflow_run={"id": RUN, "head_sha": HEAD}))
    return result


class ArtifactMetadataTests(unittest.TestCase):
    def test_complete_metadata_still_blocks_physical(self):
        report = verify_artifact_metadata(fixtures(), head=HEAD, run_id=RUN)
        self.assertTrue(report["metadata_valid"])
        self.assertEqual(report["status"], "BLOCKED")

    def test_missing_artifact(self):
        report = verify_artifact_metadata(fixtures()[:-1], head=HEAD, run_id=RUN)
        self.assertFalse(report["metadata_valid"])

    def test_stale_head(self):
        data = fixtures()
        data[0]["workflow_run"]["head_sha"] = "b"*40
        self.assertFalse(verify_artifact_metadata(data, head=HEAD, run_id=RUN)["metadata_valid"])

    def test_bad_digest(self):
        data = fixtures()
        data[0]["digest"] = "sha256:bad"
        self.assertFalse(verify_artifact_metadata(data, head=HEAD, run_id=RUN)["metadata_valid"])

    def test_duplicate(self):
        data = fixtures()
        data[-1] = data[0].copy()
        self.assertFalse(verify_artifact_metadata(data, head=HEAD, run_id=RUN)["metadata_valid"])

    def test_artifact_name_alias_denied(self):
        data = fixtures()
        data[0]["name"] = data[0]["name"].replace("financial-", "", 1)
        self.assertFalse(verify_artifact_metadata(data, head=HEAD, run_id=RUN)["metadata_valid"])

    def test_wrong_native_prefix_denied(self):
        data = fixtures()
        for item in data:
            if item["name"].startswith("native-component-proof-"):
                item["name"] = "financial-" + item["name"]
        self.assertFalse(verify_artifact_metadata(data, head=HEAD, run_id=RUN)["metadata_valid"])

    def test_duplicate_artifact_id(self):
        data = fixtures()
        data[1]["id"] = data[0]["id"]
        self.assertFalse(verify_artifact_metadata(data, head=HEAD, run_id=RUN)["metadata_valid"])

    def test_missing_artifact_id(self):
        data = fixtures()
        del data[0]["id"]
        self.assertFalse(verify_artifact_metadata(data, head=HEAD, run_id=RUN)["metadata_valid"])

    def test_boolean_run_id(self):
        self.assertFalse(verify_artifact_metadata(fixtures(), head=HEAD, run_id=True)["metadata_valid"])


if __name__ == "__main__":
    unittest.main()
