"""Closed public reference response contract, version 1.0."""

import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def _public_clingen_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname
        not in {
            "clinicalgenome.org",
            "www.clinicalgenome.org",
            "search.clinicalgenome.org",
        }
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 80, 443}
        or any(ord(char) < 33 for char in value)
    ):
        raise ValueError("Expected a public ClinGen source URL")
    return value


class Association(Closed):
    geneSymbol: str
    hgncId: str | None
    diseaseName: str
    diseaseId: str
    modeOfInheritance: str
    modeOfInheritanceId: str | None
    classification: str
    expertPanel: str | None
    reportUrl: str | None
    classificationDate: str | None
    sopVersion: str | None

    @field_validator("reportUrl")
    @classmethod
    def validate_report_url(cls, value):
        return _public_clingen_url(value) if value is not None else None


class Source(Closed):
    name: Literal["ClinGen Gene-Disease Validity"]
    version: str
    snapshotSha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    downloadUrl: str
    license: Literal["CC0-1.0"]
    attribution: str

    @field_validator("downloadUrl")
    @classmethod
    def validate_download_url(cls, value):
        return _public_clingen_url(value)


class Query(Closed):
    kind: Literal["gene", "disease"]
    value: str
    match: Literal["exact", "name_contains"]


class Pagination(Closed):
    limit: int = Field(ge=1, le=50)
    offset: int = Field(ge=0, le=1000)
    total: int = Field(ge=0)
    nextOffset: int | None = Field(ge=0, le=1000)


class UsageBoundary(Closed):
    intended_use: Literal["professional_gene_disease_review"]
    patient_context_evaluated: Literal[False]
    review_required: Literal[True]
    not_for: list[
        Literal[
            "patient_diagnosis",
            "treatment_decision",
            "variant_pathogenicity_classification",
        ]
    ]

    @field_validator("not_for")
    @classmethod
    def validate_prohibitions(cls, value):
        if value != [
            "patient_diagnosis",
            "treatment_decision",
            "variant_pathogenicity_classification",
        ]:
            raise ValueError("The complete professional-review boundary is required")
        return value


class GeneDiseaseResponse(Closed):
    contractVersion: Literal["1.0"]
    status: Literal["ok", "not_found"]
    query: Query
    associations: list[Association] = Field(max_length=50)
    pagination: Pagination
    source: Source
    warnings: list[str]
    usage_boundary: UsageBoundary

    @model_validator(mode="after")
    def validate_page(self):
        page = self.pagination
        expected_rows = min(page.limit, max(0, page.total - page.offset))
        if len(self.associations) != expected_rows:
            raise ValueError("Assertion count disagrees with pagination")
        if (self.status == "not_found") != (page.total == 0):
            raise ValueError("Status disagrees with total assertion count")
        next_offset = page.offset + len(self.associations)
        more = next_offset < page.total
        expected_next = next_offset if more and next_offset <= 1000 else None
        if page.nextOffset != expected_next:
            raise ValueError("Continuation offset disagrees with page contents")
        if (
            more
            and next_offset > 1000
            and not any("pagination ceiling" in warning for warning in self.warnings)
        ):
            raise ValueError("A truncated page requires the pagination ceiling warning")
        if self.query.kind == "gene" and self.query.match != "exact":
            raise ValueError("Gene queries require exact identity matching")
        return self


class ReadyResponse(Closed):
    status: Literal["ready"]
    source: Source


class ReferenceBounds(Closed):
    limit: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Maximum number of source assertions per page, from 1 to 50.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        le=1000,
        description="Zero-based assertion offset; use the returned nextOffset when present.",
    )


class GetGeneDiseaseArguments(ReferenceBounds):
    gene: str = Field(
        min_length=1,
        max_length=64,
        description="One public human gene symbol or HGNC identifier, for example BRCA1 or HGNC:1100. No patient data.",
    )

    @field_validator("gene")
    @classmethod
    def validate_gene(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"(?:HGNC:[0-9]+|[A-Z0-9][A-Z0-9.-]{0,63})", value):
            raise ValueError("Use one HGNC gene symbol or HGNC identifier")
        return value


class SearchDiseaseGenesArguments(ReferenceBounds):
    disease: str = Field(
        min_length=3,
        max_length=160,
        description="One public disease name or exact MONDO identifier (MONDO: followed by seven digits). A name search may match multiple distinct diseases. No symptoms or patient narrative.",
    )

    @field_validator("disease")
    @classmethod
    def validate_disease(cls, value: str) -> str:
        value = value.strip()
        if (
            len(value) < 3
            or any(ord(c) < 32 for c in value)
            or not any(c.isalpha() for c in value)
        ):
            raise ValueError("Use one disease name or MONDO identifier")
        if ":" in value and not re.fullmatch(r"MONDO:[0-9]{7}", value.upper()):
            raise ValueError(
                "Supported disease identifiers use MONDO followed by seven digits"
            )
        return value


def gene_disease_boundary() -> dict:
    return {
        "intended_use": "professional_gene_disease_review",
        "patient_context_evaluated": False,
        "review_required": True,
        "not_for": [
            "patient_diagnosis",
            "treatment_decision",
            "variant_pathogenicity_classification",
        ],
    }
