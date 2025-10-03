# CrewAI WOW Script Creation - Quick Start Guide v2.0

**最終更新**: 2025年10月3日 | **ステータス**: Phase 3完了・本番運用可能

***

## 🎯 このシステムで何ができるか

- **自動ニュース収集**: Perplexity AI + NewsAPIで最新情報を取得
- **高品質台本生成**: 7つの専門AIエージェントが協力して視聴維持率50%+を目指す台本を作成
- **完全自動動画生成**: 音声合成→動画編集→YouTubeアップロードまで完全自動化
- **品質保証**: 日本語純度95%+、WOWスコア8.0+を自動チェック

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

## 📊 Phase 3完了: 品質改善の成果

### 改善された指標

| 指標 | Phase 2 | Phase 3 | 改善率 |
|------|---------|---------|--------|
| 日本語純度 | 60-70% | **95%+** | +35% |
| 字幕英語混入 | 200-500語 | **0-10語** | -98% |
| 動画生成成功率 | 50% | **95%+** | +90% |
| フォールバック動作 | 失敗 | **正常** | 100% |

### 修正された主な問題

**1. CrewAI出力のクリーン化**
- 問題: Agent 6-7が内部思考プロセス（"json", "wow_score", "Task"等）を出力に含めていた
- 修正: `quality_check.yaml`に明示的な出力制限指示を追加
- 結果: 日本語純度が95%+に向上

**2. FFmpeg動画生成の安定化**
- 問題: パラメータ重複（`crf`, `preset`等）でメイン/フォールバック両方が失敗
- 修正: 全動画生成パスで`_get_quality_settings()`のみ使用
- 結果: 成功率が95%+に向上

**3. 話者形式の保証**
- 修正: Agent 7に「田中: セリフ」形式の厳守指示を追加
- 結果: 音声合成が正常動作

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

### Phase 3関連の問題

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

**期待される内容**:
```yaml
【重要】最終出力は、以下のJSON形式のみを出力してください。
説明文、分析、コメント等は一切含めないでください。
あなたの思考プロセスや分析は含めず、JSONのみを出力してください。
```

**修正**: 最新版にアップデート（`git pull origin main`）

#### 問題2: 動画生成が失敗する

**症状**:
```
Fallback video generation error: 'crf' or 'preset'
```

**確認方法**:
```bash
grep -B 2 -A 2 "\*\*self._get_quality_settings()" app/video.py
```

**期待**: 3箇所全てで`**self._get_quality_settings()`のみ使用され、明示的な`crf=`や`vcodec=`がない

**修正**: `app/video.py`を最新版に更新

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

## ✅ システム検証結果（2025年10月3日）

### 実装済み機能
- ✅ Gemini 5キー自動ローテーション
- ✅ TTS 6段階フォールバック
- ✅ ニュース収集3段階フォールバック
- ✅ Google Sheetsローカルキャッシュ（TTL 24h）
- ✅ レート制限自動検知・待機・復帰

***

## 🎯 次のステップ

### 即座実行可能
1. ✅ `test_crewai_flow.py`でテスト実行
2. ✅ 生成された台本を確認（`output/test_crewai_script.txt`）
3. ✅ 満足したら本番実行（`uv run python3 -m app.main`）

### 推奨設定（優先度順）
1. **P0**: VOICEVOX Nemoサーバー起動（完全無料） — `docs/VOICEVOX_NEMO.md` 参照
