"""
Agent Engine Module

Handles LLM-based pharmacogenomics simulation using LangChain.
This is the "Brain" that simulates the patient.
"""

import logging
import os
import re
from typing import List, Optional

from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import config
from src.exceptions import ConfigurationError, LLMError

logger = logging.getLogger(__name__)

# Hard timeout for all LLM calls (seconds). Shared with llm_bedrock.py via env var.
_LLM_TIMEOUT: int = int(os.getenv("LLM_CALL_TIMEOUT_SECONDS", "60"))

_llm = None
_claude_llm = None


def _get_llm():
    """Lazy initialization of the LLM to ensure API key is loaded."""
    global _llm
    if _llm is None:
        if not config.GOOGLE_API_KEY:
            raise ConfigurationError(
                "GOOGLE_API_KEY or GEMINI_API_KEY not set. "
                "Please add it to your environment or .env file.",
                missing_keys=["GOOGLE_API_KEY", "GEMINI_API_KEY"],
            )

        logger.info(
            f"Initializing LLM: model={config.GEMINI_MODEL}, "
            f"temperature={config.GEMINI_TEMPERATURE}"
        )

        _llm = ChatGoogleGenerativeAI(
            model=config.GEMINI_MODEL,
            temperature=config.GEMINI_TEMPERATURE,
            google_api_key=config.GOOGLE_API_KEY,
            request_timeout=_LLM_TIMEOUT,
        )
    return _llm


def _get_claude_llm():
    """Lazy initialization of Anthropic Claude LLM (direct API, not Bedrock)."""
    global _claude_llm
    if _claude_llm is None:
        import os

        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_key:
            raise ConfigurationError(
                "ANTHROPIC_API_KEY not set. Add it to your .env file.",
                missing_keys=["ANTHROPIC_API_KEY"],
            )

        claude_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        logger.info(f"Initializing Claude LLM: model={claude_model}")

        from langchain_anthropic import ChatAnthropic

        _claude_llm = ChatAnthropic(
            model=claude_model,
            temperature=0.1,
            anthropic_api_key=anthropic_key,
            max_tokens=2048,
            timeout=_LLM_TIMEOUT,
        )
    return _claude_llm


