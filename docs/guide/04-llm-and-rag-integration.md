# Chapter 4: LLM & RAG Integration

The LLM layer adds natural language explanation to deterministic PGx results. It never
overrides the deterministic layer — it only explains what was already computed.

For the current trial MVP wedge, deterministic exports are the primary deliverable.
LLM output is supplemental context and is not required to generate trial-facing rows.

## 4.1 Design Principle

```
Deterministic Layer → "CYP2C19 *1/*2, Intermediate Metabolizer"
LLM Layer           → "This patient has one loss-of-function allele (*2) in CYP2C19,
                        which reduces their ability to activate clopidogrel. CPIC
                        recommends considering prasugrel or ticagrelor instead."
```

The LLM receives the deterministic results as ground truth in its prompt and is instructed
to explain — never contradict — the provided data.

## 4.2 LLM Backends

### Amazon Nova (Default)

**Module**: `src/llm_bedrock.py` (`generate_pgx_response_nova`)

Amazon Nova Lite and Nova Pro on AWS Bedrock are the default LLM backends (`LLM_BACKEND=nova`):

```python
def generate_pgx_response_nova(patient_data, drug_info, pgx_results, model_id=None):
    """Generate PGx explanation using Amazon Nova Lite/Pro."""
    model_id = model_id or resolve_nova_model_id()  # e.g. amazon.nova-lite-v1:0
    response = bedrock_client.invoke_model(
        modelId=model_id,
        body=json.dumps({
            "messages": [{"role": "user", "content": prompt}],
            "inferenceConfig": {"maxTokens": 1024, "temperature": 0.3}
        })
    )
    return response
```

Select via `LLM_BACKEND=nova` (default) or `LLM_BACKEND=bedrock` for Claude.

### Google Gemini (Alternative)

**Module**: `src/agent_engine.py`

Set `LLM_BACKEND=gemini` and provide `GOOGLE_API_KEY` to use Gemini:

```python
# Lazy initialization
def _get_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",  # or gemini-2.5-pro, gemini-2.0-flash
        google_api_key=config.GOOGLE_API_KEY,
        temperature=0.3
    )
```

### AWS Bedrock Claude (Alternative)

**Module**: `src/llm_bedrock.py`

```python
def generate_pgx_response(patient_data, drug_info, pgx_results):
    prompt = _build_prompts(patient_data, drug_info, pgx_results)
    response = bedrock_client.invoke_model(
        modelId="anthropic.claude-3-sonnet-20240229-v1:0",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.3
        })
    )
    return response
```

Prompt engineering rules for all Bedrock models:
1. Use the provided PGx data as absolute truth
2. Never invent alleles, phenotypes, or recommendations
3. Cite CPIC guidelines when making statements
4. Explain mechanisms (enzyme function, drug metabolism pathway)
5. Flag limitations (evidence gaps, population-specific caveats)

### Anthropic Claude (Direct API)

**Module**: `src/agent_engine.py` (via `_get_claude_llm()`)

Alternative to Bedrock — direct Anthropic API access via `langchain-anthropic`.

## 4.3 RAG Architecture

### Drug Similarity Search (OpenSearch/Pinecone)

**Module**: `src/vector_search.py`

```
Drug SMILES → RDKit Morgan Fingerprint (2048-bit) → OpenSearch/Pinecone Query → Similar Drugs
```

Flow:
1. `input_processor.py` validates SMILES and generates a 2048-dimensional Morgan fingerprint
2. `vector_search.py` queries OpenSearch (preferred) or Pinecone for top-k similar drugs
3. Results include: drug names, targets, mechanisms, known side effects
4. These are injected into the LLM prompt as additional context

**Resilience**: Circuit breaker pattern (`src/resilience.py`) protects vector DB queries:

```python
@circuit_breaker(failure_threshold=5, recovery_timeout=60)
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
def _query_opensearch_with_retry(vector, top_k):
    return client.search(index="drug-index", body=knn_body)
```

States: CLOSED → OPEN (after 5 failures) → HALF-OPEN (after 60s) → CLOSED (on success)

Fallback: If OpenSearch/Pinecone is unavailable, `_get_mock_drugs()` provides curated drug data.

Mock fallback is intentionally surfaced in API audit metadata (`vector_mock_fallback`)
so trial users can detect and reject non-production retrieval context when needed.

## 4.3.1 Novel Drug Mode (Confidence-Tiered)

`POST /analyze/novel-drug` extends standard analysis with:

- metadata inputs (`targets`, `metabolism_enzymes`, `transporters`, `evidence_notes`)
- inferred candidate genes from analog retrieval + metadata evidence via `src/novel_drug_inference.py`
- explicit confidence tiers (classified by `src/confidence_tiering.py`):
  - `high`: deterministic CPIC/PharmVar coverage for inferred candidate genes
  - `moderate`: strong multi-source evidence (analogs + metadata), but incomplete deterministic coverage
  - `exploratory`: sparse/similarity-led evidence only
