from taskiq_redis import RedisAsyncResultBackend, RedisStreamBroker

from manifold.config import settings

broker = RedisStreamBroker(url=settings.redis_url).with_result_backend(
    RedisAsyncResultBackend(redis_url=settings.redis_url)
)
broker.is_worker_process = False
