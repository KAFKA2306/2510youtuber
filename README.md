# 2510youtuber — AIエージェントによるYouTube動画生成

[![Python syntax safety](https://github.com/KAFKA2306/2510youtuber/actions/workflows/python-syntax-safety.yml/badge.svg)](https://github.com/KAFKA2306/2510youtuber/actions/workflows/python-syntax-safety.yml)
[![News collection async contract](https://github.com/KAFKA2306/2510youtuber/actions/workflows/news-collection-async-contract.yml/badge.svg)](https://github.com/KAFKA2306/2510youtuber/actions/workflows/news-collection-async-contract.yml)

**リポジトリ:** https://github.com/KAFKA2306/2510youtuber

ニュースや設定情報から動画台本を作り、音声・画像・字幕・動画へ変換する処理を、CrewAIベースのエージェントとメディア処理サービスで管理するプロジェクトです。

このリポジトリは2025年10月期の動画生成基盤として保持されています。現在の後継実装は[2511youtuber](https://github.com/KAFKA2306/2511youtuber)です。

## Vision

この世代の役割は、ニュースや設定情報から台本、音声、画像、字幕、動画へ進む複数工程を分断せず、制作者が各工程の状態を追いながら一本の制作フローとして扱えることです。

新規機能の正準実装を担うことではありません。現在の開発は原則として後継の`2511youtuber`へ進め、このrepositoryは旧世代の再現・診断・比較に使います。

## Design philosophy

- AI生成量より、取得元・取得日時・生成内容を公開前に確認できることを優先する
- 台本生成、media生成、動画化、公開を同じ成功状態として扱わない
- 旧世代の再現性を保ちつつ、新機能をlegacy側へ重複実装しない
- API key、Cookie、YouTube認証情報を成果物やlogへ残さない
- workflow成功を動画品質やremote publicationの証拠へ読み替えない

## Why / historical differentiation

当時の単発AI生成と比べた価値は、台本・音声・画像・字幕・動画という複数media工程を同じ制作フローで扱い、途中成果と検証状態を追えることにありました。CrewAIやPydantic自体が価値なのではありません。

現在の利用者は、新しい制作を始めるなら`2511youtuber`へ進み、2510固有の挙動を再現したい場合、旧成果を診断したい場合、または世代差を比較したい場合にこのrepositoryを参照します。

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
| エージェント用プロンプト | [app/config_prompts/prompts/](app/config_prompts/prompts/) |

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

**README最終監査:** 2026-09-07
