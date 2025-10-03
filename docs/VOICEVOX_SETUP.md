# VOICEVOX Nemo セットアップガイド

VOICEVOX Nemoは完全無料のオープンソース日本語音声合成エンジンです。このガイドでは、VOICEVOX NemoをDockerで起動し、YouTube自動化システムで使用する方法を説明します。

## 概要

**VOICEVOX Nemoの役割:**
- ElevenLabs TTSの無料バックアップ
- 日本語音声合成に最適化
- 完全ローカルで動作（API制限なし）

**フォールバックチェーン:**
1. ElevenLabs TTS（プライマリ）
2. **VOICEVOX Nemo**（無料バックアップ）
3. gTTS（Google TTS Free）
4. pyttsx3（オフライン・最終フォールバック）

---

## 前提条件

### WSL2環境

WSL2 Ubuntu 22.04内でDocker EngineまたはPodmanを独立して使用する方法を説明します。[1][2]

## Docker Engineのインストール

### リポジトリのセットアップ

```bash
# GPGキーの追加
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# aptリポジトリの追加
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
```

### Dockerパッケージのインストール

```bash
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 動作確認

```bash
sudo docker run hello-world
```

---

## セットアップ手順

#### Step 3: WSL2で確認
```bash
# WSL2を再起動
wsl --shutdown  # PowerShellで実行
# WSL2を再度開く

# Dockerコマンドが使えることを確認
docker --version
# 出力例: Docker version 24.0.6, build ed223bc

docker ps
# 出力例: CONTAINER ID   IMAGE   COMMAND   CREATED   STATUS   PORTS   NAMES
```

---

問題が判明しました。Dockerデーモンは正常に起動していますが（`Active: active (running)`）、現在のユーザーが`docker.sock`にアクセスする権限がありません。`voicevox_manager.sh`の`check_docker()`関数が`docker info`を実行する際に権限エラーが発生しています。[1][2][3]

以下のコマンドで解決します:

```bash
# dockerグループにユーザーを追加
sudo usermod -aG docker $USER

# グループ変更を即座に反映
newgrp docker

# docker.sockのパーミッション設定
sudo chown root:docker /var/run/docker.sock
sudo chmod 660 /var/run/docker.sock

# 動作確認
docker ps
```

これでsudoなしで`docker`コマンドが実行できるようになります。その後、VOICEVOXスクリプトを再実行してください:[2][1]

```bash
./scripts/voicevox_manager.sh start
```

**注意**: `newgrp docker`は現在のシェルセッションのみに適用されます。恒久的に反映するには、一度ログアウトして再ログインするか、WSLを再起動してください:[1]

```powershell
# PowerShellから
wsl --shutdown
```

その後、WSLを再起動すれば、どのシェルセッションでもsudoなしでdockerコマンドが使用できるようになります。[2][1]

[1](https://linuxbeast.com/blog/resolving-wsl-permission-denied-when-connecting-to-docker-daemon/)
[2](https://dev.to/kenji_goh/got-permission-denied-while-trying-to-connect-to-the-docker-daemon-socket-3dne)
[3](https://docs.docker.com/go/wsl2/)
[4](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/52522745/c3b21baa-8a0d-40b1-9182-fa269b3353f0/voicevox_manager.sh)


---

### 2. VOICEVOX Nemoコンテナの起動

#### 自動起動（推奨）

専用管理スクリプトを使用:

```bash
# プロジェクトルートで実行
cd /home/kafka/projects/youtuber

sudo service docker start


# VOICEVOX Nemoを起動
./scripts/voicevox_manager.sh start
```

**出力例:**
```
[2025-10-03 15:00:00] Starting VOICEVOX Nemo server...
[2025-10-03 15:00:05] Pulling Docker image (if needed)...
[2025-10-03 15:00:10] Starting container...
[2025-10-03 15:00:15] Waiting for VOICEVOX Nemo to be ready...
[2025-10-03 15:00:30] ✅ VOICEVOX Nemo started successfully on port 50121
```

#### 手動起動（デバッグ用）

```bash
docker run -d \
  --rm \
  --name voicevox-nemo \
  -p 50121:50021 \
  voicevox/voicevox_engine:cpu-ubuntu20.04-latest
```

---

### 3. 動作確認

#### ステータス確認
```bash
./scripts/voicevox_manager.sh status
```

**期待される出力:**
```
✅ VOICEVOX Nemo is running
   Container ID: abc123def456
   Port: 50121
   Health: OK
