# CrewAI WOW Script Creation - Quick Start Guide

## 🚀 クイックスタート

### 1. テスト実行（推奨：最初のステップ）

```bash
# サンプルニュースでCrewAIをテスト
python3 test_crewai_flow.py
```

これにより、3つのサンプル経済ニュースから8分間の台本が生成されます。

### 2. 本番ワークフロー実行

```bash
# 完全ワークフロー（ニュース収集→台本生成→動画作成）
python3 app/main.py
```

---

## ⚙️ 設定

### CrewAI の有効化/無効化

**.env ファイルで制御**:
```env
# CrewAI使用（デフォルト）
USE_CREWAI_SCRIPT_GENERATION=true

# 従来の3段階品質チェック使用
USE_CREWAI_SCRIPT_GENERATION=false
```

### 品質基準の設定

**config.yaml で設定**:
```yaml
quality_thresholds:
  wow_score_min: 8.0              # WOWスコア最低基準
  japanese_purity_min: 95.0       # 日本語純度最低基準
  retention_prediction_min: 50.0  # 保持率予測最低基準
  surprise_points_min: 5          # 驚きポイント最低数
  emotion_peaks_min: 5            # 感情ピーク最低数
```

---

## 📊 7つのエージェント

CrewAIは以下の7つの専門エージェントで構成されています:

1. **Deep News Analyzer** - ニュースから隠れた驚きを発掘
2. **Curiosity Gap Researcher** - 視聴者の好奇心を刺激するギャップを設計
3. **Emotional Story Architect** - 感情に訴えるストーリー構造を構築
4. **Script Writer** - 対談形式の台本初稿を執筆
5. **Engagement Optimizer** - 視聴維持率を最大化する最適化
6. **Quality Guardian** - WOWスコア8.0+を保証する品質チェック
7. **Japanese Purity Polisher** - 完璧な日本語に仕上げ

---

## 📁 ディレクトリ構成

```
app/
├── config/                    # 設定管理
│   ├── settings.py           # 統合設定
│   └── prompts/              # プロンプトYAML
│       ├── agents.yaml       # エージェント定義
│       ├── analysis.yaml     # 分析プロンプト
│       ├── script_generation.yaml
│       └── quality_check.yaml
│
├── crew/                     # CrewAI実装
│   ├── agents.py            # エージェント生成
│   ├── tasks.py             # タスク定義
│   ├── flows.py             # フロー実装
│   └── tools/
│       └── ai_clients.py    # AI抽象化
│
├── models/                   # データモデル
│   ├── news.py
│   ├── script.py
│   └── workflow.py
│
└── main.py                   # メインワークフロー
```

---

## 🔧 カスタマイズ

### プロンプトの編集

プロンプトは全て外部YAMLファイルで管理されています:

```yaml
# app/config/prompts/agents.yaml
agents:
  deep_news_analyzer:
    role: Deep News Analyzer
    goal: Uncover the 'WOW moments' hidden in news
    backstory: |
      あなたは20年の経験を持つ金融アナリストです...
```

### 新エージェントの追加

1. `app/config/prompts/agents.yaml` に定義追加
2. `app/crew/tasks.py` にタスク追加
3. `app/crew/agents.py` の `create_wow_agents()` に追加

---

## 🧪 テスト

### 単体テスト

```bash
# データモデルテスト
pytest tests/test_models.py

# AI Clientテスト
pytest tests/test_ai_clients.py
```

### E2Eテスト

```bash
# CrewAI完全フローテスト
python3 test_crewai_flow.py

# 本番ワークフローテスト（ドライラン）
DRY_RUN=true python3 app/main.py
```

---

## 📈 期待される成果

### 品質指標
- **視聴維持率**: 30% → **50%+** 目標
- **WOWスコア**: 6.0 → **8.0+** 目標
- **驚きポイント**: 1-2箇所 → **5箇所+** 目標
- **日本語純度**: - → **95%+** 目標

### 台本の特徴
- ✅ 30秒ごとのエンゲージメントフック
- ✅ 感情ピーク5箇所以上
- ✅ 視覚的変化指示15箇所以上
- ✅ 具体的数値データ10箇所以上
- ✅ オープンループで視聴継続を促進

---

## 🐛 トラブルシューティング

### エラー: "Agent creation failed"

**原因**: API キーが設定されていない

**解決策**:
```bash
# .env ファイルに以下を設定
GEMINI_API_KEY=your_key_here
PERPLEXITY_API_KEY=your_key_here
```

### エラー: "Quality threshold not met"

**原因**: WOWスコアが基準未達

**解決策**:
1. `config.yaml` で基準を下げる
2. プロンプトを改善
3. 品質ループ回数を増やす

```yaml
crew:
  max_quality_iterations: 3  # デフォルト: 2
```

### パフォーマンス改善

**並列化を有効化**:
```yaml
crew:
  parallel_analysis: true
```

**モデル変更**:
```yaml
crew:
  agents:
    deep_news_analyzer:
      model: gemini-2.0-flash-exp  # より高速なモデル
```

---

## 📚 ドキュメント

- **設計書**: `docs/design.md`
- **進捗管理**: `PHASE1_PROGRESS.md`
- **完了サマリー**: `PHASE1_COMPLETE.md`
- **API仕様**: `docs/api_spec.md`（TODO）

---

## 🎯 次のステップ

### 即座に実行可能
1. ✅ `python3 test_crewai_flow.py` でテスト
2. ✅ プロンプト調整
3. ✅ 品質基準チューニング

### 今後の拡張（Phase 2候補）
1. 保持率予測モデル改善
2. マルチモーダル対応
3. A/Bテスト機能
4. リアルタイムフィードバック

---

## 💡 Tips

### 最適な使い方

```bash
# 1. まずテストで動作確認
python3 test_crewai_flow.py

# 2. 生成された台本を確認
cat output/test_crewai_script.txt

# 3. 満足したら本番実行
python3 app/main.py
```

### プロンプトチューニング

エージェントのプロンプトは `app/config/prompts/agents.yaml` で編集可能:

```yaml
deep_news_analyzer:
  backstory: |
    あなたは【ここを編集】して
    エージェントの性格を調整できます
```

---

**最終更新**: 2025-10-02
