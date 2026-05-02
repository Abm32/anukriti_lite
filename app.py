import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Load .env so API_URL is set before sidebar health check
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import py3Dmol
import requests
import streamlit as st
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
from stmol import showmol
from streamlit_lottie import st_lottie

from src.agent_engine import extract_risk_level, run_simulation
from src.ancestry_risk import compute_ancestry_confidence
from src.eval.pgx_retrieval_eval import evaluate_pgx_retrieval
from src.input_processor import get_drug_fingerprint
from src.pgx_triggers import DRUG_GENE_TRIGGERS
from src.vcf_processor import (
    discover_local_vcf_paths,
    discover_vcf_paths,
    generate_patient_profile_from_vcf,
    get_sample_ids_from_vcf,
)
from src.vector_search import find_similar_drugs

# Sidebar default when session state is unset (keep in sync with config.LLM_BACKEND default)
_DEFAULT_UI_LLM_BACKEND = "Nova (AWS)"


# -----------------------------
# Google Analytics (gtag.js)
# -----------------------------
def _inject_google_analytics() -> None:
    """
    Inject GA4 gtag.js into the Streamlit app.
    Streamlit doesn't expose direct <head> injection, but this reliably loads the script
    once per session via an HTML component.
    """
    ga_id = os.getenv("GA_MEASUREMENT_ID", "G-HLF1JTN5V7").strip()
    if not ga_id:
        return
    # Avoid duplicate injection on reruns
    if st.session_state.get("_ga_injected"):
        return
    st.session_state["_ga_injected"] = True
    import streamlit.components.v1 as components

    components.html(
        f"""
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{ga_id}');
</script>
""",
        height=0,
        width=0,
    )


# Plain-English labels for metabolizer/transporter status (for Patient Genetics UI)
STATUS_LABELS = {
    "Extensive Metabolizer (Normal)": "✅ Normal speed",
    "Poor Metabolizer": "⚠️ Drug may accumulate",
    "Intermediate Metabolizer": "⚠️ Variable; may need dose adjustment",
    "Ultrarapid Metabolizer": "⚡ Drug cleared too fast",
    "Poor Metabolizer (*28/*28)": "⚠️ Drug may accumulate",
    "Intermediate Metabolizer (*1/*28)": "⚠️ Variable",
    "Normal Function": "✅ Normal uptake",
    "Decreased Function": "⚠️ Reduced uptake",
    "Poor Function": "⚠️ Statins may build up in muscle (myopathy risk)",
    "Normal Sensitivity": "✅ Standard warfarin dose expected",
    "Intermediate Sensitivity": "⚠️ May need lower warfarin dose",
    "High Sensitivity": "⚠️ Significantly lower warfarin dose required",
    "Rapid Acetylator (Normal)": "✅ Standard isoniazid / NAT2 substrate handling",
    "Intermediate Acetylator": "⚠️ Variable NAT2-mediated clearance",
    "Slow Acetylator (Poor)": "⚠️ Higher risk with NAT2-sensitive drugs",
    "Gene present (normal activity)": "✅ Typical GST conjugation capacity",
    "Homozygous deletion (null activity)": "⚠️ Altered detox of some chemotherapeutics",
    "HLA-B*57:01 proxy: negative": "✅ No proxy signal for abacavir HLA risk",
    "HLA-B*57:01 proxy: positive (abacavir risk)": "⚠️ Do not use abacavir without HLA testing",
    "HLA-B*15:02 proxy: negative": "✅ No proxy signal for carbamazepine-class HLA risk",
    "HLA-B*15:02 proxy: positive (SJS/TEN risk)": "⚠️ Elevated SJS/TEN risk — consider alternatives; confirm HLA typing",
}
GENE_HELP = {
    "CYP2D6": "Metabolizes ~25% of drugs (e.g. codeine, antidepressants).",
    "CYP2C19": "Affects clopidogrel, PPIs, some antidepressants.",
    "CYP2C9": "Key for warfarin and many NSAIDs.",
    "CYP3A4": "Major drug-metabolizing enzyme; many statins and CNI substrates.",
    "CYP3A5": "Tacrolimus / transplant immunosuppressant dosing (expressor vs non-expressor).",
    "CYP1A2": "Clozapine, theophylline, caffeine, and many psychiatry drugs.",
    "CYP2B6": "Efavirenz, bupropion, methadone, and some antiretrovirals.",
    "NAT2": "N-acetyltransferase-2; isoniazid and sulfonamide acetylation.",
    "UGT1A1": "Relevant for irinotecan and other drugs.",
    "SLCO1B1": "Transporter; affects statin uptake (myopathy risk).",
    "VKORC1": "Warfarin target; rs9923231 determines dose sensitivity.",
    "TPMT": "Thiopurine methyltransferase; key for azathioprine, mercaptopurine.",
    "DPYD": "Dihydropyrimidine dehydrogenase; key for fluorouracil, capecitabine.",
    "GSTM1": "Glutathione transferase; deletion affects some chemo toxicities.",
    "GSTT1": "Glutathione transferase; deletion affects some chemo toxicities.",
    "HLA_B5701": "Proxy for HLA-B*57:01; abacavir hypersensitivity screening.",
    "HLA_B1502": "Proxy for HLA-B*15:02 (rs3909184); carbamazepine-class SJS/TEN screening.",
}


@st.cache_data(ttl=45.0, show_spinner=False)
def _cached_streaming_status(api_base: str) -> Optional[Dict[str, Any]]:
    """Probe 1000G HTTPS tabix streaming (API must be up)."""
    base = (api_base or "").rstrip("/")
    if not base:
        return None
    try:
        r = requests.get(f"{base}/vcf-datasets/streaming-status", timeout=12)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def _parse_interpretation_sections(result: str) -> dict:
    """Split backend result into Risk Level, Predicted Reaction, Biological Mechanism, etc."""
    import re

    text = (result or "").strip()
    sections = {}
    # Section headers the agent may output (case-insensitive)
    patterns = [
        (r"PREDICTED REACTION\s*:?\s*", "predicted_reaction"),
        (r"BIOLOGICAL MECHANISM\s*:?\s*", "biological_mechanism"),
        (r"DOSING IMPLICATION\s*:?\s*", "dosing_implication"),
        (r"RAG CONTEXT\s*:?\s*", "rag_context"),
    ]
    for regex, key in patterns:
        m = re.search(regex, text, re.I)
        if m:
            start = m.end()
            # Find next section or end
            rest = text[start:]
            next_start = len(rest)
            for r, _ in patterns:
                n = re.search(r, rest)
                if n:
                    next_start = min(next_start, n.start())
            sections[key] = rest[:next_start].strip()
    # If no structure found, treat whole as body
    if not sections:
        sections["body"] = text
    return sections


def _safe_json(obj) -> str:
    """Best-effort JSON serialization for downloads."""
    return json.dumps(obj, indent=2, default=str)


def _submit_attestation_from_ui(
    api_url: str, attestation: Dict[str, Any], *, key_prefix: str
) -> Optional[Dict[str, Any]]:
    """Submit a prepared attestation memo through the backend Solana CLI path."""

    if not attestation:
        st.warning("No attestation is available to submit.")
        return None
    payload = {
        "attestation": attestation,
        "keypair_path": os.getenv("SOLANA_KEYPAIR_PATH", "").strip() or None,
        "rpc_url": os.getenv("SOLANA_RPC_URL", "").strip() or None,
    }
    try:
        with st.spinner("Submitting memo to Solana devnet..."):
            resp = requests.post(
                f"{api_url}/attestations/submit",
                json=payload,
                timeout=75,
            )
            resp.raise_for_status()
            result = resp.json()
    except Exception as exc:
        st.error(f"Solana submission failed: {exc}")
        return None

    if result.get("submitted"):
        st.success("Memo anchored on Solana devnet.")
    else:
        st.warning(result.get("message") or "Memo was prepared but not submitted.")
    st.session_state[f"{key_prefix}_submission_result"] = result
    return result


def _normalize_context_sources(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, (list, tuple)):
        return "; ".join(str(x) for x in raw)
    return str(raw)


def _render_verifiability_agent_pipeline(
    pgx_structured: Optional[Dict[str, Any]],
    audit: Dict[str, Any],
    context_sources_top: Any,
) -> None:
    """
    Surface Agents 1–5 in the UI: deterministic PGx, table verifier, retrieval,
    LLM explanation, citation grounding (matches API pgx_structured + audit).
    """
    pgx = pgx_structured if isinstance(pgx_structured, dict) else {}
    aud = audit if isinstance(audit, dict) else {}
    ctx = _normalize_context_sources(context_sources_top or aud.get("context_sources"))
    grounding = pgx.get("grounding") if isinstance(pgx.get("grounding"), dict) else {}
    vstat = pgx.get("verification_status")
    vdet = pgx.get("verification_detail")

    with st.expander("🔬 Verifiability pipeline — agents at each layer", expanded=True):
        st.caption(
            "Run order: deterministic PGx (when available) → table verification "
            "(when attached) → evidence retrieval (RAG) → LLM explanation → "
            "grounding overlap score (when computed). "
            "Agents 2 and 5 use rules only (no second LLM)."
        )

        # ① Deterministic PGx
        has_core = bool(
            pgx.get("gene")
            or pgx.get("phenotype")
            or pgx.get("clinical_recommendation")
        )
        st.markdown(
            f"**① Deterministic PGx call** — {'✅ Complete' if has_core else '⚪ No structured PGx in this run'}"
        )
        if has_core:
            bits = [
                pgx.get("gene"),
                pgx.get("genotype"),
                pgx.get("phenotype"),
                pgx.get("risk_level"),
            ]
            st.caption(" · ".join(str(b) for b in bits if b))

        # ② Verifier
        if vstat:
            if vstat == "verified_against_pharmvar_cpic_table":
                v_icon = "✅"
            elif vstat in ("ambiguous_genotype", "diplotype_not_in_cpic_table"):
                v_icon = "⚠️"
            else:
                v_icon = "ℹ️"
            st.markdown(
                f"**② Deterministic verifier (PharmVar / CPIC tables)** — {v_icon} `{vstat}`"
            )
            if vdet:
                st.caption(str(vdet))
        else:
            st.markdown(
                "**② Deterministic verifier (PharmVar / CPIC tables)** — "
                "ℹ️ Not attached (profile heuristics, HLA proxy, or path without table verification)"
            )

        # ③ Retrieval
        n_chunks = grounding.get("retrieval_passage_count")
        st.markdown(
            f"**③ Evidence retrieval** — {'✅' if ctx or n_chunks else '⚪'} "
            f"Vector / source label + CPIC passages for the explainer when Bedrock/Nova PGx runs"
        )
        if ctx:
            st.caption(f"Similar-drug / vector source: {ctx}")
        if n_chunks is not None:
            st.caption(
                f"CPIC & guideline chunks used for grounding check: **{int(n_chunks)}** passage(s), "
                f"{grounding.get('retrieval_char_count', 0)} characters."
            )
        elif not ctx:
            st.caption(
                "No retrieval metadata in this run (e.g. local fallback with API offline)."
            )

        # ④ LLM
        hint = aud.get("llm_failure_hint")
        expl = (pgx.get("explanation") or "").strip()
        if hint:
            st.markdown("**④ LLM clinical explanation** — ⚠️ Fallback or unavailable")
            st.caption(str(hint)[:400])
        elif expl:
            st.markdown("**④ LLM clinical explanation** — ✅ Generated")
        else:
            st.markdown(
                "**④ LLM clinical explanation** — ℹ️ Empty (Gemini/Claude local path or no explainer)"
            )

        # ⑤ Grounding
        if grounding:
            frac = grounding.get("grounded_sentence_fraction")
            gs = grounding.get("grounded_sentence_count", 0)
            us = grounding.get("ungrounded_sentence_count", 0)
            tot = grounding.get("sentence_count", 0)
            if frac is None and tot == 0:
                st.markdown(
                    "**⑤ Citation overlap (grounding)** — ⚪ No sentences to score (empty explanation)"
                )
            elif frac is None:
                st.markdown(
                    "**⑤ Citation overlap (grounding)** — ⚪ No retrieved text to compare "
                    "(grounding skipped)"
                )
            else:
                g_icon = "✅" if frac >= 0.5 else "⚠️"
                st.markdown(
                    f"**⑤ Citation overlap (grounding vs retrieved passages)** — {g_icon} "
                    f"**{frac:.0%}** of explanation sentences overlap retrieved CPIC/guideline text"
                )
                st.caption(
                    f"Sentences grounded: {gs} · ungrounded: {us} · total scored: {tot}"
                )
                ung = grounding.get("ungrounded_sentences") or []
                if ung:
                    with st.expander(
                        "Ungrounded sentences (first few)", expanded=False
                    ):
                        for line in ung[:8]:
                            st.markdown(f"- {line}")
        else:
            st.markdown(
                "**⑤ Citation overlap (grounding)** — ℹ️ Not computed (use Bedrock or Nova with "
                "deterministic PGx + API online for this metric)"
            )


