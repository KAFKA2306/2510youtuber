# API Fact Sheet and Management Policy

**YouTube自動化システム - API統合管理文書**  
**作成日**: 2025年10月3日  
**バージョン**: 1.0

***

## 📋 Executive Summary

本システムは8つの外部APIと3つのフォールバックAPIを統合し、YouTube動画の完全自動生成パイプラインを実現しています。本ドキュメントでは、各APIの仕様、検出された問題パターン、および運用管理ポリシーを包括的に記載します。

***

## 🔑 Core API Inventory

### 1. **Google Gemini API**
**用途**: コンテンツ生成（スクリプト、メタデータ、日本語品質チェック）  
**モデル**: `gemini-2.5-flash-lite`  
**認証**: APIキー（5キーローテーション対応）  
**エンドポイント**: `generativelanguage.googleapis.com`

**クォータ制限**:
- Free tier: 50 requests/day
- プロジェクト全体での制限

**環境変数**:
```bash
GEMINI_API_KEY      # Primary key
GEMINI_API_KEY_2    # Rotation key 2
GEMINI_API_KEY_3    # Rotation key 3
GEMINI_API_KEY_4    # Rotation key 4
GEMINI_API_KEY_5    # Rotation key 5
GEMINI_DAILY_QUOTA_LIMIT  # 日次制限値設定
```

**検出された問題**:
- ❌ **429 Too Many Requests** - Free tierの50リクエスト/日制限超過
- ❌ **504 Deadline Exceeded** - タイムアウト（120秒制限）
- ✅ **対策**: 5キー自動ローテーション、リトライロジック、日次クォータ管理

***

### 2. **ElevenLabs TTS API**
**用途**: 高品質音声合成（主要TTS）  
**モデル**: `eleven_multilingual_v2`  
**認証**: APIキー  
**エンドポイント**: `api.elevenlabs.io/v1/text-to-speech`

**クォータ制限**:
- 10,000クレジット/月（無料プラン）
- 1リクエスト = 約30-80クレジット

**環境変数**:
```bash
ELEVENLABS_API_KEY
```

**検出された問題**:
- ❌ **401 Unauthorized - quota_exceeded** - クレジット残高0
- ✅ **対策**: 4段階フォールバック（VoiceVox → OpenAI TTS → gTTS → pyttsx3）

***

### 3. **Perplexity API**
**用途**: ニュース収集・検索  
**モデル**: Perplexity Search  
**認証**: APIキー（最大10キーローテーション対応）  
**エンドポイント**: `api.perplexity.ai/chat/completions`

**環境変数**:
```bash
PERPLEXITY_API_KEY
PERPLEXITY_API_KEY_2 ~ PERPLEXITY_API_KEY_9  # Optional
```

**フォールバック**: NewsAPI.org

***

### 4. **Google Sheets API**
**用途**: 実行ログ管理、プロンプト管理  
**認証**: Service Account（JSON）  
**スコープ**: `https://www.googleapis.com/auth/spreadsheets`

**環境変数**:
```bash
GOOGLE_APPLICATION_CREDENTIALS  # JSON path or inline JSON
GOOGLE_SHEET_ID
```

**検出された問題**:
- ❌ **NoneType object has no attribute 'spreadsheets'** - 認証情報未設定
- ❌ **429 Rate Limit** - 書き込み頻度制限
- ✅ **対策**: ローカルフォールバック、レート制限リトライ、プロンプトキャッシュ

***

### 5. **YouTube Data API v3**
**用途**: 動画アップロード、メタデータ設定  
**認証**: OAuth 2.0（Desktop App）  
**スコープ**: 
- `https://www.googleapis.com/auth/youtube.upload`
- `https://www.googleapis.com/auth/youtube`

**環境変数**:
```bash
YOUTUBE_CLIENT_SECRET  # JSON path or inline JSON
```

**重要**: Service Accountは使用不可、OAuth 2.0必須

***

### 6. **Pexels API (Stock Footage)**
**用途**: 無料ストック動画素材検索  
**認証**: APIキー  
**制限**: 無制限（無料）