def run_simulation(
    drug_name: str,
    similar_drugs: List[str],
    patient_profile: str,
    drug_smiles: str = None,
    backend: str = "gemini",
) -> str:
    """
    Run pharmacogenomics simulation using LLM to predict drug effects.

    Args:
        drug_name: Name of the drug being tested
        similar_drugs: List of formatted drug strings from vector search
        patient_profile: String containing patient information (ID, Age, Genetics, Conditions)

    Returns:
        String containing the AI-generated pharmacogenomics prediction

    Raises:
        ValueError: If Gemini API key is not set
    """
    template = """
    ROLE: You are an advanced Pharmacogenomics AI following CPIC (Clinical Pharmacogenetics Implementation Consortium) guidelines.

    TASK: Predict the physiological reaction of a specific patient to a new drug.

    CONTEXT:
    You have access to the patient's genetic profile for the "Big 3" Metabolic Enzymes:
    1. CYP2D6 (Chromosome 22) - Metabolizes ~25% of drugs: Antidepressants, Antipsychotics, Codeine, Tramadol, Metoprolol
    2. CYP2C19 (Chromosome 10) - Metabolizes Clopidogrel (Plavix), Omeprazole, and other proton pump inhibitors
    3. CYP2C9 (Chromosome 10) - Metabolizes Warfarin (blood thinner), Ibuprofen, Phenytoin, and NSAIDs
    4. UGT1A1 (Chromosome 2) - Phase II enzyme, metabolizes Irinotecan (chemotherapy), Atazanavir
    5. SLCO1B1 (Chromosome 12) - Transporter (OATP1B1), affects Statins (Simvastatin) uptake

    INPUT DATA:
    1. NEW DRUG: {drug_name}
       SMILES Structure: {drug_smiles}
       (Use the SMILES structure to understand the molecular structure and compare with similar drugs)

    2. SIMILAR KNOWN DRUGS (with structures):
       {similar_drugs}

       IMPORTANT: Each similar drug entry includes:
       - Drug Name
       - SMILES structure (molecular formula)
       - Known Side Effects
       - Known Targets (enzymes/proteins)

       Use the SMILES structures to:
       - Compare molecular similarity between the new drug and similar drugs
       - Identify shared functional groups that might indicate CYP enzyme metabolism
       - Recognize structural patterns that correlate with known CYP substrates
       - Infer which CYP enzyme(s) likely metabolize the new drug based on structural similarity

    3. PATIENT PROFILE: {patient_profile}

    RISK LEVEL DEFINITIONS (CRITICAL - USE THESE EXACTLY):
    IMPORTANT: Risk level is based ONLY on the patient's GENETIC metabolizer status,
    NOT on the drug's general therapeutic index or inherent danger. A dangerous drug
    given to a patient with NORMAL metabolism = LOW RISK from a pharmacogenomic perspective.

    - HIGH RISK: Patient's genetics cause severe pharmacogenomic consequences
      * Complete lack of efficacy due to genetic variant (e.g., codeine + CYP2D6 poor metabolizer → no morphine)
      * Significant toxicity from drug accumulation due to genetic variant (e.g., metoprolol + CYP2D6 poor metabolizer)
      * Warfarin + CYP2C9 poor metabolizer → excessive bleeding risk
      * Fluorouracil + DPYD poor metabolizer → severe/fatal toxicity
      * Azathioprine + TPMT poor metabolizer → myelosuppression
      * CPIC recommendation: "Alternative drug recommended" or "Contraindicated"

    - MEDIUM RISK: Patient's genetics cause moderate consequences, manageable with dose adjustment
      * Reduced efficacy but alternative dosing available (e.g., tramadol + CYP2D6 poor metabolizer)
      * Intermediate metabolizer status requiring dose reduction
      * CPIC recommendation: "Consider dose adjustment" or "Monitor closely"

    - LOW RISK: Patient's genetics do NOT alter drug response — standard dosing appropriate
      * Patient is Extensive/Normal Metabolizer for the relevant enzyme(s)
      * No pharmacogenomic interaction between patient genotype and drug
      * CPIC recommendation: "No dose adjustment needed"
      * CRITICAL: Normal/Extensive Metabolizer + any drug = LOW RISK (even for narrow therapeutic index drugs like warfarin)

    CPIC GUIDELINES REFERENCE (for known substrates):
    RULE: Normal/Extensive Metabolizer for any drug = LOW RISK. Only variant metabolizers trigger Medium/High.

    CYP2D6:
    - Any drug (normal metabolizer): LOW RISK - Standard dosing, no genetic concern
    - Codeine (poor metabolizer): HIGH RISK - No activation to morphine
    - Tramadol (poor metabolizer): MEDIUM RISK - Reduced activation, dose adjustment
    - Metoprolol (poor metabolizer): HIGH RISK - Accumulation, reduce dose 50%

    CYP2C19:
    - Any drug (normal metabolizer): LOW RISK - Standard dosing
    - Clopidogrel (poor metabolizer): MEDIUM RISK - Reduced activation
    - Omeprazole (poor metabolizer): MEDIUM RISK - Reduced efficacy

    CYP2C9:
    - Warfarin (normal metabolizer): LOW RISK - Standard dosing, routine INR monitoring
    - Warfarin (poor metabolizer): HIGH RISK - Bleeding risk, reduce dose significantly
    - Ibuprofen (poor metabolizer): MEDIUM RISK - Reduced clearance

    TPMT:
    - Azathioprine (normal metabolizer): LOW RISK - Standard dosing
    - Azathioprine (intermediate metabolizer): MEDIUM RISK - Reduce dose 30-70%
    - Azathioprine (poor metabolizer): HIGH RISK - Myelosuppression, avoid or drastically reduce

    DPYD:
    - Fluorouracil (normal metabolizer): LOW RISK - Standard dosing
    - Fluorouracil (intermediate metabolizer): MEDIUM RISK - Reduce dose 50%
    - Fluorouracil (poor metabolizer): HIGH RISK - Fatal toxicity risk, avoid

    HLA-B*57:01 (abacavir hypersensitivity — immune-mediated, NOT metabolic):
    - Abacavir (HLA-B*57:01 Negative): LOW RISK - Standard dosing, no hypersensitivity
    - Abacavir (HLA-B*57:01 Positive): HIGH RISK - Severe hypersensitivity reaction, CONTRAINDICATED
    - Abacavir (HLA-B*57:01 unknown/proxy): MEDIUM RISK - Cannot confirm or exclude; recommend confirmatory HLA typing before use
    CRITICAL: Abacavir risk is HLA-mediated, NOT CYP-mediated. Do NOT cite CYP2D6 for abacavir.

    HLA-B*15:02 (carbamazepine-class SJS/TEN — immune-mediated, NOT metabolic):
    - Carbamazepine/oxcarbazepine/phenytoin (HLA-B*15:02 Negative): LOW RISK - Standard dosing
    - Carbamazepine/oxcarbazepine/phenytoin (HLA-B*15:02 Positive): HIGH RISK - SJS/TEN, CONTRAINDICATED
    CRITICAL: Carbamazepine-class risk is HLA-mediated, NOT CYP-mediated.

    REASONING STEPS (follow this logic):
    0. HLA CHECK (do this FIRST for abacavir, carbamazepine, oxcarbazepine, phenytoin):
       - These drugs have immune-mediated (HLA) pharmacogenomic risks
       - Look for HLA_B5701 or HLA_B1502 status in the patient profile
       - If the drug is abacavir, base the risk assessment on HLA-B*57:01 status, NOT CYP enzymes
       - If the drug is carbamazepine/oxcarbazepine/phenytoin, base on HLA-B*15:02, NOT CYP enzymes

    1. STRUCTURAL ANALYSIS (for CYP-metabolized drugs):
       - Compare the SMILES structure of the new drug with similar drugs' SMILES
       - Identify shared functional groups, ring systems, or structural motifs
       - Look for patterns that indicate CYP enzyme metabolism:
         * Aromatic rings + specific substituents → CYP2D6 substrates
         * Thiophene/benzimidazole rings → CYP2C19 substrates
         * Coumarin-like structures → CYP2C9 substrates (warfarin-like)

    2. ENZYME IDENTIFICATION:
       - Use structural similarity to similar drugs to infer CYP enzyme targets
       - Check similar drugs' known targets/metabolism pathways
       - CYP2D6: Antidepressants, opioids, beta-blockers (often have aromatic + basic nitrogen)
       - CYP2C19: Antiplatelets (clopidogrel), PPIs (omeprazole) (often have benzimidazole/thiophene)
       - CYP2C9: Anticoagulants (warfarin), NSAIDs (ibuprofen), anticonvulsants (phenytoin) (often have coumarin/aromatic acid)
       - If structures are very similar to a known CYP substrate, infer the same enzyme pathway

    3. PATIENT GENETIC STATUS:
       - Check patient's metabolizer status for the relevant enzyme(s) from patient profile
       - Identify if patient is poor/intermediate/ultra-rapid metabolizer for the inferred enzyme

    4. IMPACT ASSESSMENT:
       - Activation-dependent (prodrug): Will patient get active metabolite? (Complete failure = HIGH, Reduced = MEDIUM)
       - Clearance-dependent (direct substrate): Will drug accumulate? (Severe accumulation = HIGH, Moderate = MEDIUM)
       - Consider structural similarity: If very similar to a high-risk drug, apply similar risk level

    5. RISK CLASSIFICATION:
       - Consider severity: Can this be managed with dose adjustment? (Yes = MEDIUM, No = HIGH)
       - Classify risk level based on CPIC guidelines, structural similarity, and severity assessment

    OUTPUT FORMAT (MUST FOLLOW EXACTLY):
    - RISK LEVEL: [Low/Medium/High] (choose ONE based on definitions above)
    - PREDICTED REACTION: [Description]
    - BIOLOGICAL MECHANISM: [Which enzyme(s) involved and why it happens]

    IMPORTANT:
    - Always start your response with "RISK LEVEL: " followed by exactly one of: Low, Medium, or High
    - Risk level is ONLY about pharmacogenomic interaction (genetics vs drug), NOT the drug's inherent danger
    - If the patient is Normal/Extensive Metabolizer for the relevant enzyme, the risk is LOW — period
    - Do NOT classify a Normal Metabolizer as High Risk just because the drug has a narrow therapeutic index
    - Only classify as Medium/High when the patient has a VARIANT metabolizer status (Poor, Intermediate, Ultra-rapid)
    - For tramadol-like drugs (reduced activation but manageable), use MEDIUM, not HIGH
    - For codeine-like drugs (complete lack of activation), use HIGH
    - For warfarin + CYP2C9 poor metabolizer, use HIGH. For warfarin + CYP2C9 normal metabolizer, use LOW
    - For ABACAVIR: risk is determined by HLA-B*57:01 status ONLY. Do NOT reference CYP2D6. Positive = HIGH, Negative = LOW, Unknown = MEDIUM.
    - For CARBAMAZEPINE / OXCARBAZEPINE / PHENYTOIN: risk is HLA-B*15:02. Do NOT reference CYP enzymes for the primary risk.
    """

    prompt = PromptTemplate(
        input_variables=[
            "drug_name",
            "drug_smiles",
            "similar_drugs",
            "patient_profile",
        ],
        template=template,
    )

    # Get LLM instance based on backend selection
    if backend == "claude":
        llm = _get_claude_llm()
    else:
        llm = _get_llm()
    chain = prompt | llm

    # Prepare inputs
    inputs = {
        "drug_name": drug_name,
        "drug_smiles": drug_smiles or "Not provided",
        "similar_drugs": "\n".join(similar_drugs),
        "patient_profile": patient_profile,
    }

    logger.info(f"Running simulation for drug: {drug_name}")
    logger.debug(f"Similar drugs: {len(similar_drugs)}")

    # Invoke with retry logic
    try:
        response = _invoke_llm_with_retry(chain, inputs)
        result = response.content if hasattr(response, "content") else str(response)
        logger.info("Simulation completed successfully")
        return str(result)
    except Exception as e:
        logger.error(f"LLM simulation failed: {e}", exc_info=True)
        raise LLMError(
            f"Failed to run pharmacogenomics simulation: {str(e)}",
            model=config.GEMINI_MODEL,
        ) from e


