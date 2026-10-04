import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from subprocess import CompletedProcess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import Refused, Store, change_kind, checkpoint, image_ref
import gitops


class Guards(unittest.TestCase):
    def test_missing_or_unrelated_checks_cannot_allow_merge(self):
        state = {"id": "test", "config": {"repository": "/unused", "github_repository": "owner/repository"},
                 "stage_pr": {"number": 1, "url": "https://example.invalid/pr/1", "headRefOid": "expected"}}
        responses = [
            CompletedProcess([], 1, "", "no checks reported"),
            CompletedProcess([], 0, json.dumps([{"name": "Labeler", "workflow": "Labeler"}]), ""),
            CompletedProcess([], 8, json.dumps([{"name": "check", "workflow": "PostgreSQL Operations"}]), ""),
            CompletedProcess([], 1, "check failed", ""),
        ]
        with patch("gitops.output", return_value=json.dumps({"state": "OPEN", "headRefOid": "expected"})), \
             patch("gitops.run", side_effect=responses) as command, patch("common.time.sleep"):
            with self.assertRaisesRegex(Refused, "checks have not passed"):
                gitops.merge_phase(Mock(path=Path("/unused")), state, "stage")
        self.assertEqual(command.call_count, 4)
        self.assertTrue(all(call.args[0][1:3] == ["pr", "checks"] for call in command.call_args_list))
        self.assertIn("--watch", command.call_args_list[-1].args[0])

    def test_rejects_unpinned_images_and_downgrades(self):
        with self.assertRaises(Refused):
            image_ref("ghcr.io/heavybullets8/postgres-patroni:latest")
        old = {"postgres": "18.6", "patroni": "4.1.5", "uid": 999, "os": "debian:13"}
        for replacement in ({"postgres": "18.5"}, {"patroni": "4.1.4"}, {"uid": 1000}, {"os": "debian:14"}):
            with self.subTest(replacement=replacement), self.assertRaises(Refused):
                change_kind(old, dict(old, **replacement))

    def test_failed_phase_remains_resumable_and_success_is_not_repeated(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            state = {"id": "test", "completed": [], "active": None}
            failed = Mock(side_effect=RuntimeError("lost connection"))
            with self.assertRaises(RuntimeError):
                checkpoint(store, state, "upgrade", failed)
            saved = store.load("test")
            self.assertEqual(saved["completed"], [])
            self.assertEqual(saved["active"], "upgrade")
            success = Mock()
            checkpoint(store, saved, "upgrade", success)
            checkpoint(store, saved, "upgrade", success)
            success.assert_called_once()

    def test_state_is_private_and_cannot_escape_its_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            store.save("test", {"safe": True})
            self.assertEqual((Path(directory) / "test.json").stat().st_mode & 0o777, 0o600)
            with self.assertRaises(Refused):
                store.load("../elsewhere")


if __name__ == "__main__":
    unittest.main()
