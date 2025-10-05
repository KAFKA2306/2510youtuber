# VideoGeneratorにおけるエラー頻発ポイントと恒久対策案

本ドキュメントでは、運用中に再発している `VideoGenerator` 関連の障害ログを踏まえ、コードの構造から再現性が高い失敗パターンを特定し、恒久対策の方向性を整理する。

## 1. FFmpegバイナリ検出と共有設定の不足

- `VideoGenerator._get_audio_duration` は `AudioSegment.from_file` を呼び出すが、Pydub は内部で FFmpeg バイナリを利用するため、`ffmpeg` がパスに存在しない環境ではここで例外が発生し動画生成全体が停止する。【F:app/video.py†L390-L396】
- B-roll 生成クラスも同じく FFmpeg を前提としているが、初期化時に `subprocess.run([ffmpeg_path, "-version"])` を試すのみで、失敗しても警告ログで終了してしまうため後続処理まで進んでから致命的に失敗する。【F:app/services/media/broll_generator.py†L24-L35】
- 設定ロード時に `shutil.which` と `imageio_ffmpeg` による自動検出は行っているが、検出結果を Pydub に伝搬していないため、環境によっては `AudioSegment` が未解決の `ffmpeg` を指し続ける。【F:app/config/settings.py†L336-L360】
- 実際にユニットテストでも「Couldn't find ffmpeg or avconv」という警告が出ており、エラーの温床になっていることが確認できる。【4356c6†L1-L35】

**恒久対策案**
1. 設定初期化後に `AudioSegment.converter` と `AudioSegment.ffmpeg` を `settings.ffmpeg_path` に強制的に上書きし、全コンポーネントで同じバイナリを参照させる。
2. `app.verify` もしくは `FileArchivalManager` と同等の初期化フェーズで `ffmpeg -version` と `ffmpeg -filters` を実行し、失敗時は早期に例外で停止する（警告ではなく必須依存と扱う）。
3. Docker / systemd 環境に静的 FFmpeg バイナリをバンドルし、`FFMPEG_PATH` を設定ファイルで明示できるようにする。CI 上では `imageio_ffmpeg.get_ffmpeg_exe()` の結果をキャッシュし、欠落時に自動ダウンロードする。
4. 上記を自動テスト化するため、`pytest` に `@pytest.mark.integration` の初期化チェックを追加し、`settings.ffmpeg_path` で実際に 1 秒の無音動画を生成できるか検証する。

## 2. B-roll クロスフェードフィルタの境界条件不備

- ストック映像を複数結合する場合、クリップごとの長さを `clip_duration = target_duration / len(valid_clips)` と算出し、固定値 `transition_duration=1.0` をそのまま差し引いた `offset` を `xfade` に渡している。【F:app/services/media/broll_generator.py†L81-L98】【F:app/services/media/broll_generator.py†L205-L248】
- クリップ数が多い／目標尺が短い場合に `clip_duration <= transition_duration` となると `offset` が 0 以下になり、FFmpeg が `xfade` フィルタの引数不正で失敗する。失敗時には例外が投げられ、「Failed to create B-roll sequence」で静止画フォールバックに落ちるため、ストック映像が実質使えなくなる。
- さらに、`xfade` フィルタは FFmpeg 4.2 以降で追加されたため、旧バージョンではフィルタそのものが存在せず同じく失敗する。現状はバージョン検査を行っていない。

**恒久対策案**
1. `clip_duration` の 40〜50% を上限として `transition_duration` を自動クリップし、`offset` が常に正になるよう制約を追加する。極端に短い場合はクロスフェード自体をスキップし `concat` ベースに切り替える。
2. 初期化時に `ffmpeg -filters` を実行して `xfade` の有無を検出し、未対応環境では `create_simple_sequence`（`concat` ベース）に自動ダウングレードする。【F:app/services/media/broll_generator.py†L300-L337】
3. 失敗時のログだけでなく、`_generate_with_stock_footage` から例外を投げて上位に伝搬させ、運用監視で検出しやすくする。【F:app/video.py†L552-L664】
4. 代表的な短尺・長尺パターンをカバーするユニットテストを追加し、`transition_duration` の自動調整が効いているか検証する。

## 3. 字幕フォント解決失敗による `subtitles` フィルタエラー

- 字幕の `force_style` を生成する際、`fc-list` で和文フォントを探索し見つからなかった場合は `"Arial"` を返す仕様だが、コンテナ環境では `Arial` が存在しないことが多く、FFmpeg の `subtitles` フィルタが `Fontconfig error` で失敗する原因になる。【F:app/video.py†L414-L516】
- `fc-list` 自体が存在しない Windows 環境では `subprocess.run` が `FileNotFoundError` を投げ、例外が握りつぶされて `"Arial"` フォールバックに落ちる。結果としてマルチプラットフォームで同じ失敗パターンが再現する。

**恒久対策案**
1. リポジトリに OSS の日本語フォント（例: Noto Sans CJK）を同梱し、`settings.subtitle_font_path` で明示的にパスを渡せるようにする。`force_style` では `FontName` ではなく `fontsdir`/`fontfile` オプションを使うことで `Fontconfig` に依存しない描画に切り替える。
2. `fc-list` が利用できない環境では `subprocess.run` をスキップする条件分岐を追加し、フォント解決を OS 判定ベースに切り替える（Windows は `C:\\Windows\\Fonts\\*.ttc` を優先など）。
3. `app.verify` に字幕フォントの存在チェックを追加し、欠落している場合は起動前に明示的なエラーと対処方法を提示する。
4. CI で `ffmpeg` を使った 5 秒程度の字幕焼き込みスモークテストを実行し、フォント解決エラーの回帰を検知する。

## 4. 実装ロードマップ（提案）

1. **フェーズ1**: FFmpeg パス統一と起動前検証 (`AudioSegment` 連携、`app.verify` 拡張)。
2. **フェーズ2**: B-roll クロスフェードの境界条件修正とフィルタ対応状況の自動検出。
3. **フェーズ3**: 字幕フォント解決の再設計（バンドルフォント導入・設定拡張・CI スモークテスト）。
4. **フェーズ4**: 上記変更に伴うドキュメント更新と運用 Runbook の改訂。

これらを段階的に実装することで、VideoGenerator の主要な失敗パスを事前に封じ、ストック映像と字幕付き動画の安定稼働を実現できる。
