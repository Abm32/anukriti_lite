# Anukriti vs Laboratory-Developed Tests (LDTs)

**Purpose:** Clarify regulatory boundaries between laboratory testing and software interpretation
**Date:** April 12, 2026
**Status:** Regulatory Differentiation Document

---

## Executive Summary

Anukriti is **interpretation software** (post-analytical), not a laboratory test. This document clarifies the regulatory distinction between CLIA-certified laboratory-developed tests (LDTs) and FDA-exempt clinical decision support (CDS) software.

---

## Regulatory Differentiation

| Aspect | CLIA Lab (LDT) | Anukriti Platform (CDS) |
|--------|----------------|-------------------------|
| **Primary Function** | Genotyping (wet lab analysis) | Interpretation (software analysis) |
| **FDA Regulation** | Medical device (LDT Final Rule 2024) | FDA-exempt CDS (21st Century Cures Act) |
| **Input** | Patient biological sample (blood, saliva, tissue) | VCF file (text-based genomic data) |
| **Output** | Genotype calls (e.g., rs4244285 C/T) | Clinical recommendations with CPIC guidelines |
| **Process** | Laboratory procedures (DNA extraction, sequencing, variant calling) | Software algorithms (allele calling, phenotype prediction) |
| **Certification Required** | CLIA/CAP laboratory certification | Software validation and testing |
| **FDA Oversight** | Yes - LDT regulation (21 CFR 809, 21 CFR 820) | No - CDS exemption (21 CFR 520(o)(1)(E)) |
| **Quality Standards** | CLIA quality standards, CAP proficiency testing | ISO 13485 (voluntary), CPIC guidelines |
| **Turnaround Time** | Days to weeks (sample processing) | Minutes (software analysis) |
| **Cost** | $200-$2,000 per test | $0.0001 per analysis (software) |
| **Scalability** | Limited by lab capacity | Unlimited (cloud-based) |

---

## Partnership Model

Anukriti operates in a **complementary partnership** with CLIA-certified laboratories:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Clinical Workflow                             │
└─────────────────────────────────────────────────────────────────┘

1. Patient Sample Collection
   └─> Healthcare provider orders pharmacogenomic test

2. CLIA-Certified Laboratory (FDA-Regulated LDT)
   ├─> DNA extraction from blood/saliva
   ├─> Next-generation sequencing (NGS)
   ├─> Variant calling pipeline
   └─> VCF file generation

3. Anukriti Platform (FDA-Exempt CDS)
   ├─> VCF file import
   ├─> Allele calling (PharmVar/CPIC)
   ├─> Phenotype prediction
   ├─> Drug-gene interaction analysis
   └─> Clinical report generation

4. Healthcare Provider
   └─> Clinical decision-making with Anukriti recommendations