**環境変数**:
```bash
PEXELS_API_KEY
ENABLE_STOCK_FOOTAGE=true
STOCK_CLIPS_PER_VIDEO=5
```

***

### 7. **Pixabay API (Stock Footage)**
**用途**: 無料ストック動画素材検索  
**認証**: APIキー  
**制限**: 無制限（無料）

**環境変数**:
```bash
PIXABAY_API_KEY
```

***

### 8. **NewsAPI.org (Fallback)**
**用途**: Perplexity APIフォールバック  
**認証**: APIキー

**環境変数**:
```bash
NEWSAPI_API_KEY
```

***

## 🔄 API Rotation & Fallback Strategy

### **自動ローテーションシステム**
**実装**: `app/api_rotation.py`

**機能**:
1. **複数キープール管理**: 各プロバイダーで複数APIキーを管理
2. **成功率追跡**: 各キーの成功率を記録
3. **自動切替**: レート制限検出時に次のキーへ自動切替
4. **クールダウン**: 連続失敗5回で10分間休止
5. **レート制限待機**: 429エラー検出時5分間待機

**Gemini特化ローテーション**:
```python
# GEMINI_API_KEY_2 → GEMINI_API_KEY_3 → ... → GEMINI_API_KEY_5
# ラウンドロビン方式で順次切替
```

***

### **TTS 4段階フォールバック**
```
1. ElevenLabs (Primary)
   ↓ (失敗時)
2. VoiceVox Nemo (ローカル・無料)
   ↓ (失敗時)
3. OpenAI TTS (有料)
   ↓ (失敗時)
4. gTTS (無料・オンライン)
   ↓ (失敗時)
5. pyttsx3 (最終フォールバック・必ず成功)
```

**実装**: `app/tts.py::TTSManager._synthesize_with_fallback()`

***

## 🚨 Detected Issues & Resolution

### **Priority 1: システム基盤エラー**

#### **Issue #1: 設定モジュールインポートエラー**
```python
ImportError: cannot import name 'cfg' from 'app.config'
```
**影響**: 全テスト実行不可能  
**原因**: `app.config`構造変更による従来のimport破綻  
**修正済**: `from app.config import cfg` → `from app.config.settings import settings`  
**対応ファイル**: `tts.py`, `sheets.py`, `metadata.py`, `script_gen.py`, `api_rotation.py`

#### **Issue #2: Pydantic設定検証エラー**
```
ValidationError: 3 validation errors for AppSettings
speakers.0.voice_id - Input should be a valid string [input_value=None]
```
**影響**: アプリケーション起動完全停止  
**原因**: `speakers[*].voice_id`が`None`で検証失敗  
**修正**: デフォルト値設定、`settings.api_keys.get("elevenlabs")`使用

***

### **Priority 2: 運用エラー**

#### **Issue #3: ElevenLabs クォータ超過**
```
status: quota_exceeded
You have 0 credits remaining, while 38 credits are required
```
**頻度**: 全ログで大量発生  
**対策**: 
- ✅ 4段階フォールバック実装済
- ⚠️ クレジット補充推奨
- ✅ gTTSが実際に動作中（ログ確認済）

#### **Issue #4: Gemini レート制限**
```
error code 429
Quota exceeded for metric: generate_content_free_tier_requests
limit: 50
```
**頻度**: 2ログで発生  
**対策**:
- ✅ 5キーローテーション実装済
- ✅ 日次クォータ管理実装済
- ⚠️ 有料プランへの移行推奨

#### **Issue #5: Google Sheets 認証エラー**
```
ERROR - Failed to update run: 'NoneType' object has no attribute 'spreadsheets'
```
**頻度**: 全ログで発生  
**対策**:
- ✅ ローカルフォールバック実装済
- ⚠️ `GOOGLE_APPLICATION_CREDENTIALS`設定推奨

***

### **Priority 3: 機能エラー**

#### **Issue #6: generate_video() パラメータエラー**
```
TypeError: generate_video() got an unexpected keyword argument 'script_content'
```
**修正**: `main.py`でのパラメータ渡し方修正済

