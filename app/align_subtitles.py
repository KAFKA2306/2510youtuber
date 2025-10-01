"""
字幕整合モジュール

台本テキストとSTT結果を整合させて、正確なタイムスタンプ付き字幕を生成します。
これにより字幕の精度を大幅に向上させます。
"""

import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import timedelta
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

class SubtitleAligner:
    """字幕整合クラス"""

    def __init__(self):
        self.min_similarity_threshold = 60  # 類似度閾値
        self.max_subtitle_length = 80      # 字幕の最大文字数
        self.min_display_duration = 1.0    # 最小表示時間（秒）
        self.max_display_duration = 8.0    # 最大表示時間（秒）

    def align_script_with_stt(self, script_text: str,
                             stt_words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        台本テキストとSTT結果を整合

        Args:
            script_text: 元の台本テキスト
            stt_words: STTで得られた単語レベルタイムスタンプ

        Returns:
            整合済みの字幕データ
        """
        try:
            # 台本を文単位に分割
            script_sentences = self._extract_sentences_from_script(script_text)

            # STTテキストを再構成
            stt_text = " ".join([word["word"] for word in stt_words])

            # 文ごとにタイムスタンプを割り当て
            aligned_subtitles = []
            word_index = 0

            for sentence_data in script_sentences:
                sentence = sentence_data["text"]
                speaker = sentence_data.get("speaker")

                # この文に対応するSTT単語範囲を特定
                word_range, word_index = self._find_matching_word_range(
                    sentence, stt_words, word_index
                )

                if word_range:
                    # タイムスタンプを取得
                    start_time = word_range[0]["start"]
                    end_time = word_range[-1]["end"]

                    # 字幕項目を作成
                    subtitle_items = self._create_subtitle_items(
                        sentence, start_time, end_time, speaker
                    )

                    aligned_subtitles.extend(subtitle_items)

                else:
                    # マッチングに失敗した場合の推定
                    estimated_item = self._estimate_timing_for_sentence(
                        sentence, aligned_subtitles, speaker
                    )
                    if estimated_item:
                        aligned_subtitles.append(estimated_item)

            # 字幕の後処理
            cleaned_subtitles = self._post_process_subtitles(aligned_subtitles)

            logger.info(f"Aligned {len(cleaned_subtitles)} subtitle items")
            return cleaned_subtitles

        except Exception as e:
            logger.error(f"Subtitle alignment failed: {e}")
            return self._generate_fallback_subtitles(script_text, stt_words)

    def _extract_sentences_from_script(self, script_text: str) -> List[Dict[str, Any]]:
        """台本から文を抽出"""
        sentences = []
        lines = script_text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 話者名を検出
            speaker_match = re.match(r'^(田中|鈴木|ナレーター|司会)[:：]\s*(.+)', line)

            if speaker_match:
                speaker = speaker_match.group(1)
                content = speaker_match.group(2)
            else:
                speaker = None
                content = line

            # 長い文を分割
            sub_sentences = self._split_long_sentence(content)

            for sub_sentence in sub_sentences:
                if sub_sentence.strip():
                    sentences.append({
                        "text": sub_sentence.strip(),
                        "speaker": speaker
                    })

        return sentences

    def _split_long_sentence(self, sentence: str) -> List[str]:
        """長い文を適切な長さに分割"""
        if len(sentence) <= self.max_subtitle_length:
            return [sentence]

        # 句読点で分割を試行
        parts = re.split(r'[、。！？]', sentence)
        result = []
        current_part = ""

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if len(current_part + part) <= self.max_subtitle_length:
                current_part += part + "、"
            else:
                if current_part:
                    result.append(current_part.rstrip("、"))
                current_part = part + "、"

        if current_part:
            result.append(current_part.rstrip("、"))

        return result

    def _find_matching_word_range(self, sentence: str, stt_words: List[Dict[str, Any]],
                                 start_index: int) -> Tuple[Optional[List[Dict[str, Any]]], int]:
        """文に対応するSTT単語範囲を特定"""
        if not stt_words or start_index >= len(stt_words):
            return None, start_index

        # 文から単語を抽出（話者名や記号を除去）
        clean_sentence = re.sub(r'[、。！？「」『』（）]', '', sentence)
        sentence_words = clean_sentence.split()

        if not sentence_words:
            return None, start_index

        # STTから対応する単語群を探索
        best_match = None
        best_score = 0
        best_end_index = start_index

        # 複数の長さで試行
        for length in range(len(sentence_words), min(len(sentence_words) * 3, len(stt_words) - start_index) + 1):
            end_index = min(start_index + length, len(stt_words))
            stt_segment = stt_words[start_index:end_index]

            if not stt_segment:
                continue

            # STTセグメントのテキストを結合
            stt_text = " ".join([word["word"] for word in stt_segment])

            # 類似度を計算
            similarity = fuzz.ratio(clean_sentence, stt_text)

            if similarity > best_score and similarity >= self.min_similarity_threshold:
                best_score = similarity
                best_match = stt_segment
                best_end_index = end_index

        if best_match:
            logger.debug(f"Found match with {best_score}% similarity: '{sentence[:30]}...'\n")
            return best_match, best_end_index
        else:
            # マッチングに失敗した場合、推定で進める
            estimated_word_count = max(len(sentence_words), 3)
            estimated_end = min(start_index + estimated_word_count, len(stt_words))
            return stt_words[start_index:estimated_end], estimated_end

    def _create_subtitle_items(self, sentence: str, start_time: float,
                              end_time: float, speaker: Optional[str]) -> List[Dict[str, Any]]:
        """字幕アイテムを作成"""
        # 表示時間を調整
        duration = end_time - start_time
        if duration < self.min_display_duration:
            end_time = start_time + self.min_display_duration
        elif duration > self.max_display_duration:
            end_time = start_time + self.max_display_duration

        # 長い文の場合は分割
        if len(sentence) > self.max_subtitle_length:
            parts = self._split_long_sentence(sentence)
            if len(parts) > 1:
                # 複数の字幕に分割
                items = []
                part_duration = (end_time - start_time) / len(parts)

                for i, part in enumerate(parts):
                    part_start = start_time + (i * part_duration)
                    part_end = part_start + part_duration

                    items.append({
                        "start": part_start,
                        "end": part_end,
                        "text": part,
                        "speaker": speaker,
                        "confidence": 0.9
                    })

                return items

        # 単一の字幕アイテム
        return [{
            "start": start_time,
            "end": end_time,
            "text": sentence,
            "speaker": speaker,
            "confidence": 0.9
        }]

    def _estimate_timing_for_sentence(self, sentence: str,
                                     existing_subtitles: List[Dict[str, Any]],
                                     speaker: Optional[str]) -> Optional[Dict[str, Any]]:
        """文のタイミングを推定"""
        if not existing_subtitles:
            # 最初の文の場合
            return {
                "start": 0.0,
                "end": len(sentence) * 0.1,  # 1文字0.1秒と仮定
                "text": sentence,
                "speaker": speaker,
                "confidence": 0.3
            }

        # 前の字幕の終了時間から継続
        last_subtitle = existing_subtitles[-1]
        estimated_start = last_subtitle["end"] + 0.2  # 200ms の間隔

        # 文の長さから推定時間を計算
        estimated_duration = max(
            len(sentence) * 0.08,  # 1文字80ms
            self.min_display_duration
        )

        return {
            "start": estimated_start,
            "end": estimated_start + estimated_duration,
            "text": sentence,
            "speaker": speaker,
            "confidence": 0.3  # 推定値
        }

    def _post_process_subtitles(self, subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """字幕の後処理"""
        if not subtitles:
            return []

        # タイムスタンプでソート
        subtitles.sort(key=lambda x: x["start"])

        processed = []
        for i, subtitle in enumerate(subtitles):
            # 重複チェック
            if processed and abs(processed[-1]["start"] - subtitle["start"]) < 0.1:
                continue

            # 時間の重複を解決
            if processed and subtitle["start"] < processed[-1]["end"]:
                # 前の字幕の終了時間を調整
                processed[-1]["end"] = subtitle["start"] - 0.1

            # 最小表示時間を確保
            if subtitle["end"] - subtitle["start"] < self.min_display_duration:
                subtitle["end"] = subtitle["start"] + self.min_display_duration

            # インデックスを追加
            subtitle["index"] = len(processed) + 1

            processed.append(subtitle)

        return processed

    def _generate_fallback_subtitles(self, script_text: str,
                                   stt_words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """フォールバック用字幕を生成"""
        sentences = self._extract_sentences_from_script(script_text)
        fallback_subtitles = []

        if stt_words:
            # STTの総時間を取得
            total_duration = stt_words[-1]["end"] if stt_words else 30.0
        else:
            # テキストの長さから推定
            total_duration = len(script_text) * 0.08

        # 均等に時間を分割
        time_per_sentence = total_duration / len(sentences) if sentences else 2.0

        for i, sentence_data in enumerate(sentences):
            start_time = i * time_per_sentence
            end_time = (i + 1) * time_per_sentence

            fallback_subtitles.append({
                "index": i + 1,
                "start": start_time,
                "end": end_time,
                "text": sentence_data["text"],
                "speaker": sentence_data.get("speaker"),
                "confidence": 0.2  # 低い信頼度
            })

        logger.warning(f"Generated {len(fallback_subtitles)} fallback subtitles")
        return fallback_subtitles

    def to_srt_format(self, subtitles: List[Dict[str, Any]]) -> str:
        """字幕データをSRT形式に変換"""
        srt_content = ""

        for subtitle in subtitles:
            start_time = self._format_srt_timestamp(subtitle["start"])
            end_time = self._format_srt_timestamp(subtitle["end"])

            srt_content += f"{subtitle['index']}\n"
            srt_content += f"{start_time} --> {end_time}\n"
            srt_content += f"{subtitle['text']}\n\n"

        return srt_content

    def _format_srt_timestamp(self, seconds: float) -> str:
        """秒をSRT形式のタイムスタンプに変換"""
        delta = timedelta(seconds=seconds)
        total_seconds = int(delta.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        millis = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def to_vtt_format(self, subtitles: List[Dict[str, Any]]) -> str:
        """字幕データをVTT形式に変換"""
        vtt_content = "WEBVTT\n\n"

        for subtitle in subtitles:
            start_time = self._format_vtt_timestamp(subtitle["start"])
            end_time = self._format_vtt_timestamp(subtitle["end"])

            vtt_content += f"{start_time} --> {end_time}\n"
            vtt_content += f"{subtitle['text']}\n\n"

        return vtt_content

    def _format_vtt_timestamp(self, seconds: float) -> str:
        """秒をVTT形式のタイムスタンプに変換"""
        delta = timedelta(seconds=seconds)
        total_seconds = int(delta.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        millis = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    def get_subtitle_stats(self, subtitles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """字幕統計情報を取得"""
        if not subtitles:
            return {}

        total_duration = subtitles[-1]["end"] - subtitles[0]["start"]
        total_text_length = sum(len(sub["text"]) for sub in subtitles)

        confidence_scores = [sub.get("confidence", 0) for sub in subtitles]
        avg_confidence = sum(confidence_scores) / len(confidence_scores)

        return {
            "total_subtitles": len(subtitles),
            "total_duration_sec": total_duration,
            "avg_duration_per_subtitle": total_duration / len(subtitles),
            "total_text_length": total_text_length,
            "avg_text_length": total_text_length / len(subtitles),
            "avg_confidence": avg_confidence,
            "speakers": list(set(sub.get("speaker") for sub in subtitles if sub.get("speaker")))
        }

# グローバルインスタンス
subtitle_aligner = SubtitleAligner()

def align_script_with_stt(script_text: str, stt_words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """字幕整合の簡易関数"""
    return subtitle_aligner.align_script_with_stt(script_text, stt_words)

def to_srt_format(subtitles: List[Dict[str, Any]]) -> str:
    """SRT変換の簡易関数"""
    return subtitle_aligner.to_srt_format(subtitles)

def export_srt(subtitles: List[Dict[str, Any]], output_path: str):
    """SRTファイルを出力"""
    srt_content = to_srt_format(subtitles)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(srt_content)

def to_vtt_format(subtitles: List[Dict[str, Any]]) -> str:
    """VTT変換の簡易関数"""
    return subtitle_aligner.to_vtt_format(subtitles)

if __name__ == "__main__":
    # テスト実行
    print("Testing subtitle alignment...")

    # テスト用データ
    test_script = """
田中: 今日は重要な経済ニュースについて話します。

鈴木: 日経平均株価が大幅に上昇しましたね。

田中: 前日比で2.5%の上昇となりました。
"""

    test_stt_words = [
        {"word": "今日", "start": 0.0, "end": 0.5, "confidence": 0.9},
        {"word": "は", "start": 0.5, "end": 0.7, "confidence": 0.8},
        {"word": "重要", "start": 0.7, "end": 1.2, "confidence": 0.9},
        {"word": "な", "start": 1.2, "end": 1.3, "confidence": 0.7},
        {"word": "経済", "start": 1.3, "end": 1.8, "confidence": 0.9},
        {"word": "ニュース", "start": 1.8, "end": 2.3, "confidence": 0.9},
        {"word": "について", "start": 2.3, "end": 2.8, "confidence": 0.8},
        {"word": "話します", "start": 2.8, "end": 3.5, "confidence": 0.9},
        {"word": "日経", "start": 4.0, "end": 4.5, "confidence": 0.9},
        {"word": "平均", "start": 4.5, "end": 5.0, "confidence": 0.8},
        {"word": "株価", "start": 5.0, "end": 5.5, "confidence": 0.9},
        {"word": "が", "start": 5.5, "end": 5.7, "confidence": 0.7},
        {"word": "大幅", "start": 5.7, "end": 6.2, "confidence": 0.8},
        {"word": "に", "start": 6.2, "end": 6.4, "confidence": 0.7},
        {"word": "上昇", "start": 6.4, "end": 6.9, "confidence": 0.9},
        {"word": "しました", "start": 6.9, "end": 7.5, "confidence": 0.8}
    ]

    try:
        # 字幕整合テスト
        aligner = SubtitleAligner()
        subtitles = aligner.align_script_with_stt(test_script, test_stt_words)

        print(f"Generated {len(subtitles)} subtitle items:")
        for subtitle in subtitles:
            print(f"  [{subtitle['start']:.1f}s-{subtitle['end']:.1f}s] {subtitle['text']}")

        # SRT形式変換テスト
        srt_content = aligner.to_srt_format(subtitles)
        print("\nSRT format:")
        print(srt_content[:200] + "..." if len(srt_content) > 200 else srt_content)

        # 統計情報テスト
        stats = aligner.get_subtitle_stats(subtitles)
        print(f"\nStatistics: {stats}")

    except Exception as e:
        print(f"Test failed: {e}")
