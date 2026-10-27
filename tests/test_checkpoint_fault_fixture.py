import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def fault(tmp_path):
    base = tmp_path / "moo_conformance_fault"
    executable = base / "executables" / "checkpoint_fault"
    executable.parent.mkdir(parents=True)
    source = Path(__file__).parents[1] / "src/moo_conformance/_exec_fixtures/checkpoint_fault"
    shutil.copyfile(source, executable)
    (base / "profile.json").write_text("{}", encoding="utf-8")

    def run(operation):
        return subprocess.run(
            [sys.executable, str(executable), operation], capture_output=True, text=True,
        )

    return base, run


def test_publish_fault_restores_existing_output(fault):
    base, run = fault
    output = base / "Test.db.new"
    output.write_text("existing checkpoint", encoding="utf-8")
    assert run("publish").returncode == 0
    assert (output / "callback-obstruction").is_file()
    assert run("publish").returncode != 0
    assert run("clear-publish").returncode == 0
    assert output.read_text(encoding="utf-8") == "existing checkpoint"


@pytest.mark.skipif(os.name != "posix", reason="POSIX symlink and /dev/full fixture")
def test_write_fault_only_removes_its_own_symlink(fault):
    base, run = fault
    target = base / "Test.db.new.#1#"
    assert run("write").returncode == 0
    assert target.readlink() == Path("/dev/full")
    assert run("clear-write").returncode == 0
    target.write_text("unrelated", encoding="utf-8")
    assert run("write").returncode != 0
    assert run("clear-write").returncode != 0
    assert target.read_text(encoding="utf-8") == "unrelated"


def test_fault_requires_managed_directory(fault):
    base, run = fault
    (base / "profile.json").unlink()
    assert run("publish").returncode != 0
    assert not (base / "Test.db.new").exists()
