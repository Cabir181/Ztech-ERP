"""The durable outbox and its worker."""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.utils import timezone

from ztech_sales.core.models import OutboxMessage, OutboxStatus
from ztech_sales.core.outbox_handlers import HandlerNotRegistered, dispatch, register, registered_topics

pytestmark = pytest.mark.django_db


def test_a_message_is_queued_as_pending_and_due_immediately(company):
    message = OutboxMessage.objects.enqueue(topic="core.noop", payload={"a": 1}, company=company)
    assert message.status == OutboxStatus.PENDING
    assert message in list(OutboxMessage.objects.due())


def test_an_idempotency_key_prevents_a_duplicate(company):
    first = OutboxMessage.objects.enqueue(
        topic="core.noop", payload={"a": 1}, company=company, idempotency_key="quote-123-issued"
    )
    second = OutboxMessage.objects.enqueue(
        topic="core.noop", payload={"a": 1}, company=company, idempotency_key="quote-123-issued"
    )
    assert first is not None
    # A retried request produces one message, not two - which is what keeps a
    # double-clicked button from sending the customer two emails.
    assert second is None
    assert OutboxMessage.objects.filter(idempotency_key="quote-123-issued").count() == 1


def test_a_message_scheduled_for_later_is_not_due_yet(company):
    OutboxMessage.objects.enqueue(
        topic="core.noop",
        payload={},
        company=company,
        available_at=timezone.now() + timezone.timedelta(hours=1),
    )
    assert list(OutboxMessage.objects.due()) == []


def test_a_failure_is_retried_with_growing_backoff(company):
    message = OutboxMessage.objects.enqueue(topic="core.noop", payload={}, company=company)
    message.attempts = 1
    message.mark_failed("connection refused", retry_base_seconds=30)

    message.refresh_from_db()
    assert message.status == OutboxStatus.FAILED
    assert message.last_error == "connection refused"
    first_delay = (message.available_at - timezone.now()).total_seconds()
    assert 25 < first_delay <= 30

    message.attempts = 3
    message.mark_failed("connection refused", retry_base_seconds=30)
    message.refresh_from_db()
    second_delay = (message.available_at - timezone.now()).total_seconds()
    assert second_delay > first_delay


def test_retries_stop_once_they_are_exhausted(company):
    message = OutboxMessage.objects.enqueue(topic="core.noop", payload={}, company=company, max_attempts=3)
    message.attempts = 3
    message.mark_failed("still failing")

    message.refresh_from_db()
    # A dead message stays visible with its last error rather than disappearing
    # or being retried forever.
    assert message.status == OutboxStatus.DEAD
    assert message.completed_at is not None
    assert message not in list(OutboxMessage.objects.due())
    assert message.last_error == "still failing"


def test_a_long_error_is_truncated_rather_than_overflowing(company):
    message = OutboxMessage.objects.enqueue(topic="core.noop", payload={}, company=company)
    message.attempts = 1
    message.mark_failed("x" * 20000)
    message.refresh_from_db()
    assert len(message.last_error) == 8000


def test_an_unregistered_topic_is_reported_clearly(company):
    message = OutboxMessage.objects.enqueue(topic="sales.not_implemented", payload={}, company=company)
    with pytest.raises(HandlerNotRegistered, match="sales.not_implemented"):
        dispatch(message)


def test_registering_the_same_topic_twice_is_refused():
    with pytest.raises(RuntimeError, match="already registered"):
        register("core.noop")(lambda message: None)


def test_the_worker_processes_a_batch_and_records_the_result(company):
    OutboxMessage.objects.enqueue(topic="core.noop", payload={"hello": "world"}, company=company)
    call_command("run_worker", "--once", "--batch-size", "5", verbosity=0)

    message = OutboxMessage.objects.get()
    assert message.status == OutboxStatus.SUCCEEDED
    assert message.attempts == 1
    assert message.completed_at is not None
    assert message.result == {"echo": {"hello": "world"}}


def test_the_worker_keeps_going_when_one_message_fails(company):
    OutboxMessage.objects.enqueue(topic="sales.not_implemented", payload={}, company=company)
    OutboxMessage.objects.enqueue(topic="core.noop", payload={"ok": True}, company=company)

    call_command("run_worker", "--once", "--batch-size", "5", verbosity=0)

    statuses = dict(OutboxMessage.objects.values_list("topic", "status"))
    assert statuses["core.noop"] == OutboxStatus.SUCCEEDED
    # An unknown topic is a deployment error, so it is parked immediately rather
    # than retried for hours.
    assert statuses["sales.not_implemented"] == OutboxStatus.DEAD


def test_the_noop_topic_is_registered_so_the_pipeline_can_be_proved_end_to_end():
    assert "core.noop" in registered_topics()
