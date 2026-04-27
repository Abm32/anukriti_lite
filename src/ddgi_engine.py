"""
Drug-Drug-Gene Interaction (DDGI) Engine.

Detects situations where a patient's pharmacogenomic profile (gene variant)
amplifies or modifies a standard drug-drug interaction (DDI), creating
compounded risk beyond what either factor alone would predict.

This is a critical gap in current pharmacovigilance: DDI databases model
interactions assuming standard metabolizer status, but PGx variation can
dramatically change the risk profile.

Key DDGI scenarios implemented:
1. CYP2D6 PM + codeine + fluoxetine → opioid toxicity (inhibitor + PM = triple risk)
2. CYP2C19 PM + clopidogrel + omeprazole → antiplatelet failure
3. CYP2B6 PM + efavirenz + rifampin → altered ARV exposure
4. NAT2 SA + isoniazid + rifampin → hepatotoxicity risk
5. TPMT PM/IM + azathioprine + allopurinol → severe myelosuppression
6. CYP3A5 Poor + tacrolimus + azole antifungal → calcineurin inhibitor toxicity
7. SLCO1B1 Poor + statin + gemfibrozil → myopathy risk

Design principles:
- Evidence-based: each DDGI references published pharmacology
- Equity-aware: flags when variant frequency creates disproportionate risk in specific populations
- Deterministic: no LLM for risk classification; LLM is optional for explanation
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# DDGI knowledge base
# Each entry defines a three-way interaction: gene_variant + drug1 + drug2
# ---------------------------------------------------------------------------

DDGI_KNOWLEDGE_BASE: List[Dict[str, Any]] = [
    {
        "id": "CYP2D6_PM_codeine_fluoxetine",
        "gene": "CYP2D6",
        "triggering_phenotypes": ["Poor Metabolizer", "poor_metabolizer"],
        "drug_1": "codeine",
        "drug_2": "fluoxetine",
        "mechanism": (
            "Codeine requires CYP2D6 for conversion to active morphine. "
            "CYP2D6 Poor Metabolizers have reduced baseline conversion. "
            "Fluoxetine is a potent CYP2D6 inhibitor that further blocks this pathway. "
            "Combined effect: near-zero codeine activation → analgesic failure + "
            "accumulation of codeine (CNS depression risk at high doses)."
        ),
        "risk_level": "HIGH",
        "clinical_consequence": "Analgesic failure (insufficient morphine) and potential codeine accumulation with CNS effects",
        "recommendation": (
            "Avoid codeine in CYP2D6 Poor Metabolizers. If opioid analgesia required, "
            "use a non-CYP2D6 substrate (e.g., morphine, hydromorphone). "
            "If fluoxetine cannot be discontinued, consider alternative antidepressant "
            "without CYP2D6 inhibitory activity."
        ),
        "cpic_references": [
            "CPIC Codeine guideline (PMID 29460098)",
            "CPIC Antidepressants guideline",
        ],
        "equity_note": "CYP2D6 PM rate: AFR ~5%, EUR ~7%, EAS ~1%. Risk pattern consistent across populations.",
    },
    {
        "id": "CYP2D6_UM_codeine_fluoxetine",
        "gene": "CYP2D6",
        "triggering_phenotypes": ["Ultra-Rapid Metabolizer", "ultra_rapid_metabolizer"],
        "drug_1": "codeine",
        "drug_2": "fluoxetine",
        "mechanism": (
            "CYP2D6 Ultra-Rapid Metabolizers convert codeine to morphine faster than normal. "
            "Fluoxetine inhibition partially counteracts this, potentially normalizing exposure — "
            "but the interaction is unpredictable and individual response highly variable."
        ),
        "risk_level": "MODERATE",
        "clinical_consequence": "Variable morphine exposure; difficult to predict safe codeine dose",
        "recommendation": "Avoid codeine in CYP2D6 Ultra-Rapid Metabolizers regardless of concurrent CYP2D6 inhibitors. Use alternative opioids.",
        "cpic_references": ["CPIC Codeine guideline (PMID 29460098)"],
        "equity_note": "CYP2D6 UM rate: North African/Ethiopian populations up to 30%. Major equity issue for codeine use in these populations.",
    },
    {
        "id": "CYP2C19_PM_clopidogrel_omeprazole",
        "gene": "CYP2C19",
        "triggering_phenotypes": [
            "Poor Metabolizer",
            "poor_metabolizer",
            "Intermediate Metabolizer",
            "intermediate_metabolizer",
        ],
        "drug_1": "clopidogrel",
        "drug_2": "omeprazole",
        "mechanism": (
            "Clopidogrel is a prodrug activated by CYP2C19 to its active thiol metabolite. "
            "CYP2C19 Poor/Intermediate Metabolizers have reduced activation baseline. "
            "Omeprazole (and esomeprazole) are CYP2C19 inhibitors that further reduce "
            "activation → inadequate antiplatelet effect → increased risk of MACE "
            "(major adverse cardiovascular events), especially post-PCI stenting."
        ),
        "risk_level": "HIGH",
        "clinical_consequence": "Inadequate antiplatelet effect; increased risk of stent thrombosis and cardiovascular events",
        "recommendation": (
            "For CYP2C19 PM/IM patients requiring antiplatelet therapy: "
            "use prasugrel or ticagrelor (not CYP2C19 substrates). "
            "If PPI required for GI protection, use pantoprazole (weakest CYP2C19 inhibitor) "
            "rather than omeprazole or esomeprazole."
        ),
        "cpic_references": ["CPIC Clopidogrel guideline (PMID 28198005)"],
        "equity_note": "CYP2C19 PM rate: EAS ~15% (2× higher than EUR ~2-3%). Post-PCI outcomes gap in East Asian patients is well-documented.",
    },
    {
        "id": "CYP2B6_PM_efavirenz_rifampin",
        "gene": "CYP2B6",
        "triggering_phenotypes": [
            "Poor Metabolizer",
            "poor_metabolizer",
            "Slow Metabolizer",
        ],
        "drug_1": "efavirenz",
        "drug_2": "rifampin",
        "mechanism": (
            "Efavirenz is primarily metabolized by CYP2B6. CYP2B6 Poor Metabolizers have "
            "substantially elevated efavirenz plasma levels. "
            "Rifampin (rifampicin) is a potent CYP2B6/3A4 inducer used in TB treatment — "
            "it reduces efavirenz exposure. The interaction in PMs: TB coinfection is treated "
            "with rifampin, but the CYP2B6 induction partially compensates PM's elevated levels. "
            "Dose adjustments are complex and population-specific."
        ),
        "risk_level": "MODERATE",
        "clinical_consequence": "Unpredictable efavirenz plasma levels; increased CNS toxicity risk in PMs or virologic failure if inducer effect dominates",
        "recommendation": (
            "Monitor efavirenz plasma levels in CYP2B6 PM patients on rifampin-containing "
            "TB regimens. Consider WHO-endorsed efavirenz dose reduction for CYP2B6 *6/*6 "
            "genotype (400mg vs standard 600mg) where TDM is unavailable."
        ),
        "cpic_references": [
            "CPIC Efavirenz guideline (forthcoming)",
            "WHO HIV/TB treatment guidelines",
        ],
        "equity_note": "CYP2B6 *6/*6: ~25% of sub-Saharan African patients. This DDGI is a critical equity issue in HIV+TB coinfection treatment.",
    },
    {
        "id": "NAT2_SA_isoniazid_rifampin",
        "gene": "NAT2",
        "triggering_phenotypes": ["Slow Acetylator"],
        "drug_1": "isoniazid",
        "drug_2": "rifampin",
        "mechanism": (
            "Isoniazid (INH) is acetylated by NAT2. Slow Acetylators accumulate higher INH "
            "plasma levels, increasing risk of peripheral neuropathy and hepatotoxicity. "
            "Rifampin (in standard 4-drug TB regimen) induces CYP enzymes involved in INH "
            "hydrolysis to toxic hydrazine metabolites. "
            "Combined: SA status + rifampin co-administration = synergistic hepatotoxicity risk."
        ),
        "risk_level": "HIGH",
        "clinical_consequence": "Elevated risk of INH-induced hepatotoxicity (drug-induced liver injury, DILI) and peripheral neuropathy",
        "recommendation": (
            "For NAT2 Slow Acetylators on standard TB therapy (INH + rifampin): "
            "prophylactic pyridoxine (B6) 25-50mg/day is strongly recommended to prevent neuropathy. "
            "Consider INH dose reduction (5mg/kg → 4mg/kg) in resource-appropriate settings. "
            "Monitor LFTs monthly for first 3 months."
        ),
        "cpic_references": ["CPIC Isoniazid guideline (PMID 33620103)"],
        "equity_note": "NAT2 slow acetylator: ~90% Middle Eastern, ~60% European. Standard TB therapy disproportionately affects slow acetylator populations.",
    },
    {
        "id": "TPMT_PM_azathioprine_allopurinol",
        "gene": "TPMT",
        "triggering_phenotypes": ["Poor Metabolizer", "poor_metabolizer"],
        "drug_1": "azathioprine",
        "drug_2": "allopurinol",
        "mechanism": (
            "Azathioprine is converted to 6-mercaptopurine (6-MP), then to active 6-TGN "
            "via TPMT. TPMT Poor Metabolizers accumulate excessive 6-TGN → severe myelosuppression. "
            "Allopurinol inhibits xanthine oxidase, diverting more 6-MP toward 6-TGN synthesis. "
            "Combined: TPMT PM + allopurinol = dramatically elevated 6-TGN + life-threatening "
            "bone marrow suppression risk."
        ),
        "risk_level": "CRITICAL",
        "clinical_consequence": "Life-threatening myelosuppression; bone marrow failure; sepsis risk",
        "recommendation": (
            "CONTRAINDICATED combination in TPMT Poor Metabolizers. "
            "If allopurinol is required (e.g., gout with inflammatory bowel disease on azathioprine), "
            "reduce azathioprine dose by 75% and monitor CBC weekly for 6 weeks. "
            "In TPMT PM: use alternative immunosuppressant or reduce azathioprine to 10% of standard dose."
        ),
        "cpic_references": ["CPIC Thiopurines guideline (PMID 22009456)"],
        "equity_note": "TPMT PM rate is similar across ancestries (~0.3%). Allopurinol use for gout is common; this DDGI is underrecognized.",
    },
    {
        "id": "CYP3A5_poor_tacrolimus_azole",
        "gene": "CYP3A5",
        "triggering_phenotypes": ["Poor Metabolizer", "poor_metabolizer"],
        "drug_1": "tacrolimus",
        "drug_2": "fluconazole",
        "mechanism": (
            "Tacrolimus has a narrow therapeutic index and is metabolized by CYP3A4/3A5. "
            "CYP3A5 Poor Metabolizers (*3/*3) already have reduced metabolism baseline — "
            "they typically require lower doses to achieve target trough levels. "
            "Azole antifungals (fluconazole, voriconazole, itraconazole) are potent CYP3A4 "
            "inhibitors. Combined: CYP3A5 PM + azole = marked tacrolimus accumulation → "
            "nephrotoxicity, neurotoxicity, increased rejection paradox."
        ),
        "risk_level": "HIGH",
        "clinical_consequence": "Tacrolimus toxicity: nephrotoxicity, neurotoxicity, increased infection risk from over-immunosuppression",
        "recommendation": (
            "Reduce tacrolimus dose by 50-75% when initiating azole antifungal in CYP3A5 *3/*3 patients. "
            "Monitor tacrolimus trough levels daily for first week, then 2-3x/week until stable. "
            "Note: CYP3A5 expressors (*1 carriers) require HIGHER tacrolimus doses baseline, "
            "but azole interaction risk applies to both genotype groups."
        ),
        "cpic_references": ["CPIC Tacrolimus guideline (PMID 25801146)"],
        "equity_note": "CYP3A5 expressors (*1 carriers): ~75% AFR vs ~10% EUR. African transplant recipients systematically require different tacrolimus dosing — a major unaddressed disparity.",
    },
    {
        "id": "SLCO1B1_poor_statin_gemfibrozil",
        "gene": "SLCO1B1",
        "triggering_phenotypes": ["Poor Function", "poor_function"],
        "drug_1": "simvastatin",
        "drug_2": "gemfibrozil",
        "mechanism": (
            "SLCO1B1 rs4149056 (CC genotype) reduces hepatic uptake of statins, "
            "increasing systemic statin exposure and myopathy risk. "
            "Gemfibrozil inhibits SLCO1B1 and CYP2C8-mediated statin metabolism. "
            "Combined: SLCO1B1 Poor Function + gemfibrozil = markedly elevated statin "
            "plasma AUC → severe myopathy, rhabdomyolysis risk."
        ),
        "risk_level": "HIGH",
        "clinical_consequence": "Severe myopathy or rhabdomyolysis with acute kidney injury",
        "recommendation": (
            "Avoid gemfibrozil in patients on simvastatin or lovastatin, regardless of genotype. "
            "In SLCO1B1 Poor Function (CC) patients: if fibrate is required, use fenofibrate "
            "(weaker OATP1B1 inhibitor). Consider switching to rosuvastatin or pravastatin "
            "(less susceptible to OATP1B1 transport variation)."
        ),
        "cpic_references": ["CPIC Simvastatin guideline (PMID 22617227)"],
        "equity_note": "SLCO1B1 *5 (CC) frequency: EUR ~15-20%, AFR ~2-5%, EAS ~10%. Statin myopathy disparities are partly explained by this genotype-drug interaction.",
    },
    {
        "id": "G6PD_deficient_primaquine_dapsone",
        "gene": "G6PD",
        "triggering_phenotypes": [
            "Deficient (Class III)",
            "Severely Deficient (Class II)",
        ],
        "drug_1": "primaquine",
        "drug_2": "dapsone",
        "mechanism": (
            "Both primaquine and dapsone are strong oxidant drugs that generate "
            "reactive oxygen species metabolised via the G6PD-dependent pentose "
            "phosphate pathway. In G6PD-deficient patients the erythrocyte cannot "
            "regenerate NADPH, leading to oxidative damage to haemoglobin and "
            "red-cell membranes. Co-administration of two oxidant stressors "
            "causes synergistic, potentially life-threatening haemolytic anaemia."
        ),
        "risk_level": "CRITICAL",
        "clinical_consequence": (
            "Severe acute haemolytic anaemia, haemoglobinuria, acute kidney "
            "injury from haemoglobin casts, cardiovascular collapse in severe cases"
        ),
        "recommendation": (
            "CONTRAINDICATED combination in G6PD-deficient patients. "
            "For malaria radical cure, avoid primaquine; no safe oxidant "
            "alternative exists for Class II deficiency. "
            "For PCP prophylaxis, replace dapsone with atovaquone or "
            "pentamidine inhalation. Never combine two oxidant drugs."
        ),
        "cpic_references": [
            "CPIC G6PD guideline (PMID 24787449)",
            "WHO G6PD testing guideline 2018",
        ],
        "equity_note": (
            "G6PD deficiency: >25% in malaria-endemic sub-Saharan Africa, "
            "5-20% Mediterranean/Middle East, 5-15% Southeast Asia. "
            "Primaquine use for P. vivax radical cure disproportionately "
            "endangers these populations."
        ),
    },
    {
        "id": "G6PD_deficient_rasburicase_dapsone",
        "gene": "G6PD",
        "triggering_phenotypes": [
            "Deficient (Class III)",
            "Severely Deficient (Class II)",
        ],
        "drug_1": "rasburicase",
        "drug_2": "dapsone",
        "mechanism": (
            "Rasburicase generates hydrogen peroxide as a metabolic byproduct "
            "during uric acid oxidation. Dapsone is a direct oxidant stressor. "
            "In G6PD-deficient patients, both drugs independently deplete the "
            "already-impaired NADPH pool. Combined exposure results in "
            "catastrophic oxidative haemolysis."
        ),
        "risk_level": "CRITICAL",
        "clinical_consequence": (
            "Life-threatening haemolytic anaemia, methemoglobinaemia, "
            "acute renal failure from massive haemoglobin release"
        ),
        "recommendation": (
            "CONTRAINDICATED combination. Both drugs are individually "
            "contraindicated in G6PD deficiency. Use allopurinol or febuxostat "
            "for tumour lysis syndrome; use atovaquone or pentamidine for PCP "
            "prophylaxis."
        ),
        "cpic_references": [
            "CPIC G6PD guideline (PMID 24787449)",
            "Rasburicase FDA label — Black Box Warning",
        ],
        "equity_note": (
            "G6PD testing before rasburicase is FDA-mandated (Black Box Warning) "
            "but frequently omitted in emergency oncology settings, "
            "disproportionately affecting African-ancestry patients."
        ),
    },
]

# Build fast lookup indexes
_GENE_PHENOTYPE_INDEX: Dict[str, List[Dict]] = {}
_DRUG_PAIR_INDEX: Dict[tuple, List[Dict]] = {}

for _entry in DDGI_KNOWLEDGE_BASE:
    _gene = _entry["gene"]
    if _gene not in _GENE_PHENOTYPE_INDEX:
        _GENE_PHENOTYPE_INDEX[_gene] = []
    _GENE_PHENOTYPE_INDEX[_gene].append(_entry)

    # Index both orderings of the drug pair
    for _d1, _d2 in [
        (_entry["drug_1"], _entry["drug_2"]),
        (_entry["drug_2"], _entry["drug_1"]),
    ]:
        key = (_d1.lower(), _d2.lower())
        if key not in _DRUG_PAIR_INDEX:
            _DRUG_PAIR_INDEX[key] = []
        _DRUG_PAIR_INDEX[key].append(_entry)


def find_ddgi(
    gene_phenotypes: Dict[str, str],
    drugs: List[str],
    min_risk_level: str = "MODERATE",
) -> List[Dict[str, Any]]:
    """
    Identify DDGI interactions given a patient's PGx profile and concurrent drugs.

    Args:
        gene_phenotypes: Dict mapping gene → phenotype string.
            e.g. {"CYP2D6": "Poor Metabolizer", "CYP2C19": "Normal Metabolizer"}
        drugs: List of drug names (lowercase) the patient is taking.
        min_risk_level: Minimum risk level to include ("LOW", "MODERATE", "HIGH", "CRITICAL").

    Returns:
        List of DDGI finding dicts, each with interaction details and recommendation.
    """
    _RISK_RANK = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}
    min_rank = _RISK_RANK.get(min_risk_level.upper(), 1)

    drugs_lower: Set[str] = {d.lower() for d in drugs}
    findings: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    for gene, phenotype in gene_phenotypes.items():
        candidates = _GENE_PHENOTYPE_INDEX.get(gene, [])
        for entry in candidates:
            if entry["id"] in seen_ids:
                continue
            # Check phenotype match
            phen_match = any(
                p.lower() in phenotype.lower() or phenotype.lower() in p.lower()
                for p in entry["triggering_phenotypes"]
            )
            if not phen_match:
                continue
            # Check both drugs are present
            if entry["drug_1"].lower() not in drugs_lower:
                continue
            if entry["drug_2"].lower() not in drugs_lower:
                continue
            # Check risk level
            entry_rank = _RISK_RANK.get(entry["risk_level"].upper(), 0)
            if entry_rank < min_rank:
                continue

            seen_ids.add(entry["id"])
            findings.append(
                {
                    "ddgi_id": entry["id"],
                    "gene": entry["gene"],
                    "patient_phenotype": phenotype,
                    "drug_1": entry["drug_1"],
                    "drug_2": entry["drug_2"],
                    "risk_level": entry["risk_level"],
                    "mechanism": entry["mechanism"],
                    "clinical_consequence": entry["clinical_consequence"],
                    "recommendation": entry["recommendation"],
                    "cpic_references": entry["cpic_references"],
                    "equity_note": entry.get("equity_note", ""),
                }
            )

    # Sort by risk level descending
    findings.sort(key=lambda x: _RISK_RANK.get(x["risk_level"], 0), reverse=True)
    return findings


def summarize_ddgi(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a structured summary from a list of DDGI findings."""
    if not findings:
        return {
            "total_interactions": 0,
            "critical_count": 0,
            "high_count": 0,
            "moderate_count": 0,
            "overall_alert_level": "NONE",
            "priority_action": "No drug-drug-gene interactions detected in the analyzed drug combination.",
        }

    risk_counts: Dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MODERATE": 0, "LOW": 0}
    for f in findings:
        risk_counts[f.get("risk_level", "LOW")] = (
            risk_counts.get(f.get("risk_level", "LOW"), 0) + 1
        )

    if risk_counts["CRITICAL"] > 0:
        alert_level = "CRITICAL"
        priority = findings[0]["recommendation"]
    elif risk_counts["HIGH"] > 0:
        alert_level = "HIGH"
        priority = findings[0]["recommendation"]
    elif risk_counts["MODERATE"] > 0:
        alert_level = "MODERATE"
        priority = findings[0]["recommendation"]
    else:
        alert_level = "LOW"
        priority = "Review flagged interactions with prescribing physician."

    return {
        "total_interactions": len(findings),
        "critical_count": risk_counts["CRITICAL"],
        "high_count": risk_counts["HIGH"],
        "moderate_count": risk_counts["MODERATE"],
        "overall_alert_level": alert_level,
        "priority_action": priority,
        "equity_notes": [
            f.get("equity_note") for f in findings if f.get("equity_note")
        ],
    }
