"""Durable encrypted command replay acceptance for CR024."""

import pytest

from folklore_mcp_service.case_tools.common import CaseError
from folklore_mcp_service.case_tools.journal import Journal

KEY = "flk_" + "a" * 32 + "." + "b" * 43
OTHER_KEY = "flk_" + "c" * 32 + "." + "d" * 43


def test_prepare_encrypted_exact_replay_and_changed_body_conflict(tmp_path):
    directory = tmp_path / "state"
    journal = Journal(directory, KEY)
    record = journal.prepare(
        "submit",
        "original-key",
        "/folklore/v1/analyses",
        {"clinical": {"note": "SENSITIVE_FIXTURE"}},
    )
    assert record["state"] == "prepared"
    assert (
        journal.prepare(
            "submit",
            "original-key",
            "/folklore/v1/analyses",
            {"clinical": {"note": "SENSITIVE_FIXTURE"}},
        )["id"]
        == record["id"]
    )
    with pytest.raises(CaseError) as caught:
        journal.prepare(
            "submit", "original-key", "/folklore/v1/analyses", {"different": True}
        )
    assert caught.value.code == "operation_conflict"
    journal.close()
    assert all(
        b"SENSITIVE_FIXTURE" not in p.read_bytes()
        for p in directory.iterdir()
        if p.is_file()
    )


def test_sending_restarts_as_uncertain_and_acceptance_persists(tmp_path):
    directory = tmp_path / "state"
    journal = Journal(directory, KEY)
    record = journal.prepare("cancel", "cancel:A", "/folklore/v1/analyses/A/cancel", {})
    journal.sending(record["id"])
    journal.close()
    reopened = Journal(directory, KEY)
    assert reopened.get(record["id"])["state"] == "uncertain"
    reopened.accepted(record["id"], {"analysis_id": "A", "status": "running"})
    reopened.close()
    again = Journal(directory, KEY)
    assert again.get(record["id"])["response"]["status"] == "running"
    assert again.get(record["id"])["state"] == "accepted"
    again.close()


def test_rotation_preserves_pending_but_denies_recovery_with_new_credential(tmp_path):
    directory = tmp_path / "state"
    journal = Journal(directory, KEY)
    record = journal.prepare("submit", "same", "/folklore/v1/analyses", {})
    journal.sending(record["id"])
    journal.close()
    rotated = Journal(directory, OTHER_KEY)
    with pytest.raises(CaseError) as caught:
        rotated.get(record["id"])
    assert caught.value.code == "recovery_credential_required"
    rotated.close()


def test_missing_key_with_existing_journal_fails_closed(tmp_path):
    directory = tmp_path / "state"
    journal = Journal(directory, KEY)
    journal.prepare("submit", "same", "/folklore/v1/analyses", {})
    journal.close()
    (directory / "state.key").unlink()
    with pytest.raises(CaseError):
        Journal(directory, KEY)


def test_command_payload_cap_and_private_permissions(tmp_path):
    directory = tmp_path / "state"
    journal = Journal(directory, KEY)
    with pytest.raises(CaseError) as caught:
        journal.prepare(
            "submit", "large", "/folklore/v1/analyses", {"x": "x" * (1024 * 1024)}
        )
    assert caught.value.code == "journal_full"
    assert directory.stat().st_mode & 0o777 == 0o700
    assert (directory / "state.key").stat().st_mode & 0o777 == 0o600
    journal.close()


def test_second_writer_rejected_without_resetting_active_send(tmp_path):
    directory = tmp_path / "state"
    journal = Journal(directory, KEY)
    record = journal.prepare("submit", "one", "/folklore/v1/analyses", {})
    journal.sending(record["id"])
    with pytest.raises(CaseError) as caught:
        Journal(directory, KEY)
    assert caught.value.code == "journal_in_use"
    assert journal.get(record["id"])["state"] == "sending"
    journal.close()


def test_wrong_encryption_key_and_ciphertext_tampering_fail_closed(tmp_path):
    directory = tmp_path / "state"
    journal = Journal(directory, KEY)
    record = journal.prepare("submit", "one", "/folklore/v1/analyses", {})
    journal._connection.execute(
        "UPDATE commands SET payload=? WHERE id=?", (b"damaged", record["id"])
    )
    journal._connection.commit()
    with pytest.raises(CaseError) as caught:
        journal.get(record["id"])
    assert caught.value.code == "journal_unreadable"
    journal.close()
    key_path = directory / "state.key"
    original = key_path.read_bytes()
    key_path.write_bytes(b"x" * 32)
    with pytest.raises(CaseError):
        Journal(directory, KEY)
    key_path.write_bytes(original)
    # A failed constructor releases the lock so a corrected recovery can reopen.
    recovered = Journal(directory, KEY)
    recovered.close()


def test_replay_body_preserves_exact_decimal_values(tmp_path):
    from decimal import Decimal

    directory = tmp_path / "state"
    journal = Journal(directory, KEY)
    body = {"score": Decimal("0.5"), "max_cost_units": 9223372036854775807}
    first = journal.prepare("submit", "one", "/folklore/v1/analyses", body)
    second = journal.prepare("submit", "one", "/folklore/v1/analyses", body)
    assert first["id"] == second["id"]
    assert second["body"] == body
    journal.close()


def test_full_journal_denies_new_commands_but_keeps_recovery_reservation(
    tmp_path, monkeypatch
):
    from folklore_mcp_service.case_tools import journal as module

    journal = Journal(tmp_path / "state", KEY)
    first = journal.prepare("submit", "one", "/folklore/v1/analyses", {})
    monkeypatch.setattr(
        journal,
        "_size",
        lambda: module.DISK_CAP - module.RECOVERY_RESERVE - module.COMMAND_RESERVE,
    )
    with pytest.raises(CaseError) as caught:
        journal.prepare("submit", "two", "/folklore/v1/analyses", {})
    assert caught.value.code == "journal_full"
    journal.sending(first["id"])
    journal.uncertain(first["id"])
    assert journal.get(first["id"])["state"] == "uncertain"
    journal.close()


def test_terminal_gc_preserves_uncertain_entries(tmp_path):
    import time

    journal = Journal(tmp_path / "state", KEY)
    pending = journal.prepare("submit", "pending", "/folklore/v1/analyses", {})
    terminal = journal.prepare("submit", "done", "/folklore/v1/analyses", {})
    journal.accepted(terminal["id"], {"analysis_id": "fixture"})
    journal._connection.execute(
        "UPDATE commands SET updated=?", (time.time() - 31 * 86400,)
    )
    journal._connection.commit()
    journal.prepare("submit", "new", "/folklore/v1/analyses", {})
    assert journal.get(pending["id"])["state"] == "prepared"
    with pytest.raises(CaseError):
        journal.get(terminal["id"])
    journal.close()
