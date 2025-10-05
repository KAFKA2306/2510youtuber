"""B-roll video generation from stock footage clips.

複数のストック映像クリップを組み合わせて、
プロフェッショナルなB-roll動画シーケンスを生成します。
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from app.services.media.ffmpeg_support import ensure_ffmpeg_tooling

logger = logging.getLogger(__name__)


class BRollGenerator:
    """Generate professional B-roll sequences from stock footage clips."""

    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        """Initialize B-roll generator.

        Args:
            ffmpeg_path: Path to ffmpeg executable
        """
        self.ffmpeg_path = ensure_ffmpeg_tooling(ffmpeg_path)

    def create_broll_sequence(
        self,
        clip_paths: List[str],
        target_duration: float,
        output_path: Optional[str] = None,
        transition_duration: float = 1.0,
        enable_effects: bool = True,
    ) -> Optional[str]:
        """Create B-roll sequence from multiple clips.

        Args:
            clip_paths: List of video clip file paths
            target_duration: Target duration in seconds
            output_path: Output file path (temp file if not specified)
            transition_duration: Crossfade transition duration in seconds
            enable_effects: Enable zoom/pan effects (Ken Burns)

        Returns:
            Path to generated B-roll video, or None if failed
        """
        if not clip_paths:
            logger.error("No clips provided for B-roll generation")
            return None

        # Validate input clips
        valid_clips = [p for p in clip_paths if os.path.exists(p)]
        if not valid_clips:
            logger.error("No valid clips found")
            return None

        if len(valid_clips) < len(clip_paths):
            logger.warning(f"Only {len(valid_clips)}/{len(clip_paths)} clips are valid")

        # Output path
        if not output_path:
            output_path = os.path.join(tempfile.gettempdir(), f"broll_{os.getpid()}.mp4")

        logger.info(f"Generating B-roll from {len(valid_clips)} clips (target: {target_duration}s)")

        # Calculate clip duration
        clip_duration = target_duration / len(valid_clips)

        try:
            if len(valid_clips) == 1:
                # Single clip: just apply effects
                return self._process_single_clip(valid_clips[0], target_duration, output_path, enable_effects)
            else:
                # Multiple clips: concatenate with transitions
                return self._concatenate_clips(
                    valid_clips,
                    clip_duration,
                    output_path,
                    transition_duration,
                    enable_effects,
                )

        except Exception as e:
            logger.error(f"Failed to create B-roll sequence: {e}")
            return None

    def _process_single_clip(
        self,
        clip_path: str,
        duration: float,
        output_path: str,
        enable_effects: bool,
    ) -> Optional[str]:
        """Process a single clip with effects.

        Args:
            clip_path: Input clip path
            duration: Target duration
            output_path: Output path
            enable_effects: Enable zoom/pan effects

        Returns:
            Output path or None if failed
        """
        try:
            # Build filter complex
            filters = []

            # Scale to 1920x1080
            filters.append("scale=1920:1080:force_original_aspect_ratio=increase")
            filters.append("crop=1920:1080")

            # Ken Burns effect (slow zoom)
            if enable_effects:
                filters.append(f"zoompan=z='min(zoom+0.001,1.2)':d={int(duration * 25)}:s=1920x1080:fps=25")

            # Color grading (warm, professional)
            filters.append("eq=contrast=1.1:brightness=0.02:saturation=1.15")

            filter_str = ",".join(filters)

            # Run ffmpeg
            cmd = [
                self.ffmpeg_path,
                "-i",
                clip_path,
                "-vf",
                filter_str,
                "-t",
                str(duration),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-an",  # No audio
                "-y",
                output_path,
            ]

            subprocess.run(cmd, check=True, capture_output=True, timeout=300)

            if os.path.exists(output_path):
                logger.info(f"Processed single clip: {output_path}")
                return output_path

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg processing timeout")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
        except Exception as e:
            logger.error(f"Error processing clip: {e}")

        return None

    def _concatenate_clips(
        self,
        clip_paths: List[str],
        clip_duration: float,
        output_path: str,
        transition_duration: float,
        enable_effects: bool,
    ) -> Optional[str]:
        """Concatenate multiple clips with crossfade transitions.

        Args:
            clip_paths: List of input clip paths
            clip_duration: Duration per clip
            output_path: Output path
            transition_duration: Crossfade duration
            enable_effects: Enable zoom/pan effects

        Returns:
            Output path or None if failed
        """
        try:
            # Build complex filter for crossfade concatenation
            # Input clips
            input_args = []
            for clip in clip_paths:
                input_args.extend(["-i", clip])

            # Build filter complex
            filter_parts = []
            current_label = None

            for i, clip in enumerate(clip_paths):
                # Process each clip
                base_filters = [
                    f"[{i}:v]",
                    f"trim=duration={clip_duration}",
                    "scale=1920:1080:force_original_aspect_ratio=increase",
                    "crop=1920:1080",
                ]

                # Add effects
                if enable_effects:
                    # Alternate between zoom in and zoom out
                    if i % 2 == 0:
                        base_filters.append(
                            f"zoompan=z='min(zoom+0.0015,1.3)':d={int(clip_duration * 25)}:s=1920x1080:fps=25"
                        )
                    else:
                        base_filters.append(
                            f"zoompan=z='if(lte(zoom,1.0),1.3,max(1.0,zoom-0.0015))':d={int(clip_duration * 25)}:s=1920x1080:fps=25"
                        )

                # Color grading
                base_filters.append("eq=contrast=1.1:brightness=0.02:saturation=1.15")
                base_filters.append("fade=t=in:st=0:d=0.5")
                base_filters.append(f"fade=t=out:st={clip_duration - 0.5}:d=0.5")

                clip_label = f"v{i}"
                base_filters.append(f"[{clip_label}]")

                filter_parts.append("".join(base_filters))

                # Add crossfade between clips
                if i > 0:
                    prev_label = current_label
                    next_label = f"vf{i}"

                    offset = clip_duration - transition_duration
                    crossfade = (
                        f"[{prev_label}][{clip_label}]"
                        f"xfade=transition=fade:duration={transition_duration}:offset={offset}"
                        f"[{next_label}]"
                    )
                    filter_parts.append(crossfade)
                    current_label = next_label
                else:
                    current_label = clip_label

            # Combine all filters
            filter_complex = ";".join(filter_parts)

            # Run ffmpeg
            cmd = [
                self.ffmpeg_path,
                *input_args,
                "-filter_complex",
                filter_complex,
                "-map",
                f"[{current_label}]",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-y",
                output_path,
            ]

            logger.debug(f"FFmpeg command: {' '.join(cmd)}")

            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                timeout=600,  # 10 minutes max
            )

            if os.path.exists(output_path):
                file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                logger.info(f"Created B-roll sequence: {output_path} ({file_size_mb:.1f} MB)")
                return output_path

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg concatenation timeout (>10 minutes)")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg concatenation error: {e.stderr.decode() if e.stderr else e}")
        except Exception as e:
            logger.error(f"Error concatenating clips: {e}")

        return None

    def create_simple_sequence(
        self,
        clip_paths: List[str],
        target_duration: float,
        output_path: Optional[str] = None,
    ) -> Optional[str]:
        """Create simple B-roll sequence without effects (faster, fallback).

        Args:
            clip_paths: List of input clip paths
            target_duration: Target duration
            output_path: Output path

        Returns:
            Output path or None if failed
        """
        if not output_path:
            output_path = os.path.join(tempfile.gettempdir(), f"broll_simple_{os.getpid()}.mp4")

        # Create concat file
        concat_file = os.path.join(tempfile.gettempdir(), f"concat_{os.getpid()}.txt")

        try:
            clip_duration = target_duration / len(clip_paths)

            with open(concat_file, "w") as f:
                for clip in clip_paths:
                    if os.path.exists(clip):
                        f.write(f"file '{os.path.abspath(clip)}'\n")
                        f.write(f"duration {clip_duration}\n")

            # Simple concatenation
            cmd = [
                self.ffmpeg_path,
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_file,
                "-vf",
                "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-an",
                "-y",
                output_path,
            ]

            subprocess.run(cmd, check=True, capture_output=True, timeout=300)

            if os.path.exists(output_path):
                logger.info(f"Created simple B-roll: {output_path}")
                return output_path

        except Exception as e:
            logger.error(f"Failed to create simple sequence: {e}")
        finally:
            if os.path.exists(concat_file):
                os.remove(concat_file)

        return None


if __name__ == "__main__":
    # Test B-roll generator
    generator = BRollGenerator()

    print("\n=== B-roll Generator Test ===")
    print("Note: This test requires actual video files to work")
    print("\nTo test:")
    print("1. Place test video files in /tmp/test_clips/")
    print("2. Run this script")

    test_dir = Path("/tmp/test_clips")
    if test_dir.exists():
        clips = list(test_dir.glob("*.mp4"))
        if clips:
            print(f"\nFound {len(clips)} test clips")
            output = generator.create_broll_sequence(
                [str(c) for c in clips[:3]],
                target_duration=15.0,
                output_path="/tmp/test_broll.mp4",
            )
            if output:
                print(f"✓ Created test B-roll: {output}")
        else:
            print("No MP4 files found in test directory")
    else:
        print(f"Test directory not found: {test_dir}")
