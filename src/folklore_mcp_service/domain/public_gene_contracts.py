"""Public gene reference contract. No patient inputs or clinical inference."""

from __future__ import annotations

import ipaddress
import socket
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

GeneId = Annotated[str, StringConstraints(pattern=r"^HGNC:[1-9][0-9]*$")]
Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
RequestId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
Text = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
ShortText = Annotated[str, StringConstraints(min_length=1, max_length=200)]
SectionName = Literal[
    "overview",
    "disease_validity",
    "structure",
    "constraint",
    "dosage",
    "mechanisms",
    "clinical_variants",
    "clinical_variant_consequences",
    "expression",
    "gwas",
    "phenotypes",
    "protein_pathways",
    "literature",
]
SECTION_NAMES = frozenset(SectionName.__args__)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


def public_url(value: str) -> str:
    """Data links only; never fetch these URLs from request handlers."""
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or any(ord(c) < 33 for c in value)
        or "%" in host
        or "\\" in host
        or host.endswith(
            (
                ".local",
                ".internal",
                ".localhost",
                ".test",
                ".invalid",
                ".example",
                ".home.arpa",
            )
        )
        or "." not in host
    ):
        raise ValueError("public HTTPS URL required")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP-literal source links are not supported")
    try:
        socket.inet_aton(host)  # Parse only; catches browser-compatible 127.1/hex IPv4.
    except OSError:
        pass
    else:
        raise ValueError("IP-literal source links are not supported")
    return value


class Source(StrictModel):
    source_id: ShortText
    provider: ShortText
    dataset: ShortText
    release: ShortText
    raw_sha256: Digest
    projection_sha256: Digest
    source_url: Annotated[str, Field(max_length=2000)]
    retrieved_at: ShortText
    provider_updated_at: ShortText | None
    accepted_at: ShortText | None
    transform_version: ShortText
    rights_receipt_sha256: Digest
    public_display: Literal[True]
    attribution: Text
    license_url: Annotated[str, Field(max_length=2000)] | None = None
    transformation_notice: Text | None = None
    normalized_at: ShortText | None = None
    source_metadata_sha256: Digest | None = None

    _license_url = field_validator("license_url")(
        lambda value: public_url(value) if value is not None else None
    )
    _url = field_validator("source_url")(public_url)


class GeneIdentity(StrictModel):
    gene_id: GeneId
    symbol: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    name: Text
    locus_type: ShortText
    status: Literal["Approved", "Entry Withdrawn", "Merged/Split"]
    aliases: list[ShortText] = Field(default_factory=list, max_length=500)
    previous_symbols: list[ShortText] = Field(default_factory=list, max_length=500)
    ensembl_ids: list[Annotated[str, StringConstraints(pattern=r"^ENSG[0-9]+$")]] = (
        Field(default_factory=list, max_length=20)
    )
    ncbi_gene_ids: list[Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")]] = (
        Field(default_factory=list, max_length=20)
    )
    source_id: ShortText
    replacement_gene_ids: list[GeneId] = Field(default_factory=list, max_length=50)


class ResolveRequest(StrictModel):
    query: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    request_id: RequestId

    @field_validator("query")
    @classmethod
    def query_text(cls, value: str) -> str:
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("control characters are not supported")
        value = value.strip()
        if not value:
            raise ValueError("empty query")
        return value


class ProfileRequest(StrictModel):
    gene_id: GeneId
    request_id: RequestId
    snapshot_id: Digest | None = None


class SectionRequest(ProfileRequest):
    section: SectionName
    limit: int = Field(default=20, ge=1, le=50)
    cursor: Annotated[str, Field(max_length=512)] | None = None


class CatalogRequest(StrictModel):
    request_id: RequestId
    snapshot_id: Digest | None = None
    limit: int = Field(default=500, ge=1, le=1000)
    cursor: Annotated[str, Field(max_length=512)] | None = None


class CatalogEntry(StrictModel):
    gene_id: GeneId
    canonical_symbol: ShortText


