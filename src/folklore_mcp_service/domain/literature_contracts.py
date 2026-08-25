"""Closed public contracts for Folklore variant-literature search."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from folklore_mcp_service.domain.contracts import SearchStatus, VariantQuery


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SearchVariantLiteratureArguments(StrictModel):
    assembly: Annotated[
        Literal["GRCh38"],
        Field(
            description=(
                "Reference genome assembly. Folklore currently accepts GRCh38 only."
            )
        ),
    ] = "GRCh38"
    query: Annotated[
        VariantQuery,
        Field(
            description=(
                "One germline nuclear SNV or simple indel to resolve before "
                "retrieving its literature; this is a variant identifier, not a "
                "natural-language question. Accepts a returned Folklore "
                "canonical_key in GRCh38:chrN:position:REF:ALT form."
            )
        ),
    ]
    question: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=3, max_length=500),
        Field(
            description=(
                "Optional natural-language focus applied after the variant is "
                "resolved, such as a condition or evidence question; do not put "
                "the variant identifier here."
            )
        ),
    ] = None
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=25,
            description="Maximum number of publications to return, from 1 to 25.",
        ),
    ] = 10


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
    pmid: Annotated[
        str,
        StringConstraints(pattern=r"^[0-9]{1,12}$"),
        Field(
            description=(
                "One PubMed identifier to look up in Folklore's current corpus, "
                "as 1 to 12 digits without a PMID prefix."
            )
        ),
    ]


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


CorpusMatchType = Literal[
    "pmid",
    "doi",
    "pmcid",
    "title",
    "abstract",
    "gene",
    "variant",
    "phenotype",
    "hpo",
    "omim",
    "semantic",
]
CorpusArticleEntityType = Literal[
    "gene",
    "variant",
    "phenotype",
    "pmid",
    "doi",
    "pmcid",
    "omim",
]
CorpusEntitySourceField = Literal[
    "work_identifiers.normalized_value",
    "gene_mentions.gene_symbol",
    "variant_mentions.normalized_variant",
    "phenotype_mentions.hpo_id",
    "phenotype_mentions.omim_id",
    "phenotype_mentions.mesh_term",
    "phenotype_mentions.phenotype_name",
]
CorpusNormalizationState = Literal["normalized", "source_indexed"]
CorpusCursor = Annotated[
    str,
    StringConstraints(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
]


class SearchCorpusArguments(StrictModel):
    query: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=3, max_length=200),
        Field(
            description=(
                "Natural-language literature question or exact PMID, DOI, PMCID, "
                "gene, variant, phenotype, HPO, or OMIM query. Include every known "
                "publication identifier when comparing or finding related papers."
            )
        ),
    ]
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=25,
            description="Maximum number of publications to return, from 1 to 25.",
        ),
    ] = 20
    sort: Annotated[
        Literal["relevance", "newest", "oldest"],
        Field(
            description=(
                "Result ordering: relevance-ranked, newest publication first, or "
                "oldest publication first."
            )
        ),
    ] = "relevance"
    cursor: Annotated[
        CorpusCursor | None,
        Field(
            description=(
                "Opaque continuation cursor from the preceding response for the "
                "same query and sort order; omit for the first page."
            )
        ),
    ] = None


class PublicCorpusArticleEntity(StrictModel):
    entity_type: CorpusArticleEntityType
    identifier: str | None
    label: str
    source_field: CorpusEntitySourceField
    normalization_state: CorpusNormalizationState


class PublicCorpusSearchResult(StrictModel):
    work_id: str
    pmid: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,12}$")] | None
    title: str
    abstract_excerpt: str
    journal: str | None
    publication_date: str | None
    doi: str | None
    pmc_id: str | None
    source_url: str
    pubmed_url: str | None
    match_types: list[CorpusMatchType]
    structured_score: float
    semantic_score: float | None = None
    rank_score: float = 0.0
    article_entities: list[PublicCorpusArticleEntity] = Field(default_factory=list)


class PublicCorpusSearchResponse(StrictModel):
    contract_version: Literal["1.0"]
    query: str
    returned_count: int
    results: list[PublicCorpusSearchResult]
    has_more: bool = False
    next_cursor: str | None = None
    searchable_fields: list[str]
    semantic_index_used: bool = False
    semantic_degraded_reason: str | None = None
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
