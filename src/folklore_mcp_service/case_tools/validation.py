"""Local cross-field admission rules from the Partner Analysis DTOs (CR024)."""

from __future__ import annotations

from uuid import UUID

from .common import CaseError


def _reject(field):
    raise CaseError("invalid_input", details={"field": field})


def validate_submit(args: dict) -> None:
    """Validate source semantic rules without changing the caller's command."""
    profile = args["profile"]
    if profile not in {
        "singleton-germline-v1",
        "singleton-germline-v2",
        "singleton-sequencing-v1",
    }:
        _reject("profile")
    source = args["input"]
    sequencing = profile == "singleton-sequencing-v1"
    if sequencing:
        if source["kind"] != "s3_sequencing" or not isinstance(
            args.get("sequencing"), dict
        ):
            _reject("sequencing")
        objects = source["objects"]
    else:
        if source["kind"] != "s3_object" or "sequencing" in args:
            _reject("input.kind")
        objects = [source]
    for selected in objects:
        key, version = selected["key"], selected["version_id"]
        if any(ord(char) < 32 for char in key):
            _reject("input.key")
        if any(ord(char) < 32 for char in version) or version.lower() in {
            "null",
            "latest",
        }:
            _reject("input.version_id")
        # These visible path rules mirror the current UMS S3 authority boundary.
        if (
            key.startswith("/")
            or "\\" in key
            or any(part in {".", ".."} for part in key.split("/"))
        ):
            _reject("input.key")
    if sequencing:
        kind = source["input_type"]
        expected_roles = ["R1", "R2"] if kind == "FASTQ" else ["ALIGNMENT"]
        if sorted(item["role"] for item in objects) != expected_roles:
            _reject("input.objects")
        if len({(item["bucket"], item["key"]) for item in objects}) != len(objects):
            _reject("input.objects")
        suffixes = (".fastq.gz", ".fq.gz") if kind == "FASTQ" else ("." + kind.lower(),)
        if any(not item["key"].lower().endswith(suffixes) for item in objects):
            _reject("input.objects")
    elif not source["key"].lower().endswith((".vcf", ".vcf.gz")):
        _reject("input.key")
    if profile == "singleton-germline-v1":
        if "clinical_profile" in args or "json" not in args.get("outputs", ["json"]):
            _reject("clinical_profile")
        return
    if "clinical" in args or args.get("clinical_profile") is None:
        _reject("clinical_profile")
    clinical = args["clinical_profile"]
    demographics = clinical["demographics"]
    if (
        demographics.get("age_years") is not None
        and demographics.get("age_days") is not None
    ):
        _reject("clinical_profile.demographics")
    screening = clinical.get("modules", {}).get("enable_screening", False)
    if screening:
        consent = clinical.get("consent")
        if (
            consent is None
            or consent.get("secondary_findings") is None
            or consent.get("carrier_results") is None
        ):
            _reject("clinical_profile.consent")
    elif clinical.get("panel_ids") or clinical.get("custom_genes"):
        _reject("clinical_profile.panel_ids")
    for panel_id in clinical.get("panel_ids") or []:
        try:
            UUID(panel_id)
        except (TypeError, ValueError, AttributeError):
            _reject("clinical_profile.panel_ids")
