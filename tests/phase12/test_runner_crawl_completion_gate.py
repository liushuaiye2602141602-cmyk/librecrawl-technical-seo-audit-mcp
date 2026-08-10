"""Regression: the crawl runner must not finish on a single terminal
snapshot (upstream start race)."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _status(is_running=True, status_str="running", crawled=10):
    return {
        "is_running": is_running,
        "status_str": status_str,
        "crawled": crawled,
    }


def test_single_terminal_snapshot_does_not_finish_crawl():
    from runner import _consecutive_terminal_reached
    # First poll right after start_crawl: upstream briefly reports idle/not
    # running with a few pages recorded — must NOT be terminal yet.
    terminal, count = _consecutive_terminal_reached(
        _status(is_running=False, status_str="idle", crawled=9), 0)
    assert terminal is False
    assert count == 1


def test_two_consecutive_terminal_snapshots_finish_crawl():
    from runner import _consecutive_terminal_reached
    terminal, count = _consecutive_terminal_reached(
        _status(is_running=False, status_str="idle", crawled=228), 0)
    assert terminal is False
    terminal, count = _consecutive_terminal_reached(
        _status(is_running=False, status_str="idle", crawled=228), count)
    assert terminal is True
    assert count == 2


def test_running_snapshot_resets_consecutive_count():
    from runner import _consecutive_terminal_reached
    _, count = _consecutive_terminal_reached(
        _status(is_running=False, status_str="idle", crawled=9), 0)
    terminal, count = _consecutive_terminal_reached(
        _status(is_running=True, status_str="running", crawled=20), count)
    assert terminal is False
    assert count == 0