from src.resilience import CircuitBreakerOpenError, circuit_breaker


@circuit_breaker(failure_threshold=3, reset_timeout=60, name="Gemini-LLM")
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((Exception,)),
    reraise=True,
)
def _invoke_llm_with_retry(chain, inputs):
    """
    Invoke LLM chain with retry logic and circuit breaker.
    """
    try:
        return chain.invoke(inputs)
    except Exception as e:
        raise


def _normalize_risk_word(word: str) -> Optional[str]:
    w = word.strip().replace("**", "").replace("*", "").strip()
    if not w:
        return None
    low = w.lower()
    if low.startswith("low"):
        return "Low"
    if low.startswith("medium") or low.startswith("moderate"):
        return "Medium"
    if low.startswith("high"):
        return "High"
    return None


def extract_risk_level(result: str) -> Optional[str]:
    """
    Extract risk level from simulation result

    Args:
        result: AI-generated simulation result

    Returns:
        Risk level string (Low/Medium/High) or None if not found
    """
    text = result or ""
    lines = text.split("\n")

    for line in lines:
        line_stripped = line.strip()
        if line_stripped.startswith("RISK LEVEL:") or line_stripped.startswith(
            "- RISK LEVEL:"
        ):
            parts = line_stripped.split(":", 1)
            if len(parts) >= 2:
                risk = parts[1].strip()
                risk = risk.replace("**", "").replace("*", "").strip()
                norm = _normalize_risk_word(risk.split()[0] if risk else "")
                if norm:
                    return norm

    # Gemini often ignores the template and uses numbered sections, e.g. "1. Risk Level" then "Low"
    m = re.search(
        r"(?im)^\s*RISK\s*LEVEL\s*:\s*\**([A-Za-z]+)",
        text,
    )
    if m:
        norm = _normalize_risk_word(m.group(1))
        if norm:
            return norm

    for i, line in enumerate(lines):
        if re.match(r"^\s*\d+\.\s*Risk\s*Level\s*$", line, re.I):
            for j in range(i + 1, min(i + 5, len(lines))):
                cand = lines[j].strip()
                if not cand:
                    continue
                norm = _normalize_risk_word(cand.split()[0])
                if norm:
                    return norm
            break

    # Markdown / variant headings: "**RISK LEVEL:** Low", "- Risk Level: Medium", "### RISK LEVEL — High"
    for pat in (
        r"(?im)^\s*[-*]?\s*#*\s*\*?\*?RISK\s*LEVEL\*?\*?\s*[:.\-–—]\s*\*?\*?\s*([A-Za-z]+)",
        r"(?im)^\s*[-*]?\s*#*\s*\*?\*?Risk\s*Level\*?\*?\s*[:.\-–—]\s*\*?\*?\s*([A-Za-z]+)",
    ):
        m = re.search(pat, text)
        if m:
            norm = _normalize_risk_word(m.group(1))
            if norm:
                return norm

    # Same line with prose prefix, e.g. "Overall risk level is High"
    m = re.search(
        r"(?i)\brisk\s*level\s+is\s+\*?\*?([A-Za-z]+)",
        text,
    )
    if m:
        norm = _normalize_risk_word(m.group(1))
        if norm:
            return norm

    return None
