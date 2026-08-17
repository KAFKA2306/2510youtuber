# 2510youtuber — AIエージェントによるYouTube動画生成

[![Python syntax safety](https://github.com/KAFKA2306/2510youtuber/actions/workflows/python-syntax-safety.yml/badge.svg)](https://github.com/KAFKA2306/2510youtuber/actions/workflows/python-syntax-safety.yml)
[![News collection async contract](https://github.com/KAFKA2306/2510youtuber/actions/workflows/news-collection-async-contract.yml/badge.svg)](https://github.com/KAFKA2306/2510youtuber/actions/workflows/news-collection-async-contract.yml)

**リポジトリ:** https://github.com/KAFKA2306/2510youtuber

ニュースや設定情報から動画台本を作り、音声・画像・字幕・動画へ変換する処理を、CrewAIベースのエージェントとメディア処理サービスで管理するプロジェクトです。

このリポジトリは2025年10月期の動画生成基盤として保持されています。現在の後継実装は[2511youtuber](https://github.com/KAFKA2306/2511youtuber)です。

## 主な機能

- エージェントによるテーマ整理と台本生成
- Pydanticモデルによる入出力検証
- 動画・音声・画像処理サービス
- 日次ワークフロー
- 実行ログと分析情報の確認
- 単体テストと改善ループ
- プロンプト・設定の外部ファイル管理

## 主な入口

| 内容 | ファイル |
| --- | --- |
| 開発・運用ルール | [AGENTS.md](AGENTS.md) |
| 詳細資料 | [docs/](docs/) |
| 全体設定 | [config.yaml](config.yaml) |
| エージェント用プロンプト | [app/config/prompts/](app/config/prompts/) |
| Serena用メモリ | [.serena/memories/](.serena/memories/) |

## 実行

日次ワークフロー:

```bash
uv sync
uv run python -m app.main daily
```

改善・検証ループ:

```bash
python scripts/tasks.py improve --iterations 3
```

ログ・分析確認:

```bash
python scripts/tasks.py analytics
python scripts/tasks.py logs
```

台本生成フローの確認:

```bash
uv run python test_crewai_flow.py
```

テストと静的検査:

```bash
pytest tests/unit -v
uv run ruff check .
uv run ruff format --check .
```

## 主な構成

```text
2510youtuber/
├── app/
│   ├── crew/               # CrewAIのエージェント・タスク・フロー
│   ├── config/             # 設定とプロンプト
│   ├── models/             # Pydanticモデル
│   └── services/media/     # 音声・画像・動画処理
├── tests/                  # テスト
├── docs/                   # 文書
├── scripts/                # 運用・検証スクリプト
├── config.yaml             # 全体設定
└── CLAUDE.md               # Claude Code向けAGENTS.md読み込み
```

## 運用上の注意

- APIキー、Cookie、YouTube認証情報をコミットしない
- ニュースの取得元と取得日時を記録する
- AIが生成した文章を事実確認なしで公開しない
- 音楽、画像、フォント、キャラクター素材の利用条件を確認する
- 自動生成した動画を公開前に人間が確認する
- 旧実装のため、新機能は原則として`2511youtuber`側へ追加する

**README最終監査:** 2026-08-01