# --- Configuration ---
st.set_page_config(
    page_title="Anukriti | AI Pharmacogenomics",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject Google Analytics early (safe no-op if disabled)
_inject_google_analytics()


# --- Helper Functions ---
def load_lottieurl(url: str):
    try:
        r = requests.get(url)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None


# Load Animations
lottie_dna = load_lottieurl(
    "https://lottie.host/80706597-2858-4504-8b89-138332994c63/E8e4Xg6KqE.json"
)  # Example DNA animation
lottie_success = load_lottieurl(
    "https://assets9.lottiefiles.com/packages/lf20_jbrw3hcz.json"
)
lottie_loading = load_lottieurl(
    "https://assets9.lottiefiles.com/packages/lf20_p8bfn5to.json"
)

# --- Custom CSS (reference: dark dashboard with panels) ---
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Dark theme base */
    .stApp { background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%); }
    .main .block-container { padding: 1.5rem 2rem 2rem; max-width: 100%; }

    /* Main header */
    .hero-title {
        font-size: 1.75rem;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 0.25rem;
    }

    /* Quick Start banner (dark blue) */
    .quick-start-banner {
        background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 1rem;
    }
    .quick-start-banner .steps {
        color: #94a3b8;
        font-size: 0.95rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .quick-start-banner .steps strong { color: #38bdf8; }

    /* Panel cards (reference: 1. PARAMETERS, 2. PATIENT PROFILE, 3. MOLECULAR VIEW) */
    .panel-card {
        background-color: #1e293b;
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        border: 1px solid #334155;
        margin-bottom: 1.25rem;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.2);
    }
    .panel-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #94a3b8;
        letter-spacing: 0.05em;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .panel-title .num { color: #38bdf8; }
    .panel-footer {
        font-size: 0.75rem;
        color: #64748b;
        margin-top: 1rem;
        padding-top: 0.75rem;
        border-top: 1px solid #334155;
    }

    /* Orange "Relevant" tag (reference) */
    .relevant-tag {
        display: inline-block;
        background: #c2410c;
        color: #fff7ed;
        font-size: 0.7rem;
        font-weight: 600;
        padding: 0.2rem 0.5rem;
        border-radius: 6px;
        margin-left: 0.5rem;
    }

    /* AI Insight Preview (Molecular View) */
    .ai-insight-preview {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 1rem;
        margin-top: 1rem;
    }
    .ai-insight-preview .label { font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.25rem; }
    .ai-insight-preview .risk { font-weight: 700; font-size: 1rem; }
    .ai-insight-preview .bar {
        height: 6px;
        border-radius: 3px;
        background: #334155;
        margin: 0.5rem 0;
        overflow: hidden;
    }
    .ai-insight-preview .bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
    .ai-insight-preview .hint { font-size: 0.8rem; color: #64748b; margin-top: 0.5rem; }

    /* Cards (legacy + panel) */
    .card {
        background-color: #1e293b;
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        border: 1px solid #334155;
        margin-bottom: 1.25rem;
    }

    /* Risk */
    .risk-high { color: #EF4444; font-weight: bold; }
    .risk-medium { color: #F59E0B; font-weight: bold; }
    .risk-low { color: #10B981; font-weight: bold; }
    .risk-badge {
        display: inline-block;
        padding: 0.5rem 1.5rem;
        border-radius: 9999px;
        font-weight: 700;
        font-size: 1.1rem;
        margin-bottom: 1rem;
    }
    .risk-badge.low { background: #065F46; color: #6EE7B7; }
    .risk-badge.medium { background: #92400E; color: #FCD34D; }
    .risk-badge.high { background: #7F1D1D; color: #FCA5A5; animation: pulse 2s ease-in-out infinite; }
    .risk-badge.unknown { background: #334155; color: #cbd5e1; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.85; } }

    /* Primary button (Run Simulation) */
    .stButton > button {
        background: linear-gradient(135deg, #0ea5e9, #0284c7);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1.25rem;
        font-weight: 600;
        width: 100%;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        box-shadow: 0 0 20px rgba(14, 165, 233, 0.4);
    }

    /* Sidebar: warning box orange/brown */
    [data-testid="stSidebar"] .stAlert {
        border-radius: 10px;
        border: 1px solid #334155;
    }
    [data-testid="stSidebar"] [data-baseweb="notification"] {
        background-color: #78350f !important;
        color: #fef3c7 !important;
        border-color: #92400e !important;
    }
    /* Pro tip / info in sidebar */
    [data-testid="stSidebar"] [data-baseweb="notification"][kind="info"] {
        background-color: #0c4a6e !important;
        color: #e0f2fe !important;
        border-color: #0369a1 !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Safety disclaimer (research prototype; not for clinical use)
SAFETY_DISCLAIMER = (
    "**Anukriti is a research prototype.** Outputs are synthetic predictions and must not be used "
    "for clinical decision-making, diagnosis, or treatment. Not medical advice."
)

# --- Sidebar (reference: branding, warning, nav, status, pro tip) ---
with st.sidebar:
    st.markdown("### 🧬 Anukriti")
    st.caption("**AI-POWERED VIRTUAL TRIALS**")
    st.markdown("")
    st.warning(
        "**Research Prototype:** Outputs are synthetic and not for clinical decision-making."
    )
    st.markdown("---")
    st.caption("**Navigation**")
    nav = st.radio(
        "Go to",
        [
            "Simulation Lab",
            "Batch Mode",
            "Datasets",
            "Solana Proofs",
            "Analytics",
            "Population Dashboard",
            "About",
        ],
        label_visibility="collapsed",
        key="sidebar_nav",
    )
    st.markdown("---")
    st.caption("**Configuration**")
    api_url = os.getenv("API_URL", "http://127.0.0.1:8000")
    if "localhost" in api_url:
        api_url = api_url.replace("localhost", "127.0.0.1")
    health_timeout = int(os.getenv("HEALTH_CHECK_TIMEOUT", "3"))
    try:
        resp = requests.get(f"{api_url}/", timeout=health_timeout)
        resp.raise_for_status()
        health = resp.json()
        model_str = health.get("model", "unknown")
        if ":" in model_str:
            backend_label, model_label = model_str.split(":", 1)
        else:
            backend_label, model_label = "gemini", model_str
        # Show active backend (per-session override or server default)
        active_ui = st.session_state.get("ui_llm_backend", _DEFAULT_UI_LLM_BACKEND)
        if "Claude" in active_ui:
            active_label = "Claude (Anthropic)"
        elif "Bedrock" in active_ui:
            active_label = "Bedrock (AWS)"
        elif "Nova" in active_ui:
            _nv = st.session_state.get("ui_nova_variant", "lite")
            active_label = f"Nova {_nv.title()} (AWS)"
        else:
            active_label = f"{backend_label} ({model_label})"
        st.success(
            f"✅ System Online (v{health.get('version', '0.0.0')}) · "
            f"Active backend: {active_label}"
        )

        # AWS Integration Status (fast; cached; deep mode optional)
        try:
            resp = requests.get(f"{api_url}/aws-status?deep=0", timeout=3)
            resp.raise_for_status()
            aws_status = resp.json()
            aws_info = aws_status.get("aws_integration", aws_status) or {}

            if aws_info.get("s3_genomic_connected"):
                st.success("☁️ AWS S3 Genomic Data: Connected")
                st.caption(f"📊 {aws_info.get('vcf_files_count', 0)} VCF files in S3")
            else:
                st.info("💾 Using Local VCF Files")

            if aws_info.get("lambda_available"):
                st.success("⚡ AWS Lambda: Available")

            if aws_info.get("step_functions_available"):
                st.success("🔄 AWS Step Functions: Available")

        except requests.exceptions.Timeout:
            st.info("💾 Using Local Data Sources")
            st.caption("AWS status check timed out - using local fallback")
        except requests.exceptions.RequestException as e:
            st.info("💾 Using Local Data Sources")
            st.caption(f"Could not reach AWS status endpoint: connection error")
        except (ValueError, KeyError) as e:
            st.info("💾 Using Local Data Sources")
            st.caption(f"AWS status response invalid")
        except Exception as e:
            st.info("💾 Using Local Data Sources")
            st.caption(f"AWS status check failed")

        # Vector backend status (OpenSearch / Pinecone / Mock)
        try:
            ds = requests.get(f"{api_url}/data-status", timeout=3)
            ds.raise_for_status()
            data_status = ds.json()
            vector_backend = str(data_status.get("vector_db", "mock")).lower()
            configured_backend = str(
                data_status.get("vector_db_configured", "pinecone")
            ).lower()
            if vector_backend == "opensearch":
                st.success("🔎 Vector DB: OpenSearch")
            elif vector_backend == "pinecone":
                st.success("🔎 Vector DB: Pinecone")
            else:
                st.warning("🔎 Vector DB: Mock fallback (no vector index available)")
            st.caption(
                f"Configured: {configured_backend} · Effective: {vector_backend}"
            )
            if vector_backend == "mock":
                st.caption(
                    "ChEMBL similar-drug search needs OpenSearch/Pinecone configured; "
                    "PGx engine and Bedrock explanations still work without it."
                )
            st.caption(
                "Demo drugs include tacrolimus/CYP3A, efavirenz/CYP2B6, isoniazid/NAT2, abacavir/HLA, "
                "plus clopidogrel, warfarin, statins, fluoropyrimidines, thiopurines."
            )
        except Exception:
            st.info("🔎 Vector DB: Unknown")

        try:
            ls = requests.get(f"{api_url}/health/llm-status", timeout=4)
            ls.raise_for_status()
            lj = ls.json()
            llm_disp = lj.get("active_backend_display") or lj.get(
                "active_backend", "unknown"
            )
            st.caption(f"🤖 **LLM resolution:** {llm_disp}")
            oa = lj.get("ollama") or {}
            if oa.get("available"):
                st.caption(
                    f"Local Ollama: available ({oa.get('model', 'model')}) — optional fallback"
                )
            else:
                st.caption(
                    "Local Ollama: not detected (optional; see /health/llm-status)"
                )
        except Exception:
            st.caption("LLM status: could not reach /health/llm-status")

    except requests.exceptions.Timeout:
        st.error("❌ Backend Timeout")
        st.caption(
            f"API did not respond within {health_timeout}s. Simulation will run locally."
        )
        st.caption(
            "Start API in a separate terminal: `uvicorn api:app --host 0.0.0.0 --port 8000`"
        )
        with st.expander("🔍 Debug: Troubleshooting", expanded=False):
            st.caption(f"API_URL={api_url} · timeout={health_timeout}s")
            st.code(f"curl -v --max-time {health_timeout} {api_url}/", language="bash")
            st.caption("**Common fixes:**")
            st.caption("1. Ensure you're in the `synthatrial` conda environment")
            st.caption(
                "2. Check if server is actually running: `ps aux | grep uvicorn`"
            )
            st.caption("3. Test server response: `curl http://127.0.0.1:8000/`")
            st.caption("4. Restart server if hanging: Kill process and restart")
            if st.button("Retry health check", key="retry_health_timeout"):
                st.rerun()
    except requests.exceptions.ConnectionError:
        st.error("❌ Backend Offline")
        st.caption("**Error:** Cannot connect to API server")
        st.caption(
            "**Solution:** Start API server: `uvicorn api:app --host 0.0.0.0 --port 8000 --reload`"
        )
        with st.expander("🔍 Debug: Connection troubleshooting", expanded=False):
            st.caption(f"API_URL={api_url} · timeout={health_timeout}s")
            st.code(f"curl -v --max-time {health_timeout} {api_url}/", language="bash")
            st.caption("**Setup checklist:**")
            st.caption("1. Activate conda environment: `conda activate synthatrial`")
            st.caption(
                "2. Start API server: `uvicorn api:app --host 0.0.0.0 --port 8000 --reload`"
            )
            st.caption("3. Verify port is available: `netstat -tlnp | grep :8000`")
            if st.button("Retry health check", key="retry_health_connection"):
                st.rerun()
    except Exception as e:
        st.error("❌ Backend Offline")
        err_msg = str(e)
        err_type = type(e).__name__
        st.caption(f"**Error:** {err_type}: {err_msg}")
        st.caption(
            "Simulation will run locally. Start API: `uvicorn api:app --host 0.0.0.0 --port 8000`"
        )
        with st.expander("🔍 Debug: Error details", expanded=False):
            st.caption(f"API_URL={api_url} · timeout={health_timeout}s")
            st.code(f"curl -v --max-time {health_timeout} {api_url}/", language="bash")
            st.caption("**Troubleshooting steps:**")
            st.caption("1. Check server logs for errors")
            st.caption("2. Verify environment variables in .env file")
            st.caption(
                "3. Test with: `python -c 'from api import app; print(\"API imports successful\")'`"
            )
            if st.button("Retry health check", key="retry_health_error"):
                st.rerun()
    # Per-session backend selector (Bedrock-only while Gemini/Claude credits are exhausted)
    backend_ui = st.radio(
        "AI backend (per session)",
        ["Nova (AWS)", "Bedrock (AWS)", "QVAC (Local)"],
        index=0,
        key="ui_llm_backend",
    )
    st.caption(
        "Nova/Bedrock run through AWS. QVAC uses the local partner-track "
        "SDK bridge when installed. Gemini and direct Claude are temporarily unavailable."
    )
    if "Nova" in backend_ui:
        st.radio(
            "Amazon Nova model",
            ["lite", "pro"],
            format_func=lambda x: "Nova Lite" if x == "lite" else "Nova Pro",
            horizontal=True,
            key="ui_nova_variant",
            index=0,
        )
    st.markdown("---")
    st.info("**PRO TIP:** Use **Batch Mode** for processing large cohorts efficiently.")

# --- Main Content (nav-driven) ---
st.markdown(
    '<div class="hero-title">Virtual Clinical Trials</div>', unsafe_allow_html=True
)

# Route by sidebar nav
if nav == "Simulation Lab":
    # Quick Start Guide banner (reference: dark blue bar, steps + Got it)
    if st.session_state.get("onboarding_expanded", True):
        bc1, bc2 = st.columns([4, 1])
        with bc1:
            st.markdown(
                '<div class="quick-start-banner">'
                '<span class="steps">🔷 <strong>Quick Start Guide:</strong> '
                "1. Select Drug &nbsp; 2. Map Genes &nbsp; 3. Simulate</span></div>",
                unsafe_allow_html=True,
            )
        with bc2:
            if st.button("Got it", key="onboarding_dismiss"):
                st.session_state["onboarding_expanded"] = False
                st.rerun()
    st.markdown("")

    _api_for_banner = os.getenv("API_URL", "http://127.0.0.1:8000")
    if "localhost" in _api_for_banner:
        _api_for_banner = _api_for_banner.replace("localhost", "127.0.0.1")
    _stream = _cached_streaming_status(_api_for_banner)
    if _stream and _stream.get("streaming_available"):
        lat = _stream.get("latency_ms")
        lat_s = f"~{int(lat)} ms" if lat is not None else "n/a"
        st.success(
            f"**1000 Genomes HTTPS streaming** is live ({lat_s}). "
            f"{_stream.get('cost', '')} — use **VCF → Remote 1000G** or **S3 Open Data** for zero-local-download PGx."
        )

    # Three-panel layout: 1. PARAMETERS | 2. PATIENT PROFILE | 3. MOLECULAR VIEW
    col_params, col_profile, col_mol = st.columns([1, 1, 1])

    with col_params:
        st.markdown(
            '<div class="panel-card">'
            '<div class="panel-title"><span class="num">1.</span> PARAMETERS</div>',
            unsafe_allow_html=True,
        )
        drug_source = st.radio(
            "Drug Source",
            ["Standard Library", "Custom Molecule/SMILES"],
            horizontal=True,
            key="drug_src",
        )
        if drug_source == "Standard Library":
            drug_name = st.selectbox(
                "Selected Molecule",
                [
                    "Abacavir",
                    "Azathioprine",
                    "Carbamazepine",
                    "Bupropion",
                    "Capecitabine",
                    "Clozapine",
                    "Clopidogrel",
                    "Codeine",
                    "Cyclophosphamide",
                    "Efavirenz",
                    "Fluorouracil",
                    "Ibuprofen",
                    "Irinotecan",
                    "Isoniazid",
                    "Mercaptopurine",
                    "Oxcarbazepine",
                    "Phenytoin",
                    "Metoprolol",
                    "Midazolam",
                    "Simvastatin",
                    "Tacrolimus",
                    "Warfarin",
                ],
                key="drug_select",
            )
            smiles_map = {
                "Warfarin": "CC(=O)CC(C1=CC=CC=C1)C2=C(O)C3=CC=CC=C3OC2=O",
                "Clopidogrel": "COC(=O)C(C1=CC=CC=C1Cl)N2CCC3=CC=C(C=C32)S",
                "Codeine": "CN1CCC23C4C1CC5=C2C(C(C=C5)O)OC3C(C=C4)O",
                "Ibuprofen": "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
                "Metoprolol": "CC(C)NCC(O)COC1=CC=C(C=C1)CCOC",
                "Simvastatin": "CCC(C)(C)C(=O)OC1CC(C)C=C2C1C(C)C=C2C",
                "Irinotecan": "CCC1=C2CN3C(=CC4=C(C3=O)COC(=O)C4(CC)O)C2=NC=C1N5CCC(CC5)N6CCCCC6",
                "Azathioprine": "Cn1c(=O)c2c(ncn2[C@@H]2OC(CO)C(O)C2O)n1[N+](=O)[O-]",
                "Capecitabine": "CCCCCOC(=O)NC1=NC(=O)N(C=C1F)[C@@H]1O[C@@H](C)[C@@H](O)[C@H]1O",
                "Fluorouracil": "O=c1[nH]cc(F)c(=O)[nH]1",
                "Mercaptopurine": "S=c1[nH]cnc2[nH]cnc12",
                "Abacavir": "C1CC1NC2=C3C(=NC(=N2)N)N(C=N3)[C@@H]4C[C@@H](C=C4)CO",
                "Carbamazepine": "NC(=O)N1c2ccccc2C=Cc3ccccc13",
                "Oxcarbazepine": "NC(=O)N1c2ccccc2CC(=O)Nc3ccccc13",
                "Phenytoin": "O=C1NC(=O)C(N2C(=O)c3ccccc3C2=O)(c2ccccc2)N1",
                "Bupropion": "CC(C(=O)C1=CC(=CC=C1)Cl)NC(C)(C)C",
                "Clozapine": "CN1CCN(CC1)C2=NC3=C(C=CC(=C3)Cl)NC4=CC=CC=C42",
                "Cyclophosphamide": "C1CNP(=O)(OC1)N(CCCl)CCCl",
                "Efavirenz": "C1CC1C#C[C@]2(C3=C(C=CC(=C3)Cl)NC(=O)O2)C(F)(F)F",
                "Isoniazid": "C1=CN=CC=C1C(=O)NN",
                "Midazolam": "CC1=NC=C2N1C3=C(C=C(C=C3)Cl)C(=NC2)C4=CC=CC=C4F",
                "Tacrolimus": (
                    "C[C@@H]1C[C@@H]([C@@H]2[C@H](C[C@H]([C@@](O2)(C(=O)C(=O)N3CCCC[C@H]3C(=O)O[C@@H]([C@@H]([C@H](CC(=O)[C@@H](/C=C(/C1)\\C)CC=C)O)C)/C(=C/[C@@H]4CC[C@H]([C@@H](C4)OC)O)/C)O)C)OC)OC"
                ),
            }
            smiles_input = smiles_map.get(drug_name, "")
            novel_drug_mode = False
            novel_targets = []
            novel_enzymes = []
            novel_transporters = []
            novel_notes = ""
        else:
            drug_name = st.text_input("Drug Name", "New Molecule", key="drug_name")
            smiles_input = st.text_area(
                "SMILES String", value="CC(=O)Nc1ccc(O)cc1", key="smiles"
            )
            novel_drug_mode = st.checkbox(
                "Novel Drug Mode (confidence-tiered output)",
                value=True,
                key="novel_drug_mode",
                help="Use evidence-tiered novel-drug analysis endpoint.",
            )
            if novel_drug_mode:
                novel_targets_raw = st.text_input(
                    "Known Targets (comma-separated)",
                    value="",
                    key="novel_targets",
                )
                novel_enzymes_raw = st.text_input(
                    "Metabolism Enzymes (comma-separated)",
                    value="",
                    key="novel_enzymes",
                )
                novel_transporters_raw = st.text_input(
                    "Transporters (comma-separated)",
                    value="",
                    key="novel_transporters",
                )
                novel_notes = st.text_area(
                    "Evidence Notes (optional)",
                    value="",
                    key="novel_notes",
                )
                novel_targets = [
                    x.strip() for x in (novel_targets_raw or "").split(",") if x.strip()
                ]
                novel_enzymes = [
                    x.strip() for x in (novel_enzymes_raw or "").split(",") if x.strip()
                ]
                novel_transporters = [
                    x.strip()
                    for x in (novel_transporters_raw or "").split(",")
                    if x.strip()
                ]
            else:
                novel_targets = []
                novel_enzymes = []
                novel_transporters = []
                novel_notes = ""
        anchor_simulation_to_devnet = st.checkbox(
            "Anchor proof on Solana devnet after simulation",
            value=False,
            key="anchor_simulation_to_devnet",
            help=(
                "Optional. The simulation is always hashed locally. This also submits "
                "the hash memo using the backend host's Solana CLI and funded devnet keypair."
            ),
        )
        run_clicked = st.button("🚀 Run Simulation", use_container_width=True)
        st.markdown(
            '<div class="panel-footer">Engine: v0.2.0 • CPIC tier-1 panel (16 genes + HLA proxies)</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    triggered_genes = set(DRUG_GENE_TRIGGERS.get(str(drug_name).strip().lower(), []))
    patient_id = f"PT-{int(time.time()) % 100000}"

    with col_profile:
        st.markdown(
            '<div class="panel-card">'
            '<div class="panel-title"><span class="num">2.</span> PATIENT PROFILE'
            f' &nbsp; <span style="color:#94a3b8;font-size:0.8rem;">ID: {patient_id}</span></div>',
            unsafe_allow_html=True,
        )
        profile_source = st.radio(
            "Profile Source",
            ["Manual", "VCF"],
            index=1,
            horizontal=True,
            key="profile_src",
            help="Manual: set phenotypes by hand. VCF: derive from genomic VCF (local or S3).",
        )
        vcf_samples: List[str] = []
        vcf_available = False
        use_local_vcf = False
        vcf_input_mode = "Local"
        vcf_primary_chrom = "chr22"
        vcf_upload_id = st.session_state.get("vcf_upload_id")

        if profile_source == "VCF":
            api_url = os.getenv("API_URL", "http://127.0.0.1:8000")
            if "localhost" in api_url:
                api_url = api_url.replace("localhost", "127.0.0.1")

            vcf_input_mode = st.radio(
                "VCF Source",
                ["Auto", "Local", "S3", "S3 Open Data", "Remote 1000G", "Upload"],
                index=3,
                horizontal=True,
                key="vcf_input_mode",
                help="Auto: local first then S3 fallback. Local: use data/genomes. S3: use your bucket VCFs. S3 Open Data: public s3://1000genomes. Remote 1000G: stream from IGSR via tabix. Upload: provide your own VCF (index built server-side).",
            )

            selected_dataset_id = None

            if vcf_input_mode in (
                "Auto",
                "Local",
                "S3",
                "S3 Open Data",
                "Remote 1000G",
            ):
                source_param = (
                    "auto"
                    if vcf_input_mode == "Auto"
                    else (
                        "local"
                        if vcf_input_mode == "Local"
                        else (
                            "s3"
                            if vcf_input_mode == "S3"
                            else (
                                "open_data"
                                if vcf_input_mode == "S3 Open Data"
                                else "remote"
                            )
                        )
                    )
                )
                try:
                    ds = requests.get(
                        f"{api_url}/vcf-datasets",
                        params={"source": source_param},
                        timeout=10 if vcf_input_mode in ("Auto", "Local") else 30,
                    )
                    ds.raise_for_status()
                    datasets = ds.json().get("datasets", [])
                except Exception:
                    datasets = []

                if source_param == "auto":
                    filtered = [
                        d for d in datasets if d.get("source") in ("local", "s3")
                    ]
                else:
                    filtered = [
                        d
                        for d in datasets
                        if d.get("source", "").startswith(source_param)
                    ]
                if filtered:
                    labels = [
                        f"{d.get('source','?').upper()} · {d.get('chrom','?')} · {d.get('label','')}"
                        for d in filtered
                    ]
                    ids = [d.get("dataset_id") for d in filtered]
                    chroms = [d.get("chrom", "") for d in filtered]
                    default_idx = chroms.index("chr22") if "chr22" in chroms else 0
                    if labels and ids:
                        selected_dataset_id = st.selectbox(
                            "VCF Dataset",
                            list(range(len(labels))),
                            index=default_idx,
                            format_func=lambda i: labels[i],
                            key="vcf_dataset_idx",
                        )
                        selected_dataset_id = ids[int(selected_dataset_id)]
                        vcf_primary_chrom = filtered[
                            ids.index(selected_dataset_id)
                        ].get("chrom", "chr22")
                        if vcf_primary_chrom == "all_pgx":
                            st.caption(
                                "All PGx Chromosomes streams 11 VCFs covering all 16 tier-1 pharmacogenes. "
                                "Profile generation will take longer (~1-2 min) but provides full gene panel coverage."
                            )

                if selected_dataset_id:
                    # Prefer API sample listing; local fallback remains available for Local source.
                    try:
                        r = requests.get(
                            f"{api_url}/vcf-samples",
                            params={"dataset_id": selected_dataset_id},
                            timeout=10 if vcf_input_mode in ("Auto", "Local") else 60,
                        )
                        if r.status_code == 200:
                            data = r.json()
                            vcf_samples = data.get("samples", [])
                            vcf_available = data.get("vcf_available", False)
                    except Exception:
                        pass

                if (not vcf_available or not vcf_samples) and vcf_input_mode in (
                    "Auto",
                    "Local",
                ):
                    # Local fallback: parse directly from filesystem
                    app_root = os.path.dirname(os.path.abspath(__file__))
                    genomes_dir = os.path.join(app_root, "data", "genomes")
                    vcf_paths = discover_local_vcf_paths(genomes_dir)
                    if vcf_paths:
                        vcf_path = vcf_paths.get("chr22") or next(
                            iter(vcf_paths.values())
                        )
                        try:
                            vcf_samples = get_sample_ids_from_vcf(vcf_path, limit=50)
                            vcf_available = bool(vcf_samples)
                            use_local_vcf = vcf_available
                        except Exception:
                            pass

            else:
                st.caption(
                    "Upload a bgzipped VCF (.vcf.gz). Optional: provide a .tbi index."
                )
                up_vcf = st.file_uploader(
                    "Upload VCF (.vcf.gz)",
                    type=["vcf.gz"],
                    key="vcf_upload_vcf",
                )
                up_tbi = st.file_uploader(
                    "Upload index (.tbi) (optional)",
                    type=["tbi"],
                    key="vcf_upload_tbi",
                )
                if up_vcf and st.button(
                    "Load samples from upload", key="vcf_upload_load"
                ):
                    try:
                        if up_tbi:
                            resp = requests.post(
                                f"{api_url}/vcf-upload-samples",
                                files={
                                    "vcf": (
                                        up_vcf.name,
                                        up_vcf.getvalue(),
                                        "application/gzip",
                                    ),
                                    "tbi": (
                                        up_tbi.name,
                                        up_tbi.getvalue(),
                                        "application/octet-stream",
                                    ),
                                },
                                timeout=120,
                            )
                        else:
                            resp = requests.post(
                                f"{api_url}/vcf-upload",
                                files={
                                    "vcf": (
                                        up_vcf.name,
                                        up_vcf.getvalue(),
                                        "application/gzip",
                                    )
                                },
                                timeout=180,
                            )
                        resp.raise_for_status()
                        data = resp.json()
                        st.session_state["vcf_upload_id"] = data.get("upload_id")
                        vcf_upload_id = st.session_state["vcf_upload_id"]
                        vcf_samples = data.get("samples", [])
                        vcf_available = bool(vcf_samples)
                    except Exception as e:
                        st.error(f"Upload failed: {e}")

            if not vcf_available or not vcf_samples:
                st.warning("No VCF samples available. Falling back to manual profile.")
                profile_source = "Manual"
            else:
                vcf_sample_id = st.selectbox(
                    "Sample ID",
                    vcf_samples,
                    key="vcf_sample",
                    help="Select a sample from the chosen VCF source.",
                )
        st.caption("Set phenotypes; fields **relevant for your drug** are tagged.")
        with st.expander("ℹ️ How do I know what to select?", expanded=False):
            st.markdown(
                "**With genetic data:** Use the phenotype from your lab report. "
                "**Without:** Use **Extensive Metabolizer (Normal)** and **Normal Function**."
            )
        if profile_source == "Manual":
            grp_meta, grp_trans = st.columns([1, 1])
            with grp_meta:
                st.markdown("**🧬 Metabolizing enzymes**")
                opts_2d6 = [
                    "Extensive Metabolizer (Normal)",
                    "Poor Metabolizer",
                    "Intermediate Metabolizer",
                    "Ultrarapid Metabolizer",
                ]
                cyp2d6 = st.selectbox(
                    "CYP2D6", opts_2d6, help=GENE_HELP["CYP2D6"], key="cyp2d6"
                )
                st.caption(STATUS_LABELS.get(cyp2d6, ""))
                if "CYP2D6" in triggered_genes:
                    st.markdown(
                        '📍 <span class="relevant-tag">Relevant</span>',
                        unsafe_allow_html=True,
                    )
                opts_2c19 = opts_2d6.copy()
                cyp2c19 = st.selectbox(
                    "CYP2C19", opts_2c19, help=GENE_HELP["CYP2C19"], key="cyp2c19"
                )
                st.caption(STATUS_LABELS.get(cyp2c19, ""))
                if "CYP2C19" in triggered_genes:
                    st.markdown(
                        '📍 <span class="relevant-tag">Relevant</span>',
                        unsafe_allow_html=True,
                    )
                opts_2c9 = opts_2d6[:3]
                cyp2c9 = st.selectbox(
                    "CYP2C9", opts_2c9, help=GENE_HELP["CYP2C9"], key="cyp2c9"
                )
                st.caption(STATUS_LABELS.get(cyp2c9, ""))
                if "CYP2C9" in triggered_genes:
                    st.markdown(
                        '📍 <span class="relevant-tag">Relevant</span>',
                        unsafe_allow_html=True,
                    )
                opts_ugt = [
                    "Extensive Metabolizer (Normal)",
                    "Poor Metabolizer (*28/*28)",
                    "Intermediate Metabolizer (*1/*28)",
                ]
                ugt1a1 = st.selectbox(
                    "UGT1A1", opts_ugt, help=GENE_HELP["UGT1A1"], key="ugt1a1"
                )
                st.caption(STATUS_LABELS.get(ugt1a1, ""))
                if "UGT1A1" in triggered_genes:
                    st.markdown(
                        '📍 <span class="relevant-tag">Relevant</span>',
                        unsafe_allow_html=True,
                    )
            with grp_trans:
                st.markdown("**🚛 Drug transporters**")
                opts_slco = ["Normal Function", "Decreased Function", "Poor Function"]
                slco1b1 = st.selectbox(
                    "SLCO1B1", opts_slco, help=GENE_HELP["SLCO1B1"], key="slco1b1"
                )
                st.caption(STATUS_LABELS.get(slco1b1, ""))
                if "SLCO1B1" in triggered_genes:
                    st.markdown(
                        '📍 <span class="relevant-tag">Relevant</span>',
                        unsafe_allow_html=True,
                    )
                st.markdown("**💊 Pharmacodynamic targets**")
                opts_vkorc1 = [
                    "Normal Sensitivity",
                    "Intermediate Sensitivity",
                    "High Sensitivity",
                ]
                vkorc1 = st.selectbox(
                    "VKORC1",
                    opts_vkorc1,
                    help=GENE_HELP["VKORC1"],
                    key="vkorc1",
                )
                st.caption(STATUS_LABELS.get(vkorc1, ""))
                if "VKORC1" in triggered_genes:
                    st.markdown(
                        '📍 <span class="relevant-tag">Relevant</span>',
                        unsafe_allow_html=True,
                    )
                st.markdown("**🧪 Additional pharmacogenes**")
                opts_tpmt = [
                    "Extensive Metabolizer (Normal)",
                    "Poor Metabolizer",
                    "Intermediate Metabolizer",
                ]
                tpmt = st.selectbox(
                    "TPMT", opts_tpmt, help=GENE_HELP["TPMT"], key="tpmt"
                )
                st.caption(STATUS_LABELS.get(tpmt, ""))
                if "TPMT" in triggered_genes:
                    st.markdown(
                        '📍 <span class="relevant-tag">Relevant</span>',
                        unsafe_allow_html=True,
                    )
                opts_dpyd = [
                    "Extensive Metabolizer (Normal)",
                    "Poor Metabolizer",
                    "Intermediate Metabolizer",
                ]
                dpyd = st.selectbox(
                    "DPYD", opts_dpyd, help=GENE_HELP["DPYD"], key="dpyd"
                )
                st.caption(STATUS_LABELS.get(dpyd, ""))
                if "DPYD" in triggered_genes:
                    st.markdown(
                        '📍 <span class="relevant-tag">Relevant</span>',
                        unsafe_allow_html=True,
                    )
            st.markdown("---")
            with st.expander(
                "🌍 Expanded PGx panel (CYP3A, CYP1A2, CYP2B6, NAT2, GST, HLA proxy)",
                expanded=False,
            ):
                ex1, ex2 = st.columns(2)
                opts_cyp_extra = opts_2d6[:3]
                with ex1:
                    cyp3a4 = st.selectbox(
                        "CYP3A4",
                        opts_cyp_extra,
                        help=GENE_HELP["CYP3A4"],
                        key="cyp3a4",
                    )
                    st.caption(STATUS_LABELS.get(cyp3a4, ""))
                    if "CYP3A4" in triggered_genes:
                        st.markdown(
                            '📍 <span class="relevant-tag">Relevant</span>',
                            unsafe_allow_html=True,
                        )
                    cyp3a5 = st.selectbox(
                        "CYP3A5",
                        opts_cyp_extra,
                        help=GENE_HELP["CYP3A5"],
                        key="cyp3a5",
                    )
                    st.caption(STATUS_LABELS.get(cyp3a5, ""))
                    if "CYP3A5" in triggered_genes:
                        st.markdown(
                            '📍 <span class="relevant-tag">Relevant</span>',
                            unsafe_allow_html=True,
                        )
                    cyp1a2 = st.selectbox(
                        "CYP1A2",
                        opts_cyp_extra,
                        help=GENE_HELP["CYP1A2"],
                        key="cyp1a2",
                    )
                    st.caption(STATUS_LABELS.get(cyp1a2, ""))
                    if "CYP1A2" in triggered_genes:
                        st.markdown(
                            '📍 <span class="relevant-tag">Relevant</span>',
                            unsafe_allow_html=True,
                        )
                    cyp2b6 = st.selectbox(
                        "CYP2B6",
                        opts_cyp_extra,
                        help=GENE_HELP["CYP2B6"],
                        key="cyp2b6",
                    )
                    st.caption(STATUS_LABELS.get(cyp2b6, ""))
                    if "CYP2B6" in triggered_genes:
                        st.markdown(
                            '📍 <span class="relevant-tag">Relevant</span>',
                            unsafe_allow_html=True,
                        )
                with ex2:
                    opts_nat2 = [
                        "Rapid Acetylator (Normal)",
                        "Intermediate Acetylator",
                        "Slow Acetylator (Poor)",
                    ]
                    nat2 = st.selectbox(
                        "NAT2", opts_nat2, help=GENE_HELP["NAT2"], key="nat2"
                    )
                    st.caption(STATUS_LABELS.get(nat2, ""))
                    if "NAT2" in triggered_genes:
                        st.markdown(
                            '📍 <span class="relevant-tag">Relevant</span>',
                            unsafe_allow_html=True,
                        )
                    opts_gst = [
                        "Gene present (normal activity)",
                        "Homozygous deletion (null activity)",
                    ]
                    gstm1 = st.selectbox(
                        "GSTM1", opts_gst, help=GENE_HELP["GSTM1"], key="gstm1"
                    )
                    st.caption(STATUS_LABELS.get(gstm1, ""))
                    if "GSTM1" in triggered_genes:
                        st.markdown(
                            '📍 <span class="relevant-tag">Relevant</span>',
                            unsafe_allow_html=True,
                        )
                    gstt1 = st.selectbox(
                        "GSTT1", opts_gst, help=GENE_HELP["GSTT1"], key="gstt1"
                    )
                    st.caption(STATUS_LABELS.get(gstt1, ""))
                    if "GSTT1" in triggered_genes:
                        st.markdown(
                            '📍 <span class="relevant-tag">Relevant</span>',
                            unsafe_allow_html=True,
                        )
                    opts_hla = [
                        "HLA-B*57:01 proxy: negative",
                        "HLA-B*57:01 proxy: positive (abacavir risk)",
                    ]
                    hla_b57 = st.selectbox(
                        "HLA-B*57:01 (proxy)",
                        opts_hla,
                        help=GENE_HELP["HLA_B5701"],
                        key="hla_b5701",
                    )
                    st.caption(STATUS_LABELS.get(hla_b57, ""))
                    if "HLA_B5701" in triggered_genes:
                        st.markdown(
                            '📍 <span class="relevant-tag">Relevant</span>',
                            unsafe_allow_html=True,
                        )
                    opts_hla15 = [
                        "HLA-B*15:02 proxy: negative",
                        "HLA-B*15:02 proxy: positive (SJS/TEN risk)",
                    ]
                    hla_b15 = st.selectbox(
                        "HLA-B*15:02 (proxy)",
                        opts_hla15,
                        help=GENE_HELP["HLA_B1502"],
                        key="hla_b1502",
                    )
                    st.caption(STATUS_LABELS.get(hla_b15, ""))
                    if "HLA_B1502" in triggered_genes:
                        st.markdown(
                            '📍 <span class="relevant-tag">Relevant</span>',
                            unsafe_allow_html=True,
                        )
            patient_profile = f"""ID: {patient_id}
Age: 45
Genetics:
- CYP2D6: {cyp2d6}
- CYP2C19: {cyp2c19}
- CYP2C9: {cyp2c9}
- UGT1A1: {ugt1a1}
- SLCO1B1: {slco1b1}
- VKORC1: {vkorc1}
- TPMT: {tpmt}
- DPYD: {dpyd}
- CYP3A4: {cyp3a4}
- CYP3A5: {cyp3a5}
- CYP1A2: {cyp1a2}
- CYP2B6: {cyp2b6}
- NAT2: {nat2}
- GSTM1: {gstm1}
- GSTT1: {gstt1}
- HLA_B5701: {hla_b57}
- HLA_B1502: {hla_b15}
Conditions: Hypertension, Hyperlipidemia
"""
        else:
            patient_profile = None
        st.markdown("</div>", unsafe_allow_html=True)

    with col_mol:
        st.markdown(
            '<div class="panel-card">'
            '<div class="panel-title"><span class="num">3.</span> MOLECULAR VIEW</div>',
            unsafe_allow_html=True,
        )
        if smiles_input:
            try:
                # Validate SMILES first
                from rdkit import Chem
                from rdkit.Chem import AllChem

                mol = Chem.MolFromSmiles(smiles_input)
                if mol is not None:
                    st.caption(f"Molecule: {drug_name}")

                    # Add hydrogens for better 3D structure
                    mol_with_h = Chem.AddHs(mol)

                    # Generate 3D coordinates with multiple attempts
                    embed_result = -1
                    for attempt in range(3):
                        try:
                            if attempt == 0:
                                # First attempt with random seed
                                embed_result = AllChem.EmbedMolecule(
                                    mol_with_h, randomSeed=42
                                )
                            elif attempt == 1:
                                # Second attempt without random seed
                                embed_result = AllChem.EmbedMolecule(mol_with_h)
                            else:
                                # Third attempt with different parameters
                                embed_result = AllChem.EmbedMolecule(
                                    mol_with_h, useRandomCoords=True, maxAttempts=100
                                )

                            if embed_result == 0:
                                break
                        except Exception:
                            continue

                    if embed_result == 0:
                        # Optimize geometry for better visualization
                        try:
                            AllChem.MMFFOptimizeMolecule(mol_with_h)
                        except Exception:
                            pass  # Continue even if optimization fails

                        # Convert to mol block format for py3Dmol
                        mol_block = Chem.MolToMolBlock(mol_with_h)

                        # Create 3D visualization with enhanced styling
                        view = py3Dmol.view(width=400, height=300)
                        view.addModel(mol_block, "mol")
                        view.setStyle(
                            {
                                "stick": {"colorscheme": "cyanCarbon", "radius": 0.15},
                                "sphere": {"scale": 0.25},
                            }
                        )
                        view.setBackgroundColor("#1E293B")
                        view.zoomTo()

                        # Render the molecule
                        showmol(view, height=300, width=400)

                        # Show molecular properties
                        num_atoms = mol.GetNumAtoms()
                        num_bonds = mol.GetNumBonds()
                        mol_weight = Descriptors.MolWt(mol)
                        st.caption(
                            f"⚛️ {num_atoms} atoms · 🔗 {num_bonds} bonds · "
                            f"⚖️ {mol_weight:.1f} g/mol"
                        )
                    else:
                        # Fallback: show 2D structure if 3D fails
                        st.warning(
                            "3D coordinates unavailable. Showing 2D structure..."
                        )
                        try:
                            import io

                            from PIL import Image
                            from rdkit.Chem import Draw

                            # Generate 2D image
                            img = Draw.MolToImage(mol, size=(400, 300))
                            st.image(img, use_column_width=True)

                            num_atoms = mol.GetNumAtoms()
                            num_bonds = mol.GetNumBonds()
                            mol_weight = Descriptors.MolWt(mol)
                            st.caption(
                                f"⚛️ {num_atoms} atoms · 🔗 {num_bonds} bonds · "
                                f"⚖️ {mol_weight:.1f} g/mol"
                            )
                        except Exception as e2:
                            st.error(f"Could not generate structure: {e2}")
                else:
                    st.warning("Invalid SMILES string - could not parse molecule")
            except Exception as e:
                st.error(f"Visualization Error: {e}")
                st.caption("Try selecting a drug from the Standard Library")
        else:
            st.info("Select a drug or enter a SMILES string to visualize structure")
        # AI Insight Preview (reference)
        last_risk = st.session_state.get("last_risk_level", "—")
        risk_lower = (last_risk or "—").strip().lower()
        if risk_lower not in ("low", "medium", "high"):
            risk_lower = "low"  # default display
        bar_pct = (
            33 if risk_lower == "high" else (66 if risk_lower == "medium" else 100)
        )
        bar_color = (
            "#10B981"
            if risk_lower == "low"
            else "#F59E0B"
            if risk_lower == "medium"
            else "#EF4444"
        )
        display_risk = last_risk if last_risk and last_risk != "—" else "—"
        st.markdown(
            f'<div class="ai-insight-preview">'
            f'<div class="label">Interaction Risk</div>'
            f'<div class="risk risk-{risk_lower}">{display_risk}</div>'
            f'<div class="bar"><div class="bar-fill" style="width:{bar_pct}%;background:{bar_color};"></div></div>'
            f'<div class="hint">Current genotype suggests standard dosing is likely safe. Monitoring is still advised.</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
        st.caption("[Documentation](https://github.com/abhimanyu/anukriti) · Privacy")
        st.markdown("</div>", unsafe_allow_html=True)

    if run_clicked:
        api_url = os.getenv("API_URL", "http://127.0.0.1:8000")
        if "localhost" in api_url:
            api_url = api_url.replace("localhost", "127.0.0.1")
        backend_online = False
        try:
            r = requests.get(f"{api_url}/", timeout=5)
            backend_online = r.status_code == 200
        except Exception:
            pass

        if not backend_online:
            st.warning(
                "Backend API unreachable. Running simulation locally (Gemini). "
                "Start the API with `uvicorn api:app --host 0.0.0.0 --port 8000` for full features."
            )

        vcf_profile_timeout = int(os.getenv("VCF_PROFILE_TIMEOUT", "180"))
        if not backend_online:
            vcf_profile_timeout = 60

        def _run_local_simulation():
            """Fallback when API is offline. Gemini/Claude credits exhausted — requires API with Bedrock."""
            st.error(
                "Local simulation unavailable: Gemini and Claude credits are "
                "exhausted. Please ensure the FastAPI backend is running so "
                "requests route through AWS Bedrock (Nova)."
            )
            return None

        if True:
            progress_placeholder = st.empty()
            try:
                profile_to_use = patient_profile
                if profile_source == "VCF" and vcf_available and vcf_samples:
                    vcf_sample_id = st.session_state.get("vcf_sample", vcf_samples[0])
                    profile_to_use = None

                    if vcf_input_mode == "Upload":
                        if not backend_online:
                            st.error(
                                "Backend is offline. Upload-based VCF profile needs the API running."
                            )
                        elif not vcf_upload_id:
                            st.error("No upload session found. Re-upload the VCF.")
                        else:
                            progress_placeholder.info(
                                "📤 Generating VCF profile from upload..."
                            )
                            try:
                                r = requests.post(
                                    f"{api_url}/vcf-upload-profile",
                                    json={
                                        "upload_id": vcf_upload_id,
                                        "drug_name": drug_name,
                                        "sample_id": vcf_sample_id,
                                    },
                                    timeout=vcf_profile_timeout,
                                )
                                r.raise_for_status()
                                profile_to_use = r.json().get("patient_profile", "")
                            except Exception as e:
                                st.error(f"Uploaded VCF profile failed: {e}")

                    elif use_local_vcf or (
                        vcf_input_mode in ("Auto", "Local") and not backend_online
                    ):
                        progress_placeholder.info(
                            "📂 Generating VCF profile from local files..."
                        )
                        app_root = os.path.dirname(os.path.abspath(__file__))
                        genomes_dir = os.path.join(app_root, "data", "genomes")
                        vcf_paths = discover_local_vcf_paths(genomes_dir)
                        if vcf_paths:
                            primary = (
                                vcf_paths.get(vcf_primary_chrom)
                                or vcf_paths.get("chr22")
                                or next(iter(vcf_paths.values()))
                            )
                            try:
                                profile_to_use = generate_patient_profile_from_vcf(
                                    vcf_path=primary,
                                    sample_id=vcf_sample_id,
                                    drug_name=drug_name,
                                    vcf_paths_by_chrom=vcf_paths,
                                )
                            except Exception as e:
                                st.error(f"Local VCF profile failed: {e}")
                    else:
                        progress_placeholder.info(
                            "📂 Generating VCF profile from API..."
                        )
                        try:
                            source_param = (
                                "auto"
                                if vcf_input_mode == "Auto"
                                else "local"
                                if vcf_input_mode == "Local"
                                else "s3"
                            )
                            job_req = {
                                "drug_name": drug_name,
                                "sample_id": vcf_sample_id,
                                "source": source_param,
                                "dataset_id": selected_dataset_id,
                            }
                            jr = requests.post(
                                f"{api_url}/jobs/vcf-profile",
                                json=job_req,
                                timeout=10,
                            )
                            jr.raise_for_status()
                            job_id = jr.json().get("job_id")
                            if not job_id:
                                raise RuntimeError(
                                    "Job creation failed: missing job_id"
                                )

                            poll_start = time.time()
                            last_msg = ""
                            while True:
                                if (time.time() - poll_start) > float(
                                    vcf_profile_timeout
                                ):
                                    raise TimeoutError("VCF profile job timed out")
                                gr = requests.get(
                                    f"{api_url}/jobs/{job_id}", timeout=10
                                )
                                gr.raise_for_status()
                                job = gr.json()
                                status = job.get("status")
                                msg = job.get("message") or ""
                                if msg and msg != last_msg:
                                    progress_placeholder.info(
                                        f"📂 VCF profile job: {msg}"
                                    )
                                    last_msg = msg
                                if status == "succeeded":
                                    profile_to_use = (job.get("result") or {}).get(
                                        "patient_profile"
                                    ) or ""
                                    break
                                if status == "failed":
                                    raise RuntimeError(
                                        job.get("error") or "VCF profile job failed"
                                    )
                                time.sleep(1.0)
                        except Exception as e:
                            if vcf_input_mode in ("Auto", "Local"):
                                st.warning(
                                    f"API VCF profile failed ({e}). Trying local files..."
                                )
                                app_root = os.path.dirname(os.path.abspath(__file__))
                                genomes_dir = os.path.join(app_root, "data", "genomes")
                                vcf_paths = discover_local_vcf_paths(genomes_dir)
                                if vcf_paths:
                                    primary = (
                                        vcf_paths.get(vcf_primary_chrom)
                                        or vcf_paths.get("chr22")
                                        or next(iter(vcf_paths.values()))
                                    )
                                    try:
                                        profile_to_use = (
                                            generate_patient_profile_from_vcf(
                                                vcf_path=primary,
                                                sample_id=vcf_sample_id,
                                                drug_name=drug_name,
                                                vcf_paths_by_chrom=vcf_paths,
                                            )
                                        )
                                    except Exception as e2:
                                        st.error(f"Local VCF profile also failed: {e2}")
                                else:
                                    st.error(
                                        "No local VCF files available for fallback."
                                    )
                            else:
                                st.error(f"VCF profile failed: {e}")

                # --- Run simulation (both Manual and VCF modes) ---
                if profile_to_use:
                    progress_placeholder.info("🤖 Running AI simulation...")
                    # Determine backend from UI selector
                    ui_backend = st.session_state.get(
                        "ui_llm_backend", _DEFAULT_UI_LLM_BACKEND
                    )
                    if "Claude" in ui_backend:
                        llm_backend_key = "claude"
                    elif "QVAC" in ui_backend:
                        llm_backend_key = "qvac"
                    elif "Bedrock" in ui_backend:
                        llm_backend_key = "bedrock"
                    elif "Nova" in ui_backend:
                        llm_backend_key = "nova"
                    else:
                        llm_backend_key = "gemini"

                    data = None
                    if backend_online:
                        use_novel_endpoint = bool(
                            drug_source == "Custom Molecule/SMILES" and novel_drug_mode
                        )
                        if use_novel_endpoint:
                            payload = {
                                "drug_name": drug_name,
                                "patient_profile": profile_to_use,
                                "drug_smiles": smiles_input,
                                "llm_backend": llm_backend_key,
                                "targets": novel_targets,
                                "metabolism_enzymes": novel_enzymes,
                                "transporters": novel_transporters,
                                "evidence_notes": novel_notes,
                                "include_population_summary": True,
                                "cohort_size": 300,
                            }
                            if llm_backend_key == "nova":
                                payload["nova_variant"] = st.session_state.get(
                                    "ui_nova_variant", "lite"
                                )
                            endpoint = "/analyze/novel-drug"
                        else:
                            payload = {
                                "drug_name": drug_name,
                                "patient_profile": profile_to_use,
                                "drug_smiles": smiles_input,
                                "llm_backend": llm_backend_key,
                            }
                            if llm_backend_key == "nova":
                                payload["nova_variant"] = st.session_state.get(
                                    "ui_nova_variant", "lite"
                                )
                            endpoint = "/analyze"
                        timeout_sec = int(os.getenv("API_TIMEOUT", "120"))
                        try:
                            _t0 = time.time()
                            response = requests.post(
                                f"{api_url}{endpoint}",
                                json=payload,
                                timeout=timeout_sec,
                            )
                            _elapsed_ms = int((time.time() - _t0) * 1000)
                            if response.status_code == 200:
                                data = response.json()
                                st.session_state["last_response_ms"] = _elapsed_ms
                            else:
                                st.warning(
                                    f"API returned {response.status_code}. Trying local simulation..."
                                )
                                data = _run_local_simulation()
                        except Exception as e:
                            st.warning(
                                f"API request failed ({e}). Trying local simulation..."
                            )
                            data = _run_local_simulation()
                    else:
                        data = _run_local_simulation()

                    if data:
                        st.session_state["simulation_count"] = (
                            st.session_state.get("simulation_count", 0) + 1
                        )
                        progress_placeholder.empty()
                        result = data["result"]
                        risk_level = data.get("risk_level") or "Unknown"
                        st.session_state["last_risk_level"] = risk_level
                        similar_drugs_used = data.get("similar_drugs_used") or []
                        genetics_summary = data.get("genetics_summary") or ""
                        context_sources = data.get("context_sources") or ""
                        pgx_structured = data.get("pgx_structured")
                        audit = data.get("audit") or {}
                        ehr_bundle = data.get("ehr_bundle") or None
                        attestation = data.get("attestation") or {}
                        novel_payload = data.get("novel_drug") or {}
                        if anchor_simulation_to_devnet and attestation and backend_online:
                            submission = _submit_attestation_from_ui(
                                api_url,
                                attestation,
                                key_prefix="simulation_attestation",
                            )
                            updated_attestation = (
                                submission or {}
                            ).get("attestation")
                            if updated_attestation:
                                attestation = updated_attestation
                                data["attestation"] = updated_attestation
                        elif anchor_simulation_to_devnet and not backend_online:
                            st.warning(
                                "Backend is offline, so the proof was not submitted to Solana."
                            )

                        # --- Results pipeline tabs ---
                        st.markdown("---")
                        st.markdown("## 📋 Simulation Results")
                        if audit.get("llm_failure_hint"):
                            st.warning(audit["llm_failure_hint"])
                        st.caption(
                            "Pipeline: Genetics → Similar drugs → Predicted response"
                        )
                        _render_verifiability_agent_pipeline(
                            pgx_structured, audit, context_sources
                        )
                        pipe_tab1, pipe_tab2, pipe_tab3, pipe_tab4 = st.tabs(
                            [
                                "📋 Predicted Response + Risk",
                                "🧬 Patient Genetics",
                                "💊 Similar Drugs Retrieved",
                                "🔐 Solana Proof",
                            ]
                        )

                        with pipe_tab1:
                            rl = (risk_level or "Unknown").strip().lower()
                            if rl == "low":
                                badge_class = "low"
                            elif rl == "high":
                                badge_class = "high"
                            elif rl == "medium":
                                badge_class = "medium"
                            else:
                                badge_class = "unknown"
                            st.markdown(
                                f"<div class='risk-badge {badge_class}'>● {risk_level or 'Unknown'} risk</div>",
                                unsafe_allow_html=True,
                            )
                            if isinstance(novel_payload, dict) and novel_payload:
                                tier = novel_payload.get(
                                    "confidence_tier", "exploratory"
                                )
                                st.info(
                                    f"Novel drug mode enabled · confidence tier: {tier}"
                                )
                            sections = _parse_interpretation_sections(result)
                            if sections.get("predicted_reaction"):
                                st.markdown("#### 📋 Predicted Reaction")
                                st.markdown(sections["predicted_reaction"])
                            if sections.get("biological_mechanism"):
                                st.markdown("#### 🧬 Biological Mechanism")
                                st.markdown(sections["biological_mechanism"])
                            if sections.get("dosing_implication"):
                                st.markdown("#### 💊 Dosing Implication")
                                st.markdown(sections["dosing_implication"])
                            if sections.get("body") and not any(
                                sections.get(k)
                                for k in (
                                    "predicted_reaction",
                                    "biological_mechanism",
                                    "dosing_implication",
                                )
                            ):
                                st.markdown("#### Clinical interpretation")
                                st.markdown(sections["body"])
                            elif sections.get("body"):
                                st.markdown("#### Additional context")
                                st.markdown(sections["body"])
                            if (
                                similar_drugs_used
                                or context_sources
                                or sections.get("rag_context")
                            ):
                                st.markdown("#### 🔬 RAG Context Used")
                                if similar_drugs_used:
                                    st.caption(
                                        "Structurally similar: "
                                        + ", ".join(
                                            d.split("|")[0].strip()
                                            for d in similar_drugs_used[:5]
                                        )
                                    )
                                if context_sources:
                                    st.caption("**Sources:** " + context_sources)
                                if sections.get("rag_context"):
                                    st.markdown(sections["rag_context"])
                            if pgx_structured:
                                st.markdown("### 🧬 Genetic Risk Summary")
                                summary_cols = st.columns([2, 2, 3, 2])
                                with summary_cols[0]:
                                    st.markdown("**Gene**")
                                    st.markdown(pgx_structured.get("gene", "—"))
                                with summary_cols[1]:
                                    st.markdown("**Genotype**")
                                    st.markdown(pgx_structured.get("genotype", "—"))
                                with summary_cols[2]:
                                    st.markdown("**Phenotype**")
                                    st.markdown(pgx_structured.get("phenotype", "—"))
                                with summary_cols[3]:
                                    st.markdown("**Risk**")
                                    st.markdown(pgx_structured.get("risk_level", "—"))
                                if pgx_structured.get("verification_status"):
                                    st.caption(
                                        f"**Table verification (Agent 2):** "
                                        f"`{pgx_structured.get('verification_status')}`"
                                    )
                                _g = pgx_structured.get("grounding")
                                if (
                                    isinstance(_g, dict)
                                    and _g.get("grounded_sentence_fraction") is not None
                                ):
                                    st.caption(
                                        f"**Explanation grounding (Agent 5):** "
                                        f"{float(_g['grounded_sentence_fraction']):.0%} of sentences "
                                        f"overlap retrieved guideline text"
                                    )
                                st.markdown("### 💊 Drug Recommendation")
                                st.markdown(
                                    pgx_structured.get("clinical_recommendation", "")
                                )
                                st.markdown("### 🧠 AI Clinical Explanation")
                                st.markdown(pgx_structured.get("explanation", ""))
                                conf = pgx_structured.get("confidence")
                                if conf is not None:
                                    st.markdown(
                                        f"**Confidence:** {int(conf * 100)}% (based on CPIC evidence for this gene)"
                                    )
                                from src.report_pdf import generate_pdf_bytes

                                report_payload = {
                                    "drug_name": drug_name,
                                    "gene": pgx_structured.get("gene"),
                                    "genotype": pgx_structured.get("genotype"),
                                    "phenotype": pgx_structured.get("phenotype"),
                                    "risk_level": pgx_structured.get("risk_level"),
                                    "clinical_recommendation": pgx_structured.get(
                                        "clinical_recommendation"
                                    ),
                                    "explanation": pgx_structured.get("explanation"),
                                }
                                pdf_bytes = generate_pdf_bytes(report_payload)
                                st.download_button(
                                    "👉 Download Clinical Report (PDF)",
                                    data=pdf_bytes,
                                    file_name=f"pgx_report_{drug_name}.pdf",
                                    mime="application/pdf",
                                )

                                # EHR-style JSON export (FHIR-like bundle from API when available)
                                export_obj = (
                                    ehr_bundle
                                    if isinstance(ehr_bundle, dict) and ehr_bundle
                                    else {
                                        "drug_name": drug_name,
                                        "risk_level": risk_level,
                                        "patient_profile": profile_to_use,
                                        "pgx_structured": pgx_structured,
                                        "audit": audit,
                                        "attestation": attestation,
                                    }
                                )
                                st.download_button(
                                    "⬇️ Download EHR JSON (FHIR-like)",
                                    data=_safe_json(export_obj),
                                    file_name=f"anukriti_ehr_{drug_name}.json",
                                    mime="application/json",
                                )
                                if backend_online and pgx_structured.get("gene"):
                                    try:
                                        _dip = (
                                            pgx_structured.get("genotype")
                                            or pgx_structured.get("diplotype")
                                            or "*1/*1"
                                        )
                                        _phen = (
                                            pgx_structured.get("phenotype") or "Unknown"
                                        )
                                        _fh = requests.post(
                                            f"{api_url}/analyze/fhir-report",
                                            json={
                                                "patient_id": patient_id,
                                                "drug_name": drug_name,
                                                "gene_results": [
                                                    {
                                                        "gene": pgx_structured.get(
                                                            "gene"
                                                        ),
                                                        "diplotype": _dip,
                                                        "phenotype": _phen,
                                                        "cpic_level": pgx_structured.get(
                                                            "cpic_level"
                                                        ),
                                                        "recommendation": pgx_structured.get(
                                                            "clinical_recommendation"
                                                        ),
                                                    }
                                                ],
                                            },
                                            timeout=45,
                                        )
                                        if _fh.status_code == 200:
                                            st.download_button(
                                                "⬇️ Download FHIR R4 Genomics bundle",
                                                data=_safe_json(_fh.json()),
                                                file_name=f"pgx_fhir_{drug_name}.json",
                                                mime="application/fhir+json",
                                                key="dl_fhir_genomics_bundle",
                                            )
                                    except Exception:
                                        pass
                            # Ancestry-aware confidence
                            triggered = DRUG_GENE_TRIGGERS.get(
                                str(drug_name).strip().lower(), []
                            )
                            if triggered:
                                st.markdown("#### 🌍 Ancestry-Aware Confidence")
                                conf_cols = st.columns(len(triggered))
                                for ci, tg in enumerate(triggered):
                                    with conf_cols[ci]:
                                        conf = compute_ancestry_confidence(tg, "EUR")
                                        st.metric(
                                            f"{tg} evidence",
                                            f"{int(conf['confidence'] * 100)}%",
                                        )
                                        st.caption(f"Level: {conf['evidence_level']}")
                            st.warning(SAFETY_DISCLAIMER)
                            with st.expander(
                                "🔎 Audit trail (for reproducibility)", expanded=False
                            ):
                                st.caption(
                                    "Non-sensitive metadata about this run: backend/model, timing, and sources."
                                )
                                _meta = {
                                    "backend": audit.get("backend")
                                    or st.session_state.get(
                                        "ui_llm_backend", _DEFAULT_UI_LLM_BACKEND
                                    ),
                                    "model": audit.get("model"),
                                    "elapsed_ms": st.session_state.get(
                                        "last_response_ms", None
                                    ),
                                    "context_sources": audit.get("context_sources")
                                    or context_sources,
                                    "used_pinecone": audit.get("used_pinecone"),
                                    "vector_backend": audit.get("vector_backend"),
                                    "vector_mock_fallback": audit.get(
                                        "vector_mock_fallback"
                                    ),
                                    "ts": audit.get("ts"),
                                    "novel_drug_mode": audit.get("novel_drug_mode"),
                                    "confidence_tier": audit.get("confidence_tier"),
                                    "llm_failure_hint": audit.get("llm_failure_hint"),
                                    "attestation_schema": attestation.get(
                                        "schema_version"
                                    ),
                                    "attestation_hash": attestation.get("payload_hash"),
                                    "solana_proof_status": (
                                        attestation.get("solana") or {}
                                    ).get("devnet_proof_status"),
                                }
                                st.code(_safe_json(_meta), language="json")
                                if isinstance(pgx_structured, dict) and pgx_structured:
                                    st.caption("Deterministic PGx (structured)")
                                    st.code(_safe_json(pgx_structured), language="json")
                                if isinstance(novel_payload, dict) and novel_payload:
                                    st.caption("Novel-drug evidence summary")
                                    st.code(_safe_json(novel_payload), language="json")
                            if lottie_success:
                                st_lottie(
                                    lottie_success,
                                    height=100,
                                    key="success",
                                    loop=False,
                                )

                        with pipe_tab2:
                            st.markdown("### Genetics used in this prediction")
                            if genetics_summary:
                                st.info(genetics_summary)
                            if genetics_summary and "Warfarin PGx:" in genetics_summary:
                                st.markdown("#### Warfarin PGx (deterministic)")
                                warfarin_snippet = next(
                                    (
                                        s.strip()
                                        for s in genetics_summary.split(",")
                                        if "Warfarin PGx:" in s
                                    ),
                                    None,
                                )
                                if warfarin_snippet:
                                    st.success(warfarin_snippet)
                            if genetics_summary and "Statin PGx:" in genetics_summary:
                                st.markdown("#### Statin Myopathy PGx (deterministic)")
                                for part in genetics_summary.split(","):
                                    if "Statin PGx:" in part:
                                        st.success(part.strip())
                                        break
                            st.markdown("#### Full patient profile")
                            st.text(profile_to_use)

                        with pipe_tab3:
                            st.markdown("### Similar drugs retrieved (RAG context)")
                            # Explicitly show when mock fallback was used for this run
                            if (
                                isinstance(audit, dict)
                                and audit.get("vector_backend", "") == "mock"
                            ):
                                st.warning(
                                    "Using mock similar-drug list (vector DB unavailable or not configured)."
                                )
                            if similar_drugs_used:
                                for i, drug in enumerate(similar_drugs_used, 1):
                                    st.markdown(f"**{i}.** {drug}")
                            else:
                                st.caption("No similar drugs returned by this run.")
                            if context_sources:
                                st.markdown("**Sources:** " + context_sources)

                        with pipe_tab4:
                            st.markdown("### Web3 verification proof")
                            if attestation:
                                solana = attestation.get("solana") or {}
                                st.success(
                                    "This simulation output is cryptographically hashed inside the analysis pipeline. "
                                    "Only the schema label and hash are sent on-chain when you anchor it."
                                )
                                p1, p2, p3 = st.columns([2, 1, 1])
                                with p1:
                                    st.text_input(
                                        "Payload hash",
                                        value=attestation.get("payload_hash", ""),
                                        key="simulation_attestation_hash",
                                    )
                                with p2:
                                    st.text_input(
                                        "Schema",
                                        value=attestation.get("schema_version", ""),
                                        key="simulation_attestation_schema",
                                    )
                                with p3:
                                    st.text_input(
                                        "Status",
                                        value=solana.get("devnet_proof_status", ""),
                                        key="simulation_attestation_status",
                                    )
                                st.caption(attestation.get("privacy_model", ""))
                                st.code(solana.get("memo", ""), language="text")
                                if solana.get("explorer_url"):
                                    st.link_button(
                                        "Open Solana Explorer",
                                        solana["explorer_url"],
                                    )
                                elif backend_online:
                                    st.caption(
                                        "To anchor this run, enable the Solana devnet checkbox before running the simulation."
                                    )
                                submission_result = st.session_state.get(
                                    "simulation_attestation_submission_result"
                                )
                                if submission_result:
                                    with st.expander(
                                        "Latest Solana submission result",
                                        expanded=bool(
                                            submission_result.get("submitted")
                                        ),
                                    ):
                                        st.json(submission_result)
                                st.download_button(
                                    "⬇️ Download simulation proof JSON",
                                    data=_safe_json(
                                        {
                                            "drug_name": drug_name,
                                            "risk_level": risk_level,
                                            "attestation": attestation,
                                        }
                                    ),
                                    file_name=f"anukriti_simulation_proof_{drug_name}.json",
                                    mime="application/json",
                                )
                                with st.expander("Raw attestation", expanded=False):
                                    st.json(attestation)
                            else:
                                st.info(
                                    "No attestation returned. Start the FastAPI backend with the updated code and rerun the simulation."
                                )

                    else:
                        progress_placeholder.empty()
                        st.error(
                            "Simulation could not complete. Try again or use Manual profile."
                        )
                else:
                    progress_placeholder.empty()
                    st.error(
                        "No patient profile available. Select Manual phenotypes or ensure VCF data is loaded."
                    )

            except Exception as e:
                progress_placeholder.empty()
                st.error(f"Error: {e}")

elif nav == "Batch Mode":
    st.markdown("### 📦 High-Throughput Batch Analysis")
    st.markdown(
        "Run cohort-based population simulations or upload a CSV to process multiple patients."
    )

    # Cohort-based population simulation (like Analytics demo)
    st.markdown("#### 🌍 Cohort-Based Population Simulation")
    with st.expander("Configure cohort", expanded=True):
        col_cs, col_drug = st.columns(2)
        with col_cs:
            cohort_size = st.slider(
                "Cohort size",
                min_value=50,
                max_value=2000,
                value=100,
                step=50,
                help="Number of diverse synthetic patients to simulate",
            )
        with col_drug:
            drug = st.selectbox(
                "Drug",
                [
                    "Warfarin",
                    "Clopidogrel",
                    "Codeine",
                    "Azathioprine",
                    "Fluorouracil",
                    "Capecitabine",
                ],
                help="Drug for response simulation",
            )
        st.caption(
            "Population mix (AFR, EUR, EAS, SAS, AMR) uses default distribution."
        )
    if st.button("🚀 Run Cohort Simulation", key="batch_cohort_run"):
        api_url = os.getenv("API_URL", "http://127.0.0.1:8000")
        if "localhost" in api_url:
            api_url = api_url.replace("localhost", "127.0.0.1")
        status_ph = st.empty()
        try:
            jr = requests.post(
                f"{api_url}/jobs/population-simulate",
                json={"cohort_size": cohort_size, "drug": drug},
                timeout=10,
            )
            jr.raise_for_status()
            job_id = jr.json().get("job_id")
            if not job_id:
                raise RuntimeError("Job creation failed: missing job_id")

            status_ph.info(f"⏳ Cohort job queued ({job_id[:8]}). Running…")
            poll_start = time.time()
            while True:
                if (time.time() - poll_start) > 180:
                    raise TimeoutError("Cohort job timed out")
                gr = requests.get(f"{api_url}/jobs/{job_id}", timeout=10)
                gr.raise_for_status()
                job = gr.json()
                if job.get("message"):
                    status_ph.info(f"⏳ {job.get('message')}")
                if job.get("status") == "succeeded":
                    data = job.get("result") or {}
                    break
                if job.get("status") == "failed":
                    raise RuntimeError(job.get("error") or "Cohort job failed")
                time.sleep(1.5)

            demo_sim = (data or {}).get("demo_simulation", {})
            if demo_sim:
                status_ph.empty()
                st.success("✅ Cohort simulation completed!")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**📊 Cohort Overview**")
                    st.write(f"Drug: {demo_sim.get('drug', 'N/A')}")
                    st.write(
                        f"Cohort Size: {demo_sim.get('cohort_size', 0):,} patients"
                    )
                    st.write(
                        f"AWS Lambda: {'✅ Yes' if demo_sim.get('aws_lambda_used') else '❌ No'}"
                    )
                    if demo_sim.get("step_functions_used") is not None:
                        st.write(
                            f"Step Functions: {'✅ Yes' if demo_sim.get('step_functions_used') else '❌ No'}"
                        )
                with c2:
                    st.markdown("**🌍 Population Diversity**")
                    for pop, count in demo_sim.get("population_breakdown", {}).items():
                        st.write(f"{pop}: {count} patients")
                risk_dist = demo_sim.get("risk_distribution", {})
                if risk_dist:
                    st.markdown("**⚠️ Risk Distribution**")
                    st.bar_chart(risk_dist)

                gene_ph = demo_sim.get("gene_phenotype_distribution") or {}
                if isinstance(gene_ph, dict) and gene_ph:
                    st.markdown("**🧬 Gene Phenotype Distributions**")
                    trg = DRUG_GENE_TRIGGERS.get(str(drug).strip().lower(), [])
                    preferred = [g for g in trg if g in gene_ph] or list(gene_ph.keys())
                    gene_sel = st.selectbox(
                        "Select gene",
                        preferred,
                        key="cohort_gene_sel",
                    )
                    dist = gene_ph.get(gene_sel, {}) if gene_sel else {}
                    if dist:
                        st.bar_chart(dist)

                perf = demo_sim.get("performance_metrics", {})
                if perf:
                    st.markdown("**⏱️ Performance**")
                    st.write(
                        f"Throughput: {perf.get('throughput_patients_per_minute', 0):.1f} patients/min"
                    )
                    st.write(f"Total time: {perf.get('total_time_seconds', 0):.2f}s")

                try:
                    import csv
                    import io

                    out = io.StringIO()
                    w = csv.writer(out)
                    w.writerow(["metric", "value"])
                    w.writerow(["drug", demo_sim.get("drug")])
                    w.writerow(["cohort_size", demo_sim.get("cohort_size")])
                    for pop, count in (
                        demo_sim.get("population_breakdown") or {}
                    ).items():
                        w.writerow([f"pop_{pop}", count])
                    for k, v in (demo_sim.get("risk_distribution") or {}).items():
                        w.writerow([f"risk_{k}", v])
                    for k, v in (perf or {}).items():
                        w.writerow([f"perf_{k}", v])
                    st.download_button(
                        "⬇️ Download Cohort Summary (CSV)",
                        data=out.getvalue(),
                        file_name=f"anukriti_cohort_summary_{drug}.csv",
                        mime="text/csv",
                        key="download_cohort_summary",
                    )
                except Exception:
                    pass
            else:
                status_ph.empty()
                st.warning("No simulation data returned.")
        except Exception as e:
            status_ph.empty()
            st.error(f"Cohort simulation error: {e}")

    st.markdown("---")
    st.markdown("#### 📄 CSV Cohort Upload")
    st.markdown(
        "Upload a CSV with patient data for per-patient pharmacogenomic analysis. "
        "Required columns: `patient_id`, `drug_name`. "
        "Optional gene columns: `CYP2D6`, `CYP2C19`, `CYP2C9`, `CYP3A4`, `CYP3A5`, `CYP1A2`, `CYP2B6`, "
        "`NAT2`, `UGT1A1`, `SLCO1B1`, `VKORC1`, `TPMT`, `DPYD`, `GSTM1`, `GSTT1`, `HLA_B5701`. "
        "Optional: `population` (AFR/EUR/EAS/SAS/AMR) for ancestry-aware confidence scoring."
    )
    # Sample CSV template download
    sample_csv = (
        "patient_id,drug_name,population,CYP2D6,CYP2C19,CYP2C9,CYP3A4,CYP3A5,CYP1A2,CYP2B6,NAT2,UGT1A1,SLCO1B1,VKORC1,TPMT,DPYD,GSTM1,GSTT1,HLA_B5701\n"
        "PT-001,Warfarin,EUR,Extensive Metabolizer (Normal),Extensive Metabolizer (Normal),Poor Metabolizer,,,,,,,High Sensitivity,,,,,,\n"
        "PT-002,Codeine,AFR,Poor Metabolizer,,,,,,,,,,,,,,,\n"
        "PT-003,Tacrolimus,EUR,,,,Extensive Metabolizer (Normal),Poor Metabolizer,,,,,,,,,,,\n"
        "PT-004,Efavirenz,AFR,,,,,,Poor Metabolizer,,,,,,,,,,\n"
        "PT-005,Isoniazid,SAS,,,,,,,Slow Acetylator (Poor),,,,,,,,,\n"
        "PT-006,Abacavir,EUR,,,,,,,,,,,,,,,,HLA-B*57:01 proxy: negative\n"
    )
    st.download_button(
        "Download Sample CSV Template",
        data=sample_csv,
        file_name="pgx_batch_template.csv",
        mime="text/csv",
        key="download_template",
    )
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded_file:
        import pandas as pd

        df = pd.read_csv(uploaded_file)
        st.dataframe(df.head(10), use_container_width=True)
        st.caption(f"{len(df)} patients loaded")
        if st.button("Run Batch Pipeline", key="batch_csv_run"):
            api_url = os.getenv("API_URL", "http://127.0.0.1:8000")
            if "localhost" in api_url:
                api_url = api_url.replace("localhost", "127.0.0.1")
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            gene_cols = [
                "CYP2D6",
                "CYP2C19",
                "CYP2C9",
                "CYP3A4",
                "CYP3A5",
                "CYP1A2",
                "CYP2B6",
                "NAT2",
                "UGT1A1",
                "SLCO1B1",
                "VKORC1",
                "TPMT",
                "DPYD",
                "GSTM1",
                "GSTT1",
                "HLA_B5701",
            ]
            _default_for_gene = {
                "VKORC1": "Normal Sensitivity",
                "NAT2": "Rapid Acetylator (Normal)",
                "GSTM1": "Gene present (normal activity)",
                "GSTT1": "Gene present (normal activity)",
                "HLA_B5701": "HLA-B*57:01 proxy: negative",
            }

            for idx, row in df.iterrows():
                pct = (idx + 1) / len(df)
                progress_bar.progress(pct)
                status_text.text(f"Processing patient {idx + 1}/{len(df)}...")
                patient_id = row.get("patient_id", f"PT-{idx}")
                drug = row.get("drug_name", "Warfarin")
                genetics_lines = []
                for g in gene_cols:
                    if g in row and pd.notna(row[g]):
                        genetics_lines.append(f"- {g}: {row[g]}")
                    else:
                        genetics_lines.append(
                            f"- {g}: {_default_for_gene.get(g, 'Extensive Metabolizer (Normal)')}"
                        )
                profile = f"ID: {patient_id}\nAge: 45\nGenetics:\n" + "\n".join(
                    genetics_lines
                )
                try:
                    _ui_b = st.session_state.get(
                        "ui_llm_backend", _DEFAULT_UI_LLM_BACKEND
                    )
                    _batch_backend = (
                        "claude"
                        if "Claude" in _ui_b
                        else (
                            "qvac"
                            if "QVAC" in _ui_b
                            else (
                                "bedrock"
                                if "Bedrock" in _ui_b
                                else "nova"
                                if "Nova" in _ui_b
                                else "gemini"
                            )
                        )
                    )
                    _batch_json = {
                        "drug_name": str(drug),
                        "patient_profile": profile,
                        "llm_backend": _batch_backend,
                    }
                    if _batch_backend == "nova":
                        _batch_json["nova_variant"] = st.session_state.get(
                            "ui_nova_variant", "lite"
                        )
                    resp = requests.post(
                        f"{api_url}/analyze",
                        json=_batch_json,
                        timeout=60,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        st.session_state["simulation_count"] = (
                            st.session_state.get("simulation_count", 0) + 1
                        )
                        row_result = {
                            "patient_id": patient_id,
                            "drug": drug,
                            "risk_level": data.get("risk_level", "Unknown"),
                            "status": "success",
                        }
                        _att = data.get("attestation") or {}
                        if _att:
                            row_result["proof_hash"] = _att.get("payload_hash", "")
                            row_result["proof_status"] = (_att.get("solana") or {}).get(
                                "devnet_proof_status", ""
                            )
                        # Ancestry-aware confidence scoring
                        pop = row.get("population", "") if "population" in row else ""
                        if pop and str(pop).strip().upper() in {
                            "AFR",
                            "EUR",
                            "EAS",
                            "SAS",
                            "AMR",
                        }:
                            triggered = DRUG_GENE_TRIGGERS.get(
                                str(drug).strip().lower(), []
                            )
                            if triggered:
                                conf = compute_ancestry_confidence(
                                    triggered[0], str(pop).strip().upper()
                                )
                                row_result["confidence"] = conf.get("confidence", "")
                                row_result["evidence_level"] = conf.get(
                                    "evidence_level", ""
                                )
                                row_result["population"] = str(pop).strip().upper()
                        results.append(row_result)
                    else:
                        results.append(
                            {
                                "patient_id": patient_id,
                                "drug": drug,
                                "risk_level": "Error",
                                "status": f"API error {resp.status_code}",
                            }
                        )
                except Exception as e:
                    results.append(
                        {
                            "patient_id": patient_id,
                            "drug": drug,
                            "risk_level": "Error",
                            "status": str(e),
                        }
                    )
            progress_bar.progress(1.0)
            status_text.text("Batch processing complete!")
            results_df = pd.DataFrame(results)
            st.success(f"Processed {len(results_df)} patients")
            st.dataframe(results_df, use_container_width=True)
            risk_counts = results_df["risk_level"].value_counts()
            st.markdown("**Risk Distribution**")
            st.bar_chart(risk_counts)
            csv_output = results_df.to_csv(index=False)
            st.download_button(
                "Download Results CSV",
                data=csv_output,
                file_name="batch_pgx_results.csv",
                mime="text/csv",
            )

elif nav == "Datasets":
    st.markdown("### 🗂️ VCF Datasets Manager")
    st.caption(
        "Manage available VCF datasets (local, S3, and temporary uploads). "
        "Local datasets are read from `data/genomes`. Upload datasets live under server temp storage."
    )

    api_url = os.getenv("API_URL", "http://127.0.0.1:8000")
    if "localhost" in api_url:
        api_url = api_url.replace("localhost", "127.0.0.1")

    src = st.radio("Source", ["Local", "S3", "Auto"], horizontal=True, key="ds_src")
    src_param = "local" if src == "Local" else ("s3" if src == "S3" else "auto")
    try:
        r = requests.get(
            f"{api_url}/vcf-datasets",
            params={"source": src_param},
            timeout=15 if src_param == "s3" else 8,
        )
        r.raise_for_status()
        datasets = r.json().get("datasets", [])
    except Exception as e:
        st.error(f"Failed to load datasets: {e}")
        datasets = []

    if not datasets:
        st.info("No datasets found for this source.")
    else:
        rows = []
        for d in datasets:
            dsid = d.get("dataset_id", "")
            source = d.get("source", "")
            label = d.get("label", "")
            chrom = d.get("chrom", "")
            ref = dsid.split("|", 2)[-1] if dsid and "|" in dsid else ""
            indexed = None
            size_mb = None
            if source == "local" and ref and os.path.exists(ref):
                try:
                    indexed = os.path.exists(ref + ".tbi")
                    size_mb = round(os.path.getsize(ref) / (1024 * 1024), 2)
                except Exception:
                    pass
            rows.append(
                {
                    "source": source,
                    "chrom": chrom,
                    "label": label,
                    "indexed": indexed,
                    "size_mb": size_mb,
                    "dataset_id": dsid,
                }
            )

        st.dataframe(rows, use_container_width=True, hide_index=True)

        upload_rows = [x for x in rows if x.get("source") == "upload"]
        if upload_rows:
            st.markdown("#### 🧹 Cleanup uploaded datasets")
            for ur in upload_rows:
                dsid = ur.get("dataset_id", "")
                upload_id = dsid.split("|", 2)[-1] if dsid else ""
                cols = st.columns([6, 2])
                with cols[0]:
                    st.caption(f"Upload: `{upload_id}` · {ur.get('label','')}")
                with cols[1]:
                    if st.button("Delete", key=f"del_upload_{upload_id}"):
                        try:
                            dr = requests.delete(
                                f"{api_url}/vcf-upload/{upload_id}", timeout=10
                            )
                            dr.raise_for_status()
                            st.success(f"Deleted upload {upload_id}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Delete failed: {e}")

elif nav == "Solana Proofs":
    st.markdown("### 🔐 Anukriti Lite: Solana Trial Export Proofs")
    st.caption(
        "Lightweight Web3 verification loop: deterministic PGx simulation output → "
        "canonical SHA-256 hash → optional Solana memo reference → local verification → tamper failure."
    )

    api_url = os.getenv("API_URL", "http://127.0.0.1:8000")
    if "localhost" in api_url:
        api_url = api_url.replace("localhost", "127.0.0.1")

    st.info(
        "Privacy model: sensitive genomic data and sample-level PGx rows stay off-chain. "
        "The Solana memo contains only the Anukriti schema label and output hash."
    )
    st.markdown("#### Submission wedge")
    wedge_col, solana_col, qvac_col = st.columns(3)
    with wedge_col:
        st.markdown(
            "**Colosseum**\n\n"
            "Deterministic PGx trial exports become reproducible proof artifacts, "
            "not generic healthcare records."
        )
    with solana_col:
        st.markdown(
            "**Solana**\n\n"
            "The chain receives only `anukriti:<schema>:<hash>` memo text; cohort "
            "rows stay off-chain."
        )
    with qvac_col:
        st.markdown(
            "**QVAC**\n\n"
            "Local explanations can describe deterministic PGx results without "
            "becoming the clinical decision engine."
        )

    proof_col, action_col = st.columns([2, 1])
    with proof_col:
        workflow = st.radio(
            "Workflow",
            ["clopidogrel_cyp2c19", "warfarin_cyp2c9_vkorc1"],
            format_func=lambda x: {
                "clopidogrel_cyp2c19": "Clopidogrel / CYP2C19",
                "warfarin_cyp2c9_vkorc1": "Warfarin / CYP2C9 + VKORC1",
            }.get(x, x),
            horizontal=True,
            key="solana_proof_workflow",
        )
        submit_to_devnet = st.checkbox(
            "Submit memo to Solana devnet with local CLI",
            value=False,
            help=(
                "Optional. Requires a configured and funded devnet keypair on the backend host. "
                "Leave off for the prepared proof demo."
            ),
        )
    with action_col:
        st.markdown("")
        st.markdown("")
        run_proof = st.button("Generate Proof", key="run_solana_proof")

    if run_proof:
        try:
            with st.spinner("Generating deterministic export and proof artifact..."):
                resp = requests.post(
                    f"{api_url}/lite/demo",
                    json={
                        "workflow": workflow,
                        "submit_to_devnet": bool(submit_to_devnet),
                    },
                    timeout=60 if submit_to_devnet else 15,
                )
                resp.raise_for_status()
                st.session_state["solana_proof_demo"] = resp.json()
        except Exception as e:
            st.error(f"Proof generation failed: {e}")

    proof_demo = st.session_state.get("solana_proof_demo")
    if proof_demo:
        export = proof_demo.get("export", {})
        attestation = export.get("attestation", {})
        solana = attestation.get("solana", {})
        verification = proof_demo.get("verification", {})
        tamper = (proof_demo.get("tamper_demo") or {}).get("verification", {})

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Workflow", export.get("drug_name", "N/A"))
        m2.metric("Rows", export.get("requested_samples", 0))
        m3.metric("Proof", "Valid" if verification.get("valid") else "Invalid")
        m4.metric(
            "Tamper Test", "Rejected" if not tamper.get("valid", True) else "Passed"
        )

        st.markdown("#### Proof Artifact")
        st.code(solana.get("memo", ""), language="text")
        hash_col, status_col = st.columns([2, 1])
        with hash_col:
            st.text_input(
                "Payload hash",
                value=attestation.get("payload_hash", ""),
                key="solana_payload_hash",
            )
        with status_col:
            st.text_input(
                "Devnet proof status",
                value=solana.get("devnet_proof_status", ""),
                key="solana_proof_status",
            )

        explorer_url = solana.get("explorer_url")
        if explorer_url:
            st.link_button("Open Solana Explorer", explorer_url)
        elif st.button("Anchor this proof to Solana devnet", key="lite_submit_memo"):
            submission = _submit_attestation_from_ui(
                api_url,
                attestation,
                key_prefix="lite_attestation",
            )
            updated_attestation = (submission or {}).get("attestation")
            if updated_attestation:
                proof_demo["export"]["attestation"] = updated_attestation
                st.session_state["solana_proof_demo"] = proof_demo
                st.rerun()

        lite_submission_result = st.session_state.get("lite_attestation_submission_result")
        if lite_submission_result:
            with st.expander("Latest Solana submission result", expanded=False):
                st.json(lite_submission_result)

        st.markdown("#### Cohort Export Rows")
        rows = export.get("rows", [])
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)

        tab_export, tab_verify, tab_tamper = st.tabs(
            ["Raw export", "Verification", "Tamper failure"]
        )
        with tab_export:
            st.json(export)
        with tab_verify:
            st.json(verification)
        with tab_tamper:
            if tamper.get("valid") is False:
                st.error(
                    "Tamper detected: recomputed export hash does not match the attested hash."
                )
            st.json(proof_demo.get("tamper_demo", {}))

        st.download_button(
            "Download proof JSON",
            data=_safe_json(proof_demo),
            file_name="anukriti_lite_solana_proof.json",
            mime="application/json",
        )
    else:
        st.markdown("#### What this page proves")
        st.markdown(
            "- Generates a de-identified trial export fixture for the Colosseum demo.\n"
            "- Builds the same attestation format used by `/trial/export`.\n"
            "- Verifies the original export locally.\n"
            "- Modifies one row and shows that verification fails.\n"
            "- Optionally submits the memo via Solana CLI when a devnet wallet is configured."
        )

elif nav == "Analytics":
    st.markdown("### 📊 Platform Analytics")

    # System Metrics (session-based)
    _sim_count = st.session_state.get("simulation_count", 0)
    _last_ms = st.session_state.get("last_response_ms", None)
    _resp_display = f"{_last_ms}ms" if _last_ms is not None else "N/A"
    try:
        _health = requests.get(f"{api_url}/", timeout=3)
        _backend_status = "Connected" if _health.status_code == 200 else "Disconnected"
    except Exception:
        _backend_status = "Disconnected"
    c1, c2, c3 = st.columns(3)
    c1.metric("Simulations (this session)", f"{_sim_count:,}")
    c2.metric("Last Response Time", _resp_display)
    c3.metric("Backend Status", _backend_status)

    # RAG Scoreboard (retrieval quality)
    st.markdown("### 🧠 RAG Scoreboard (Retrieval Quality)")
    st.caption(
        "Measures whether the PGx retriever is actually fetching the right CPIC-aligned row "
        "(precision@k / recall@k / MRR / nDCG)."
    )
    with st.expander("Run retrieval evaluation", expanded=False):
        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            eval_limit = st.number_input(
                "Queries",
                min_value=5,
                max_value=500,
                value=50,
                step=5,
                key="rag_eval_limit",
            )
        with col_b:
            eval_top_k = st.number_input(
                "Top-K retrieved",
                min_value=3,
                max_value=50,
                value=10,
                step=1,
                key="rag_eval_top_k",
            )
        with col_c:
            eval_ks = st.text_input(
                "Report k values", value="1,3,5,10", key="rag_eval_ks"
            )
        with col_d:
            eval_examples = st.number_input(
                "Show examples",
                min_value=3,
                max_value=25,
                value=10,
                step=1,
                key="rag_eval_examples",
            )

        sft_path = st.text_input(
            "Labeled queries JSONL",
            value="data/training/pgx_sft.jsonl",
            key="rag_eval_queries_path",
            help="Generated by training/lm_finetune/export_pgx_sft_jsonl.py",
        )

        run_btn = st.button("▶ Run RAG retrieval eval", key="rag_eval_run")
        if run_btn:
            try:
                ks = [int(x.strip()) for x in eval_ks.split(",") if x.strip()]
                with st.spinner(
                    "Running retrieval evaluation (may call Bedrock embeddings)..."
                ):
                    res = evaluate_pgx_retrieval(
                        Path(sft_path),
                        top_k=int(eval_top_k),
                        ks=ks,
                        limit=int(eval_limit),
                        examples=int(eval_examples),
                    )
                st.session_state["rag_eval_result"] = res
                st.success("Evaluation complete.")
            except Exception as e:
                st.error(f"RAG evaluation failed: {e}")

    res = st.session_state.get("rag_eval_result")
    if res:
        ks_sorted = sorted(res.scores.precision_at_k.keys())
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Queries scored", f"{res.n_queries:,}")
        m2.metric("Misses (no relevant in top-k)", f"{res.misses:,}")
        m3.metric("MRR", f"{res.scores.mrr:.3f}")
        # highlight precision@3 when available
        p3 = res.scores.precision_at_k.get(3)
        m4.metric("Precision@3", f"{p3:.3f}" if p3 is not None else "N/A")

        st.markdown("**Aggregate metrics**")
        rows = []
        for k in ks_sorted:
            rows.append(
                {
                    "k": k,
                    "precision@k": round(res.scores.precision_at_k[k], 3),
                    "recall@k": round(res.scores.recall_at_k[k], 3),
                    "nDCG@k": round(res.scores.ndcg_at_k[k], 3),
                }
            )
        st.dataframe(rows, hide_index=True, use_container_width=True)

        st.markdown("**Example queries (hit/miss)**")
        ex_rows = []
        for ex in res.examples:
            ex_rows.append(
                {
                    "hit": "✅" if ex.hit else "❌",
                    "rr": round(ex.rr, 3),
                    "relevant_doc_id": ex.relevant_doc_id,
                    "top_retrieved": "\n".join(ex.ranked_doc_ids[:5]),
                    "query_preview": ex.query_preview,
                }
            )
        st.dataframe(ex_rows, hide_index=True, use_container_width=True)

    # ZerveHack demo panel: evidence + operational metrics
    st.markdown("### 🛡️ Evidence & Trust Dashboard")
    st.caption(
        "A judge-friendly view: when evidence is weak, we refuse to generate confident-sounding medical explanations."
    )
    with st.expander("Open Evidence & Trust Dashboard", expanded=False):
        st.markdown("**Wow moment (safety gate): vague query → refusal**")
        st.caption(
            "Most AI systems would hallucinate here. Ours knows when not to answer."
        )
        try:
            zs = requests.get(f"{api_url}/zervehack/status", timeout=8)
            if zs.status_code == 200:
                st.markdown("**Backend status**")
                st.json(zs.json())
            else:
                st.warning(f"Status request failed: {zs.status_code}")
        except Exception as e:
            st.warning(f"Could not fetch /zervehack/status: {e}")

        st.markdown("**Grounding monitor**")
        demo_q = st.text_area(
            "Query",
            value="Is this safe for me? Explain the risk.",
            height=120,
            key="zervehack_query",
        )
        gate_on = st.checkbox("Enforce evidence-confidence gating", value=True)
        min_conf = st.slider(
            "Minimum confidence (top score) required",
            min_value=0.0,
            max_value=1.0,
            value=0.2,
            step=0.01,
        )
        demo_k = st.number_input(
            "Top-k",
            min_value=1,
            max_value=20,
            value=5,
            step=1,
            key="zervehack_topk",
        )
        if st.button("🔎 Retrieve evidence", key="zervehack_retrieve_btn"):
            try:
                rr = requests.post(
                    f"{api_url}/zervehack/retrieve",
                    json={
                        "query": demo_q,
                        "top_k": int(demo_k),
                        "min_confidence": float(min_conf),
                        "enforce_gating": bool(gate_on),
                    },
                    timeout=15,
                )
                rr.raise_for_status()
                payload = rr.json()
                conf = payload.get("confidence") or {}
                cols = st.columns(3)
                cols[0].metric("Decision", str(conf.get("decision", "unknown")))
                cols[1].metric("Top score", str(conf.get("top_score", "N/A")))
                cols[2].metric("Min required", str(conf.get("min_confidence", "N/A")))

                msg = payload.get("message")
                if conf.get("decision") == "refuse":
                    st.error(msg or "Refused due to low evidence confidence.")
                else:
                    if msg:
                        st.success(msg)
                st.markdown("**Retrieved evidence (with scores)**")
                st.json(payload.get("docs", []))
            except Exception as e:
                st.error(f"Retrieve failed: {e}")

        st.divider()
        st.markdown("**Hint vs hintless (instant visual)**")
        try:
            import json as _json
            from pathlib import Path as _Path

            hint = _json.loads(
                _Path("zervehack/artifacts/pgx_retrieval_eval.json").read_text(
                    encoding="utf-8"
                )
            )
            hintless = _json.loads(
                _Path("zervehack/artifacts/pgx_retrieval_eval_hintless.json").read_text(
                    encoding="utf-8"
                )
            )
            mrr_hint = float((hint.get("scores") or {}).get("mrr", 0.0))
            mrr_hintless = float(((hintless.get("scores") or {}).get("mrr") or 0.0))
            st.bar_chart({"MRR (with hints)": mrr_hint, "MRR (hintless)": mrr_hintless})
        except Exception as e:
            st.caption(f"(Chart unavailable locally: {e})")

    # AWS Integration Status
    st.markdown("### ☁️ AWS Integration Status")

    try:
        deep_aws = st.checkbox(
            "Detailed AWS status (may take longer)",
            value=False,
            key="analytics_aws_deep",
        )
        aws_timeout = 15 if deep_aws else 3
        aws_status_response = requests.get(
            f"{api_url}/aws-status?deep={1 if deep_aws else 0}",
            timeout=aws_timeout,
        )
        if aws_status_response.status_code == 200:
            aws_status = aws_status_response.json()
            aws_info = aws_status.get("aws_integration", {})

            # AWS Services Status
            aws_col1, aws_col2, aws_col3 = st.columns(3)

            with aws_col1:
                if aws_info.get("s3_genomic_connected"):
                    st.success("✅ S3 Genomic Data")
                    st.caption(f"📊 {aws_info.get('vcf_files_count', 0)} VCF files")
                    st.caption(
                        f"🪣 {aws_info.get('s3_bucket_info', {}).get('bucket_name', 'N/A')}"
                    )
                else:
                    st.info("💾 Local VCF Files")

            with aws_col2:
                if aws_info.get("lambda_available"):
                    st.success("⚡ Lambda Functions")
                    st.caption(f"🔧 {aws_info.get('lambda_function_name', 'N/A')}")
                else:
                    st.info("🖥️ Local Processing")

            with aws_col3:
                if aws_info.get("step_functions_available"):
                    st.success("🔄 Step Functions")
                    st.caption("🎯 Trial Orchestration")
                else:
                    st.info("📝 Manual Workflows")

            # AWS Account Information
            if aws_status.get("status") == "live":
                st.success("🌟 **Live AWS Integration**")
            else:
                st.info("🏠 **Local Development Mode** - No AWS services connected")

        else:
            st.warning("⚠️ Could not fetch AWS status")

    except Exception as e:
        st.error(f"❌ AWS status check failed: {str(e)}")

    # Population Simulation Demo
    st.markdown("### 🌍 Population Simulation Capabilities")

    if st.button("🚀 Run Demo Population Simulation", key="pop_sim_demo"):
        with st.spinner("Running population simulation demo..."):
            try:
                pop_response = requests.get(
                    f"{api_url}/population-simulate", timeout=30
                )
                if pop_response.status_code == 200:
                    pop_data = pop_response.json()
                    demo_sim = pop_data.get("demo_simulation", {})

                    if demo_sim:
                        st.success("✅ Population simulation completed!")

                        # Display results
                        sim_col1, sim_col2 = st.columns(2)

                        with sim_col1:
                            st.markdown("**📊 Cohort Overview**")
                            st.write(f"Drug: {demo_sim.get('drug', 'N/A')}")
                            st.write(
                                f"Cohort Size: {demo_sim.get('cohort_size', 0):,} patients"
                            )
                            st.write(
                                f"AWS Lambda Used: {'✅ Yes' if demo_sim.get('aws_lambda_used') else '❌ No'}"
                            )
                            if demo_sim.get("step_functions_used") is not None:
                                st.write(
                                    f"Step Functions: {'✅ Yes' if demo_sim.get('step_functions_used') else '❌ No'}"
                                )

                        with sim_col2:
                            st.markdown("**🌍 Population Diversity**")
                            pop_breakdown = demo_sim.get("population_breakdown", {})
                            for pop, count in pop_breakdown.items():
                                st.write(f"{pop}: {count} patients")

                        # Risk Distribution
                        risk_summary = demo_sim.get("risk_distribution", {})
                        if risk_summary:
                            st.markdown("**⚠️ Risk Distribution**")
                            st.bar_chart(risk_summary)

                        # Performance Metrics
                        perf_metrics = demo_sim.get("performance_metrics", {})
                        if perf_metrics:
                            st.markdown("**⚡ Performance Metrics**")
                            perf_col1, perf_col2, perf_col3 = st.columns(3)
                            perf_col1.metric(
                                "Processing Time",
                                f"{perf_metrics.get('total_time_seconds', 0):.2f}s",
                            )
                            perf_col2.metric(
                                "Patients/Second",
                                f"{perf_metrics.get('patients_per_second', 0):.0f}",
                            )
                            perf_col3.metric(
                                "Cost per Patient",
                                f"${perf_metrics.get('cost_per_patient', 0):.4f}",
                            )
                    else:
                        st.error("❌ Population simulation failed")

                else:
                    st.error(
                        f"❌ Population simulation request failed: {pop_response.status_code}"
                    )

            except Exception as e:
                st.error(f"❌ Population simulation error: {str(e)}")

    # Validation Results
    st.markdown("### 🔬 Validation Results")
    st.markdown(
        "Anukriti has been validated across **2,253 patients** using four independent strategies."
    )

    val_tab1, val_tab2, val_tab3, val_tab4 = st.tabs(
        [
            "GeT-RM Benchmark",
            "Clinical Cases",
            "Population Validation",
            "Ablation Study",
        ]
    )

    with val_tab1:
        st.markdown("**GeT-RM Concordance (240 samples, 8 genes)**")
        st.markdown(
            "Diplotype concordance against CDC GeT-RM consensus genotypes, "
            "compared with published rates for PharmCAT, Aldy, and Stargazer."
        )
        import pandas as pd

        getrm_data = {
            "Gene": [
                "CYP2D6",
                "CYP2C19",
                "CYP2C9",
                "UGT1A1",
                "TPMT",
                "DPYD",
                "SLCO1B1",
                "VKORC1",
                "Overall",
            ],
            "N": [30, 30, 30, 30, 30, 30, 30, 30, 240],
            "Anukriti": [
                "100%",
                "100%",
                "100%",
                "100%",
                "100%",
                "100%",
                "100%",
                "100%",
                "100%",
            ],
            "PharmCAT": [
                "---",
                "96.7%",
                "95.7%",
                "95.7%",
                "97.1%",
                "94.3%",
                "95.0%",
                "99.0%",
                "96.2%",
            ],
            "Aldy": [
                "88.6%",
                "98.6%",
                "98.6%",
                "---",
                "98.6%",
                "97.1%",
                "97.0%",
                "---",
                "96.4%",
            ],
            "Stargazer": [
                "84.3%",
                "94.3%",
                "92.9%",
                "91.4%",
                "95.7%",
                "91.4%",
                "93.0%",
                "---",
                "91.9%",
            ],
        }
        st.dataframe(
            pd.DataFrame(getrm_data), hide_index=True, use_container_width=True
        )
        st.caption(
            "Anukriti's 100% reflects the deterministic CPIC translation layer. "
            "PharmCAT/Aldy/Stargazer rates are from end-to-end VCF calling (Halman et al. 2024)."
        )

    with val_tab2:
        st.markdown("**Published Clinical Case Reports (13 cases, 7 genes)**")
        st.markdown(
            "Validated against real adverse drug reactions from peer-reviewed literature."
        )
        cases_data = {
            "Gene": [
                "CYP2D6",
                "CYP2D6",
                "CYP2C19",
                "CYP2C9",
                "VKORC1",
                "DPYD",
                "DPYD",
                "TPMT",
                "TPMT",
                "UGT1A1",
                "SLCO1B1",
                "SLCO1B1",
                "CYP2D6",
            ],
            "Diplotype": [
                "*1/*1x3",
                "*4/*4",
                "*2/*2",
                "*3/*3",
                "AA",
                "*2A/*2A",
                "*1/*2A",
                "*3A/*3A",
                "*1/*3A",
                "*1/*28",
                "CC",
                "TC",
                "*4/*4",
            ],
            "Drug": [
                "Codeine",
                "Tramadol",
                "Clopidogrel",
                "Warfarin",
                "Warfarin",
                "5-FU",
                "5-FU",
                "Azathioprine",
                "Azathioprine",
                "Irinotecan",
                "Simvastatin",
                "Simvastatin",
                "Tramadol",
            ],
            "Outcome": [
                "Opioid intoxication",
                "Therapeutic failure",
                "Stent thrombosis",
                "Hemorrhage",
                "Extreme sensitivity",
                "Fatal toxicity",
                "Severe toxicity",
                "Pancytopenia",
                "Myelosuppression",
                "Gr4 neutropenia",
                "Myopathy (OR 16.9)",
                "Rhabdomyolysis",
                "Therapeutic failure",
            ],
            "Concordant": ["Y"] * 13,
        }
        st.dataframe(
            pd.DataFrame(cases_data), hide_index=True, use_container_width=True
        )
        st.success("13/13 (100%) phenotype concordance")

    with val_tab3:
        st.markdown("**Expanded Population Validation (2,000 patients, 5 ancestries)**")
        st.markdown(
            "Synthetic patients generated using gnomAD v4.1 allele frequencies "
            "with Hardy-Weinberg sampling."
        )
        pop_data = {
            "Gene": [
                "CYP2C19",
                "CYP2C19",
                "CYP2C9",
                "CYP2C9",
                "TPMT",
                "TPMT",
                "DPYD",
                "DPYD",
            ],
            "Metric": [
                "Concordance",
                "Sensitivity",
                "Concordance",
                "Sensitivity",
                "Concordance",
                "Sensitivity",
                "Concordance",
                "Sensitivity",
            ],
            "AFR": ["100%"] * 8,
            "EUR": ["100%"] * 8,
            "EAS": ["100%"] * 8,
            "SAS": ["100%"] * 8,
            "AMR": ["100%"] * 8,
        }
        st.dataframe(pd.DataFrame(pop_data), hide_index=True, use_container_width=True)

    with val_tab4:
        st.markdown("**Ablation Study — Component Contribution**")
        st.markdown(
            "Systematic removal of framework components to validate the hybrid design."
        )
        ablation_data = {
            "Condition": ["Full System", "No RAG", "No LLM", "LLM Only"],
            "CPIC": ["Yes", "Yes", "Yes", "No"],
            "RAG": ["Yes", "No", "No", "Yes"],
            "LLM": ["Yes", "Yes", "No", "Yes"],
            "Risk Accuracy": ["100%", "100%", "100%", "92%"],
            "Phenotype Accuracy": ["100%", "100%", "100%", "92%"],
            "Explanation Quality": ["0.95", "0.72", "0.00", "0.65"],
        }
        st.dataframe(
            pd.DataFrame(ablation_data), hide_index=True, use_container_width=True
        )
        st.info(
            "The deterministic CPIC engine alone achieves 100% accuracy. "
            "The LLM adds clinical explanations but is not relied upon for decisions."
        )

    # Capabilities Overview
    st.markdown("### 🎯 Platform Capabilities")

    cap_col1, cap_col2 = st.columns(2)

    with cap_col1:
        st.markdown("**🧬 Pharmacogenomics Engine**")
        st.write(
            "• 8-gene panel (CYP2D6, CYP2C19, CYP2C9, UGT1A1, SLCO1B1, VKORC1, TPMT, DPYD)"
        )
        st.write("• CPIC guideline compliance")
        st.write("• Deterministic PGx + AI explanation")
        st.write("• PDF report generation + CSV batch processing")

    with cap_col2:
        st.markdown("**☁️ Cloud-Native Architecture**")
        st.write("• S3 genomic data storage (16 VCF files)")
        st.write("• Lambda batch processing")
        st.write("• Step Functions orchestration")
        st.write("• Population-scale simulation (up to 10K patients)")

    # Gene Usage Distribution
    st.markdown("### 🧬 Gene Analysis Distribution")
    st.bar_chart(
        {
            "CYP2D6": 35,
            "CYP2C19": 25,
            "CYP2C9": 18,
            "UGT1A1": 7,
            "SLCO1B1": 5,
            "VKORC1": 5,
            "TPMT": 3,
            "DPYD": 2,
        }
    )

elif nav == "Population Dashboard":
    st.markdown("### 🌍 Population Allele-Frequency Dashboard")
    st.caption(
        "Visualise how pharmacogenomic variant frequencies and predicted phenotype "
        "distributions differ across global populations. Data from 1000 Genomes "
        "Phase 3 / gnomAD (simplified)."
    )

    import plotly.express as px
    import plotly.graph_objects as go

    from src.ancestry_risk import EVIDENCE_STRENGTH, POPULATION_VARIANT_FREQUENCIES

    _pop_genes = sorted(POPULATION_VARIANT_FREQUENCIES.keys())
    _pop_names = ["AFR", "EUR", "EAS", "SAS", "AMR"]
    _pop_labels = {
        "AFR": "African",
        "EUR": "European",
        "EAS": "East Asian",
        "SAS": "South Asian",
        "AMR": "Americas (Admixed)",
    }

    # ------- Heatmap: Allele Frequencies -------
    st.markdown("#### Allele Frequency Heatmap")
    _hm_gene = st.selectbox(
        "Select gene",
        _pop_genes,
        key="pop_dash_gene",
    )
    _gene_data = POPULATION_VARIANT_FREQUENCIES.get(_hm_gene, {})
    if _gene_data:
        _alleles = sorted(_gene_data.keys())
        _z = []
        for allele in _alleles:
            _row = [_gene_data[allele].get(p, 0.0) for p in _pop_names]
            _z.append(_row)

        _fig_hm = go.Figure(
            data=go.Heatmap(
                z=_z,
                x=[_pop_labels.get(p, p) for p in _pop_names],
                y=_alleles,
                colorscale="YlOrRd",
                text=[[f"{v:.3f}" for v in row] for row in _z],
                texttemplate="%{text}",
                colorbar=dict(title="Frequency"),
            )
        )
        _fig_hm.update_layout(
            title=f"{_hm_gene} Variant Allele Frequencies by Population",
            xaxis_title="Superpopulation",
            yaxis_title="Allele",
            height=max(300, len(_alleles) * 60 + 100),
        )
        st.plotly_chart(_fig_hm, use_container_width=True)
    else:
        st.info(f"No allele frequency data available for {_hm_gene}.")

    st.markdown("---")

    # ------- Bar Chart: Phenotype Distribution -------
    st.markdown("#### Predicted Phenotype Distribution")
    st.caption(
        "Estimated population-level phenotype distribution based on allele "
        "frequencies. For genes with two major functional alleles, a simplified "
        "Hardy-Weinberg model is applied."
    )
    _pheno_gene = st.selectbox(
        "Select gene for phenotype breakdown",
        _pop_genes,
        key="pop_dash_pheno_gene",
    )
    _pheno_data = POPULATION_VARIANT_FREQUENCIES.get(_pheno_gene, {})
    if _pheno_data:
        _pheno_rows: list[dict] = []
        for pop in _pop_names:
            total_var_freq = sum(_pheno_data[a].get(pop, 0.0) for a in _pheno_data)
            total_var_freq = min(total_var_freq, 0.99)

            pm_est = total_var_freq**2
            im_est = 2.0 * total_var_freq * (1.0 - total_var_freq)
            nm_est = max(0.0, 1.0 - pm_est - im_est)

            _pheno_rows.append(
                {
                    "Population": _pop_labels.get(pop, pop),
                    "Poor Metabolizer": round(pm_est * 100, 1),
                    "Intermediate Metabolizer": round(im_est * 100, 1),
                    "Normal Metabolizer": round(nm_est * 100, 1),
                }
            )

        import pandas as pd

        _df_pheno = pd.DataFrame(_pheno_rows)
        _df_melted = _df_pheno.melt(
            id_vars="Population",
            value_vars=[
                "Poor Metabolizer",
                "Intermediate Metabolizer",
                "Normal Metabolizer",
            ],
            var_name="Phenotype",
            value_name="Percentage (%)",
        )
        _fig_bar = px.bar(
            _df_melted,
            x="Population",
            y="Percentage (%)",
            color="Phenotype",
            barmode="stack",
            title=f"{_pheno_gene} — Estimated Phenotype Distribution by Population",
            color_discrete_map={
                "Poor Metabolizer": "#d62728",
                "Intermediate Metabolizer": "#ff7f0e",
                "Normal Metabolizer": "#2ca02c",
            },
        )
        _fig_bar.update_layout(height=450)
        st.plotly_chart(_fig_bar, use_container_width=True)
    else:
        st.info(f"No phenotype distribution data for {_pheno_gene}.")

    st.markdown("---")

    # ------- Evidence Strength Indicator -------
    st.markdown("#### Evidence Strength by Population")
    st.caption(
        "How well-characterised is each gene in each ancestry group? "
        "Scale: 0 (no evidence) → 1 (strong CPIC Level A evidence in that population)."
    )
    _ev_genes = sorted(EVIDENCE_STRENGTH.keys())
    _ev_z = []
    for gene in _ev_genes:
        _ev_z.append([EVIDENCE_STRENGTH[gene].get(p, 0.0) for p in _pop_names])

    _fig_ev = go.Figure(
        data=go.Heatmap(
            z=_ev_z,
            x=[_pop_labels.get(p, p) for p in _pop_names],
            y=_ev_genes,
            colorscale="Blues",
            text=[[f"{v:.2f}" for v in row] for row in _ev_z],
            texttemplate="%{text}",
            colorbar=dict(title="Strength"),
            zmin=0,
            zmax=1,
        )
    )
    _fig_ev.update_layout(
        title="PGx Evidence Strength (per gene × population)",
        xaxis_title="Superpopulation",
        yaxis_title="Gene",
        height=max(350, len(_ev_genes) * 40 + 100),
    )
    st.plotly_chart(_fig_ev, use_container_width=True)

elif nav == "About":
    st.markdown("### What is this?")
    st.markdown(
        "**Anukriti** is an *in silico* research tool to simulate **drug–gene interactions** and **pharmacogenomics (PGx) risk** for a virtual patient. "
        "It features **live AWS integration** with S3 genomic data storage, Lambda batch processing, and Step Functions orchestration for population-scale clinical trial simulation. "
        "It is intended for **trial design, teaching, and internal exploration only** — not for clinical use or decision-making."
    )
    st.warning(SAFETY_DISCLAIMER)

    st.markdown("### What am I trying to achieve?")
    st.markdown(
        "- Explore how **patient genetics** (metabolizing enzymes, transporters) affect response to a given drug.\n"
        "- Get **AI-generated interpretation** (risk level, mechanism, dosing implication) using similar drugs and RAG context.\n"
        "- Support **virtual trial setups** (e.g. batch runs) and structured outputs without running real trials.\n"
        "- Demonstrate **cloud-native architecture** with AWS services for scalable pharmacogenomics research.\n"
        "- Enable **population-scale simulation** supporting up to 10,000 diverse patients with real-time performance metrics."
    )

    st.markdown("### AWS Integration Features")
    st.markdown(
        "🌟 **Live AWS Infrastructure**\n\n"
        "- **S3 Genomic Data Storage:** 16 VCF files across 8 chromosomes stored in `synthatrial-genomic-data` bucket\n"
        "- **Lambda Batch Processing:** `synthatrial-batch-processor` function for parallel cohort analysis\n"
        "- **Step Functions Orchestration:** `synthatrial-trial-orchestrator` for clinical trial workflows\n"
        "- **Population Simulation:** Large-scale cohort simulation with diverse global populations (AFR, EUR, EAS, SAS, AMR)\n"
        "- **Cost Optimization:** Intelligent S3 tiering and Lambda-based scaling for cost-effective processing\n"
        "- **Professional Architecture:** Programmatic diagram generation for technical communication"
    )

    st.markdown("### Use and how to use it")
    st.markdown(
        "1. **Simulation Lab:** Pick a drug (or SMILES), set patient phenotypes for CYP/UGT/SLCO1B1 (or use Normal if unknown), then click **Analyze Interaction**. "
        "Results open on **Predicted Response + Risk**; use the other tabs for genetics used and similar drugs.\n"
        "2. **Batch / Analytics:** For cohort-style runs and metrics; includes AWS integration status and population simulation demos.\n"
        "3. **VCF mode:** If you have VCF data, use the backend/API to derive phenotypes from genotype; the app can consume precomputed profiles.\n"
        "4. **Population Simulation:** Use the Analytics tab to run demo population simulations showcasing scalability."
    )
    st.caption(
        "This tool is for the above purposes only. Do not use it for clinical decisions, diagnosis, or treatment."
    )

    st.markdown("### Chromosomes used (VCF-based profiles)")
    st.markdown(
        "When using VCF data (e.g. 1000 Genomes), patient genetics are derived from these chromosomes:\n\n"
        "| Chromosome | Genes | Role |\n"
        "|------------|-------|------|\n"
        "| **chr22** | CYP2D6 | Metabolizer; required for VCF profiles |\n"
        "| **chr10** | CYP2C19, CYP2C9 | Big 3 enzymes; recommended |\n"
        "| **chr2** | UGT1A1 | Phase II; optional |\n"
        "| **chr12** | SLCO1B1 | Statin myopathy (rs4149056); optional |\n"
        "| **chr16** | VKORC1 | Warfarin sensitivity; optional (for Warfarin PGx) |\n"
        "| **chr6** | TPMT | Thiopurine toxicity; for azathioprine/mercaptopurine |\n"
        "| **chr1** | DPYD | Fluoropyrimidine toxicity; for 5-FU/capecitabine |\n\n"
        "PGx allele and phenotype data follow PharmVar/CPIC-style curation; no live external API at runtime."
    )

    st.markdown("### Current limitations")
    st.markdown(
        "- **Allele coverage:** Incomplete; not all star-alleles are represented in curated tables.\n"
        "- **CYP2D6:** Copy-number and structural variants (CNVs) are **not** yet supported; only single-variant defining alleles are used.\n"
        "- **Allele calling:** Currently supports **single-variant** defining alleles (e.g. CYP2C19*2). Multi-variant haplotypes and full CNV handling are planned for future work.\n"
        "- **TPMT/DPYD:** VCF-based calling for TPMT (chr6) and DPYD (chr1) requires the corresponding chromosome VCF files to be downloaded.\n"
        "- **Guidance:** Phenotype and drug recommendations are derived from CPIC/PharmVar where data exists; they are **not a substitute for clinical testing** or certified PGx interpretation."
    )

    st.markdown("---")
    st.markdown("*Built by **Abhimanyu** · Anukriti*")
    st.markdown(
        '<a href="https://x.com/AbhimanyuRB2" target="_blank" rel="noopener">'
        '<img src="https://cdn.simpleicons.org/x/000000" width="24" height="24" style="vertical-align:middle;margin-right:8px" alt="X" />'
        "</a> "
        '<a href="https://www.linkedin.com/in/abhimanyurb/" target="_blank" rel="noopener">'
        '<img src="https://www.linkedin.com/favicon.ico" width="24" height="24" style="vertical-align:middle;margin-right:8px" alt="LinkedIn" />'
        "</a> "
        '<a href="https://www.instagram.com/abhimanyurb111/" target="_blank" rel="noopener">'
        '<img src="https://cdn.simpleicons.org/instagram/E4405F" width="24" height="24" style="vertical-align:middle" alt="Instagram" />'
        "</a>",
        unsafe_allow_html=True,
    )
