# Chapter 6: Population Simulation & Ancestry

Anukriti can simulate drug response across synthetic patient populations of up to 10,000
individuals, using real-world allele frequencies from gnomAD v4.1 and the 1000 Genomes Project.

## 6.1 Population Simulator (`src/population_simulator.py`)

### Core Data Structures

```python
@dataclass
class SyntheticPatient:
    patient_id: str
    ancestry: str              # AFR, EUR, EAS, SAS, AMR
    genotypes: Dict[str, str]  # gene → diplotype
    phenotypes: Dict[str, str] # gene → phenotype
    metadata: Dict             # age, sex, comorbidities

@dataclass
class AdverseEvent:
    patient_id: str
    drug: str
    event_type: str           # toxicity, reduced_efficacy, etc.
    severity: str             # mild, moderate, severe
    gene: str
    phenotype: str

@dataclass
class PerformanceMetrics:
    total_patients: int
    processing_time_sec: float
    throughput_per_min: float
    memory_usage_mb: float
    aws_cost_estimate: float

@dataclass
class CohortResults:
    patients: List[SyntheticPatient]
    phenotype_distributions: Dict
    adverse_events: List[AdverseEvent]
    metrics: PerformanceMetrics
```

### Synthetic Patient Generation

```python
def generate_synthetic_cohort(n_patients, ancestry_distribution=None):
    """
    Generate N synthetic patients with realistic genotypes.

    Default ancestry distribution (proportional to global representation):
    - EUR: 30%
    - AFR: 25%
    - EAS: 20%
    - SAS: 15%
    - AMR: 10%
    """
    patients = []
    for i in range(n_patients):
        ancestry = sample_ancestry(ancestry_distribution)
        genotypes = {}
        phenotypes = {}

        for gene in SUPPORTED_GENES:
            # Sample alleles based on ancestry-specific frequencies
            allele1 = sample_allele(gene, ancestry)
            allele2 = sample_allele(gene, ancestry)
            diplotype = build_diplotype([allele1, allele2], gene)
            phenotype = diplotype_to_phenotype(diplotype, gene)

            genotypes[gene] = diplotype
            phenotypes[gene] = phenotype

        patients.append(SyntheticPatient(
            patient_id=f"SYN_{i:05d}",
            ancestry=ancestry,
            genotypes=genotypes,
            phenotypes=phenotypes
        ))

    return patients
```

### Parallel Execution

```python
def run_population_simulation(drug, n_patients, ancestry_dist=None):
    """Run population-scale simulation with ThreadPoolExecutor."""
    patients = generate_synthetic_cohort(n_patients, ancestry_dist)

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = [
            executor.submit(analyze_patient, patient, drug)
            for patient in patients
        ]
        results = [f.result() for f in futures]

    return CohortResults(
        patients=patients,
        phenotype_distributions=aggregate_phenotypes(results),
        adverse_events=collect_adverse_events(results),
        metrics=compute_metrics(start_time, n_patients)
    )
```

## 6.2 Allele Frequencies

### gnomAD v4.1 Frequencies

Used in `src/benchmark/expanded_validation.py`:

```python
ALLELE_FREQUENCIES = {
    "CYP2C19": {
        "*1": {"EUR": 0.63, "AFR": 0.73, "EAS": 0.60, "SAS": 0.65, "AMR": 0.66},
        "*2": {"EUR": 0.15, "AFR": 0.15, "EAS": 0.29, "SAS": 0.15, "AMR": 0.12},
        "*3": {"EUR": 0.00, "AFR": 0.00, "EAS": 0.05, "SAS": 0.02, "AMR": 0.00},
        "*17": {"EUR": 0.22, "AFR": 0.12, "EAS": 0.06, "SAS": 0.18, "AMR": 0.22},
    },
    "CYP2D6": {
        "*1": {"EUR": 0.40, "AFR": 0.42, "EAS": 0.35, "SAS": 0.41, "AMR": 0.43},
        "*4": {"EUR": 0.20, "AFR": 0.07, "EAS": 0.01, "SAS": 0.10, "AMR": 0.12},
        "*10": {"EUR": 0.02, "AFR": 0.06, "EAS": 0.43, "SAS": 0.09, "AMR": 0.05},
        "*41": {"EUR": 0.09, "AFR": 0.09, "EAS": 0.02, "SAS": 0.15, "AMR": 0.07},
        "*5": {"EUR": 0.03, "AFR": 0.06, "EAS": 0.06, "SAS": 0.03, "AMR": 0.03},
    },
    # ... (all 8 genes × 5 ancestries)
}
```

