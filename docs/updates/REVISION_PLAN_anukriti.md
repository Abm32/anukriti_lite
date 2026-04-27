# Revision Plan: Anukriti Conference Paper (Post First-Level Evaluation)

## Clarification: “Add all authors”

**“Authors” = people who wrote *this* paper** (you and any co-authors). It does **not** mean the authors of the papers you cite; those stay in the **References** section only.

- If you are the **sole contributor**, listing only your name (Abhimanyu R. B.) is correct. The reviewer may have used a generic checklist item.
- If you later add **co-authors** (e.g. advisors, collaborators), add them in the same `\author{...}` block on the first page. No need to add cited papers’ authors as paper authors.

---

## Summary of Reviewer Feedback

| # | Feedback Point | Category | Priority |
|---|----------------|----------|----------|
| 1 | Add all author names on first page | Formatting | High |
| 2 | Detailed comparison with existing safety screening models; clearer benchmark (accuracy, speed, metrics) | Content | High |
| 3 | No quantitative benchmark (sensitivity/specificity, F1 score) | Content | High |
| 4 | Stronger experimental validation required | Content | High |
| 5 | More discussion on real-world deployment (pharma pipelines, healthcare systems) | Content | Medium |
| 6 | More explicit discussion of limitations (edge cases, ambiguous data) | Content | Medium |
| 7 | Expand future work (biomarkers, scalability, ethical concerns—bias, transparency) | Content | Medium |
| 8 | Clarify scalability (larger/diverse datasets, computational resources) | Content | Medium |
| 9 | Include references to recent works (2023–2025) in AI drug screening & pharmacogenomics | References | High |
| 10 | Irregular spacing | Formatting | Low |
| 11 | Paper clearly written and logically structured? (No) | Structure | High |
| 12 | Figures, tables, and references clearly formatted and legible? (No) | Formatting | High |

---

## Planned Changes (Mapping to anukriti.tex)

### 1. Author names on first page

- **Current:** Single author block (Abhimanyu R. B.).
- **Action:** “Authors” = writers of this paper only (not reference authors). If you are the sole contributor, the first page is correct with just your name. Optional: remove the commented “Second Author” placeholder in `anukriti.tex` to avoid confusion. When you have co-authors, add them in the same `\author{...}` block.

### 2. Quantitative benchmark comparison

- **Location:** Section IV (Results and Discussion).
- **Action:**
  - Add a new **Table: Quantitative metrics** with Sensitivity, Specificity, F1 score, Accuracy (and optionally Precision/Recall) for the pilot study (Warfarin–CYP2C9 and Codeine–CYP2D6 vs. CPIC ground truth).
  - Add a short subsection **“Quantitative Benchmark Comparison”** that reports these metrics and compares with “no AI” or rule-based baseline if applicable (or state that this is pilot and no direct numerical benchmark exists in literature for the same task).
  - Reframe Figure 3 (validation) to reference this table and state that future work will include larger cohorts for statistical significance.

### 3. Stronger experimental validation

- **Location:** Results (Section IV) and Methodology (Section III).
- **Action:**
  - Add a sentence or short paragraph on validation protocol: how CPIC was used as ground truth, how many patient profiles per drug, and that predictions were compared category-wise (Standard / High risk).
  - Optionally add leave-one-out or cross-validation phrasing if applicable (e.g., “per-patient comparison with CPIC guidelines”).
  - In Conclusion or Results, explicitly state that “stronger experimental validation on larger cohorts and additional drug–gene pairs is planned.”

### 4. Real-world deployment

- **Location:** New subsection under Results and Discussion or before Conclusion.
- **Action:** Add subsection **“Real-World Deployment Considerations”** covering:
  - Feasibility of integrating Anukriti into existing pharmaceutical pipelines (e.g., pre-clinical stage gate).
  - Compatibility with healthcare systems (EHR, clinical decision support).
  - Regulatory and validation requirements (e.g., FDA decision support, IVD considerations).
  - 1–2 short paragraphs.

### 5. Explicit limitations

- **Location:** New subsection before or within Conclusion.
- **Action:** Add subsection **“Limitations”** covering:
  - Edge cases: rare alleles, copy-number variants, gene–gene interactions not in the current panel.
  - Ambiguous or missing data: low-quality VCF, novel drugs with no ChEMBL analogues.
  - Dependence on LLM reasoning (hallucination risk) and RAG coverage.
  - Small pilot scale (60 patients, 2 drug–gene pairs).

### 6. Future work and ethical concerns

- **Location:** Expand “Conclusion” or add “Future Work” subsection.
- **Action:**
  - Extend future work: CYP3A4, HLA (Chromosome 6), other biomarkers; scalability to larger and more diverse datasets.
  - Add a short **“Ethical Considerations”** paragraph: bias in training data (population diversity), transparency and explainability of AI decisions, need for clinician-in-the-loop.

### 7. Scalability and computational resources

- **Location:** Methodology (Implementation Details) or new “Scalability” paragraph in Discussion.
- **Action:** Add explicit statements on:
  - How the framework scales with number of patients and drugs (e.g., linear in patients for current design).
  - Computational requirements: cloud/API usage, approximate cost, and what would be needed for “thousands” of patients or full pharmacogene panels.

### 8. Recent references (2023–2025)

- **Location:** Related Work + bibliography.
- **Action:** Add 4–6 references from 2023–2025 on:
  - AI/ML in drug screening and safety.
  - Pharmacogenomics and precision medicine.
  - LLMs or agentic systems in biomedical applications.
  - Cite them in Related Work and optionally in Introduction/Discussion.

### 9. Irregular spacing

