# CrewAI WOW Script Creation - Quick Start Guide v2.1

**最終更新**: 2025年10月4日 | **ステータス**: Phase 4完了・品質メトリクス記録機能追加

***

## 🎯 このシステムで何ができるか

- **自動ニュース収集**: Perplexity AI + NewsAPIで最新情報を取得
- **高品質台本生成**: 7つの専門AIエージェントが協力して視聴維持率50%+を目指す台本を作成
- **完全自動動画生成**: 音声合成→動画編集→YouTubeアップロードまで完全自動化
- **品質保証**: 日本語純度95%+、WOWスコア8.0+を自動チェック
- **フィードバックループ**: 品質メトリクスを自動記録・分析し、継続的改善をサポート

***

## ⚡ 5分でスタート

### 1. 環境確認
```bash
# 必須APIキーが設定されているか確認
uv run python -m app.verify
```

**必要なAPIキー**:
- `GEMINI_API_KEY` (必須)
- `ELEVENLABS_API_KEY` または `VOICEVOX_API_KEY` (どちらか)
- `PERPLEXITY_API_KEY` (推奨)

### 2. テスト実行（推奨）
```bash
# サンプルニュースで動作確認
uv run python3 test_crewai_flow.py
```

**期待される出力**: 3つの経済ニュースから8-10分の対談台本が生成されます

### 3. 本番実行
```bash
# 完全ワークフロー実行
uv run python3 -m app.main daily

# 実行後、品質分析レポートを確認
python scripts/analytics_report.py
```

***

## 🤖 7つのAIエージェント

CrewAIは以下の専門チームで台本を生成します：

1. **Deep News Analyzer** - ニュースの深層分析と隠れた驚きの発掘
2. **Curiosity Gap Researcher** - 視聴者の好奇心を刺激するギャップ設計
3. **Emotional Story Architect** - 感情に訴えるストーリー構造構築
4. **Script Writer** - 対談形式の台本初稿執筆
5. **Engagement Optimizer** - 視聴維持率最大化の最適化
6. **Quality Guardian** - WOWスコア8.0+保証の品質チェック
7. **Japanese Purity Polisher** - 日本語純度95%+への最終仕上げ

***

## 📊 Phase 4完了: 品質メトリクス記録機能

### 新機能: フィードバックループシステム

**自動記録される品質メトリクス**:
- ✅ **WOWスコア** (0-10点) - CrewAI Agent 6が評価
- ✅ **驚きポイント数** - 視聴者の驚き要素カウント
- ✅ **感情ピーク数** - 感情的な高揚ポイント
- ✅ **視覚指示数** - B-roll映像指示の充実度
- ✅ **日本語純度** (%) - 日本語テキストの割合
- ✅ **リテンション予測** (%) - 視聴維持率予測値

**記録先**:
- `output/execution_log.jsonl` - 詳細分析用JSONL
- Google Sheets - 3タブ構成（ダッシュボード/品質/プロダクション）
- `data/metadata_history.csv` - 後方互換性維持

**分析レポート**:
```bash
# 週次レポート（最新7実行）
python scripts/analytics_report.py

# フック戦略別パフォーマンス
python scripts/analytics_report.py --hooks

# トピック分布
python scripts/analytics_report.py --topics
```

### Phase 3の改善内容（継続中）

| 指標 | Phase 2 | Phase 3 | 改善率 |
|------|---------|---------|--------|
| 日本語純度 | 60-70% | **95%+** | +35% |
| 字幕英語混入 | 200-500語 | **0-10語** | -98% |
| 動画生成成功率 | 50% | **95%+** | +90% |
| フォールバック動作 | 失敗 | **正常** | 100% |

### Phase 4で修正された問題

**1. 品質メトリクスが記録されなかった問題**
- 問題: CrewAIが生成した`quality_data`がWorkflowResultに渡されていなかった
- 修正: `app/workflow/steps.py`で`crew_result`全体を保存、`app/main.py`で抽出メソッド実装
- 結果: WOWスコア等が正しくJSONL + Google Sheetsに記録される

