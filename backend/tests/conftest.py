import pytest
from taskiq import InMemoryBroker

from manifold.tasks.broker import broker


@pytest.fixture(autouse=True)
def use_in_memory_broker():
    broker._broker = InMemoryBroker()
    broker.is_worker_process = True
    yield
    broker.is_worker_process = False
