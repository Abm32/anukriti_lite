import {
  loadModel,
  LLAMA_3_2_1B_INST_Q4_0,
  completion,
  unloadModel,
} from "@qvac/sdk";

async function readStdinJson() {
  let input = "";
  for await (const chunk of process.stdin) {
    input += chunk;
  }
  return input.trim() ? JSON.parse(input) : {};
}

function valueOrBlank(value) {
  return value === undefined || value === null ? "" : String(value);
}

function buildPrompt({ context = "", query = "", pgx_data = null }) {
  const safetyRules = [
    "You are Anukriti Lite, a clinical pharmacogenomics explanation assistant.",
    "Use the supplied deterministic PGx result as the source of truth.",
    "Do not invent patient identifiers, diagnoses, lab values, citations, or genomic findings.",
    "Write concise clinical decision-support text, not medical orders.",
    "Always include the sections: RISK LEVEL, PREDICTED REACTION, BIOLOGICAL MECHANISM, DOSING IMPLICATION.",
  ].join("\n");

  if (pgx_data) {
    return `${safetyRules}

Deterministic PGx result:
Gene: ${valueOrBlank(pgx_data.gene)}
Genotype: ${valueOrBlank(pgx_data.genotype)}
Phenotype: ${valueOrBlank(pgx_data.phenotype)}
Risk: ${valueOrBlank(pgx_data.risk || pgx_data.risk_level)}
Recommendation: ${valueOrBlank(pgx_data.recommendation || pgx_data.clinical_recommendation)}

Retrieved context:
${context}

Clinical query:
${query}

Return only the explanation text.`;
  }

  return `${safetyRules}

Retrieved context:
${context}

Clinical query:
${query}

Return only the explanation text.`;
}

let modelId;

try {
  const payload = await readStdinJson();
  modelId = await loadModel({
    modelSrc: LLAMA_3_2_1B_INST_Q4_0,
    modelType: "llm",
    onProgress: () => {},
  });

  const result = completion({
    modelId,
    history: [{ role: "user", content: buildPrompt(payload) }],
    stream: true,
  });

  let text = "";
  for await (const token of result.tokenStream) {
    text += token;
  }

  process.stdout.write(
    JSON.stringify({
      text,
      backend: "qvac",
      model: "LLAMA_3_2_1B_INST_Q4_0",
    }),
  );
} catch (error) {
  process.stderr.write(String(error?.stack || error?.message || error));
  process.exitCode = 1;
} finally {
  if (modelId) {
    await unloadModel({ modelId });
  }
}
