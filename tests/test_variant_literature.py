import httpx
import pytest

from folklore_mcp_service.application.literature_gateway import (
    LiteratureGateway,
    LiteratureGatewayError,
)
from folklore_mcp_service.config.settings import Settings
from folklore_mcp_service.domain.literature_contracts import (
    PublicationDetailsResponse,
    PublicCorpusSearchResponse,
    SearchVariantLiteratureArguments,
)


def corpus_search_payload() -> dict:
    return {
        "contract_version": "1.0",
        "query": "BRCA1 homologous recombination",
        "returned_count": 1,
        "results": [
            {
                "work_id": "pmid:12345678",
                "pmid": "12345678",
                "title": "A complete publication",
                "abstract_excerpt": "BRCA1 participates in homologous recombination.",
                "journal": "Genetics",
                "publication_date": "2025-06-01",
                "doi": "10.1000/example",
                "pmc_id": "PMC1234567",
                "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
                "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
                "match_types": ["gene", "semantic"],
                "structured_score": 1.0,
                "semantic_score": 0.91,
                "rank_score": 1.91,
                "article_entities": [
                    {
                        "entity_type": "gene",
                        "identifier": "BRCA1",
                        "label": "BRCA1",
                        "source_field": "gene_mentions.gene_symbol",
                        "normalization_state": "normalized",
                    }
                ],
            }
        ],
        "has_more": True,
        "next_cursor": "MToyNTphYmNkZWYxMjM0NTY3ODkw",
        "searchable_fields": ["title", "abstract", "gene"],
        "semantic_index_used": True,
        "semantic_degraded_reason": None,
        "usage_boundary": {
            "review_required": True,
            "patient_context_evaluated": False,
            "not_for": ["patient_diagnosis", "treatment_decision"],
        },
    }


def publication_details_payload() -> dict:
    return {
        "contract_version": "1.0",
        "publication": {
            "pmid": "12345678",
            "title": "A complete publication",
            "abstract": "Full abstract.",
            "authors": ["Smith J", "Doe A"],
            "journal": "Genetics",
            "publication_date": "2025-06-01",
            "publication_types": ["Journal Article"],
            "mesh_terms": ["Genetic Diseases"],
            "doi": "10.1000/example",
            "pmc_id": "PMC1234567",
            "is_retracted": False,
            "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
            "full_text_url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1234567/",
            "gene_mentions": [
                {
                    "gene_symbol": "GENE",
                    "association_type": "disease",
                    "mention_count": 3,
                }
            ],
            "variant_mentions": [
                {
                    "gene_symbol": "GENE",
                    "hgvs_cdna": "c.1A>G",
                    "hgvs_protein": "p.Met1Val",
                    "normalized_variant": "GENE:c.1A>G",
                    "clinical_significance": "pathogenic",
                    "evidence_type": "case_report",
                    "sentence_text": "The variant was reported.",
                    "confidence_score": 0.95,
                }
            ],
        },
        "usage_boundary": {
            "result_type": "publication_details",
            "review_required": True,
            "patient_context_evaluated": False,
            "changes_variant_classification": False,
            "intended_use": "professional_literature_review",
            "not_for": ["patient_diagnosis", "causality_claim", "treatment_decision"],
        },
    }


def literature_search_payload() -> dict:
    return {
        "contract_version": "1.0",
        "status": "resolved",
        "variant_result": {"search_contract_version": "1.0", "status": "resolved"},
        "literature": {
            "contract_version": "1.0",
            "assembly": "GRCh38",
            "canonical_key": "GRCh38:chr1:1:A:G",
            "gene_symbol": "GENE",
            "aliases": ["chr1:g.1A>G"],
            "question": None,
            "candidate_count": 0,
            "publications": [],
            "provenance": {
                "source": "PubMed-derived Helena genetics corpus",
                "publication_count": 1,
                "latest_publication_date": "2025-01-01",
                "retrieved_at": "2026-08-12T00:00:00+00:00",
                "semantic_index_used": False,
            },
            "limitations": ["For professional review."],
        },
        "usage_boundary": {
            "result_type": "variant_literature_retrieval",
            "review_required": True,
            "patient_context_evaluated": False,
            "changes_variant_classification": False,
            "intended_use": "professional_literature_review",
            "not_for": ["patient_diagnosis", "causality_claim", "treatment_decision"],
        },
    }


def settings() -> Settings:
    return Settings(
        ENVIRONMENT="test",
        FOLKLORE_LITERATURE_ENABLED=True,
        FOLKLORE_API_BASE_URL="http://127.0.0.1:9001",
        FOLKLORE_MCP_DEADLINE_SECONDS=5.0,
    )


@pytest.mark.asyncio
async def test_literature_gateway_calls_public_search_contract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/folklore/v1/literature/search"
        return httpx.Response(
            200,
            json=literature_search_payload(),
            headers={"Content-Type": "application/json"},
        )

    client = httpx.AsyncClient(
        base_url="http://127.0.0.1:9001", transport=httpx.MockTransport(handler)
    )
    result = await LiteratureGateway(settings(), client).search(
        SearchVariantLiteratureArguments(query="chr1:1 A>G")
    )
    assert result.status == "resolved"
    assert result.literature is not None
    assert result.literature.gene_symbol == "GENE"
    await client.aclose()


@pytest.mark.asyncio
async def test_literature_gateway_calls_public_publication_contract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/folklore/v1/literature/publications/12345678"
        return httpx.Response(
            200,
            json=publication_details_payload(),
            headers={"Content-Type": "application/json"},
        )

    client = httpx.AsyncClient(
        base_url="http://127.0.0.1:9001", transport=httpx.MockTransport(handler)
    )
    result = await LiteratureGateway(settings(), client).get_publication("12345678")
    assert isinstance(result, PublicationDetailsResponse)
    assert result.publication.authors == ["Smith J", "Doe A"]
    assert result.usage_boundary["patient_context_evaluated"] is False
    await client.aclose()


@pytest.mark.asyncio
async def test_publication_not_found_is_scoped_to_folklore_corpus() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/folklore/v1/literature/publications/12345678"
        return httpx.Response(404)

    client = httpx.AsyncClient(
        base_url="http://127.0.0.1:9001", transport=httpx.MockTransport(handler)
    )

    with pytest.raises(LiteratureGatewayError) as captured:
        await LiteratureGateway(settings(), client).get_publication("12345678")

    assert captured.value.code == "publication_not_found"
    assert captured.value.retryable is False
    assert str(captured.value) == (
        "No record for this PMID exists in Folklore's current PubMed-derived "
        "genetics corpus."
    )
    await client.aclose()


@pytest.mark.asyncio
async def test_literature_gateway_calls_public_corpus_search_contract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/folklore/v1/literature/corpus/search"
        assert request.method == "POST"
        return httpx.Response(
            200,
            json=corpus_search_payload(),
            headers={"Content-Type": "application/json"},
        )

    client = httpx.AsyncClient(
        base_url="http://127.0.0.1:9001", transport=httpx.MockTransport(handler)
    )
    result = await LiteratureGateway(settings(), client).search_corpus(
        {
            "query": "BRCA1 homologous recombination",
            "limit": 5,
            "sort": "relevance",
        }
    )
    assert isinstance(result, PublicCorpusSearchResponse)
    assert result.results[0].article_entities[0].identifier == "BRCA1"
    assert result.next_cursor == "MToyNTphYmNkZWYxMjM0NTY3ODkw"
    await client.aclose()
