"""Concurrency behaviour, exercised with real threads against real PostgreSQL.

These tests cannot be written against SQLite: they depend on ``SELECT ... FOR
UPDATE`` row locking and on ``SKIP LOCKED``, neither of which SQLite provides.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connections, transaction

from ztech_sales.core.exceptions import StaleObjectError
from ztech_sales.core.models import DocumentSequence, OutboxMessage, OutboxStatus, User
from ztech_sales.core.services.identity import update_user

pytestmark = pytest.mark.django_db(transaction=True)


def _in_thread(func):
    """Run ``func`` on a fresh database connection and always close it.

    A thread that leaves its connection open holds the test database open too,
    which makes the teardown hang rather than fail.
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        finally:
            connections.close_all()

    return wrapper


def test_two_simultaneous_edits_leave_exactly_one_winner(company, admin_user, rep_user):
    """The loser is told, rather than having their change silently discarded."""
    start = threading.Barrier(2)
    version = User.objects.get(pk=rep_user.pk).version
    results: list[str] = []

    @_in_thread
    def attempt(job_title: str) -> None:
        start.wait(timeout=10)
        try:
            update_user(
                company=company,
                user_id=rep_user.pk,
                data={"job_title": job_title, "version": version},
                actor=admin_user,
            )
        except StaleObjectError:
            results.append("stale")
        else:
            results.append("saved")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt, "Title A"), pool.submit(attempt, "Title B")]
        for future in futures:
            future.result(timeout=30)

    assert sorted(results) == ["saved", "stale"]

    rep_user.refresh_from_db()
    assert rep_user.job_title in {"Title A", "Title B"}
    assert rep_user.version == version + 1


def test_a_document_sequence_never_issues_the_same_number_twice(company):
    """Ten users saving at the same instant get ten distinct references."""
    workers = 10
    start = threading.Barrier(workers)
    references: list[str] = []
    lock = threading.Lock()

    @_in_thread
    def allocate() -> None:
        start.wait(timeout=10)
        with transaction.atomic():
            reference = DocumentSequence.allocate(company, "quotation")
        with lock:
            references.append(reference)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in [pool.submit(allocate) for _ in range(workers)]:
            future.result(timeout=30)

    assert len(references) == workers
    assert len(set(references)) == workers, f"duplicate reference issued: {references}"
    year = company.today().year
    assert all(reference.startswith(f"QT-{year}-") for reference in references)


def test_a_sequence_number_is_released_when_the_work_is_rolled_back(company):
    sequence = DocumentSequence.objects.get(company=company, key="sales_order")
    before = sequence.next_value

    class Rollback(Exception):
        pass

    with pytest.raises(Rollback), transaction.atomic():
        DocumentSequence.allocate(company, "sales_order")
        raise Rollback

    sequence.refresh_from_db()
    assert sequence.next_value == before


def test_allocation_outside_a_transaction_is_refused(company):
    # Allocating without a surrounding transaction would burn a number even if
    # the record it was for is never saved.
    with pytest.raises(RuntimeError, match="inside a transaction"):
        DocumentSequence.allocate(company, "quotation")


def test_two_workers_never_claim_the_same_outbox_message(company):
    for index in range(20):
        OutboxMessage.objects.enqueue(topic="core.noop", payload={"index": index}, company=company)

    start = threading.Barrier(2)
    claimed: list[list[str]] = []
    lock = threading.Lock()

    @_in_thread
    def claim(worker_id: str) -> None:
        start.wait(timeout=10)
        batch = OutboxMessage.objects.claim_batch(worker_id=worker_id, limit=10)
        with lock:
            claimed.append([str(message.id) for message in batch])

    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in [pool.submit(claim, "worker-a"), pool.submit(claim, "worker-b")]:
            future.result(timeout=30)

    first, second = claimed
    assert set(first).isdisjoint(second), "the same message was claimed twice"
    assert len(first) + len(second) == 20
    assert OutboxMessage.objects.filter(status=OutboxStatus.IN_PROGRESS).count() == 20
