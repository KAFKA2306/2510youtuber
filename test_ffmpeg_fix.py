#!/usr/bin/env python3
"""Quick test to verify FFmpeg fix."""

import os
import subprocess
import tempfile
from app.video import VideoGenerator

def main():
    print("Testing FFmpeg video generation fix...")

    vg = VideoGenerator()

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "test_audio.wav")
        subtitle_path = os.path.join(tmpdir, "test_subtitle.srt")
        video_path = os.path.join(tmpdir, "test_video.mp4")

        # Create 2 second audio
        print("Creating test audio...")
        subprocess.run([
            "ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", "2.0", "-y", audio_path
        ], capture_output=True, check=True)

        # Create subtitle
        print("Creating test subtitle...")
        with open(subtitle_path, "w", encoding="utf-8") as f:
            f.write("1\n00:00:00,000 --> 00:00:02,000\nテスト字幕\n")

        # Generate video
        print("Generating video (this should complete in ~5-10 seconds)...")
        try:
            result_path = vg.generate_video(
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                output_path=video_path,
                enable_ab_test=False,
                use_stock_footage=False,
                title="Test Video"
            )

            print(f"✓ Video generated: {result_path}")

            # Check file size
            file_size = os.path.getsize(result_path)
            print(f"✓ File size: {file_size:,} bytes")

            # Check duration
            probe_result = subprocess.run([
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                result_path
            ], capture_output=True, text=True, check=True)

            duration = float(probe_result.stdout.strip())
            print(f"✓ Video duration: {duration:.2f}s")

            # Check frame count
            probe_result = subprocess.run([
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-count_packets",
                "-show_entries", "stream=nb_read_packets",
                "-of", "csv=p=0",
                result_path
            ], capture_output=True, text=True, check=True)

            frame_count = int(probe_result.stdout.strip())
            expected_frames = int(2.0 * vg.motion_fps)
            print(f"✓ Frame count: {frame_count} (expected ~{expected_frames})")

            if abs(duration - 2.0) <= 0.1 and frame_count >= expected_frames - 2:
                print("\n✅ SUCCESS: Video generation working correctly!")
                return 0
            else:
                print("\n❌ FAIL: Video metadata incorrect")
                return 1

        except Exception as e:
            print(f"\n❌ FAIL: {e}")
            import traceback
            traceback.print_exc()
            return 1

if __name__ == "__main__":
    exit(main())
