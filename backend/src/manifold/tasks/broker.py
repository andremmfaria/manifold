from taskiq.middlewares import SmartRetryMiddleware
from taskiq_redis import RedisAsyncResultBackend, RedisStreamBroker

from manifold.config import settings

broker = (
    RedisStreamBroker(url=settings.redis_url)
    .with_result_backend(
        RedisAsyncResultBackend(
            redis_url=settings.redis_url, result_ex_time=settings.taskiq_result_ttl
        )
    )
    .with_middlewares(
        SmartRetryMiddleware(default_retry_count=3, use_jitter=True, use_delay_exponent=True)
    )
)
broker.is_worker_process = False
