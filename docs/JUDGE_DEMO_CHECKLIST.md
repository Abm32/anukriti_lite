# Judge demo checklist (Project Anukriti)

Use this before recording a **video** or hosting a **live judge session**. It aligns with the judge-ready strategy: reproducible demo, honest fallbacks, Bedrock working.

## Preconditions

1. **AWS credentials** in `.env` (or IAM role on EC2): `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` / `BEDROCK_REGION` aligned with Bedrock model access.
2. **No quarantine policy** on the IAM user (`AWSCompromisedKeyQuarantineV3` must be detached).
3. **Bedrock model access** enabled in console for **Amazon Nova Lite**, **Nova Pro**, and **Titan Text Embeddings** (and Claude if you demo it).
4. **API running:** `uvicorn api:app --host 0.0.0.0 --port 8000`
5. **Streamlit running:** `streamlit run app.py` with `API_URL=http://127.0.0.1:8000` (or your backend URL).
6. **Health:** Open `API_URL/` — response should show `nova` backend and a Nova model id if `LLM_BACKEND=nova`.

## Cold run (about 5 minutes)

1. New browser **incognito** window (no stale session).
2. Sidebar: **AI backend** = **Nova (AWS)**; **Nova Lite** selected (faster/cheaper).
3. **Simulation Lab** → drug **Warfarin** → **Manual** profile with genetics lines that trigger deterministic warfarin PGx (or use VCF if stable).
4. Click run; wait for **Predicted Response** with non-empty sections.
5. Expand **Audit trail** — confirm `backend`, `model`, no `llm_failure_hint` (unless you are demoing failure transparency on purpose).
6. **PDF** / **EHR JSON** if shown — download once.
7. **Batch Mode** — small cohort (e.g. 50–100) to avoid timeout; note **Lambda/Step** indicators are optional.

## OpenSearch / vector fallback

- If **OpenSearch** returns 403 or is unset, similar drugs show **Mock Drug A/B/C** — **expected**. Say on camera: *“Vector index unavailable; deterministic PGx and Bedrock explanation still work.”*
- To show **real ChEMBL similarity**, fix AOSS data access policy for your IAM principal and set `OPENSEARCH_HOST`.

## Screenshot pack (capture for Builder Center)

1. Architecture diagram (from docs or generated).
2. Simulation Lab — drug + backend **Nova**.
3. Results — risk sections + **audit** JSON.
4. Similar Drugs tab — either OpenSearch **or** mock warning (honesty counts).
5. Batch Mode — cohort chart (optional).

## Video script outline (2–3 minutes)

1. Problem in one sentence (equity / PGx blind spot).
2. Show pipeline: deterministic first → Titan RAG → Nova explains.
3. Live click: Warfarin → result → audit.
4. Disclaimer: research prototype, not clinical advice.

## After recording

- Upload video to YouTube (unlisted if preferred).
- Add link to **AWS Builder Center** article and GitHub **README**.
