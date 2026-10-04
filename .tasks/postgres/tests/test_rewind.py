import contextlib
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
SOURCES = [ROOT / root / "database/patroni/app/scripts/pg_rewind"
           for root in ("kubernetes/apps", "kubernetes/cloud/apps")]


def load_wrapper(source):
    loader = importlib.machinery.SourceFileLoader("rewind_wrapper", str(source))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class RewindGuards(unittest.TestCase):
    @contextlib.contextmanager
    def invocation(self, source, major, args):
        wrapper = load_wrapper(source)
        with patch.dict(os.environ, {"PG_MAJOR": major}), \
             patch.object(wrapper.sys, "argv", ["pg_rewind", *args]), \
             patch.object(wrapper.os, "execv", side_effect=SystemExit) as execute, \
             patch.object(wrapper.subprocess, "run") as command:
            yield wrapper, execute, command

    def test_informational_flags_use_the_running_image_major_without_pgdata(self):
        for source in SOURCES:
            for major in ("17", "18", "19"):
                for flag in ("--version", "-V", "--help", "-?"):
                    with self.subTest(source=source, major=major, flag=flag), \
                         self.invocation(source, major, [flag]) as (wrapper, execute, command):
                        with self.assertRaises(SystemExit):
                            wrapper.main()
                        binary = f"/usr/lib/postgresql/{major}/bin/pg_rewind"
                        execute.assert_called_once_with(binary, [binary, flag])
                        command.assert_not_called()

    def test_invalid_image_major_cannot_select_a_binary(self):
        for source in SOURCES:
            for major in ("", "../18", "18/bin", "18.6", "１８"):
                with self.subTest(source=source, major=major), \
                     self.invocation(source, major, ["--version"]) as (wrapper, execute, command):
                    with self.assertRaisesRegex(RuntimeError, "PG_MAJOR"):
                        wrapper.main()
                    execute.assert_not_called()
                    command.assert_not_called()

    def test_rewind_requires_matching_data_major_before_touching_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            (data / "PG_VERSION").write_text("18\n")
            for source in SOURCES:
                with self.subTest(source=source), \
                     patch.dict(os.environ, {"HA_REWIND_PGDATA": str(data)}), \
                     self.invocation(source, "19", ["-D", str(data)]) as (wrapper, execute, command):
                    with self.assertRaisesRegex(RuntimeError, "major version"):
                        wrapper.main()
                    execute.assert_not_called()
                    command.assert_not_called()

    def test_matching_major_still_requires_a_dedicated_forensic_volume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data, forensics = root / "data", root / "forensics"
            data.mkdir()
            forensics.mkdir()
            (data / "PG_VERSION").write_text("19\n")
            for source in SOURCES:
                with self.subTest(source=source), \
                     patch.dict(os.environ, {"HA_REWIND_PGDATA": str(data),
                                             "HA_REWIND_QUARANTINE": str(forensics)}), \
                     self.invocation(source, "19", ["-D", str(data)]) as (wrapper, execute, command):
                    with self.assertRaisesRegex(RuntimeError, "dedicated volume mount"):
                        wrapper.main()
                    with patch.object(Path, "is_mount", return_value=True):
                        with self.assertRaisesRegex(RuntimeError, "separate filesystems"):
                            wrapper.main()
                    execute.assert_not_called()
                    command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