### Key Ancestry-Specific Patterns

| Gene | Notable Pattern |
|------|-----------------|
| CYP2D6 | *10 highest in EAS (43%), rare in EUR (2%) |
| CYP2D6 | *4 highest in EUR (20%), rare in EAS (1%) |
| CYP2C19 | *2 highest in EAS (29%), drives clopidogrel resistance |
| CYP2C19 | *17 highest in EUR/AMR (22%), ultra-rapid metabolism |
| DPYD | *2A rare globally (0.5-2%), but fatal toxicity when present |
| SLCO1B1 | C allele (rs4149056) 15-18% in EUR, lower in EAS |

## 6.3 Ancestry-Aware Confidence (`src/ancestry_risk.py`)

Confidence adjustments based on evidence strength per population:

```python
POPULATION_VARIANT_FREQUENCIES = {
    "CYP2C19": {
        "rs4244285": {"AFR": 0.15, "EUR": 0.15, "EAS": 0.29, "SAS": 0.15, "AMR": 0.12},
        ...
    },
    ...
}

EVIDENCE_STRENGTH = {
    "CYP2D6": {"EUR": "strong", "AFR": "moderate", "EAS": "moderate",
               "SAS": "limited", "AMR": "limited"},
    "CYP2C19": {"EUR": "strong", "AFR": "moderate", "EAS": "strong",
                "SAS": "moderate", "AMR": "moderate"},
    ...
}

def compute_ancestry_confidence(gene, population, phenotype=None):
    """
    Adjust confidence based on:
    1. CPIC evidence level for this gene
    2. Population-specific study representation
    3. Phenotype rarity (rare phenotypes = lower confidence)
    """
    base_confidence = 0.95 if evidence == "strong" else 0.85 if evidence == "moderate" else 0.70
    if phenotype and is_rare_phenotype(phenotype, gene, population):
        base_confidence *= 0.9  # Reduce for rare phenotypes
    return {"confidence": base_confidence, "evidence_level": evidence}
```

## 6.4 Throughput Benchmarks

Throughput depends heavily on hardware, cohort size, and whether Bedrock/OpenSearch are used.
Run `scripts/benchmark_performance.py` on your deployment to get accurate numbers.

Indicative ranges (deterministic engine only, no LLM):

| Configuration | Patients/minute | Notes |
|---------------|-----------------|-------|
| Single-threaded | ~50,000 | Deterministic engine only |
| ThreadPoolExecutor (8 cores) | ~200,000–400,000 | Local parallel, hardware-dependent |
| AWS Lambda (100 concurrent) | Scales with concurrency | Production cloud path |

> **Note**: Do not cite fixed throughput numbers in presentations without running `scripts/benchmark_performance.py` on your own hardware first. Results vary significantly by environment.

## 6.5 Population Simulation in the UI

The Streamlit frontend (`app.py`) provides:

1. **Cohort size selector**: 100 to 10,000 patients
2. **Ancestry distribution**: Customizable percentages
3. **Drug selection**: From CPIC drug list
4. **Real-time progress**: Streamlit progress bar during simulation
5. **Results visualization**:
   - Phenotype distribution pie charts (per gene)
   - Ancestry breakdown bar charts
   - Adverse event risk table
   - Performance metrics panel

## 6.6 AWS Integration for Scale

For production-scale simulations:

### Lambda Batch Processing (`src/aws/lambda_batch_processor.py`)

```python
class LambdaBatchProcessor:
    def process_batch(self, patients, drug, batch_size=100):
        """Invoke Lambda functions in parallel for each batch."""
        batches = chunk(patients, batch_size)
        futures = [self.invoke_lambda(batch, drug) for batch in batches]
        return aggregate_results(futures)
```

### Step Functions Orchestration (`src/aws/step_functions_orchestrator.py`)

```python
class StepFunctionsOrchestrator:
    def start_clinical_trial_simulation(self, trial_params):
        """
        State machine flow:
        1. Generate synthetic cohort
        2. Split into batches
        3. Parallel Lambda invocation (Map state)
        4. Aggregate results
        5. Generate report
        6. Upload to S3
        """
        return self.start_execution(
            state_machine_arn=self.trial_arn,
            input_data=trial_params
        )
```

---

**Next**: [Chapter 7 — Benchmarking & Validation](07-benchmarking-and-validation.md)