```

---

## FDA LDT Final Rule (April 2024)

### Background
On April 29, 2024, the FDA finalized its rule to actively regulate all laboratory-developed tests (LDTs) as medical devices. Most pharmacogenomic tests available in the U.S. today are non-FDA-approved LDTs.

### Impact on Anukriti
**Anukriti is NOT an LDT** because:
1. ✅ Does not perform laboratory testing on patient samples
2. ✅ Does not conduct DNA extraction, sequencing, or variant calling
3. ✅ Operates post-analytical (after laboratory genotyping is complete)
4. ✅ Interprets existing VCF files from CLIA-certified laboratories

### LDT Regulation Scope
The FDA LDT rule applies to:
- ❌ Laboratory procedures (DNA extraction, PCR, sequencing)
- ❌ Variant calling pipelines (bioinformatics analysis of sequencing data)
- ❌ In-house developed laboratory tests

The FDA LDT rule does NOT apply to:
- ✅ Software that interprets existing laboratory results (like Anukriti)
- ✅ Clinical decision support software meeting 21st Century Cures Act criteria
- ✅ Post-analytical interpretation tools

---

## CLIA Certification Requirements

### What CLIA Regulates
- **Laboratory Operations:** Physical laboratory facilities and procedures
- **Personnel:** Laboratory director, technical supervisor, testing personnel qualifications
- **Quality Control:** Proficiency testing, quality assurance, calibration
- **Analytical Validity:** Accuracy, precision, sensitivity, specificity of laboratory tests

### Anukriti's CLIA Status
**Anukriti does NOT require CLIA certification** because:
1. ✅ No physical laboratory operations
2. ✅ No patient sample handling
3. ✅ No laboratory testing procedures
4. ✅ Software-only interpretation platform

### Partner Laboratory Requirements
Anukriti partners with CLIA-certified laboratories that:
- ✅ Hold valid CLIA certificate (high-complexity testing)
- ✅ Maintain CAP (College of American Pathologists) accreditation
- ✅ Perform pharmacogenomic testing with validated methods
- ✅ Generate VCF files meeting quality standards

---

## Comparison with Commercial PGx Tests

### Traditional PGx Testing Services
Companies like **Invitae**, **GeneDx**, **Color Genomics**:
- Provide **end-to-end service:** Sample collection → Laboratory testing → Report
- Operate **CLIA-certified laboratories**
- Subject to **FDA LDT regulation**
- Charge **$200-$2,000 per patient**

### Anukriti Platform
- Provides **interpretation software only:** VCF file → Analysis → Report
- Partners with **existing CLIA laboratories**
- **FDA-exempt CDS software**
- Costs **$0.0001 per analysis** (software)

### Value Proposition
Anukriti enables:
1. **Laboratory Independence:** Any CLIA lab can use Anukriti for interpretation
2. **Cost Reduction:** Eliminates need for proprietary interpretation software
3. **Scalability:** Cloud-based platform handles unlimited analyses
4. **Transparency:** Open-source algorithms vs. proprietary black boxes
5. **Equity Focus:** Diverse population support (not Euro-centric)

---

## Regulatory Advantages

### For Healthcare Providers
- ✅ Use existing CLIA laboratory relationships
- ✅ No new regulatory approvals needed
- ✅ Faster turnaround (minutes vs. days)
- ✅ Lower cost per patient

### For CLIA Laboratories
- ✅ Add pharmacogenomic interpretation without new infrastructure
- ✅ Maintain CLIA compliance (no additional requirements)
- ✅ Differentiate services with equity-focused PGx
- ✅ Scale interpretation capacity without hiring PharmD staff

### For Anukriti
- ✅ FDA-exempt (no premarket review)
- ✅ Faster innovation cycles
- ✅ Lower regulatory burden
- ✅ Focus on software quality and clinical utility

---

## Quality Assurance

### Laboratory Quality (Partner Responsibility)
- **CLIA Standards:** High-complexity testing requirements
- **CAP Proficiency Testing:** Biannual proficiency surveys
- **Analytical Validation:** Sensitivity, specificity, accuracy, precision
- **Quality Control:** Daily controls, calibration, maintenance

### Software Quality (Anukriti Responsibility)
- **ISO 13485:** Medical device quality management system (planned Month 2)
- **ISO 14971:** Risk management for medical devices (planned Month 2)
- **Software Validation:** Unit tests (95%+ coverage), integration tests, property-based tests
- **Clinical Validation:** Coriell concordance (95%), PharmCAT comparison (90-95%)
- **CPIC Compliance:** Systematic review against CPIC guidelines

---

## Data Flow and Responsibilities

### Laboratory Responsibilities
1. **Sample Processing:** DNA extraction, quality control
2. **Sequencing:** NGS platform operation, run quality metrics
3. **Variant Calling:** Bioinformatics pipeline, VCF generation
4. **Quality Assurance:** CLIA/CAP compliance, proficiency testing
5. **Data Security:** HIPAA compliance, secure VCF transmission

### Anukriti Responsibilities
1. **VCF Import:** Secure file upload, format validation
2. **Allele Calling:** PharmVar/CPIC-based interpretation
3. **Phenotype Prediction:** Diplotype → phenotype translation
4. **Clinical Recommendations:** CPIC guideline-based dosing advice
5. **Report Generation:** PDF reports with evidence citations

### Healthcare Provider Responsibilities
1. **Test Ordering:** Appropriate test selection for patient
2. **Result Interpretation:** Clinical context integration
3. **Clinical Decision:** Final drug selection and dosing
4. **Patient Communication:** Explanation of results and recommendations
5. **Documentation:** Medical record documentation

---

## Liability and Risk Management

### Laboratory Liability
- **Analytical Errors:** Incorrect genotype calls due to laboratory error
- **Sample Mix-ups:** Patient identification errors
- **Quality Failures:** Failed quality control, contamination

### Anukriti Liability
- **Software Errors:** Incorrect allele calling or phenotype prediction
- **Algorithm Bugs:** Software defects causing incorrect recommendations
- **Data Security:** Unauthorized access or data breaches

### Healthcare Provider Liability
- **Clinical Decisions:** Final responsibility for drug selection and dosing
- **Patient Harm:** Adverse events from medication decisions
- **Standard of Care:** Appropriate use of pharmacogenomic information

### Risk Mitigation
- **Laboratory:** CLIA/CAP compliance, proficiency testing, quality controls
- **Anukriti:** 95%+ test coverage, clinical validation, transparent algorithms
- **Provider:** Professional judgment, clinical guidelines, informed consent

---

## Reimbursement Considerations

### Laboratory Testing (CPT Codes)
- **81225:** CYP2C19 (e.g., clopidogrel metabolism)
- **81226:** CYP2D6 (e.g., codeine metabolism)
- **81227:** CYP2C9 (e.g., warfarin metabolism)
- **81355:** VKORC1 (e.g., warfarin sensitivity)
- **81401-81408:** Molecular pathology procedures

**Reimbursement:** $200-$2,000 per test (varies by payer)

### Software Interpretation (No CPT Code Yet)
- **Current Status:** No specific CPT code for PGx interpretation software
- **Billing Model:** Bundled with laboratory test or separate professional fee
- **Advocacy:** Working with AMA CPT Editorial Panel for new code (Month 6)

**Proposed CPT Code:**
- **Description:** "Pharmacogenomic interpretation and clinical decision support"
- **Reimbursement Target:** $50-$100 per analysis
- **Justification:** Reduces adverse drug reactions, improves outcomes, lowers healthcare costs

---

## Competitive Landscape

### Integrated PGx Services (Lab + Interpretation)
- **Invitae:** $250-$2,000 per test, CLIA lab + proprietary software
- **GeneDx:** $300-$1,500 per test, CLIA lab + proprietary software
- **Color Genomics:** $250-$500 per test, CLIA lab + proprietary software

### Software-Only Interpretation
- **PharmCAT:** Free, open-source, limited clinical features
- **Anukriti:** $0.0001 per analysis, equity-focused, comprehensive clinical features

### Anukriti Differentiation
1. **Cost:** 10,000x cheaper than integrated services
2. **Equity:** Diverse population support (not Euro-centric)
3. **Transparency:** Open-source algorithms (not proprietary black boxes)
4. **Scalability:** Cloud-based (unlimited capacity)
5. **Innovation:** Rapid feature updates (not constrained by FDA approval cycles)

---

## Future Regulatory Considerations

### Potential FDA Oversight Scenarios
1. **Maintain CDS Exemption:** Continue as FDA-exempt software (most likely)
2. **Voluntary FDA Submission:** Seek FDA clearance for marketing advantage
3. **Breakthrough Device:** Apply for expedited review pathway (Month 6)
4. **International Expansion:** CE Mark (EU), MHRA (UK), Health Canada (Months 9-12)

### Monitoring FDA Guidance
- **CDS Guidance Updates:** Monitor FDA guidance revisions
- **LDT Rule Implementation:** Track FDA enforcement priorities
- **Software as Medical Device (SaMD):** Stay informed on SaMD framework evolution

---

## Conclusion

Anukriti operates as **FDA-exempt clinical decision support software**, not a laboratory-developed test. This regulatory positioning enables:

1. ✅ **Faster Innovation:** No FDA premarket review delays
2. ✅ **Lower Costs:** Software-only model vs. laboratory infrastructure
3. ✅ **Greater Access:** Cloud-based platform available to any CLIA lab
4. ✅ **Equity Focus:** Diverse population support without regulatory constraints
5. ✅ **Transparency:** Open-source algorithms vs. proprietary black boxes

By partnering with CLIA-certified laboratories, Anukriti provides comprehensive pharmacogenomic interpretation while maintaining clear regulatory boundaries and minimizing compliance burden.

---

## References

1. FDA (2024). "Laboratory Developed Tests: Final Rule." Federal Register 89 FR 37286
2. FDA (2022). "Clinical Decision Support Software: Guidance for Industry." https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software
3. CMS (2024). "Clinical Laboratory Improvement Amendments (CLIA)." https://www.cms.gov/regulations-and-guidance/legislation/clia
4. CAP (2024). "Laboratory Accreditation Program." https://www.cap.org/laboratory-improvement/accreditation

---

**Document Version:** 1.0
**Date:** April 12, 2026
**Next Review:** July 12, 2026 (Quarterly)