#### **Issue #7: VoiceVox Nemo 接続エラー**
```
WARNING - VOICEVOX Nemo server is not reachable.
```
**対策**: ローカルサーバー起動不要（gTTSで代替動作中）

---

## 📊 API Usage Monitoring

### **推奨監視項目**

1. **Gemini API**:
   - 日次リクエスト数（50/day制限）
   - キー別成功率
   - 429エラー発生頻度

2. **ElevenLabs**:
   - 残クレジット数
   - 月次使用量
   - フォールバック発動回数

3. **Google Sheets**:
   - 書き込み成功率
   - レート制限発生頻度

### **ログ監視コマンド**
```bash
# エラーパターン抽出
grep -E "ERROR|quota|429|401" logs/daily_run_*.log

# API呼び出し統計
grep "API call" logs/daily_run_*.log | wc -l

# フォールバック発動確認
grep "fallback" logs/daily_run_*.log
```

***

## 🔐 Security & Compliance

### **APIキー管理**
- ✅ 環境変数経由での読み込み（`.env`ファイル）
- ✅ GitHubへのコミット禁止（`.gitignore`設定必須）
- ✅ ローテーション機能による単一キー依存回避

### **認証情報保護**
```bash
# 必須: .gitignoreに追加
.env
token.pickle
google_credentials.json
youtube_client_secret.json
```

***

## 📋 Required Environment Variables Checklist

```bash
# 必須（Tier 1）
GEMINI_API_KEY=sk-xxx
ELEVENLABS_API_KEY=xxx
PERPLEXITY_API_KEY=pplx-xxx

# 高優先（Tier 2）
GEMINI_API_KEY_2=sk-xxx  # ローテーション推奨
GEMINI_API_KEY_3=sk-xxx
GEMINI_API_KEY_4=sk-xxx
GEMINI_API_KEY_5=sk-xxx
GOOGLE_SHEET_ID=xxx
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# オプション（Tier 3）
YOUTUBE_CLIENT_SECRET=/path/to/client_secret.json
PEXELS_API_KEY=xxx
PIXABAY_API_KEY=xxx
NEWSAPI_API_KEY=xxx
OPENAI_API_KEY=sk-xxx  # TTSフォールバック用
```

***

## 🎯 Action Items

### **即座対応（緊急）**
1. ✅ 設定モジュールimport修正（完了）
2. ⚠️ ElevenLabsクレジット補充
3. ⚠️ `GOOGLE_APPLICATION_CREDENTIALS`設定

### **短期対応（1週間以内）**
4. ⚠️ Gemini API有料プラン検討（50→50,000 requests/day）
5. ⚠️ API使用量ダッシュボード構築
6. ⚠️ エラー通知システム構築（Discord Webhook活用）

### **中長期対応（1ヶ月以内）**
7. ⚠️ APIコスト最適化分析
8. ⚠️ バックアップAPIプロバイダー検討
9. ⚠️ 自動テストスイート完成（テストケース仕様書参照）

***

## 📚 Related Documentation

- **テストケース仕様書**: `docs/TEST_CASE_SPECIFICATIONS.md`（本分析で作成済）
- **API統合図**: `docs/API_INTEGRATION_DIAGRAM.md`（作成推奨）
- **トラブルシューティングガイド**: `docs/TROUBLESHOOTING.md`（作成推奨）

***

**文書管理者**: Kafka Financial Group Development Team  
**最終更新**: 2025年10月3日 11:12 JST  
**次回レビュー予定**: 2025年11月3日

[1](https://cloud.ibm.com/apidocs/factsheets)
[2](https://advicement.io/dynamic-documents-api/json-to-pdf-templates/factsheet-template)
[3](https://www.postman.com/templates/collections/api-documentation/)
[4](https://www.notion.com/templates/api-template)
[5](https://help.sap.com/docs/leanix/ea/creating-fact-sheet)
[6](https://cloud.ibm.com/apidocs/factsheets-cpd)
[7](https://documentero.com/templates/it-engineering/document/api-documentation/)
[8](https://www.docubee.com/resources/fact-sheets/expand-applications-with-esignature-and-more/)
[9](https://stoplight.io/api-documentation-guide)
[10](https://bit.ai/templates/api-documentation-template)