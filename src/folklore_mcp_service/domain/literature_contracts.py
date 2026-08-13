"""Closed public contracts for Folklore variant-literature search."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from folklore_mcp_service.domain.contracts import SearchStatus, VariantQuery


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SearchVariantLiteratureArguments(StrictModel):
    assembly: Literal["GRCh38"] = "GRCh38"
    query: VariantQuery
    question: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=3, max_length=500),
    ] = None
    limit: Annotated[int, Field(ge=1, le=25)] = 10


class LiteraturePublication(StrictModel):
    pmid: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,12}$")]
    title: str
    abstract_excerpt: str
    journal: str | None
    publication_date: str | None
    doi: str | None
    pmc_id: str | None
    pubmed_url: str
    match_type: Literal["exact_variant", "variant_alias", "gene_association"]
    matched_variant: str | None
    mention_context: str | None
    phenotype_terms: list[str]
    structured_score: float


class CorpusProvenance(StrictModel):
    source: Literal["PubMed-derived Helena genetics corpus"]
    publication_count: int
    latest_publication_date: str | None
    retrieved_at: str
    semantic_index_used: bool


class LiteratureAuthorityResponse(StrictModel):
    contract_version: Literal["1.0"]
    assembly: Literal["GRCh38"]
    canonical_key: str
    gene_symbol: str
    aliases: list[str]
    question: str | None
    candidate_count: int
    publications: list[LiteraturePublication]
    provenance: CorpusProvenance
    limitations: list[str]


class PublicVariantLiteratureResponse(StrictModel):
    contract_version: Literal["1.0"] = "1.0"
    status: SearchStatus
    variant_result: dict[str, Any]
    literature: LiteratureAuthorityResponse | None
    usage_boundary: dict[str, Any]


class GetPublicationDetailsArguments(StrictModel):
    pmid: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,12}$")]


class PublicGeneMention(StrictModel):
    gene_symbol: str
    association_type: str | None
    mention_count: int


class PublicVariantMention(StrictModel):
    gene_symbol: str | None
    hgvs_cdna: str | None
    hgvs_protein: str | None
    normalized_variant: str | None
    clinical_significance: str | None
    evidence_type: str | None
    sentence_text: str | None
    confidence_score: float | None


class PublicPublicationDetails(StrictModel):
    pmid: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,12}$")]
    title: str
    abstract: str | None
    authors: list[str]
    journal: str | None
    publication_date: str | None
    publication_types: list[str]
    mesh_terms: list[str]
    doi: str | None
    pmc_id: str | None
    is_retracted: bool
    pubmed_url: str
    full_text_url: str | None
    gene_mentions: list[PublicGeneMention]
    variant_mentions: list[PublicVariantMention]


class PublicationDetailsResponse(StrictModel):
    contract_version: Literal["1.0"]
    publication: PublicPublicationDetails
    usage_boundary: dict[str, Any]


def literature_usage_boundary() -> dict[str, Any]:
    return {
        "result_type": "variant_literature_retrieval",
        "review_required": True,
        "patient_context_evaluated": False,
        "changes_variant_classification": False,
        "intended_use": "professional_literature_review",
        "not_for": ["patient_diagnosis", "causality_claim", "treatment_decision"],
    }
