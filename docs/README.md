# 2510youtuber documentation

このdirectoryは、2025-10期のlegacy実装を再現・診断するために必要な詳細資料だけを保持します。日常の入口はrepository rootの [README.md](../README.md)、agent運用契約は [AGENTS.md](../AGENTS.md) です。新機能は原則として後継の [`KAFKA2306/2511youtuber`](https://github.com/KAFKA2306/2511youtuber) 側で扱います。

## Start here

| 目的 | 文書 |
| --- | --- |
| 環境構築・日次運用・障害対応 | [JAPANESE_MASTER_GUIDE.md](JAPANESE_MASTER_GUIDE.md) |
| 現行構成とデータフロー | [ARCHITECTURE.md](ARCHITECTURE.md) |
| 機能別の詳細 | [FEATURES.md](FEATURES.md) |
| API・rate limit・rotation | [API_REFERENCE.md](API_REFERENCE.md) |
| logs / archive / persisted data | [DATA_MANAGEMENT.md](DATA_MANAGEMENT.md) |
| CrewAI構成 | [README_CREWAI.md](README_CREWAI.md) |
| LLM出力の検証境界 | [LLM_OUTPUT_DISCIPLINE.md](LLM_OUTPUT_DISCIPLINE.md) |
| GUI backend setup | [GUI_SETUP.md](GUI_SETUP.md) |
| GUI design reference | [GUI_DESIGN.md](GUI_DESIGN.md) |
| VOICEVOX設定 | [VOICEVOX.md](VOICEVOX.md) |

## Documentation policy

現在の実行可能コード・`config.yaml`・tests・CIをdocumentationより優先します。文書と実装が食い違う場合は、実装を確認してから文書を修正します。

残す文書は、次のどれかに明確に該当するものだけです。

- repository固有のsetup/operation
- architectureやdata semanticsでコードだけから安全に推測できない情報
- external API/media/credential境界
- 再現や障害解析に必要な手順

redirectだけの文書、未参照prototype、同じ手順の複製、現在コードに存在しない構成を説明する設計資料は残しません。過去の資料が必要な場合はGit historyを参照します。

## Basic verification

```bash
uv run python -m compileall -q app tests
uv run pytest tests/unit -v
uv run ruff check .
uv run ruff format --check .
```

外部API、media生成、YouTube uploadを伴う処理は、必要なcredentialと明示的な実行目的がある場合だけ実行してください。