- **Location:** Whole document.
- **Action:**
  - Normalize space around section titles, tables, figures (e.g., consistent use of `\vspace` or no double newlines).
  - Fix table column alignment and `\arraystretch` if needed.
  - Ensure no stray spaces or inconsistent line breaks in author block, abstract, and captions.

### 10. Clarity and logical structure (Q4: Is the paper clearly written and logically structured?)

- **Actions taken:**
  - Added a **roadmap paragraph** at the end of the Introduction (“The remainder of the paper is organized as follows. Section II reviews... Section III describes... Section IV presents... Section V concludes...”) so readers know what comes next.
  - Added **transition sentences** between sections (Related Work → Methodology; Methodology opening sentence listing the three stages; Results opening sentence listing what the section covers).
  - **Conclusion** now opens with a one-sentence summary (“We have presented Anukriti...”) before the main claims.
  - In-text references to figures and tables now use consistent LaTeX-style macros for figures and tables and explicitly tie captions to the narrative.

### 11. Figures, tables, and references (Q9: Clearly formatted and legible?)

- **Actions taken:**
  - **Figure captions:** All figures now have numbered, descriptive captions (for example, “Fig. 1 ...”, “Fig. 2 ...”) that explain what the figure shows and key terms (e.g., phenotype names, axis meaning).
  - **Table captions:** Tables I and II have clear captions above the tables with a short explanation in parentheses.
  - **Table layout:** Consistent `\arraystretch`, `@{}` for column padding, and `\bottomrule`; Table II header split across two lines for legibility.
  - **Fig. 4 (performance):** Y-axis labeled “Time (seconds, log scale)”, explicit `ytick` values (1, 10, ..., 10^6) for readable log scale; x-axis label “Mol. Dynamics” to avoid overflow.
  - **References:** Bibliography standardized (abbreviated journal names, consistent page and volume formatting); recent/preprint entries clearly marked as preprints or “to appear”.

---

## Implementation Order

1. Fix author block and spacing (quick).
2. Add quantitative metrics table and subsection (high impact).
3. Add Limitations and expand Future Work + Ethics (high impact).
4. Add Real-World Deployment and Scalability (medium impact).
5. Add recent references and cite in text (high impact).
6. Strengthen validation wording in Results and Methodology (medium impact).

After implementation, run a final pass for spacing and typo check.

---

## Paper vs. Project Progress (as of current codebase)

The paper was written last month; the codebase has evolved. Here is a concise alignment check so the paper stays accurate and you can optionally mention newer scope in Future Work.

| Paper claim | Current project state | Suggestion |
|-------------|-----------------------|------------|
| **Chromosomes 22 and 10**, “Big 3” (CYP2D6, CYP2C19, CYP2C9) | Code also has CYP3A4 (chr7), UGT1A1 (chr2), SLCO1B1 (chr12), VKORC1 (chr16). VCF processor and `CYP_GENE_LOCATIONS` include these. | Keep paper focused on the **reported experiment** (chr22, chr10, Big 3). In Future Work you already mention CYP3A4 and HLA; you could add “SLCO1B1 (statins), VKORC1 (warfarin)” as extensions if you want. |
| **60 synthetic patient profiles** from 1000 Genomes | No hardcoded “60” in scripts. `generate_validation_results.py` uses **synthetic text profiles** (e.g. “CYP2D6 Poor Metabolizer”) for a few drug/phenotype cases. VCF pipeline can run on any number of 1000 Genomes samples. | If “60” came from a specific run (e.g. 60 VCF samples), keep it as reported. If the number was illustrative, consider adding a short clarification: e.g. “pilot cohort of 60 synthetic profiles (or N samples from 1000 Genomes VCFs).” |
| **Warfarin–CYP2C9, Codeine–CYP2D6** | Implemented. Plus **Warfarin** uses CYP2C9 **and** VKORC1 (`warfarin_caller.py`, `warfarin_response.json`). **Statins** → SLCO1B1; **Clopidogrel** → CYP2C19 (`pgx_triggers.py`). | Paper’s two drug–gene pairs are correct for the pilot. Optionally mention in Future Work that the system now supports Warfarin (CYP2C9+VKORC1) and statin (SLCO1B1) pipelines. |
| **RAG from ChEMBL, Pinecone, top-k=3** | Matches: `config.PINECONE_TOP_K=3`, ChEMBL ingestion, `vector_search.py`, `chembl_processor.py`. Optional **Bedrock** path (Claude, Titan) exists. | No change needed; paper correctly describes the primary (Gemini + Pinecone) pipeline. |
| **Gemini 2.5 Flash** | `config.GEMINI_MODEL = "gemini-2.5-flash"`; `agent_engine.py` uses LangChain + ChatGoogleGenerativeAI. | Aligned. |
| **RDKit Morgan 2048, radius 2** | `input_processor.py`: `FINGERPRINT_BITS=2048`, `FINGERPRINT_RADIUS=2`, caching. | Aligned. |
| **Validation** | `generate_validation_results.py` compares LLM risk level to CPIC expectations for Codeine, Tramadol, Metoprolol (CYP2D6); no Warfarin in that script. CPIC-based callers (`warfarin_caller`, `slco1b1_caller`, allele callers) provide deterministic phenotype/response. | Paper’s “CPIC as ground truth” and “qualitative match” are consistent. For stronger validation, you could run the script on VCF-derived profiles (chr22+chr10) for a subset of 1000 Genomes samples and report metrics in a future version. |

**Summary:** The paper accurately describes the core architecture (RDKit, Pinecone, ChEMBL, Gemini, chr22/chr10, Big 3, two drug–gene pairs, 60 profiles). The project has since added more genes and drug–gene triggers (Warfarin full pipeline, statins, Clopidogrel) and optional Bedrock; you can keep the paper as-is for the pilot and reflect the extended scope in Future Work or a short “Current implementation” sentence if the conference allows.