class CatalogResponse(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    request_id: RequestId
    snapshot_id: Digest
    count_unit: Literal["approved_human_hgnc_gene"] = "approved_human_hgnc_gene"
    total: int = Field(ge=0)
    entries: list[CatalogEntry] = Field(max_length=1000)
    returned: int = Field(ge=0, le=1000)
    next_cursor: str | None

    @model_validator(mode="after")
    def counts(self):
        if (
            self.returned != len(self.entries)
            or self.returned > self.total
            or len({e.gene_id for e in self.entries}) != self.returned
        ):
            raise ValueError("catalog page mismatch")
        return self


class Candidate(StrictModel):
    identity: GeneIdentity
    match_types: list[
        Literal[
            "approved_symbol",
            "previous_symbol",
            "alias",
            "stable_id",
            "withdrawn_symbol",
        ]
    ]
    matched_terms: list[ShortText]


class ResolveResponse(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    request_id: RequestId
    identity_snapshot_id: Digest
    status: Literal["exact", "alias", "ambiguous", "not_found", "withdrawn"]
    normalized_query: ShortText
    candidates: list[Candidate] = Field(max_length=50)
    candidate_total: int = Field(ge=0)
    complete: Literal[True] = True

    @model_validator(mode="after")
    def count_scope(self):
        count = len(self.candidates)
        if count != self.candidate_total or (self.status == "not_found") != (
            count == 0
        ):
            raise ValueError("resolution count mismatch")
        if (self.status == "ambiguous") != (count > 1):
            raise ValueError("ambiguity mismatch")
        return self


class OverviewData(StrictModel):
    kind: Literal["overview"]
    summary: Annotated[str, StringConstraints(min_length=1, max_length=40000)] | None
    summary_source_id: ShortText | None

    @model_validator(mode="after")
    def attribution(self):
        if (self.summary is None) != (self.summary_source_id is None):
            raise ValueError("summary attribution required")
        return self


class DiseaseAssertion(StrictModel):
    assertion_id: ShortText
    source_id: ShortText
    disease_id: ShortText
    disease_name: Text
    inheritance: ShortText | None
    classification: ShortText
    curation_date: ShortText | None
    panel: Text | None
    criteria_version: ShortText | None
    report_url: Annotated[str, Field(max_length=2000)]
    mechanism: Text | None = None
    allelic_requirement: Text | None = None
    mirrored_assertion_id: ShortText | None = None
    original_disease_id: ShortText | None = None
    submitter: Text | None = None
    mechanism_support: Text | None = None
    variant_consequence: Text | None = None
    pmids: list[Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")]] = Field(
        default_factory=list, max_length=500
    )

    _url = field_validator("report_url")(public_url)


class DiseaseData(StrictModel):
    kind: Literal["disease_validity"]
    count_unit: Literal["source_assertion"] = "source_assertion"
    records: list[DiseaseAssertion] = Field(max_length=5000)

    @model_validator(mode="after")
    def unique_assertions(self):
        keys = [(row.source_id, row.assertion_id) for row in self.records]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate source assertion")
        return self


class Exon(StrictModel):
    rank: int = Field(ge=1)
    start: int = Field(ge=1)
    end: int = Field(ge=1)

    @model_validator(mode="after")
    def interval(self):
        if self.end < self.start:
            raise ValueError("reversed interval")
        return self


class CodingSegment(Exon):
    phase: Literal[0, 1, 2]


class Transcript(StrictModel):
    transcript_id: ShortText
    source_id: ShortText
    assembly: Literal["GRCh37", "GRCh38"]
    assembly_accession: ShortText | None
    annotation_release: ShortText
    coordinate_system: Literal["1-based-closed"]
    contig: ShortText
    strand: Literal["+", "-"]
    start: int = Field(ge=1)
    end: int = Field(ge=1)
    mane_status: Literal["Select", "Plus Clinical"] | None
    refseq_transcript: ShortText | None
    refseq_protein: ShortText | None = None
    protein_id: ShortText | None
    protein_length: int | None = Field(default=None, ge=1)
    exons: list[Exon] = Field(min_length=1, max_length=1000)
    coding_segments: list[CodingSegment] = Field(default_factory=list, max_length=1000)
    stop_codon_segments: list[Exon] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def structure(self):
        if self.end < self.start or [e.rank for e in self.exons] != list(
            range(1, len(self.exons) + 1)
        ):
            raise ValueError("invalid transcript/exon order")
        if any(e.start < self.start or e.end > self.end for e in self.exons):
            raise ValueError("exon outside transcript")
        starts = [e.start for e in self.exons]
        if starts != sorted(starts, reverse=self.strand == "-"):
            raise ValueError("exon ranks must follow transcription direction")
        genomic = sorted(self.exons, key=lambda e: e.start)
        if any(a.end >= b.start for a, b in zip(genomic, genomic[1:], strict=False)):
            raise ValueError("overlapping exons")
        for label, parts in (
            ("coding", self.coding_segments),
            ("stop codon", self.stop_codon_segments),
        ):
            if [e.rank for e in parts] != list(range(1, len(parts) + 1)):
                raise ValueError(f"invalid {label} segment order")
            if [e.start for e in parts] != sorted(
                [e.start for e in parts], reverse=self.strand == "-"
            ):
                raise ValueError(
                    f"{label} segments must follow transcription direction"
                )
            if any(
                not any(
                    exon.start <= part.start <= part.end <= exon.end
                    for exon in self.exons
                )
                for part in parts
            ):
                raise ValueError(f"{label} segment outside exons")
            genomic_parts = sorted(parts, key=lambda e: e.start)
            if any(
                a.end >= b.start
                for a, b in zip(genomic_parts, genomic_parts[1:], strict=False)
            ):
                raise ValueError(f"overlapping {label} segments")
        return self


class StructureData(StrictModel):
    kind: Literal["structure"]
    count_unit: Literal["source_transcript_model"] = "source_transcript_model"
    transcript_scope: Literal["MANE", "provider_catalog", "multi_source_native"]
    distinct_transcript_total: int | None = Field(default=None, ge=0)
    records: list[Transcript] = Field(max_length=5000)

    @model_validator(mode="after")
    def unique_transcripts(self):
        keys = [
            (row.source_id, row.assembly, row.transcript_id) for row in self.records
        ]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate source transcript")
        if (
            self.distinct_transcript_total is not None
            and self.distinct_transcript_total
            < len({(r.assembly, r.transcript_id) for r in self.records})
        ):
            raise ValueError("distinct transcript total below represented models")
        return self


class ConstraintMetric(StrictModel):
    source_gene_id: ShortText | None = None
    source_gene_namespace: Literal["ncbi_gene", "ensembl_gene"] | None = None
    source_canonical: bool | None = None
    source_mane_select: bool | None = None
    source_id: ShortText
    gene_id: GeneId
    transcript_id: ShortText | None
    selection_rule: Text
    pli: float | None = Field(ge=0, le=1)
    oe_lof: float | None = Field(ge=0)
    oe_lof_lower: float | None = Field(ge=0)
    oe_lof_upper: float | None = Field(ge=0)
    observed_lof: int | None = Field(ge=0)
    oe_missense: float | None = Field(default=None, ge=0)
    oe_missense_lower: float | None = Field(default=None, ge=0)
    oe_missense_upper: float | None = Field(default=None, ge=0)
    observed_missense: int | None = Field(default=None, ge=0)
    expected_lof: float | None = Field(ge=0)
    missense_z: float | None
    quality_flags: list[ShortText]
    expected_synonymous: float | None = Field(default=None, ge=0)
    expected_missense: float | None = Field(default=None, ge=0)
    display_status: Literal["available", "caution", "unreliable"] = "available"
    gene_flags: list[ShortText] = Field(default_factory=list, max_length=100)
    constraint_flags: list[ShortText] = Field(default_factory=list, max_length=100)
    reported_metrics: dict[
        Literal[
            "pli",
            "oe_lof",
            "oe_lof_lower",
            "oe_lof_upper",
            "missense_z",
            "oe_missense",
            "oe_missense_lower",
            "oe_missense_upper",
        ],
        float | None,
    ] = Field(default_factory=dict)

    @model_validator(mode="after")
    def confidence_bounds(self):
        if (
            self.oe_lof_lower is not None
            and self.oe_lof_upper is not None
            and self.oe_lof_lower > self.oe_lof_upper
        ):
            raise ValueError("reversed provided confidence bounds")
        if (
            self.oe_missense_lower is not None
            and self.oe_missense_upper is not None
            and self.oe_missense_lower > self.oe_missense_upper
        ):
            raise ValueError("reversed provided missense confidence bounds")
        for prefix in ("oe_lof", "oe_missense"):
            lower, upper = (
                self.reported_metrics.get(prefix + "_lower"),
                self.reported_metrics.get(prefix + "_upper"),
            )
            if lower is not None and upper is not None and lower > upper:
                raise ValueError("reversed reported confidence bounds")
        if self.display_status == "unreliable" and any(
            v is not None
            for v in (
                self.pli,
                self.oe_lof,
                self.oe_lof_lower,
                self.oe_lof_upper,
                self.missense_z,
                self.oe_missense,
                self.oe_missense_lower,
                self.oe_missense_upper,
            )
        ):
            raise ValueError("unreliable calibration must suppress displayed metrics")
        return self


class ConstraintData(StrictModel):
    kind: Literal["constraint"]
    count_unit: Literal["source_metric_record"] = "source_metric_record"
    records: list[ConstraintMetric] = Field(max_length=5000)


class DosageAssertion(StrictModel):
    source_id: ShortText
    assertion_id: ShortText
    axis: Literal["haploinsufficiency", "triplosensitivity"]
    score: Literal["0", "1", "2", "3", "30", "40", "Not yet evaluated", "-1"]
    description: Text | None
    disease_id: ShortText | None
    evaluated_at: ShortText | None
    pmids: list[Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")]] = Field(
        max_length=100
    )
    report_url: Annotated[str, Field(max_length=2000)]
    _url = field_validator("report_url")(public_url)


class DosageData(StrictModel):
    kind: Literal["dosage"]
    count_unit: Literal["source_dosage_assertion"] = "source_dosage_assertion"
    records: list[DosageAssertion] = Field(max_length=5000)

    @model_validator(mode="after")
    def unique_assertions(self):
        keys = [(r.source_id, r.assertion_id, r.axis) for r in self.records]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate dosage assertion")
        return self


class MechanismAssertion(StrictModel):
    source_id: ShortText
    assertion_id: ShortText
    disease_id: ShortText
    disease_name: Text
    mechanism: Text
    support: Text | None
    allelic_requirement: Text | None
    variant_consequence: Text | None
    classification: ShortText
    report_url: Annotated[str, Field(max_length=2000)]
    _url = field_validator("report_url")(public_url)


class MechanismsData(StrictModel):
    kind: Literal["mechanisms"]
    count_unit: Literal["source_relation"] = "source_relation"
    records: list[MechanismAssertion] = Field(max_length=5000)

    @model_validator(mode="after")
    def unique_assertions(self):
        keys = [(r.source_id, r.assertion_id) for r in self.records]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate mechanism assertion")
        return self


class DistributionBin(StrictModel):
    label: Text
    count: int = Field(ge=0)


class ClinicalAxis(StrictModel):
    axis: Literal["germline", "somatic_clinical_impact", "oncogenicity"]
    represented_variations: int = Field(ge=0)
    classification_counts: list[DistributionBin] = Field(max_length=1000)
    review_status_counts: list[DistributionBin] = Field(max_length=1000)

    @model_validator(mode="after")
    def conserved(self):
        for bins in (self.classification_counts, self.review_status_counts):
            if (
                len({b.label for b in bins}) != len(bins)
                or sum(b.count for b in bins) != self.represented_variations
            ):
                raise ValueError("classification-axis count mismatch")
        return self


class ResolverAllele(StrictModel):
    assembly: Literal["GRCh38"]
    chromosome: ShortText
    position: int = Field(ge=1)
    reference: Annotated[str, StringConstraints(pattern=r"^[ACGT]+$", max_length=100)]
    alternate: Annotated[str, StringConstraints(pattern=r"^[ACGT]+$", max_length=100)]


class ClinicalVariantExample(StrictModel):
    source_id: ShortText
    variation_id: Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")]
    name: Text
    variant_type: ShortText
    germline: Text | None
    germline_review_status: Text | None
    somatic_clinical_impact: Text | None
    somatic_review_status: Text | None
    oncogenicity: Text | None
    oncogenicity_review_status: Text | None
    source_url: Annotated[str, Field(max_length=2000)]
    resolver_allele: ResolverAllele | None
    resolver_status: Literal[
        "supported_exact_allele_requires_resolution",
        "unsupported_or_no_unique_grch38_allele",
    ]
    _url = field_validator("source_url")(public_url)

    @model_validator(mode="after")
    def handoff(self):
        if (self.resolver_allele is not None) != (
            self.resolver_status == "supported_exact_allele_requires_resolution"
        ):
            raise ValueError("variant handoff mismatch")
        return self


class ClinicalVariantsData(StrictModel):
    kind: Literal["clinical_variants"]
    count_unit: Literal["selected_variant_example"] = "selected_variant_example"
    source_id: ShortText
    unique_variation_total: int = Field(ge=0)
    membership_rule: Literal["explicit_hgnc_or_unique_ncbi_gene_crosswalk"]
    axes: list[ClinicalAxis] = Field(min_length=3, max_length=3)
    variant_type_counts: list[DistributionBin] = Field(max_length=1000)
    example_selection: Literal["lowest_variation_id_bounded_50"]
    records: list[ClinicalVariantExample] = Field(max_length=50)

    @model_validator(mode="after")
    def denominators(self):
        if {a.axis for a in self.axes} != {
            "germline",
            "somatic_clinical_impact",
            "oncogenicity",
        }:
            raise ValueError("clinical axes mismatch")
        if any(
            a.represented_variations > self.unique_variation_total for a in self.axes
        ):
            raise ValueError("axis exceeds unique variations")
        if (
            sum(b.count for b in self.variant_type_counts)
            != self.unique_variation_total
        ):
            raise ValueError("variant-type count mismatch")
        if (
            len({r.variation_id for r in self.records}) != len(self.records)
            or len(self.records) > self.unique_variation_total
        ):
            raise ValueError("variant example count mismatch")
        return self


class ClinicalConsequenceRecord(StrictModel):
    source_id: ShortText
    so_id: Annotated[str, StringConstraints(pattern=r"^SO:[0-9]{7}$")]
    term: Text
    represented_variations: int = Field(ge=1)
    axes: list[ClinicalAxis] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def axis_bounds(self):
        if {a.axis for a in self.axes} != {
            "germline",
            "somatic_clinical_impact",
            "oncogenicity",
        }:
            raise ValueError("consequence clinical axes mismatch")
        if any(
            a.represented_variations > self.represented_variations for a in self.axes
        ):
            raise ValueError("consequence axis exceeds bin denominator")
        return self


class ClinicalConsequencesData(StrictModel):
    kind: Literal["clinical_variant_consequences"]
    source_id: ShortText
    count_unit: Literal["source_consequence_bin"] = "source_consequence_bin"
    eligible_variations: int = Field(ge=0)
    membership_rule: Literal["single_native_geneinfo_unique_ncbi_crosswalk"]
    consequence_scope: Literal["provider_transcript_collapsed_MC"]
    records: list[ClinicalConsequenceRecord] = Field(max_length=1000)

    @model_validator(mode="after")
    def overlapping_denominators(self):
        keys = [(r.source_id, r.so_id, r.term) for r in self.records]
        if len(keys) != len(set(keys)) or any(
            r.source_id != self.source_id for r in self.records
        ):
            raise ValueError("duplicate/mismatched consequence source bin")
        if any(
            r.represented_variations > self.eligible_variations for r in self.records
        ):
            raise ValueError("consequence bin exceeds eligible denominator")
        if bool(self.records) != bool(self.eligible_variations):
            raise ValueError("eligible variants require represented MC terms")
        return self


class ExpressionRecord(StrictModel):
    source_id: ShortText
    ensembl_gene_id: ShortText
    tissue_id: ShortText
    tissue_label: Text
    median_tpm: float | None = Field(ge=0)
    unit: Literal["TPM"]
    statistic: Literal["median"]
    sample_count: int | None = Field(ge=1)
    category_type: Literal["provider_expression_category"]


class ExpressionData(StrictModel):
    kind: Literal["expression"]
    count_unit: Literal["provider_expression_category"] = "provider_expression_category"
    records: list[ExpressionRecord] = Field(max_length=5000)


class GwasRecord(StrictModel):
    source_id: ShortText
    association_id: ShortText
    association_identity_kind: Literal["provider_id", "full_source_row_digest"]
    study_accession: Annotated[str, StringConstraints(pattern=r"^GCST[0-9]+$")]
    trait: Text
    trait_ids: list[Text] = Field(
        max_length=100
    )  # Source identifiers; plain text, never an unvalidated link.
    mapped_trait: Annotated[str, Field(max_length=10000)]
    pmid: Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")] | None
    reported_genes: Annotated[str, Field(max_length=10000)]
    mapped_genes: Annotated[str, Field(max_length=10000)]
    variant: Annotated[str, Field(max_length=10000)]
    p_value: Annotated[
        str, Field(max_length=200)
    ]  # Exact decimal text preserves very small source values.
    p_value_context: Text | None
    odds_ratio_or_beta: (
        Text | None
    )  # Untyped source field, not a direction-of-effect claim.
    confidence_interval: Text | None
    source_url: Annotated[str, Field(max_length=2000)]
    gene_assignment: Literal["reported_gene", "mapped_gene"]
    gene_assignments: list[Literal["reported_gene", "mapped_gene"]] = Field(
        min_length=1, max_length=2
    )
    mapped_gene_context: list[
        Literal["intergenic_neighbor", "within_gene", "provider_mapping_unspecified"]
    ] = Field(max_length=3)
    _url = field_validator("source_url")(public_url)

    @model_validator(mode="after")
    def assignments(self):
        if (
            len(set(self.gene_assignments)) != len(self.gene_assignments)
            or self.gene_assignment not in self.gene_assignments
        ):
            raise ValueError("GWAS assignment mismatch")
        if self.mapped_gene_context and "mapped_gene" not in self.gene_assignments:
            raise ValueError("GWAS mapping context without mapped relationship")
        return self


class GwasData(StrictModel):
    kind: Literal["gwas"]
    count_unit: Literal["source_association_record"] = "source_association_record"
    records: list[GwasRecord] = Field(max_length=50000)

    @model_validator(mode="after")
    def unique_records(self):
        keys = [(r.source_id, r.association_id) for r in self.records]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate GWAS gene association")
        return self


class PhenotypeRecord(StrictModel):
    source_id: ShortText
    assertion_id: ShortText
    disease_id: ShortText
    disease_name: Text
    phenotype_id: Annotated[str, StringConstraints(pattern=r"^HP:[0-9]{7}$")]
    phenotype_label: None = (
        None  # Labels require a separately qualified ontology component.
    )
    allelic_requirement: Text | None
    classification: ShortText
    curation_date: ShortText | None
    report_url: Annotated[str, Field(max_length=2000)]
    pmids: list[Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")]] = Field(
        max_length=1000
    )
    _url = field_validator("report_url")(public_url)


class PhenotypesData(StrictModel):
    kind: Literal["phenotypes"]
    count_unit: Literal["source_relation_phenotype"] = "source_relation_phenotype"
    records: list[PhenotypeRecord] = Field(max_length=10000)

    @model_validator(mode="after")
    def unique_pairs(self):
        keys = [(r.source_id, r.assertion_id, r.phenotype_id) for r in self.records]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate source-listed HPO identifier pair")
        return self


class ProteinCrossReference(StrictModel):
    database: ShortText
    accession: ShortText
    label: Text | None
    source_url: Annotated[str, Field(max_length=2000)] | None
    _url = field_validator("source_url")(
        lambda value: public_url(value) if value is not None else None
    )


class ProteinRecord(StrictModel):
    source_id: ShortText
    accession: ShortText
    entry_name: ShortText
    reviewed: bool
    protein_name: Text
    protein_length: int = Field(ge=1)
    function_text: Annotated[str, Field(max_length=40000)] | None
    function_evidence: list[Text] = Field(max_length=100)
    pathway_text: Annotated[str, Field(max_length=10000)] | None
    cross_references: list[ProteinCrossReference] = Field(max_length=500)
    source_url: Annotated[str, Field(max_length=2000)]
    _url = field_validator("source_url")(public_url)


class ProteinPathwaysData(StrictModel):
    kind: Literal["protein_pathways"]
    count_unit: Literal["reviewed_protein_record"] = "reviewed_protein_record"
    records: list[ProteinRecord] = Field(max_length=1000)

    @model_validator(mode="after")
    def unique_records(self):
        keys = [(r.source_id, r.accession) for r in self.records]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate protein record")
        return self


SectionData = Annotated[
    OverviewData
    | DiseaseData
    | StructureData
    | ConstraintData
    | DosageData
    | MechanismsData
    | ClinicalVariantsData
    | ClinicalConsequencesData
    | ExpressionData
    | GwasData
    | PhenotypesData
    | ProteinPathwaysData,
    Field(discriminator="kind"),
]


class Freshness(StrictModel):
    last_source_check: ShortText | None
    stale: bool
    stale_reason: Text | None

    @model_validator(mode="after")
    def reason(self):
        if self.stale != (self.stale_reason is not None):
            raise ValueError("stale reason mismatch")
        return self


class StoredSection(StrictModel):
    gene_id: GeneId
    section: SectionName
    status: Literal[
        "available",
        "source_has_no_record",
        "unavailable",
        "not_integrated",
        "not_applicable",
    ]
    coverage: Literal["complete", "partial", "truncated", "unknown"]
    coverage_scope: Text
    freshness: Freshness
    source_ids: list[ShortText] = Field(max_length=50)
    data: SectionData | None
    limitations: list[Text] = Field(max_length=30)

    @model_validator(mode="after")
    def data_scope(self):
        if self.data is not None and self.data.kind != self.section:
            raise ValueError("section kind mismatch")
        if self.status == "available" and self.data is None:
            raise ValueError("available section requires data")
        if (
            self.status in ("unavailable", "not_integrated", "not_applicable")
            and self.data is not None
        ):
            raise ValueError("unavailable section has data")
        if self.status == "source_has_no_record":
            empty = self.data is not None and (
                (hasattr(self.data, "records") and not self.data.records)
                or (isinstance(self.data, OverviewData) and self.data.summary is None)
            )
            if not self.source_ids or self.coverage != "complete" or not empty:
                raise ValueError("absence requires covered source and empty records")
        if self.data is not None and hasattr(self.data, "records"):
            if self.status == "available" and not self.data.records:
                raise ValueError("empty collection requires explicit absence state")
            for record in self.data.records:
                if record.source_id not in self.source_ids:
                    raise ValueError("record source outside section")
                if (
                    isinstance(record, ConstraintMetric)
                    and record.gene_id != self.gene_id
                ):
                    raise ValueError("constraint gene mismatch")
        if (
            isinstance(self.data, (ClinicalVariantsData, ClinicalConsequencesData))
            and self.data.source_id not in self.source_ids
        ):
            raise ValueError("clinical aggregate source outside section")
        if (
            isinstance(self.data, OverviewData)
            and self.data.summary_source_id
            and self.data.summary_source_id not in self.source_ids
        ):
            raise ValueError("summary source outside section")
        return self


class StoredProfile(StrictModel):
    gene_id: GeneId
    canonical_symbol: ShortText
    sections: dict[SectionName, StoredSection]

    @model_validator(mode="after")
    def complete_shape(self):
        if set(self.sections) != SECTION_NAMES:
            raise ValueError("all section states required")
        if any(
            v.gene_id != self.gene_id or v.section != k
            for k, v in self.sections.items()
        ):
            raise ValueError("mixed gene or section")
        return self


class Pagination(StrictModel):
    observed_total: int | None = Field(default=None, ge=0)
    total: int | None = Field(ge=0)
    returned: int = Field(ge=0, le=50)
    count_unit: ShortText | None
    next_cursor: str | None


class SectionResponse(StoredSection):
    request_id: RequestId
    snapshot_id: Digest
    pagination: Pagination | None


class ProfileResponse(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    gene_id: GeneId
    request_id: RequestId
    snapshot_id: Digest
    canonical_symbol: ShortText
    generated_at: ShortText
    identity: GeneIdentity
    sources: dict[str, Source]
    sections: dict[SectionName, SectionResponse]

    @model_validator(mode="after")
    def same_snapshot(self):
        if (
            self.identity.gene_id != self.gene_id
            or self.identity.symbol != self.canonical_symbol
            or set(self.sections) != SECTION_NAMES
        ):
            raise ValueError("profile identity mismatch")
        if self.identity.source_id not in self.sources:
            raise ValueError("identity source missing")
        for key, section in self.sections.items():
            if (
                section.gene_id,
                section.request_id,
                section.snapshot_id,
                section.section,
            ) != (self.gene_id, self.request_id, self.snapshot_id, key):
                raise ValueError("mixed response identity")
            if not set(section.source_ids) <= self.sources.keys():
                raise ValueError("section source missing")
        return self


# Standalone public DTOs mirror the owning public gene HTTP contract.
# Scientific records remain upstream-owned; this module only validates transport.


class ResolveGeneArguments(StrictModel):
    query: Annotated[
        str,
        Field(
            min_length=1,
            max_length=128,
            description="One public gene symbol, previous symbol, alias, HGNC ID, Ensembl gene ID or NCBI Gene ID. No patient or case narrative.",
        ),
    ]

    _query_text = field_validator("query")(ResolveRequest.query_text.__func__)


class GetGeneProfileArguments(StrictModel):
    gene_id: Annotated[
        GeneId,
        Field(
            description="Canonical HGNC gene_id returned by resolve_gene. Select an explicit candidate when resolution is ambiguous."
        ),
    ]
    snapshot_id: Annotated[
        Digest,
        Field(
            description="identity_snapshot_id returned by resolve_gene, or snapshot_id from the current gene profile. Restart resolution after snapshot_unavailable."
        ),
    ]


class GetGeneSectionArguments(GetGeneProfileArguments):
    section: Annotated[
        SectionName,
        Field(
            description="Source-qualified section from the current profile. Literature is a separate live capture; use search_gene_literature for it."
        ),
    ]
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=50,
            description="Maximum source records per page, from 1 to 50. Counts retain their original source unit.",
        ),
    ] = 20
    cursor: Annotated[
        str | None,
        Field(
            max_length=512,
            description="Opaque next_cursor returned for this same gene, snapshot and section. Omit for its first page.",
        ),
    ] = None


class SearchGeneLiteratureArguments(GetGeneProfileArguments):
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=25,
            description="Maximum publication records in one live discovery page, from 1 to 25.",
        ),
    ] = 20
    sort: Annotated[
        Literal["relevance", "newest", "oldest"],
        Field(
            description="Discovery ordering. Keep the same sort for continuation pages."
        ),
    ] = "relevance"
    cursor: Annotated[
        str | None,
        Field(
            max_length=4096,
            description="Opaque next_cursor returned for this same gene, snapshot and sort. Omit for the first page.",
        ),
    ] = None