- deterministic coverage report (`callable_genes`, `missing_genes`)
- validation gate (`decision_grade`) and benchmark artifact summary

This keeps novel-drug outputs transparent and prevents similarity-only claims from being
misread as decision-grade PGx guidance.

### ChEMBL Drug Database

**Module**: `src/chembl_processor.py`

ChEMBL v34 SQLite database provides:
- Drug molecules with SMILES (Phase 2+ clinical candidates)
- Drug-target interactions (binding affinity, mechanism)
- Known side effects and adverse reactions

**Pipelines**: `scripts/ingest_chembl_to_opensearch.py` or `scripts/ingest_chembl_to_pinecone.py`
```
ChEMBL SQLite → Extract molecules → Generate fingerprints → Upload to OpenSearch/Pinecone
```

### Local PGx Document Retrieval

**Module**: `src/rag/retriever.py`

For Bedrock-based RAG, a local retrieval layer indexes CPIC JSON files:

```python
def _load_documents():
    # Load all CPIC JSON files from data/pgx/cpic/
    # Generate Titan embeddings for each document
    # Store in-memory for cosine similarity search

def retrieve(query, top_k=3):
    query_embedding = get_embedding(query)  # Titan Embed Text v2
    similarities = [cosine_similarity(query_embedding, doc_emb) for doc_emb in docs]
    return top_k_documents
```

### Bedrock RAG Pipeline

**Module**: `src/rag_bedrock.py`

End-to-end flow:
```
1. build_query()     → Combine drug + patient profile + similar drugs into text
2. retrieve_context() → Fetch relevant CPIC knowledge from local retriever
3. generate()         → Call Claude via Bedrock with context + query
```

### Embeddings

**Module**: `src/embeddings_bedrock.py`

Uses Amazon Titan Embed Text v2 for text-to-vector conversion:

```python
def get_embedding(text):
    response = bedrock_client.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": text})
    )
    return response["embedding"]  # 1024-dimensional vector
```

## 4.4 Agent Engine Orchestration

**Module**: `src/agent_engine.py`

The agent engine ties everything together:

```python
def run_simulation(drug_smiles, patient_profile, drug_name=None):
    # 1. Get drug fingerprint
    fingerprint = get_drug_fingerprint(drug_smiles)

    # 2. Find similar drugs via configured vector backend
    similar_drugs = find_similar_drugs(fingerprint)

    # 3. Get relevant genes for this drug
    gene_triggers = get_gene_triggers(drug_name)

    # 4. Build prompt with deterministic PGx data
    prompt = build_prompt(
        patient_profile=patient_profile,
        similar_drugs=similar_drugs,
        gene_triggers=gene_triggers,
        pgx_results=patient_profile.get("pgx_results")
    )

    # 5. Generate LLM explanation
    llm = _get_llm()  # or _get_claude_llm()
    response = llm.invoke(prompt)

    return {
        "pgx_results": patient_profile["pgx_results"],  # Deterministic
        "explanation": response.content,                  # LLM-generated
        "similar_drugs": similar_drugs,
        "confidence": compute_confidence(patient_profile)
    }
```

## 4.5 Prompt Engineering

The LLM prompt is carefully structured to prevent hallucination:

```
System: You are a pharmacogenomics expert. You will be provided with
deterministic PGx analysis results. Your role is to EXPLAIN these results,
not to modify or override them. Always cite CPIC guidelines.

Context:
- Patient genotype: {diplotype}
- Phenotype: {phenotype} (determined by CPIC lookup)
- Drug: {drug_name}
- Similar drugs: {similar_drugs_list}
- Relevant CPIC guideline: {guideline_summary}

Task: Explain the clinical significance of this patient's pharmacogenomic
profile for {drug_name}. Include:
1. How the genotype affects drug metabolism
2. The CPIC recommendation
3. Alternative drugs if applicable
4. Any ancestry-specific considerations

IMPORTANT: Do not invent data. Only use the information provided above.
```

## 4.6 Vector Index Setup

**OpenSearch scripts (recommended)**:
- `scripts/setup_opensearch_index.py`
- `scripts/ingest_chembl_to_opensearch.py`

```python
# Index configuration
index_name = "drug-index"
dimension = 2048  # RDKit Morgan fingerprint size
metric = "cosine"
backend = "opensearch"
```

**Alternative Pinecone scripts**:
- `scripts/setup_pinecone_index.py`
- `scripts/ingest_chembl_to_pinecone.py`

---

**Next**: [Chapter 5 — VCF Processing Pipeline](05-vcf-processing-pipeline.md)
