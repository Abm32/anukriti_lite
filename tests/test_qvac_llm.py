import json
import subprocess

import pytest

from src.exceptions import LLMError
from src.qvac_llm import generate_pgx_response_qvac


def test_qvac_wrapper_parses_bridge_json(monkeypatch, tmp_path):
    script = tmp_path / "qvac_pgx_explain.mjs"
    script.write_text("console.log('stub')\n", encoding="utf-8")

    monkeypatch.setattr("src.qvac_llm.config.QVAC_ENABLED", True)
    monkeypatch.setattr("src.qvac_llm.config.QVAC_SCRIPT_PATH", str(script))
    monkeypatch.setattr("src.qvac_llm.config.QVAC_NODE_BIN", "node")
    monkeypatch.setattr("src.qvac_llm.config.QVAC_TIMEOUT_SECONDS", 3)

    captured = {}

    def fake_run(argv, input, text, capture_output, timeout, check):
        captured["argv"] = argv
        captured["payload"] = json.loads(input)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps({"text": "RISK LEVEL: High\n\nUse alternative."}),
            stderr="",
        )

    monkeypatch.setattr("src.qvac_llm.subprocess.run", fake_run)

    result = generate_pgx_response_qvac(
        context="CYP2C19 context",
        query="CYP2C19 clopidogrel",
        pgx_data={"gene": "CYP2C19", "risk": "High"},
    )

    assert result.startswith("RISK LEVEL: High")
    assert captured["argv"] == ["node", str(script)]
    assert captured["payload"]["pgx_data"]["gene"] == "CYP2C19"


def test_qvac_wrapper_gives_install_hint(monkeypatch, tmp_path):
    script = tmp_path / "qvac_pgx_explain.mjs"
    script.write_text("console.log('stub')\n", encoding="utf-8")

    monkeypatch.setattr("src.qvac_llm.config.QVAC_ENABLED", True)
    monkeypatch.setattr("src.qvac_llm.config.QVAC_SCRIPT_PATH", str(script))

    def fake_run(argv, input, text, capture_output, timeout, check):
        return subprocess.CompletedProcess(
            argv,
            1,
            stdout="",
            stderr="Error [ERR_MODULE_NOT_FOUND]: Cannot find package '@qvac/sdk'",
        )

    monkeypatch.setattr("src.qvac_llm.subprocess.run", fake_run)

    with pytest.raises(LLMError) as exc:
        generate_pgx_response_qvac(context="", query="test")

    assert "cd qvac && npm install" in str(exc.value)
