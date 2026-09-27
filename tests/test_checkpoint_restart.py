"""Restart must adopt a completed fresh checkpoint before stopping Toast."""
import os
from unittest.mock import Mock

import pytest

from moo_conformance.runner import YamlTestRunner
from moo_conformance.schema import validate_test_suite
from moo_conformance.server import ManagedServer, snapshot_regular_files


def test_restart_waits_for_publication_and_ignores_stale_or_partial_output(tmp_path, monkeypatch):
    database = tmp_path / 'Test.db'
    database.write_text('old input')
    stale = tmp_path / 'Test.db.out'
    stale.write_text('stale checkpoint')
    os.utime(stale, (4000000000, 4000000000))  # Newest timestamp must not trump freshness.
    boundary = snapshot_regular_files(tmp_path)
    partial = tmp_path / 'Test.db.new.#1#'
    partial.write_text('fresh checkpoint')
    server = ManagedServer('fake {db} {port}', database)
    server._db_copy_path = database
    server._temp_dir = str(tmp_path)
    events = []
    server.stop = lambda **kwargs: events.append(('stop', database.read_text()))
    server.start = lambda **kwargs: events.append(('start', database.read_text()))

    def publish(seconds):
        assert events == []  # Neither stop nor stale adoption may precede publication.
        assert database.read_text() == 'old input'
        partial.rename(tmp_path / 'Test.db.new')

    monkeypatch.setattr('moo_conformance.server.time.sleep', publish)
    server.restart(checkpoint_timeout_ms=1000, checkpoint_boundary=boundary)
    assert events == [('stop', 'fresh checkpoint'), ('start', 'fresh checkpoint')]


def test_checkpoint_timeout_preserves_live_server_and_old_input(tmp_path):
    database = tmp_path / 'Test.db'
    database.write_text('old input')
    (tmp_path / 'Test.db.new').write_text('stale checkpoint')
    boundary = snapshot_regular_files(tmp_path)
    server = ManagedServer('fake {db} {port}', database)
    server._db_copy_path = database
    server._temp_dir = str(tmp_path)
    server.stop = Mock()
    server.start = Mock()
    with pytest.raises(TimeoutError, match='fresh completed checkpoint'):
        server.restart(checkpoint_timeout_ms=0, checkpoint_boundary=boundary)
    server.stop.assert_not_called()
    server.start.assert_not_called()
    assert database.read_text() == 'old input'


def test_yaml_checkpoint_deadline_reaches_restart_with_test_boundary(tmp_path):
    suite = validate_test_suite({'name': 'checkpoint', 'tests': [{
        'name': 'wait', 'steps': [{'restart_server': {'checkpoint_timeout_ms': 5000}}],
    }]})
    transport = Mock()
    transport.current_user = 'wizard'
    server = Mock()
    server.host = 'localhost'
    server.port = 12345
    server.process_file_snapshot = {}
    runner = YamlTestRunner(transport, managed_server=server)
    boundary = {'Test.db.new': (1, 2, 3, 4, 5)}
    runner._file_boundary = boundary
    runner._execute_steps(suite.tests[0])
    server.restart.assert_called_once_with(
        down_ms=0, checkpoint_timeout_ms=5000, checkpoint_boundary=boundary)


@pytest.mark.parametrize('deadline', [-1, True, '5000', 1.5, None])
def test_checkpoint_deadline_rejects_invalid_values(deadline):
    with pytest.raises(ValueError, match='checkpoint_timeout_ms'):
        validate_test_suite({'name': 'checkpoint', 'tests': [{
            'name': 'invalid', 'steps': [{'restart_server': {'checkpoint_timeout_ms': deadline}}],
        }]})
