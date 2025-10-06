from unittest.mock import MagicMock

import yaml

from app.services.script.generator import StructuredScriptGenerator
from app.services.script.validator import DialogueEntry, Script


def test_dump_script_to_yaml_round_trip():
    generator = StructuredScriptGenerator(client=MagicMock(), allowed_speakers=("テストA", "テストB"))
    script = Script(
        title="テスト台本",
        dialogues=[
            DialogueEntry(speaker="テストA", line="こんにちは"),
            DialogueEntry(speaker="テストB", line="解説を始めましょう"),
        ],
    )

    yaml_blob = generator._dump_script_to_yaml(script)

    loaded = yaml.safe_load(yaml_blob)
    assert loaded == script.model_dump(mode="json")
