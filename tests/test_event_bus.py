import queue

from pchome.services.event_bus import EventBus


def test_publish_delivers_to_subscriber():
    bus = EventBus()
    q = bus.subscribe()
    bus.publish({"type": "log", "msg": "hi"})
    assert q.get_nowait() == {"type": "log", "msg": "hi"}


def test_publish_fans_out_to_all_subscribers():
    bus = EventBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    bus.publish({"type": "log"})
    assert q1.get_nowait() == {"type": "log"}
    assert q2.get_nowait() == {"type": "log"}


def test_unsubscribe_stops_delivery():
    bus = EventBus()
    q = bus.subscribe()
    bus.unsubscribe(q)
    bus.publish({"type": "log"})
    assert q.empty()


def test_unsubscribe_unknown_queue_is_noop():
    bus = EventBus()
    bus.unsubscribe(queue.Queue())


def test_publish_with_no_subscribers_is_noop():
    bus = EventBus()
    bus.publish({"type": "log"})


def test_full_queue_drops_event_without_raising():
    bus = EventBus()
    q = bus.subscribe()
    for i in range(500):
        bus.publish({"i": i})
    bus.publish({"i": "overflow"})
    assert q.qsize() == 500
    assert q.get_nowait() == {"i": 0}
