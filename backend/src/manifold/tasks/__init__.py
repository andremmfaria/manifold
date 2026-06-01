"""Taskiq task registry.

Importing this package must import every task module so their ``@broker.task``
decorators run and register the tasks on the broker. The worker is launched as
``taskiq worker manifold.tasks.broker:broker manifold.tasks`` — it imports this
package for discovery, so without these imports no task is registered and the
worker reports ``task "..." is not found``.
"""

from manifold.tasks import alarms, maintenance, notifications, sync

__all__ = ["alarms", "maintenance", "notifications", "sync"]