**2. Analytics レポートのエラー**
- 問題: 品質メトリクスが空の場合にdivision by zeroエラー
- 修正: `app/analytics.py`で安全な計算、親切なエラーメッセージ追加
- 結果: メトリクスがない場合も正常動作し、理由を説明

**3. データフロー改善**
- `GenerateScriptStep` → CrewAI → `quality_data` → `WorkflowResult` → JSONL/Sheets
- 全ての品質指標が自動的に記録され、後から分析可能

***

## 🔧 設定とカスタマイズ

### CrewAI有効化/無効化

**.env**:
```bash
# CrewAI使用（デフォルト・推奨）
USE_CREWAI_SCRIPT_GENERATION=true

# 従来の3段階チェック使用
USE_CREWAI_SCRIPT_GENERATION=false
```

### 品質基準調整

**config.yaml**:
```yaml
quality_thresholds:
  wow_score_min: 8.0              # WOWスコア（6.0-10.0）
  japanese_purity_min: 95.0       # 日本語純度（%）
  retention_prediction_min: 50.0  # 視聴維持率予測（%）
  surprise_points_min: 5          # 驚きポイント数
  emotion_peaks_min: 5            # 感情ピーク数
```

### プロンプトカスタマイズ

**app/config/prompts/agents.yaml**:
```yaml
agents:
  deep_news_analyzer:
    role: Deep News Analyzer
    goal: Uncover WOW moments hidden in news
    backstory: |
      あなたは20年の経験を持つ金融アナリストです...
      【ここを編集してエージェントの性格を調整】
```

***

## 🚨 トラブルシューティング

### Phase 4関連の問題

#### 問題1: 品質メトリクスが記録されない

**症状**:
```bash
python scripts/analytics_report.py
# 出力: 平均WOWスコア: 0.00/10.0
# 警告: 品質メトリクスが未記録（CrewAI未使用またはデータ抽出エラー）
```

**原因**:
- CrewAIが無効化されている（`USE_CREWAI_SCRIPT_GENERATION=false`）
- または古いバージョンで実行された動画

**解決**:
```bash
# .envでCrewAIを有効化
USE_CREWAI_SCRIPT_GENERATION=true

# 新規実行
uv run python3 -m app.main daily

# 確認
python scripts/analytics_report.py
```

#### 問題2: Analytics レポートのクラッシュ

**症状**: `ZeroDivisionError: division by zero`

**解決**: 最新版にアップデート済み（2025年10月4日以降は発生しない）

### Phase 3関連の問題（解決済み）

#### 問題1: 字幕に英語が混入する

**症状**:
```
Could not clean all English: ['user', 'Task', 'json', 'wow_score']
```

**確認方法**:
```bash
grep -A 3 "最終出力は、以下のJSON形式のみを出力" \
  app/config/prompts/quality_check.yaml
```

**修正**: 最新版にアップデート（Phase 3で解決済み）

#### 問題2: 動画生成が失敗する

**症状**:
```
Fallback video generation error: 'crf' or 'preset'
```

**修正**: 最新版にアップデート（Phase 3で解決済み）

### 一般的な問題

#### APIキー未設定

**エラー**: `Agent creation failed`

**解決**:
```bash
# .envファイルに設定
GEMINI_API_KEY=AIza-your-key-here
GEMINI_API_KEY_2=AIza-your-key-2    # ローテーション推奨
GEMINI_API_KEY_3=AIza-your-key-3
```

#### 品質基準未達

**エラー**: `Quality threshold not met: WOW score 7.2 < 8.0`

**解決策（3つの選択肢）**:

1. **基準を下げる** (`config.yaml`):
   ```yaml
   quality_thresholds:
     wow_score_min: 7.0  # 8.0から変更
   ```

2. **品質ループ回数を増やす**:
   ```yaml
   crew:
     max_quality_iterations: 3  # デフォルト: 2
   ```