```

#### 音声合成テスト
```bash
./scripts/voicevox_manager.sh test
```

**期待される出力:**
```
[2025-10-03 15:01:00] Testing VOICEVOX Nemo synthesis...
[2025-10-03 15:01:05] Creating audio query...
[2025-10-03 15:01:10] Synthesizing audio...
[2025-10-03 15:01:15] ✅ Test successful! Audio saved to: logs/voicevox_test.wav
[2025-10-03 15:01:15] File size: 256K
```

#### ログ確認
```bash
./scripts/voicevox_manager.sh logs
```

---

## トラブルシューティング

### 問題1: Dockerコマンドが見つからない

**症状:**
```
The command 'docker' could not be found in this WSL 2 distro.
```

**原因:**
- Docker DesktopのWSL2統合が無効

**解決策:**
1. Docker Desktop → Settings → Resources → WSL Integration
2. 使用中のWSL2ディストリビューションにチェック
3. Apply & Restart

**確認:**
```bash
docker --version
```

---

### 問題2: Docker Daemonに接続できない

**症状:**
```bash
$ docker ps
Cannot connect to the Docker daemon at unix:///var/run/docker.sock.
Is the docker daemon running?
```

**原因:**
- Docker Desktopが起動していない
- Docker Daemonが停止している

**解決策:**

**方法A: Docker Desktopを起動（Windows側）**
1. Windowsで「Docker Desktop」を起動
2. タスクトレイのDockerアイコンが緑色になるまで待つ

**方法B: WSL2を再起動**
```powershell
# PowerShellで実行
wsl --shutdown
# WSL2を再度開く
```

**確認:**
```bash
docker ps  # エラーが出なければOK
```

---

### 問題3: ポート50121が既に使用されている

**症状:**
```bash
$ ./scripts/voicevox_manager.sh start
Error: port is already allocated
```

**原因:**
- 既に別のVOICEVOXコンテナが起動している
- 他のアプリケーションがポート50121を使用

**解決策:**

**Step 1: 使用中のプロセスを確認**
```bash
sudo lsof -i :50121
```

**Step 2: 既存のVOICEVOXコンテナを停止**
```bash
./scripts/voicevox_manager.sh stop

# または
docker stop voicevox-nemo
docker rm voicevox-nemo
```

**Step 3: 再起動**
```bash
./scripts/voicevox_manager.sh start
```

---

### 問題4: コンテナが起動しない

**症状:**
```bash
$ ./scripts/voicevox_manager.sh status
❌ VOICEVOX Nemo is not running
```

**原因:**
- メモリ不足
- Dockerイメージのダウンロード失敗

**解決策:**

**Step 1: ログ確認**
```bash
./scripts/voicevox_manager.sh logs
```

**Step 2: 手動起動してエラーを確認**
```bash
docker run --rm -p 50121:50021 voicevox/voicevox_engine:cpu-ubuntu20.04-latest
# Ctrl+Cで停止
```

**Step 3: Dockerリソースを確認**
```bash
docker system df
docker system prune  # 不要なデータを削除
```

---

### 問題5: 音声合成テストが失敗する

**症状:**
```bash
$ ./scripts/voicevox_manager.sh test
[ERROR] Failed to create audio query
```

**原因:**
- VOICEVOXサーバーが完全に起動していない
- ネットワークの問題

**解決策:**

**Step 1: サーバーの完全起動を待つ**
```bash
# 起動後30秒待機
sleep 30

