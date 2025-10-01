"""
動画生成モジュール

音声ファイル、字幕ファイル、背景画像を組み合わせて最終的な動画を生成します。
FFmpegを使用して高品質な動画出力を実現します。
"""

import os
import logging
import subprocess
import tempfile
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
from pydub import AudioSegment
from app.config import cfg

logger = logging.getLogger(__name__)

class VideoGenerator:
    """動画生成クラス"""

    def __init__(self):
        self.ffmpeg_path = cfg.ffmpeg_path or "ffmpeg"
        self.video_quality = cfg.video_quality or "high"
        self.output_format = "mp4"

        if not self._check_ffmpeg():
            logger.warning("FFmpeg not found in PATH or specified location")
        else:
            logger.info("Video generator initialized")

    def _check_ffmpeg(self) -> bool:
        """FFmpegの存在確認"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def generate_video(self,
                      audio_path: str,
                      subtitle_path: str,
                      background_image: str = None,
                      title: str = "Economic News Analysis",
                      output_path: str = None) -> str:
        """
        動画を生成

        Args:
            audio_path: 音声ファイルのパス
            subtitle_path: 字幕ファイルのパス (.srt)
            background_image: 背景画像のパス
            title: 動画タイトル
            output_path: 出力パス

        Returns:
            生成された動画ファイルのパス
        """
        try:
            # 入力ファイルの検証
            self._validate_input_files(audio_path, subtitle_path, background_image)

            # 出力パスを決定
            if not output_path:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_path = f"video_{timestamp}.{self.output_format}"

            # 背景画像を準備
            bg_image_path = self._prepare_background_image(background_image, title)

            # 音声の長さを取得
            audio_duration = self._get_audio_duration(audio_path)

            # FFmpegコマンドを構築
            ffmpeg_command = self._build_ffmpeg_command(
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                background_path=bg_image_path,
                output_path=output_path,
                duration=audio_duration
            )

            # 動画生成を実行
            self._run_ffmpeg(ffmpeg_command)

            # 生成された動画の情報を取得
            video_info = self._get_video_info(output_path)
            logger.info(f"Video generated successfully: {output_path}")
            logger.info(f"Video info: {video_info}")

            return output_path

        except Exception as e:
            logger.error(f"Video generation failed: {e}")
            return self._generate_fallback_video(audio_path, title)

        finally:
            # 一時ファイルをクリーンアップ
            if 'bg_image_path' in locals() and bg_image_path != background_image:
                try:
                    os.remove(bg_image_path)
                except Exception:
                    pass

    def _validate_input_files(self, audio_path: str, subtitle_path: str,
                             background_image: str = None):
        """入力ファイルの検証"""
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if not os.path.exists(subtitle_path):
            raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")

        if background_image and not os.path.exists(background_image):
            logger.warning(f"Background image not found: {background_image}, using default")

        # 音声ファイル形式の確認
        try:
            AudioSegment.from_file(audio_path)
        except Exception as e:
            raise ValueError(f"Invalid audio file format: {e}")

    def _prepare_background_image(self, background_image: str = None,
                                 title: str = "News Analysis") -> str:
        """背景画像を準備"""
        if background_image and os.path.exists(background_image):
            return background_image

        # デフォルト背景画像を生成
        return self._create_default_background(title)

    def _create_default_background(self, title: str) -> str:
        """デフォルト背景画像を生成"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            import textwrap

            # 1920x1080の背景画像を作成
            width, height = 1920, 1080
            image = Image.new('RGB', (width, height), color=(25, 35, 45))
            draw = ImageDraw.Draw(image)

            # タイトルテキストを描画
            try:
                # システムフォントを試行
                font_size = 72
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except Exception:
                try:
                    # フォールバックフォント
                    font = ImageFont.load_default()
                except Exception:
                    font = None

            if font:
                # テキストを改行
                wrapped_title = textwrap.fill(title, width=20)

                # テキストサイズを計算
                bbox = draw.textbbox((0, 0), wrapped_title, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

                # 中央配置
                x = (width - text_width) // 2
                y = (height - text_height) // 2

                # テキストを描画（影付き）
                shadow_offset = 3
                draw.text((x + shadow_offset, y + shadow_offset), wrapped_title,
                         font=font, fill=(0, 0, 0, 128))  # 影
                draw.text((x, y), wrapped_title, font=font, fill=(255, 255, 255))  # メインテキスト

            # グラデーション効果を追加
            for y_pos in range(height):
                alpha = int(255 * (1 - y_pos / height) * 0.3)
                overlay = Image.new('RGBA', (width, 1), (70, 130, 180, alpha))
                image.paste(overlay, (0, y_pos), overlay)

            # 一時ファイルに保存
            temp_path = tempfile.mktemp(suffix='.png')
            image.save(temp_path, 'PNG')
            logger.debug(f"Created default background: {temp_path}")
            return temp_path

        except Exception as e:
            logger.warning(f"Failed to create default background: {e}")
            # 最終フォールバック: 単色画像
            return self._create_simple_background()

    def _create_simple_background(self) -> str:
        """シンプルな単色背景を生成"""
        try:
            from PIL import Image

            # 1920x1080の単色背景
            image = Image.new('RGB', (1920, 1080), color=(25, 35, 45))
            temp_path = tempfile.mktemp(suffix='.png')
            image.save(temp_path, 'PNG')
            return temp_path

        except Exception as e:
            logger.error(f"Failed to create simple background: {e}")
            # 最終的にはNoneを返し、FFmpegで色生成
            return None

    def _get_audio_duration(self, audio_path: str) -> float:
        """音声ファイルの長さを取得"""
        try:
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0  # ミリ秒を秒に変換
        except Exception as e:
            logger.warning(f"Failed to get audio duration: {e}")
            return 60.0  # デフォルト1分

    def _build_ffmpeg_command(self, audio_path: str, subtitle_path: str,
                             background_path: str, output_path: str,
                             duration: float) -> List[str]:
        """FFmpegコマンドを構築"""
        command = [self.ffmpeg_path]

        # 入力ファイル
        if background_path:
            # 背景画像から動画を作成
            command.extend([
                "-loop", "1",
                "-i", background_path,
                "-i", audio_path,
                "-c:v", "libx264"
            ])
        else:
            # 単色背景を使用
            command.extend([
                "-f", "lavfi",
                "-i", f"color=c=0x193d5a:size=1920x1080:duration={duration}",
                "-i", audio_path,
                "-c:v", "libx264"
            ])

        # 品質設定
        quality_settings = self._get_quality_settings()
        command.extend(quality_settings)

        # 字幕フィルタを追加
        subtitle_filter = self._build_subtitle_filter(subtitle_path)
        if subtitle_filter:
            command.extend(["-vf", subtitle_filter])

        # 音声設定
        command.extend([
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100"
        ])

        # 出力設定
        command.extend([
            "-t", str(duration),
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-y",  # 上書き許可
            output_path
        ])

        logger.debug(f"FFmpeg command: {' '.join(command)}")
        return command

    def _get_quality_settings(self) -> List[str]:
        """品質設定を取得"""
        quality_presets = {
            "low": ["-preset", "fast", "-crf", "28"],
            "medium": ["-preset", "medium", "-crf", "23"],
            "high": ["-preset", "slow", "-crf", "18"],
            "ultra": ["-preset", "veryslow", "-crf", "15"]
        }
        return quality_presets.get(self.video_quality, quality_presets["medium"])

    def _build_subtitle_filter(self, subtitle_path: str) -> str:
        """字幕フィルタを構築"""
        try:
            # SRTファイルのパスをエスケープ
            escaped_path = subtitle_path.replace("\\", "\\\\").replace(":", "\\:")

            # 字幕スタイル設定
            subtitle_style = (
                f"subtitles='{escaped_path}'"
                f":force_style='FontName=DejaVu Sans Bold,"
                f"FontSize=24,"
                f"PrimaryColour=&H00ffffff,"
                f"OutlineColour=&H00000000,"
                f"BorderStyle=1,"
                f"Outline=2,"
                f"Shadow=0,"
                f"Alignment=2,"
                f"MarginV=80'"
            )

            return subtitle_style

        except Exception as e:
            logger.warning(f"Failed to build subtitle filter: {e}")
            return None

    def _run_ffmpeg(self, command: List[str]):
        """FFmpegを実行"""
        try:
            logger.info("Starting video generation with FFmpeg...")

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=600  # 10分のタイムアウト
            )

            if result.returncode != 0:
                error_msg = f"FFmpeg failed with code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr}"
                raise subprocess.CalledProcessError(result.returncode, command, result.stderr)

            logger.info("FFmpeg completed successfully")

        except subprocess.TimeoutExpired:
            raise Exception("FFmpeg process timed out after 10 minutes")
        except Exception as e:
            logger.error(f"FFmpeg execution failed: {e}")
            raise

    def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """動画情報を取得"""
        try:
            command = [
                self.ffmpeg_path, "-i", video_path,
                "-f", "null", "-"
            ]

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30
            )

            # ファイルサイズを取得
            file_size = os.path.getsize(video_path)

            info = {
                "file_size_mb": file_size / (1024 * 1024),
                "file_path": video_path,
                "format": self.output_format
            }

            # FFmpegの出力から詳細情報を抽出
            if result.stderr:
                lines = result.stderr.split('\n')
                for line in lines:
                    if "Duration:" in line:
                        duration_part = line.split("Duration:")[1].split(",")[0].strip()
                        info["duration"] = duration_part
                    elif "Video:" in line:
                        info["video_codec"] = "h264"
                        if "1920x1080" in line:
                            info["resolution"] = "1920x1080"

            return info

        except Exception as e:
            logger.warning(f"Failed to get video info: {e}")
            return {"file_size_mb": 0, "error": str(e)}

    def _generate_fallback_video(self, audio_path: str, title: str) -> str:
        """フォールバック用の簡易動画を生成"""
        try:
            logger.warning("Generating fallback video...")

            # 音声の長さを取得
            duration = self._get_audio_duration(audio_path)

            # 簡単なFFmpegコマンド
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"fallback_video_{timestamp}.{self.output_format}"

            command = [
                self.ffmpeg_path,
                "-f", "lavfi",
                "-i", f"color=c=0x193d5a:size=1920x1080:duration={duration}",
                "-i", audio_path,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "28",
                "-c:a", "aac",
                "-b:a", "128k",
                "-t", str(duration),
                "-pix_fmt", "yuv420p",
                "-y",
                output_path
            ]

            result = subprocess.run(command, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                logger.info(f"Fallback video generated: {output_path}")
                return output_path
            else:
                logger.error(f"Fallback video generation failed: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Fallback video generation error: {e}")
            return None

    def create_preview_video(self, audio_path: str, duration: int = 30) -> str:
        """プレビュー動画を生成（指定秒数）"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"preview_{timestamp}.{self.output_format}"

            command = [
                self.ffmpeg_path,
                "-f", "lavfi",
                "-i", f"color=c=0x193d5a:size=1280x720:duration={duration}",
                "-i", audio_path,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "25",
                "-c:a", "aac",
                "-b:a", "96k",
                "-t", str(duration),
                "-pix_fmt", "yuv420p",
                "-y",
                output_path
            ]

            subprocess.run(command, capture_output=True, text=True, timeout=120)
            logger.info(f"Preview video created: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Preview video creation failed: {e}")
            return None

    def batch_generate_videos(self, video_specs: List[Dict[str, Any]]) -> List[str]:
        """バッチで複数動画を生成"""
        generated_videos = []

        for i, spec in enumerate(video_specs):
            try:
                logger.info(f"Generating video {i+1}/{len(video_specs)}")

                video_path = self.generate_video(
                    audio_path=spec.get("audio_path"),
                    subtitle_path=spec.get("subtitle_path"),
                    background_image=spec.get("background_image"),
                    title=spec.get("title", f"Video {i+1}"),
                    output_path=spec.get("output_path")
                )

                if video_path:
                    generated_videos.append(video_path)

            except Exception as e:
                logger.error(f"Failed to generate video {i+1}: {e}")
                continue

        logger.info(f"Batch generation completed: {len(generated_videos)}/{len(video_specs)} videos")
        return generated_videos

# グローバルインスタンス
video_generator = VideoGenerator()

def generate_video(audio_path: str, subtitle_path: str,
                  background_image: str = None, title: str = "Economic News") -> str:
    """動画生成の簡易関数"""
    return video_generator.generate_video(
        audio_path, subtitle_path, background_image, title
    )

def create_preview(audio_path: str, duration: int = 30) -> str:
    """プレビュー動画作成の簡易関数"""
    return video_generator.create_preview_video(audio_path, duration)

if __name__ == "__main__":
    # テスト実行
    print("Testing video generation...")

    # FFmpeg確認
    generator = VideoGenerator()
    print(f"FFmpeg available: {generator._check_ffmpeg()}")

    # テスト用ファイルの存在確認
    test_files = {
        "audio": ["output_audio.wav", "test_audio.wav", "sample.mp3"],
        "subtitle": ["subtitles.srt", "test.srt"],
        "background": ["background.png", "bg.jpg"]
    }

    available_files = {}
    for file_type, paths in test_files.items():
        for path in paths:
            if os.path.exists(path):
                available_files[file_type] = path
                print(f"Found {file_type} file: {path}")
                break

    if generator._check_ffmpeg() and "audio" in available_files:
        try:
            # プレビュー動画テスト
            print("\nTesting preview video generation...")
            preview_path = generator.create_preview_video(available_files["audio"], 10)
            if preview_path:
                print(f"Preview video created: {preview_path}")
                info = generator._get_video_info(preview_path)
                print(f"Preview info: {info}")

            # 字幕付き動画テスト（字幕ファイルがある場合）
            if "subtitle" in available_files:
                print("\nTesting full video generation...")
                video_path = generator.generate_video(
                    audio_path=available_files["audio"],
                    subtitle_path=available_files["subtitle"],
                    background_image=available_files.get("background"),
                    title="Test Economic News Video"
                )
                if video_path:
                    print(f"Full video created: {video_path}")
                    info = generator._get_video_info(video_path)
                    print(f"Video info: {info}")

        except Exception as e:
            print(f"Test failed: {e}")
    else:
        print("FFmpeg not available or no test audio files found, skipping tests")

    # デフォルト背景作成テスト
    try:
        print("\nTesting background image creation...")
        bg_path = generator._create_default_background("Test Economic News")
        if bg_path and os.path.exists(bg_path):
            print(f"Default background created: {bg_path}")
            os.remove(bg_path)  # テスト後削除
    except Exception as e:
        print(f"Background creation test failed: {e}")