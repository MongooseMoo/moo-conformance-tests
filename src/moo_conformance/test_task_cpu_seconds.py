"""Conformance for seconds budgets across I/O waits and suspension."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import monotonic, sleep

import pytest

from .conditions import config_skip_reason
from .schema import MooTestSuite, Requirements
from .test_conformance import _has_builtin


@pytest.fixture
def managed_wizard(runner, managed_server):
    if managed_server is None:
        pytest.skip(config_skip_reason("managed_server"))
    runner.prepare_suite_environment(MooTestSuite(
        name="task_cpu_seconds", requires=Requirements(builtins=["seconds_left"]),
    ))
    runner.transport.switch_user("wizard")
    return runner.transport


def _restore_seconds_option_after_test(request, runner, option):
    original = runner.transport.execute(f'''
        try return {{toliteral($server_options.{option})}};
        except (E_PROPNF) return {{}}; endtry
    ''')
    assert original.success, original
    if original.value:
        restore = f"$server_options.{option} = {original.value[0]};"
    else:
        restore = f'''
            try delete_property($server_options, "{option}");
            except (E_PROPNF) endtry
        '''

    def restore_option():
        runner._ensure_transport_connected()
        result = runner.transport.execute(f"{restore} load_server_options(); return 1;")
        assert result.success, result

    request.addfinalizer(restore_option)


@pytest.mark.conformance
def test_task_seconds_ignore_synchronous_io_wait(request, runner, managed_wizard, moo_server_dir):
    if not hasattr(os, "mkfifo"):
        pytest.skip("Requires POSIX named pipes")
    for builtin in (
        "file_open", "file_close", "ftime", "load_server_options", "seconds_left", "toliteral",
    ):
        if not _has_builtin(runner, builtin):
            pytest.skip(f"Requires builtin: {builtin}")

    transport = managed_wizard
    previous_timeout = transport.command_timeout
    request.addfinalizer(lambda: setattr(transport, "command_timeout", previous_timeout))
    transport.command_timeout = 15.0

    files = Path(moo_server_dir) / "files"
    fifo = files / "task_cpu_seconds.fifo"
    ready = files / "task_cpu_seconds.ready"
    os.mkfifo(fifo)
    request.addfinalizer(lambda: fifo.unlink(missing_ok=True))
    request.addfinalizer(lambda: ready.unlink(missing_ok=True))

    created = transport.execute("return tostr(create($nothing));")
    assert created.success, created
    driver = created.value

    def recycle_driver():
        runner._ensure_transport_connected()
        result = transport.execute(f"recycle({driver}); return 1;")
        assert result.success, result

    request.addfinalizer(recycle_driver)
    _restore_seconds_option_after_test(request, runner, "fg_seconds")
    setup = transport.execute(rf'''
        try
          $server_options.fg_seconds = 2;
        except (E_PROPNF)
          add_property($server_options, "fg_seconds", 2, {{player, "r"}});
        endtry
        load_server_options();
        add_verb({driver}, {{player, "xd", "probe"}}, {{"none", "none", "none"}});
        return set_verb_code({driver}, "probe", {{
            "id = task_id();",
            "start = ftime();",
            "file_close(file_open(\"task_cpu_seconds.ready\", \"w-tn\"));",
            "handle = file_open(\"task_cpu_seconds.fifo\", \"r-tn\");",
            "file_close(handle);",
            "return {{task_id() == id, ftime() - start > 2.0, seconds_left() > 0}};"
        }});
    ''')
    assert setup.success and setup.value == [], setup

    def release_fifo():
        deadline = monotonic() + 5.0
        while not ready.exists() and monotonic() < deadline:
            sleep(0.01)
        signalled = ready.exists()
        if signalled:
            sleep(2.5)
        # O_RDWR opens without a reader even if the task failed before reaching the FIFO.
        return signalled, os.open(fifo, os.O_RDWR | os.O_NONBLOCK)

    with ThreadPoolExecutor(max_workers=1) as executor:
        writer = executor.submit(release_fifo)
        try:
            result = transport.execute(f"return {driver}:probe();")
        finally:
            signalled, descriptor = writer.result()
            os.close(descriptor)
    assert signalled, "driver did not reach the named-pipe open"
    assert result.success, result
    assert result.value == [1, 1, 1], result


@pytest.mark.conformance
def test_task_seconds_reset_on_resume(request, runner, managed_wizard):
    for builtin in ("task_id", "seconds_left", "suspend", "load_server_options", "toliteral"):
        if not _has_builtin(runner, builtin):
            pytest.skip(f"Requires builtin: {builtin}")

    _restore_seconds_option_after_test(request, runner, "bg_seconds")
    result = managed_wizard.execute('''
        id = task_id();
        before = seconds_left();
        budget = before + 5;
        try
          $server_options.bg_seconds = budget;
        except (E_PROPNF)
          add_property($server_options, "bg_seconds", budget, {player, "r"});
        endtry
        load_server_options();
        suspend(1);
        after = seconds_left();
        return {task_id() == id, after > before, after <= budget};
    ''')
    assert result.success, result
    assert result.value == [1, 1, 1], result