class DiscoveryRecord(StrictModel):
    work_id: ShortText
    pmid: Annotated[str, Field(pattern=r"^[0-9]{1,12}$")] | None
    title: Text
    journal: Text | None
    publication_date: ShortText | None
    doi: ShortText | None
    source_url: Annotated[str, Field(max_length=2000)]
    match_types: list[ShortText] = Field(max_length=30)
    rank_score: float
    relation: Literal["discovery_result_not_curated_gene_association"] = (
        "discovery_result_not_curated_gene_association"
    )
    _url = field_validator("source_url")(public_url)


class GeneLiteratureResponse(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    gene_id: GeneId
    canonical_symbol: ShortText
    request_id: RequestId
    snapshot_id: Digest
    owner: Literal["canonical_literature_mining"] = "canonical_literature_mining"
    query: Text
    captured_at: ShortText
    capture_sha256: Digest
    owner_contract_version: Literal["1.0"] = "1.0"
    owner_returned_count: int = Field(ge=0, le=25)
    returned: int = Field(ge=0, le=25)
    filtered_unsafe_link_count: int = Field(ge=0, le=25)
    records: list[DiscoveryRecord] = Field(max_length=25)
    has_more: bool
    next_cursor: str | None
    semantic_index_used: bool
    semantic_degraded_reason: Text | None
    graph_used: bool
    graph_version: ShortText | None
    graph_degraded_reason: Text | None
    limits: list[Text]

    @model_validator(mode="after")
    def conservation(self):
        if (
            self.returned != len(self.records)
            or self.owner_returned_count
            != self.returned + self.filtered_unsafe_link_count
        ):
            raise ValueError("literature capture count mismatch")
        if self.has_more != (self.next_cursor is not None):
            raise ValueError("literature cursor state")
        if len({row.work_id for row in self.records}) != len(self.records):
            raise ValueError("duplicate canonical work")
        return self


PUBLIC_GENE_ARGUMENTS = {
    "resolve": ResolveGeneArguments,
    "profile": GetGeneProfileArguments,
    "section": GetGeneSectionArguments,
    "literature": SearchGeneLiteratureArguments,
}
PUBLIC_GENE_RESPONSES = {
    "resolve": ResolveResponse,
    "profile": ProfileResponse,
    "section": SectionResponse,
    "literature": GeneLiteratureResponse,
}


def public_gene_boundary() -> dict:
    return {
        "intended_use": "professional_gene_reference_review",
        "patient_context_evaluated": False,
        "review_required": True,
        "changes_variant_classification": False,
        "not_for": [
            "patient_diagnosis",
            "treatment_decision",
            "variant_pathogenicity_classification",
        ],
    }
