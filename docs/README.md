# YouTube自動生成システム

AI駆動の高品質YouTube動画自動生成システム

## 概要

このシステムは、ニュース収集から動画アップロードまでを完全自動化します：

1. **ニュース収集** - Perplexity AI/NewsAPI
2. **台本生成** - CrewAI (7専門エージェント、WOWスコア8.0+保証)
3. **音声合成** - ElevenLabs/VOICEVOX (6段階フォールバック)
4. **動画生成** - FFmpeg + Stock Footage (Pexels/Pixabay)
5. **YouTube投稿** - 自動アップロード + フィードバックループ

### 主要機能

- ✅ **CrewAI エージェント**: 7つの専門AIが協力して視聴維持率50%+を目指す台本を生成
- ✅ **Stock Footage**: プロフェッショナルなB-roll自動生成（Pexels/Pixabay）
- ✅ **TTS 6段階フォールバック**: 高品質音声（ElevenLabs → VOICEVOX → ...）
- ✅ **日本語純度ガード**: 改善処理で元の原稿より日本語純度が低下しないことを自動保証
- ✅ **品質検証**: 音声・動画・字幕の品質を自動チェック
- ✅ **Feedback Loop**: 実行ログ→Google Sheets→分析→改善
- ✅ **動画レビューAI**: Gemini Visionで生成動画を分析し改善提案

## クイックスタート

### 前提条件

- Python 3.11+
- FFmpeg 4.4+
- uv (Python package manager)

### インストール

```bash
# リポジトリクローン
git clone https://github.com/your-org/youtuber.git
cd youtuber

# 依存関係インストール
uv sync

# 環境変数設定
cp secret/.env.example secret/.env
# secret/.envを編集してAPIキーを設定
```

### 最小構成（API keyなし）

無料で動作する最小構成：

```bash
# VOICEVOX Nemo起動（TTS）
./scripts/voicevox_manager.sh start

# ダミーニュースで動画生成テスト
uv run python3 -m app.main daily
```

**必要なもの**: FFmpegのみ
**生成されるもの**: 音声付き動画（静的背景）

### 推奨構成（高品質）

```bash
# secret/.env に以下を追加:
GEMINI_API_KEY=AIza...                       # CrewAI（必須）
PEXELS_API_KEY=...                           # Stock Footage（推奨）
GOOGLE_APPLICATION_CREDENTIALS=secret/service-account.json  # Google Sheets（任意）
GOOGLE_SHEET_ID=...                          # フィードバックループ

# config.yaml で Stock Footage有効化
stock_footage:
  enabled: true
  clips_per_video: 5

# 実行
uv run python3 -m app.main daily
```

## ドキュメント

### コア

- **[SETUP.md](SETUP.md)** - 環境構築（API keys, VOICEVOX, Google認証等）
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - システム構成・データフロー
- **[FEATURES.md](FEATURES.md)** - 全機能の詳細ドキュメント

### API・設定

- **[API_REFERENCE.md](API_REFERENCE.md)** - API管理・レート制限・ローテーション
- **[VOICEVOX.md](VOICEVOX.md)** - VOICEVOX設定・話者ID

### その他

- **[README_CREWAI.md](README_CREWAI.md)** - CrewAI エージェント詳細
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - トラブルシューティング
- **[FILE_ARCHIVAL.md](FILE_ARCHIVAL.md)** - ファイル管理システム
- **[GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md)** - Google Sheets連携
- **[README_METADATA_STORAGE.md](README_METADATA_STORAGE.md)** - メタデータストレージ

## 使い方

### 基本コマンド

```bash
# 通常実行（ニュース収集 → 動画生成 → YouTube投稿）
uv run python3 -m app.main daily

# CrewAI台本生成のみテスト
uv run python3 test_crewai_flow.py

# 動画レビュー
uv run python -m scripts.video_review "output/video.mp4"

# 分析レポート
python scripts/analytics_report.py
```

### テスト

```bash
# 全テスト
pytest

# ユニットテストのみ（高速）
pytest tests/unit -v

# 統合テスト
pytest tests/integration -v

# E2Eテスト（実際のAPI呼び出し）
pytest tests/e2e --run-e2e -v
```

### Lint/Format

```bash
# Lint
uv run ruff check .

# Format
uv run ruff format .
```

## 設定

### config.yaml

全設定の中央管理：

```yaml
speakers:
  - name: 武宏
    voicevox_speaker: 11  # 玄野武宏（男性・落ち着いた声）
  - name: つむぎ
    voicevox_speaker: 8   # 春日部つむぎ（女性・明るい声）

stock_footage:
  enabled: true
  clips_per_video: 5

quality_thresholds:
  wow_score_min: 8.0
  # 日本語純度は改善時に原稿より悪化しないことのみを保証（閾値なし）
  retention_prediction_min: 50.0

video:
  quality_preset: high  # low/medium/high/ultra
```

### secret/.env

APIキー管理：

```bash
# 必須
GEMINI_API_KEY=AIza...

# 推奨
GEMINI_API_KEY_2=AIza...  # ローテーション用
GEMINI_API_KEY_3=AIza...
PEXELS_API_KEY=...

# オプション
ELEVENLABS_API_KEY=...
GOOGLE_APPLICATION_CREDENTIALS=secret/service-account.json
GOOGLE_SHEET_ID=...
```

## ワークフロー

```
1. News Collection
   ↓
2. Script Generation (CrewAI 7 agents)
   ↓
3. Audio Synthesis (TTS)
   ↓
4. STT for Alignment
   ↓
5. Subtitle Alignment
   ↓
6. B-roll Generation (Stock Footage)
   ↓
7. Video Rendering (FFmpeg)
   ↓
8. Metadata Generation
   ↓
9. YouTube Upload
   ↓
10. Feedback Logging (JSONL + Google Sheets)
```

