import threading
import time

import pytest

from pchome.core.cancel import JobCancelled, cancellable_sleep, check_cancel


class TestCheckCancel:
    def test_none_event_is_noop(self):
        check_cancel(None)

    def test_unset_event_is_noop(self):
        check_cancel(threading.Event())

    def test_set_event_raises(self):
        event = threading.Event()
        event.set()
        with pytest.raises(JobCancelled):
            check_cancel(event)


class TestCancellableSleep:
    def test_sleeps_full_duration_without_event(self):
        start = time.monotonic()
        cancellable_sleep(0.05, None)
        assert time.monotonic() - start >= 0.05

    def test_sleeps_full_duration_when_event_not_set(self):
        event = threading.Event()
        start = time.monotonic()
        cancellable_sleep(0.05, event)
        assert time.monotonic() - start >= 0.05

    def test_already_set_event_raises_immediately(self):
        event = threading.Event()
        event.set()
        start = time.monotonic()
        with pytest.raises(JobCancelled):
            cancellable_sleep(5, event)
        assert time.monotonic() - start < 1

    def test_event_set_during_sleep_raises_early(self):
        event = threading.Event()

        def setter():
            time.sleep(0.02)
            event.set()

        threading.Thread(target=setter).start()
        start = time.monotonic()
        with pytest.raises(JobCancelled):
            cancellable_sleep(5, event)
        assert time.monotonic() - start < 1