# 再度テスト
./scripts/voicevox_manager.sh test
```

**Step 2: 手動でヘルスチェック**
```bash
curl http://localhost:50121/health
# 出力: "OK" または空の場合は起動中
```

**Step 3: コンテナを再起動**
```bash
./scripts/voicevox_manager.sh restart
```

---

### 問題6: WSL2でメモリ不足

**症状:**
- Dockerコンテナが頻繁にクラッシュ
- システムが遅い

**原因:**
- WSL2のメモリ制限

**解決策:**

**Step 1: WSL2のメモリ制限を調整**

`C:\Users\<ユーザー名>\.wslconfig` を作成/編集:

```ini
[wsl2]
memory=4GB
processors=2
swap=2GB
```

**Step 2: WSL2を再起動**
```powershell
wsl --shutdown
```

**Step 3: 確認**
```bash
free -h  # メモリ確認
```

---

## Dockerが使えない場合の代替手段

### 自動フォールバック

VOICEVOX Nemoが利用できない場合、システムは自動的に以下のTTSにフォールバックします：

1. **gTTS（Google TTS Free）**
   - インターネット接続必要
   - 完全無料
   - 品質: 中

2. **pyttsx3（オフライン）**
   - インターネット接続不要
   - 完全無料
   - 品質: 低
   - 最終フォールバック

### 確認方法

```bash
python -m app.verify
```

**出力例（Dockerなし）:**
```
⚠️  VOICEVOX Nemo not available - will use fallback TTS (gTTS, pyttsx3)
✅ SYSTEM READY (with warnings)
```

---

## 管理コマンド一覧

### 基本操作

```bash
# 起動
./scripts/voicevox_manager.sh start

# 停止
./scripts/voicevox_manager.sh stop

# 再起動
./scripts/voicevox_manager.sh restart

# ステータス確認
./scripts/voicevox_manager.sh status

# ログ表示
./scripts/voicevox_manager.sh logs

# 音声合成テスト
./scripts/voicevox_manager.sh test
```

### Docker直接操作

```bash
# コンテナ一覧
docker ps | grep voicevox

# ログをリアルタイム表示
docker logs -f voicevox-nemo

# コンテナに入る
docker exec -it voicevox-nemo /bin/bash

# コンテナを強制停止
docker stop voicevox-nemo
docker rm -f voicevox-nemo
```

---

## パフォーマンス

### リソース使用量

| 項目 | 値 |
|------|-----|
| メモリ使用量 | 約500MB～1GB |
| CPU使用率 | 音声合成時: 50-100% |
| ディスク容量 | Dockerイメージ: 約2GB |
| 起動時間 | 初回: 30-60秒、2回目以降: 10-20秒 |

### 音声合成速度

| テキスト長 | 処理時間 |
|-----------|---------|
| 50文字 | 約2秒 |
| 200文字 | 約5秒 |
| 500文字 | 約10秒 |
| 1000文字 | 約20秒 |

---

## セキュリティ

### ネットワークアクセス

- **ローカルホストのみ**: `localhost:50121`
- 外部からのアクセス不可
- ファイアウォール設定不要

### データプライバシー

- ✅ 完全ローカル実行
- ✅ データは外部送信されない
- ✅ インターネット接続不要（Dockerイメージダウンロード後）

---

## よくある質問

### Q1: VOICEVOXとVOICEVOX Nemoの違いは？

**A:** VOICEVOX NemoはVOICEVOXのDocker版です。機能は同じですが、より簡単にセットアップできます。

---

### Q2: 商用利用は可能？

**A:** はい。VOICEVOX Nemoは商用利用可能です（LGPL-3.0ライセンス）。

---

### Q3: GPU版を使える？

**A:** 現在はCPU版のみサポートしています。GPU版を使用する場合は、Dockerイメージを以下に変更してください：

```bash
voicevox/voicevox_engine:gpu-ubuntu20.04-latest
```

---

### Q4: 起動を自動化できる？

**A:** はい。systemdやcronで自動起動できます：

```bash
# crontab -e
@reboot /home/kafka/projects/youtuber/scripts/voicevox_manager.sh start
```

---

### Q5: 他のポートを使いたい

**A:** `config.yaml`と管理スクリプトを修正してください：

**config.yaml:**
```yaml
tts:
  voicevox:
    port: 50021  # 変更したいポート番号
```

**scripts/voicevox_manager.sh:**
```bash
VOICEVOX_PORT=50021  # 5行目を変更
```

---

## 関連リンク

- **VOICEVOX公式**: https://voicevox.hiroshiba.jp/
- **Docker Hub**: https://hub.docker.com/r/voicevox/voicevox_engine
- **GitHub**: https://github.com/VOICEVOX/voicevox_engine
- **Docker Desktop for Windows**: https://www.docker.com/products/docker-desktop/
- **WSL2ドキュメント**: https://docs.docker.com/go/wsl2/

---

## サポート

問題が解決しない場合:

1. **ログを確認**: `logs/voicevox_nemo.log`
2. **システム検証**: `python -m app.verify`
3. **Issue報告**: https://github.com/anthropics/claude-code/issues

---

**最終更新**: 2025年10月3日