3. **プロンプトを改善** (`agents.yaml`, `quality_check.yaml`)

#### パフォーマンス遅い

**並列化を有効化** (`config.yaml`):
```yaml
crew:
  parallel_analysis: true
```

**より高速なモデルを使用** (`agents.yaml`):
```yaml
agents:
  deep_news_analyzer:
    model: gemini-1.5-flash  # より高速
```

***

## 📈 実装済み安定化機構

### 1. API Key Rotation（Gemini/Perplexity）
```
KEY1 → 429エラー → 5分待機 → KEY2 → KEY3 → KEY4 → KEY5
連続5回失敗 → 10分休止 → 復帰
```

### 2. TTS 6段階フォールバック
```
ElevenLabs → VOICEVOX Nemo → OpenAI TTS → 
gTTS → Coqui TTS → pyttsx3（必ず成功）
```

### 3. ニュース収集3段階フォールバック
```
Perplexity → NewsAPI → ダミーニュース
```

### 4. Google Sheetsローカルキャッシュ
- TTL 24時間
- API障害時は自動的にキャッシュから読込

***

## 💰 推奨API契約プラン

### 最小構成: $5/月
- **ElevenLabs Starter**: $5/月（30,000文字）
- **VOICEVOX Nemo**: 無料（ローカル）
- **Gemini Free Tier**: 無料（50リクエスト/日）
- **対応能力**: 月30-60本（1日1-2本）

***

## 📁 重要ファイル構成

```
app/
├── config/
│   ├── settings.py              # 統合設定（後方互換性あり）
│   └── prompts/                 # プロンプト管理
│       ├── agents.yaml          # エージェント定義
│       ├── analysis.yaml        # 分析プロンプト
│       ├── script_generation.yaml
│       └── quality_check.yaml   # ★Phase 3で修正
│
├── crew/
│   ├── agents.py               # エージェント生成
│   ├── tasks.py                # タスク定義
│   ├── flows.py                # フロー実装
│   └── tools/
│       └── ai_clients.py       # AI抽象化
│
├── video.py                    # ★Phase 3で修正
├── japanese_quality.py         # 日本語純度チェック
├── api_rotation.py             # APIキーローテーション
└── main.py                     # メインワークフロー
```

***

## ✅ システム検証結果（2025年10月4日）

### 実装済み機能
- ✅ Gemini 5キー自動ローテーション
- ✅ TTS 6段階フォールバック
- ✅ ニュース収集3段階フォールバック
- ✅ Google Sheetsローカルキャッシュ（TTL 24h）
- ✅ レート制限自動検知・待機・復帰
- ✅ **品質メトリクス自動記録** (Phase 4新機能)
- ✅ **Analytics レポート生成** (Phase 4新機能)
- ✅ **フィードバックループ** (Phase 4新機能)

### テスト結果
- ✅ 全86ユニットテスト通過
- ✅ Analytics レポート正常動作
- ✅ 品質メトリクス抽出機能動作確認

***

## 🎯 次のステップ

### 即座実行可能
1. ✅ `test_crewai_flow.py`でテスト実行
2. ✅ 生成された台本を確認（`output/test_crewai_script.txt`）
3. ✅ 満足したら本番実行（`uv run python3 -m app.main daily`）
4. ✅ **NEW**: Analytics レポートで品質を確認（`python scripts/analytics_report.py`）

### 推奨設定（優先度順）
1. **P0**: VOICEVOX Nemoサーバー起動（完全無料）
   - 手順・設定・テスト: `docs/VOICEVOX_NEMO.md`
2. **P1**: 複数回実行してフィードバックループを活用
   - 5-10本の動画を生成後、`analytics_report.py`でパターン分析
   - 高WOWスコアの動画の特徴を把握し、プロンプト改善に活用

### 参考ドキュメント
- **フィードバックループ詳細**: `docs/FEEDBACK_LOOP.md`
- **セットアップガイド**: `docs/setup.md`
- **API管理**: `docs/API_MANAGEMENT.md`
