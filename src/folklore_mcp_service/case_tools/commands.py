"""Three durable write commands over the existing Partner API (CR024)."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from uuid import UUID

from .common import API_PREFIX, CaseError
from .contracts import validate_input


def normalize_submit(arguments):
    """Mirror source defaults/serialization without inventing clinical facts."""
    body = deepcopy(arguments)
    body.pop("idempotency_key")
    body["context_binding_id"] = str(UUID(body["context_binding_id"]))
    body["max_cost_units"] = int(body["max_cost_units"])
    body.setdefault("external_reference", None)
    body["outputs"] = sorted(body.get("outputs", ["json"]))
    profile = body["profile"]
    source = body["input"]
    source["connection_id"] = str(UUID(source["connection_id"]))
    if profile == "singleton-germline-v1":
        clinical = body.setdefault("clinical", {})
        clinical["hpo_ids"] = sorted(set(clinical.get("hpo_ids", [])))
        clinical.setdefault("filtering_preset", "strict")
        clinical.setdefault("language", "en")
    else:
        clinical = body["clinical_profile"]
        demographics = clinical["demographics"]
        for field in ("age_years", "age_days", "age_group"):
            demographics.setdefault(field, None)
        modules = clinical.setdefault("modules", {})
        modules.setdefault("enable_screening", False)
        modules.setdefault("enable_literature", False)
        for field in (
            "ethnicity",
            "clinical_context",
            "reproductive",
            "sample_info",
            "consent",
            "panel_ids",
            "custom_genes",
        ):
            clinical.setdefault(field, None)
        phenotype = clinical.setdefault("phenotype", {})
        phenotype["hpo_ids"] = sorted(set(phenotype.get("hpo_ids", [])))
        phenotype.setdefault("clinical_notes", None)
        clinical.setdefault("language", "en")
        clinical.setdefault("filtering_preset", "strict")
        if clinical["ethnicity"] is not None:
            clinical["ethnicity"].setdefault("populations", None)
            clinical["ethnicity"].setdefault("note", None)
        context = clinical["clinical_context"]
        if context is not None:
            for field in ("indication", "indication_details", "family_history"):
                context.setdefault(field, None)
            if context["family_history"] is not None:
                history = context["family_history"]
                history.setdefault("has_affected_relatives", False)
                history.setdefault("consanguinity", False)
                history.setdefault("details", None)
        reproductive = clinical["reproductive"]
        if reproductive is not None:
            reproductive.setdefault("is_pregnant", False)
            reproductive.setdefault("gestational_age_weeks", None)
            reproductive.setdefault("family_planning", False)
        sample = clinical["sample_info"]
        if sample is not None:
            sample.setdefault("sample_type", None)
            sample.setdefault("has_parental_samples", False)
            sample.setdefault("has_affected_sibling", False)
        consent = clinical["consent"]
        if consent is not None:
            consent.setdefault("secondary_findings", None)
            consent.setdefault("carrier_results", None)
            consent.setdefault("pharmacogenomics", False)
        if clinical["panel_ids"] is not None:
            clinical["panel_ids"] = sorted(
                {str(UUID(value)) for value in clinical["panel_ids"]}
            )
        for gene in clinical["custom_genes"] or []:
            gene.setdefault("priority_score", 0.5)
            gene.setdefault("age_group_relevance", "all")
            gene.setdefault("disease_name", None)
            gene.setdefault("notes", None)
    if profile == "singleton-sequencing-v1":
        source["objects"].sort(key=lambda item: item["role"])
        settings = body["sequencing"]
        settings.setdefault("caller_selection", "default")
        settings["sample"].setdefault("expected_x_ploidy", None)
    return body


class Commands:
    def __init__(self, api, journal):
        self.api = api
        self.journal = journal
        self._lock = asyncio.Lock()

    async def call(self, tool, args):
        arguments = validate_input(tool, args)
        if tool == "submit_case_analysis":
            body = normalize_submit(arguments)
            key = arguments["idempotency_key"]
            path = API_PREFIX + "/analyses"
            kind = "submit"
            analysis_id = None
        elif tool == "acknowledge_sequencing_qc_review":
            analysis_id = str(UUID(arguments["analysis_id"]))
            body = {
                key: value for key, value in arguments.items() if key != "analysis_id"
            }
            body["job_id"] = str(UUID(body["job_id"]))
            body["attempt_id"] = str(UUID(body["attempt_id"]))
            path = API_PREFIX + "/analyses/" + analysis_id + "/review"
            key = ":".join(
                (
                    analysis_id,
                    body["job_id"],
                    body["attempt_id"],
                    body["manifest_sha256"],
                    "true",
                )
            )
            kind = "review"
        elif tool == "request_sequencing_analysis_cancellation":
            analysis_id = str(UUID(arguments["analysis_id"]))
            body = None
            path = API_PREFIX + "/analyses/" + analysis_id + "/cancel"
            key, kind = analysis_id, "cancel"
        else:
            raise CaseError("invalid_input")
        # Serialize write effects in this process. SQLite also prevents duplicate claims.
        async with self._lock:
            if kind == "submit":
                contexts = (await self.api.context())["contexts"]
                selected = next(
                    (
                        item
                        for item in contexts
                        if item["context_binding_id"] == body["context_binding_id"]
                        and item["actor_kind"] == "machine"
                    ),
                    None,
                )
                if selected is None or body["profile"] not in selected["profiles"]:
                    raise CaseError("authorization_failed")
            record = self.journal.prepare(
                kind, key, path, body, analysis_id=analysis_id
            )
            if record["state"] == "definitive_failure":
                error = record["error"]
                raise CaseError(
                    error["code"],
                    retryable=error.get("retryable", False),
                    request_id=error.get("request_id"),
                )
            self.journal.sending(record["id"])
            transmitted = False
            identity_conflict = False
            try:
                transmitted = True
                response = await self.api.request(
                    "POST",
                    record["path"],
                    body=record["body"],
                    idempotency_key=record["key"] if kind == "submit" else None,
                    expected_status=202,
                )
                if (
                    analysis_id is not None
                    and response.get("analysis_id") != analysis_id
                ):
                    raise CaseError("source_contract_mismatch")
                previous = record.get("response")
                if previous is not None and any(
                    response.get(field) != previous.get(field)
                    for field in ("analysis_id", "case_id")
                ):
                    self.journal.accepted(record["id"], previous)
                    identity_conflict = True
                    raise CaseError("operation_conflict")
                self.journal.accepted(record["id"], response)
                return response
            except CaseError as error:
                if identity_conflict:
                    raise
                definitive = (
                    error.details.get("definitive_response") is True
                    and 400 <= error.details.get("http_status", 0) < 500
                    and error.details.get("http_status") not in {408, 429}
                )
                if definitive:
                    self.journal.definitive_failure(record["id"], error.as_dict())
                    raise
                self.journal.uncertain(record["id"])
                raise CaseError(
                    "command_uncertain",
                    retryable=True,
                    request_id=error.request_id,
                    details={"operation_id": record["id"], "upstream_code": error.code},
                ) from None
            except BaseException:
                if transmitted:
                    self.journal.uncertain(record["id"])
                raise
