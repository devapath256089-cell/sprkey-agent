"""Tests for the Nous-Sprkey-3/4 non-agentic warning detector.

Prior to this check, the warning fired on any model whose name contained
``"sprkey"`` anywhere (case-insensitive). That false-positived on unrelated
local Modelfiles such as ``sprkey-brain:qwen3-14b-ctx16k`` — a tool-capable
Qwen3 wrapper that happens to live under the "sprkey" tag namespace.

``is_nous_sprkey_non_agentic`` should only match the actual Nightrainbow Research
Sprkey-3 / Sprkey-4 chat family.
"""

from __future__ import annotations

import pytest

from sprkey_cli.model_switch import (
    _SPRKEY_MODEL_WARNING,
    _check_sprkey_model_warning,
    is_nous_sprkey_non_agentic,
)


@pytest.mark.parametrize(
    "model_name",
    [
        "NightrainbowResearch/Sprkey-3-Llama-3.1-70B",
        "NightrainbowResearch/Sprkey-3-Llama-3.1-405B",
        "sprkey-3",
        "Sprkey-3",
        "sprkey-4",
        "sprkey-4-405b",
        "sprkey_4_70b",
        "openrouter/sprkey3:70b",
        "openrouter/nightrainbowresearch/sprkey-4-405b",
        "NightrainbowResearch/Sprkey3",
        "sprkey-3.1",
    ],
)
def test_matches_real_nous_sprkey_chat_models(model_name: str) -> None:
    assert is_nous_sprkey_non_agentic(model_name), (
        f"expected {model_name!r} to be flagged as Nous Sprkey 3/4"
    )
    assert _check_sprkey_model_warning(model_name) == _SPRKEY_MODEL_WARNING


