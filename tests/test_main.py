from __future__ import annotations

import json

from semantic_ci_code.__main__ import main


def test_main_prints_scope_json(capsys):
    main()

    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload["product_name"] == "Semantic CI Code Edition"
    assert payload["deterministic"] is True
    assert payload["requires_llm"] is False
