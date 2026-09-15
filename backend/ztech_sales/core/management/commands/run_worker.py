"""Outbox worker.

Claims due messages from the durable database outbox and runs the handler
registered for each topic. Several workers may run at once: claiming uses
``SELECT ... FOR UPDATE SKIP LOCKED`` so they never contend for the same row.

Delivery is at-least-once. A handler must therefore be idempotent, or must
record its own completion in a way a repeat can detect.
"""

from __future__ import annotations

import logging
import signal
import socket
import time
from typing import Any

from django.core.management.base import BaseCommand

from ztech_sales.core.context import request_context
from ztech_sales.core.models import OutboxMessage
from ztech_sales.core.outbox_handlers import HandlerNotRegistered, dispatch

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process queued outbox messages (documents, email, integration events)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--batch-size", type=int, default=10)
        parser.add_argument("--poll-seconds", type=float, default=2.0)
        parser.add_argument(
            "--once", action="store_true", help="Process one batch and exit. Used by tests and by cron."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        worker_id = f"{socket.gethostname()}:{time.time_ns()}"[:64]
        self._running = True

        def _stop(signum: int, frame: Any) -> None:
            self.stdout.write("Shutdown requested; finishing the current batch.")
            self._running = False

        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)

        self.stdout.write(self.style.SUCCESS(f"Outbox worker {worker_id} started."))
        while self._running:
            processed = self._process_batch(worker_id, options["batch_size"])
            if options["once"]:
                self.stdout.write(f"Processed {processed} message(s).")
                return
            if processed == 0:
                time.sleep(options["poll_seconds"])
        self.stdout.write("Outbox worker stopped.")

    def _process_batch(self, worker_id: str, batch_size: int) -> int:
        messages = OutboxMessage.objects.claim_batch(worker_id=worker_id, limit=batch_size)
        for message in messages:
            with request_context(source="worker"):
                try:
                    result = dispatch(message)
                except HandlerNotRegistered as exc:
                    # An unknown topic is a deployment error, not a transient
                    # fault: retrying it forever would hide the problem.
                    message.attempts = message.max_attempts
                    message.mark_failed(str(exc))
                    logger.error("Outbox message %s: %s", message.id, exc)
                except Exception as exc:  # noqa: BLE001 - one bad message must not stop the worker
                    message.mark_failed(repr(exc))
                    logger.exception("Outbox message %s failed", message.id)
                else:
                    message.mark_succeeded(result)
        return len(messages)
