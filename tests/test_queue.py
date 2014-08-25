from nose import tools

from cocaine.service import AsyncQueue
from cocaine.service import QueueFull, QueueEmpty
from concurrent.futures import TimeoutError
from cocaine.service import CocaineMonkeyPatch

CocaineMonkeyPatch()


def test_queue():
    item = "item"
    q = AsyncQueue()
    assert not q.full()
    assert q.empty()
    assert q.maxsize == 0
    q.put(item).wait(10)
    r = q.get().wait(1)
    assert r == item, r


@tools.raises(QueueFull)
def test_queue_full():
    size = 10
    item = "item"
    q = AsyncQueue(size)
    assert not q.full()
    for _ in range(0, size + 5):
        q.put_nowait(item)


@tools.raises(QueueEmpty)
def test_queue_empty():
    q = AsyncQueue()
    q.get_nowait()


@tools.raises(TimeoutError)
def test_queue_timeout_error():
    q = AsyncQueue()
    q.get().wait(0.2)