詳細: [ARCHITECTURE.md](ARCHITECTURE.md)

## CrewAI エージェント

7つの専門AIエージェント：

1. **Deep News Analyzer** - 隠れた驚きを発掘
2. **Curiosity Gap Researcher** - 「続きが気になる」を設計
3. **Emotional Story Architect** - 心に残るストーリー構築
4. **Script Writer** - 3話者の台本生成
5. **Engagement Optimizer** - 視聴維持率50%+を目指す最適化
6. **Quality Guardian** - WOWスコア8.0+を保証
7. **Japanese Purity Polisher** - 完璧な日本語に仕上げ

詳細: [README_CREWAI.md](README_CREWAI.md)

## 主要機能

### 1. Stock Footage B-roll

プロフェッショナルなストック映像を自動検索・ダウンロード・合成：

- **Pexels API**: 無料・無制限
- **Pixabay API**: フォールバック
- **キーワードマッチング**: 日本語→英語変換（経済 → economy等）
- **エフェクト**: クロスフェード、Ken Burns効果、カラーグレーディング

詳細: [FEATURES.md#stock-footage-b-roll](FEATURES.md#1-stock-footage-b-roll)

### 2. Feedback Loop

継続的改善システム：

- **実行ログ**: JSONL（分析用）+ Google Sheets（人間向け）
- **品質指標**: WOWスコア、日本語純度、保持率予測
- **YouTube統計**: Views, CTR, Retention（クーロンジョブで自動更新）
- **分析**: フック戦略、トピック分布、週次レポート

詳細: [FEATURES.md#feedback-loop-system](FEATURES.md#2-feedback-loop-system)

### 3. File Archival

動画ファイルの永続保存：

```
output/{timestamp}_{run_id}_{title}/
  ├── video.mp4
  ├── audio.wav
  ├── thumbnail.png
  ├── script.txt
  └── subtitles.srt
```

詳細: [FEATURES.md#file-archival](FEATURES.md#3-file-archival)

### 4. Video Quality Validation

音声・動画・字幕の品質を自動検証：

- **Audio**: ピーク音量、RMS、無音検出
- **Video**: 解像度、FPS、ビットレート
- **Subtitles**: カバレッジ、タイミングギャップ
- **ゲーティング**: 基準未満の場合はワークフロー停止

詳細: [FEATURES.md#video-quality-validation](FEATURES.md#6-video-quality-validation)

### 5. Video Review AI

生成済み動画をGemini Visionで分析：

- **スクリーンショット抽出**: 60秒ごと（最大15枚）
- **AI分析**: 視覚バリエーション、可読性、テンポ評価
- **改善提案**: 次回動画で試すべきこと
- **離脱リスク検出**: 視聴者が離脱しやすい箇所を特定

詳細: [FEATURES.md#video-review-ai](FEATURES.md#7-video-review-ai)

## トラブルシューティング

### よくある問題

**Q: "Could not clean all English" 警告**
```bash
# Agent 6/7のプロンプトが英語メタデータを出力している
# 解決: app/config/prompts/quality_check.yaml を確認
```

**Q: FFmpeg "crf or preset" エラー**
```bash
# 品質パラメータの重複指定
# 解決: **self._get_quality_settings() のみ使用、明示的パラメータ削除
```

**Q: TTS quota exhausted**
```bash
# ElevenLabs無料枠（10k chars/month）使い切り
# 解決: VOICEVOXに自動フォールバック、または./scripts/voicevox_manager.sh start
```

**Q: Rate limit 429 errors**
```bash
# Gemini/Perplexity APIレート制限
# 解決: 自動ローテーション＆待機、追加キー登録（GEMINI_API_KEY_2等）
```

詳細: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## パフォーマンス

**実行時間（8分動画）**:
- News Collection: ~5秒
- Script Generation (CrewAI): ~3-5分
- Audio Synthesis: ~30秒
- Video Generation (Stock Footage): ~1-2分
- **合計**: ~5-8分

**コスト（Gemini API）**:
- CrewAI 7エージェント: $0.10-0.20 per video
- Metadata生成: $0.01
- **合計**: ~$0.15 per video

## 開発

### ディレクトリ構造

```
app/
├── main.py              # エントリーポイント
├── config/              # 設定管理
├── crew/                # CrewAI エージェント
├── models/              # Pydantic データモデル
├── services/            # ビジネスロジック
├── workflow/            # ワークフローステップ
└── api_rotation.py      # APIキーローテーション
```

詳細: [ARCHITECTURE.md#ディレクトリ構造](ARCHITECTURE.md#2-ディレクトリ構造)

### コーディング規約

- **Linter**: Ruff (line length 120)
- **Imports**: isort (`app` as first-party)
- **Type hints**: 推奨（必須ではない）
- **Docstrings**: 公開APIには必須
- **Logging**: Python logging（printは使用しない）

### テスト戦略

- **Unit**: 外部API全てモック、純粋ロジックのテスト
- **Integration**: フィクスチャ使用、コンポーネント間連携テスト
- **E2E**: 実際のAPI呼び出し（`--run-e2e`フラグ必須）

## Contributing

1. Issueを作成して議論
2. Forkしてブランチ作成
3. テストを追加（t-wadaスタイルTDD推奨）
4. Lintとテストをパス
5. Pull Request作成

## License

MIT License

## 関連リンク

- [Pexels API](https://www.pexels.com/api/)
- [Pixabay API](https://pixabay.com/api/docs/)
- [CrewAI Documentation](https://docs.crewai.com/)
- [VOICEVOX](https://voicevox.hiroshiba.jp/)
- [LiteLLM](https://docs.litellm.ai/)
