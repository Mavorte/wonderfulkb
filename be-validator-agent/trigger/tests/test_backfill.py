import pytest

import backfill
from trigger import common

from .conftest import add_document, bodies, drain


def run(ctx, *argv):
    """backfill.main against the moto account; `Context()` is the one the script builds from the environment."""
    return backfill.main(["--queue-url", ctx.queue_url, "--rate", "6000", *argv])


@pytest.fixture
def account(ctx):
    for case_id, document_id in (("A", "a1"), ("A", "a2"), ("B", "b1"), ("B", "b2"), ("C", "c1"), ("C", "c2")):
        add_document(ctx, document_id, case_id)
    ctx.analysis.put_item(Item={"case_id": "A", "document_id": "a1", "processing_status": "completed", "title": "x",
                                "label": "smlouva", "updated_at": "2026-10-19T10:00:00Z"})
    ctx.analysis.put_item(Item={"case_id": "B", "document_id": "b1", "processing_status": "failed", "title": "x",
                                "updated_at": "2026-10-19T10:00:00Z"})
    ctx.analysis.put_item(Item={"case_id": "B", "document_id": "b2", "processing_status": "processing", "title": "x",
                                "updated_at": common.iso(common.now_dt())})
    ctx.analysis.put_item(Item={"case_id": "C", "document_id": "c1", "processing_status": "partial", "title": "x",
                                "updated_at": "2026-10-19T10:00:00Z"})
    return ctx


def queued(ctx):
    return sorted((b["case_id"], b["document_id"]) for b in bodies(drain(ctx)))


def test_dry_run_writes_and_sends_nothing(account, capsys):
    assert run(account) == 0
    out = capsys.readouterr().out
    assert "dry run" in out and "a2" in out and "a1" not in out
    assert drain(account) == [] and account.get_row("A", "a2") is None


def test_apply_queues_everything_that_is_not_completed(account):
    assert run(account, "--apply") == 0
    # a1 completed: untouched; b2 is held by a live worker: skipped
    assert queued(account) == [("A", "a2"), ("B", "b1"), ("C", "c1"), ("C", "c2")]
    row = account.get_row("A", "a1")
    assert row["processing_status"] == "completed" and row["label"] == "smlouva"
    assert account.get_row("B", "b2")["processing_status"] == "processing"
    assert account.get_row("A", "a2")["processing_status"] == "queued"


def test_running_it_twice_is_safe(account):
    run(account, "--apply")
    first = queued(account)
    run(account, "--apply")
    assert queued(account) == first  # queued rows are queued again (a lost message is replaced); completed stays out
    assert account.get_row("A", "a1")["processing_status"] == "completed"


def test_statuses_and_case_filters(account):
    run(account, "--apply", "--statuses", "failed")
    assert queued(account) == [("B", "b1")]
    run(account, "--apply", "--case", "C", "--statuses", "missing")
    assert queued(account) == [("C", "c2")]


def test_max_limits_the_count(account):
    run(account, "--apply", "--max", "2")
    assert len(queued(account)) == 2


def test_force_needs_a_case_and_reruns_completed(account):
    with pytest.raises(SystemExit):
        run(account, "--apply", "--force")
    run(account, "--apply", "--force", "--case", "A", "--statuses", "missing")
    assert queued(account) == [("A", "a1"), ("A", "a2")]


def test_a_row_that_completes_during_the_run_is_not_touched(account, monkeypatch):
    original = backfill.candidates

    def racing(*args, **kwargs):
        found = original(*args, **kwargs)  # a2 looked missing ...
        account.analysis.put_item(Item={"case_id": "A", "document_id": "a2", "processing_status": "completed",
                                        "title": "x", "updated_at": "2026-10-19T10:00:00Z"})  # ... and then completed
        return found

    monkeypatch.setattr(backfill, "candidates", racing)
    run(account, "--apply", "--case", "A")
    assert queued(account) == [] and account.get_row("A", "a2")["processing_status"] == "completed"


def test_unknown_status_is_rejected(account):
    with pytest.raises(SystemExit):
        run(account, "--statuses", "done")
