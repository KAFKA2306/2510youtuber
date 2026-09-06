from pathlib import Path

import yaml


def test_configured_prompt_files_exist_in_single_directory() -> None:
    root = Path(__file__).resolve().parents[2]
    config = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
    prompt_config = config["prompts"]
    prompt_dir = root / prompt_config["directory"]

    assert prompt_dir.is_dir()
    for file_name in prompt_config["files"].values():
        assert (prompt_dir / file_name).is_file(), file_name

    assert not (root / "app/config/prompts").exists()


if __name__ == "__main__":
    test_configured_prompt_files_exist_in_single_directory()
