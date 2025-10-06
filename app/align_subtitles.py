import importlib.util
import logging
import re
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional, Pattern, Tuple
from rapidfuzz import fuzz
logger = logging.getLogger(__name__)
_JAPANESE_QUALITY_SPEC = importlib.util.find_spec('app.japanese_quality')
if _JAPANESE_QUALITY_SPEC:
    from app.japanese_quality import clean_subtitle_text, validate_subtitle_text
    HAS_JAPANESE_QUALITY_CHECK = True
    logger.info('Japanese quality check available for subtitles')
else:
    HAS_JAPANESE_QUALITY_CHECK = False
    logger.warning('Japanese quality check not available for subtitles')
from app.services.script.speakers import get_speaker_registry

class SubtitleAligner:

    def __init__(self):
        self.min_similarity_threshold = 60
        self.max_subtitle_length = 25
        self.enable_two_line_mode = True
        self.min_display_duration = 0.8
        self.max_display_duration = 8.0
        self.min_gap_between_subtitles = 0.05
        self.reading_speed_chars_per_sec = 8
        registry = get_speaker_registry()
        self.speaker_alias_map = registry.alias_map
        self.speaker_pattern: Optional[Pattern[str]] = self._compile_speaker_pattern(self.speaker_alias_map.keys())

    def align_script_with_stt(self, script_text: str, stt_words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        try:
            script_sentences = self._extract_sentences_from_script(script_text)
            aligned_subtitles = []
            word_index = 0
            for sentence_data in script_sentences:
                sentence = sentence_data['text']
                speaker = sentence_data.get('speaker')
                word_range, word_index = self._find_matching_word_range(sentence, stt_words, word_index)
                if word_range:
                    start_time = word_range[0]['start']
                    end_time = word_range[-1]['end']
                    subtitle_items = self._create_subtitle_items(sentence, start_time, end_time, speaker)
                    aligned_subtitles.extend(subtitle_items)
                else:
                    estimated_item = self._estimate_timing_for_sentence(sentence, aligned_subtitles, speaker)
                    if estimated_item:
                        aligned_subtitles.append(estimated_item)
            cleaned_subtitles = self._post_process_subtitles(aligned_subtitles)
            logger.info(f'Aligned {len(cleaned_subtitles)} subtitle items')
            return cleaned_subtitles
        except Exception as e:
            logger.error(f'Subtitle alignment failed: {e}')
            return self._generate_fallback_subtitles(script_text, stt_words)

    def _extract_sentences_from_script(self, script_text: str) -> List[Dict[str, Any]]:
        sentences = []
        lines = script_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            speaker = None
            content = line
            if self.speaker_pattern:
                speaker_match = self.speaker_pattern.match(line)
            else:
                speaker_match = None
            if speaker_match:
                raw_speaker = speaker_match.group(1)
                speaker = self.speaker_alias_map.get(raw_speaker, raw_speaker)
                content = speaker_match.group(2)
            if re.match('^\\(.*\\)$', content):
                logger.debug(f'Skipping visual instruction: {content}')
                continue
            if 'WOW Script Creation Crew' in content or '視聴者の皆様が明日を切り拓く' in content:
                logger.debug(f'Skipping watermark: {content[:50]}...')
                continue
            sub_sentences = self._split_long_sentence(content)
            for sub_sentence in sub_sentences:
                if sub_sentence.strip():
                    sentences.append({'text': sub_sentence.strip(), 'speaker': speaker})
        return sentences

    def _compile_speaker_pattern(self, aliases: Iterable[str]) -> Optional[Pattern[str]]:
        alias_list = [alias for alias in aliases if alias]
        if not alias_list:
            return None
        alias_list.sort(key=len, reverse=True)
        pattern = '|'.join((re.escape(alias) for alias in alias_list))
        return re.compile(f'^({pattern})[:：]\\s*(.+)')

    def _split_long_sentence(self, sentence: str) -> List[str]:
        if len(sentence) <= self.max_subtitle_length:
            return [sentence]
        if self.enable_two_line_mode and len(sentence) <= self.max_subtitle_length * 2:
            two_line_text = self._wrap_subtitle_two_lines(sentence)
            if two_line_text:
                return [two_line_text]
        parts = re.split('[、。！？]', sentence)
        result = []
        current_part = ''
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if len(current_part + part) <= self.max_subtitle_length:
                current_part += part + '、'
            else:
                if current_part:
                    result.append(current_part.rstrip('、'))
                current_part = part + '、'
        if current_part:
            result.append(current_part.rstrip('、'))
        return result

    def _wrap_subtitle_two_lines(self, text: str) -> str:
        if len(text) <= self.max_subtitle_length:
            return None
        max_total = self.max_subtitle_length * 2
        if len(text) > max_total:
            text = text[:max_total]
        punctuation_positions = [i for i, char in enumerate(text) if char in '、。！？']
        if punctuation_positions:
            mid_point = len(text) // 2
            best_split = min(punctuation_positions, key=lambda x: abs(x - mid_point))
            line1 = text[:best_split + 1].strip()
            line2 = text[best_split + 1:].strip()
            if len(line1) <= self.max_subtitle_length and len(line2) <= self.max_subtitle_length:
                return f'{line1}\\N{line2}'
        mid = len(text) // 2
        for offset in range(0, 5):
            if mid + offset < len(text):
                line1 = text[:mid + offset].strip()
                line2 = text[mid + offset:].strip()
                if len(line1) <= self.max_subtitle_length and len(line2) <= self.max_subtitle_length:
                    return f'{line1}\\N{line2}'
        return None

    def _find_matching_word_range(self, sentence: str, stt_words: List[Dict[str, Any]], start_index: int) -> Tuple[Optional[List[Dict[str, Any]]], int]:
        if not stt_words or start_index >= len(stt_words):
            return (None, start_index)
        clean_sentence = re.sub('[、。！？「」『』（）]', '', sentence)
        sentence_words = clean_sentence.split()
        if not sentence_words:
            return (None, start_index)
        best_match = None
        best_score = 0
        best_end_index = start_index
        for length in range(len(sentence_words), min(len(sentence_words) * 3, len(stt_words) - start_index) + 1):
            end_index = min(start_index + length, len(stt_words))
            stt_segment = stt_words[start_index:end_index]
            if not stt_segment:
                continue
            stt_text = ' '.join([word['word'] for word in stt_segment])
            similarity = fuzz.ratio(clean_sentence, stt_text)
            if similarity > best_score and similarity >= self.min_similarity_threshold:
                best_score = similarity
                best_match = stt_segment
                best_end_index = end_index
        if best_match:
            logger.debug(f"Found match with {best_score}% similarity: '{sentence[:30]}...'\n")
            return (best_match, best_end_index)
        else:
            estimated_word_count = max(len(sentence_words), 3)
            estimated_end = min(start_index + estimated_word_count, len(stt_words))
            return (stt_words[start_index:estimated_end], estimated_end)

    def _create_subtitle_items(self, sentence: str, start_time: float, end_time: float, speaker: Optional[str]) -> List[Dict[str, Any]]:
        audio_duration = end_time - start_time
        text_length = len(sentence)
        reading_time = text_length / self.reading_speed_chars_per_sec
        optimal_duration = max(audio_duration, reading_time)
        optimal_duration = max(optimal_duration, self.min_display_duration)
        optimal_duration = min(optimal_duration, self.max_display_duration)
        end_time = start_time + optimal_duration
        if len(sentence) > self.max_subtitle_length:
            parts = self._split_long_sentence(sentence)
            if len(parts) > 1:
                items = []
                part_duration = (end_time - start_time) / len(parts)
                for i, part in enumerate(parts):
                    part_start = start_time + i * part_duration
                    part_end = part_start + part_duration
                    items.append({'start': part_start, 'end': part_end, 'text': part, 'speaker': speaker, 'confidence': 0.9})
                return items
        return [{'start': start_time, 'end': end_time, 'text': sentence, 'speaker': speaker, 'confidence': 0.9}]

    def _estimate_timing_for_sentence(self, sentence: str, existing_subtitles: List[Dict[str, Any]], speaker: Optional[str]) -> Optional[Dict[str, Any]]:
        if not existing_subtitles:
            return {'start': 0.0, 'end': len(sentence) * 0.1, 'text': sentence, 'speaker': speaker, 'confidence': 0.3}
        last_subtitle = existing_subtitles[-1]
        estimated_start = last_subtitle['end'] + 0.2
        estimated_duration = max(len(sentence) * 0.08, self.min_display_duration)
        return {'start': estimated_start, 'end': estimated_start + estimated_duration, 'text': sentence, 'speaker': speaker, 'confidence': 0.3}

    def _post_process_subtitles(self, subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not subtitles:
            return []
        subtitles.sort(key=lambda x: x['start'])
        processed = []
        for i, subtitle in enumerate(subtitles):
            if processed and abs(processed[-1]['start'] - subtitle['start']) < 0.1:
                continue
            if subtitle['end'] - subtitle['start'] < self.min_display_duration:
                subtitle['end'] = subtitle['start'] + self.min_display_duration
            if processed and subtitle['start'] < processed[-1]['end']:
                gap = self.min_gap_between_subtitles
                new_prev_end = subtitle['start'] - gap
                prev_duration = new_prev_end - processed[-1]['start']
                if prev_duration < self.min_display_duration:
                    subtitle['start'] = processed[-1]['end'] + gap
                    subtitle['end'] = max(subtitle['end'], subtitle['start'] + self.min_display_duration)
                else:
                    processed[-1]['end'] = new_prev_end
            if HAS_JAPANESE_QUALITY_CHECK:
                original_text = subtitle['text']
                if not validate_subtitle_text(original_text):
                    logger.warning(f"Subtitle contains non-Japanese text: '{original_text[:50]}'")
                    cleaned_text = clean_subtitle_text(original_text)
                    if cleaned_text != original_text:
                        logger.info(f"Cleaned subtitle: '{original_text}' -> '{cleaned_text}'")
                        subtitle['text'] = cleaned_text
            subtitle['index'] = len(processed) + 1
            processed.append(subtitle)
        return processed

    def _generate_fallback_subtitles(self, script_text: str, stt_words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        sentences = self._extract_sentences_from_script(script_text)
        fallback_subtitles = []
        if stt_words:
            total_duration = stt_words[-1]['end'] if stt_words else 30.0
        else:
            total_duration = len(script_text) * 0.08
        time_per_sentence = total_duration / len(sentences) if sentences else 2.0
        for i, sentence_data in enumerate(sentences):
            start_time = i * time_per_sentence
            end_time = (i + 1) * time_per_sentence
            fallback_subtitles.append({'index': i + 1, 'start': start_time, 'end': end_time, 'text': sentence_data['text'], 'speaker': sentence_data.get('speaker'), 'confidence': 0.2})
        logger.warning(f'Generated {len(fallback_subtitles)} fallback subtitles')
        return fallback_subtitles

    def to_srt_format(self, subtitles: List[Dict[str, Any]]) -> str:
        srt_content = ''
        for subtitle in subtitles:
            start_time = self._format_srt_timestamp(subtitle['start'])
            end_time = self._format_srt_timestamp(subtitle['end'])
            srt_content += f"{subtitle['index']}\n"
            srt_content += f'{start_time} --> {end_time}\n'
            srt_content += f"{subtitle['text']}\n\n"
        return srt_content

    def _format_srt_timestamp(self, seconds: float) -> str:
        delta = timedelta(seconds=seconds)
        total_seconds = int(delta.total_seconds())
        hours = total_seconds // 3600
        minutes = total_seconds % 3600 // 60
        secs = total_seconds % 60
        millis = int(seconds % 1 * 1000)
        return f'{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}'

    def to_vtt_format(self, subtitles: List[Dict[str, Any]]) -> str:
        vtt_content = 'WEBVTT\n\n'
        for subtitle in subtitles:
            start_time = self._format_vtt_timestamp(subtitle['start'])
            end_time = self._format_vtt_timestamp(subtitle['end'])
            vtt_content += f'{start_time} --> {end_time}\n'
            vtt_content += f"{subtitle['text']}\n\n"
        return vtt_content

    def _format_vtt_timestamp(self, seconds: float) -> str:
        delta = timedelta(seconds=seconds)
        total_seconds = int(delta.total_seconds())
        hours = total_seconds // 3600
        minutes = total_seconds % 3600 // 60
        secs = total_seconds % 60
        millis = int(seconds % 1 * 1000)
        return f'{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}'

    def get_subtitle_stats(self, subtitles: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not subtitles:
            return {}
        total_duration = subtitles[-1]['end'] - subtitles[0]['start']
        total_text_length = sum((len(sub['text']) for sub in subtitles))
        confidence_scores = [sub.get('confidence', 0) for sub in subtitles]
        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        return {'total_subtitles': len(subtitles), 'total_duration_sec': total_duration, 'avg_duration_per_subtitle': total_duration / len(subtitles), 'total_text_length': total_text_length, 'avg_text_length': total_text_length / len(subtitles), 'avg_confidence': avg_confidence, 'speakers': list(set((sub.get('speaker') for sub in subtitles if sub.get('speaker'))))}
subtitle_aligner = SubtitleAligner()

def align_script_with_stt(script_text: str, stt_words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return subtitle_aligner.align_script_with_stt(script_text, stt_words)

def to_srt_format(subtitles: List[Dict[str, Any]]) -> str:
    return subtitle_aligner.to_srt_format(subtitles)

def export_srt(subtitles: List[Dict[str, Any]], output_path: str):
    srt_content = to_srt_format(subtitles)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(srt_content)

def to_vtt_format(subtitles: List[Dict[str, Any]]) -> str:
    return subtitle_aligner.to_vtt_format(subtitles)
if __name__ == '__main__':
    print('Testing subtitle alignment...')
    test_script = '\n田中: 今日は重要な経済ニュースについて話します。\n\n鈴木: 日経平均株価が大幅に上昇しましたね。\n\n田中: 前日比で2.5%の上昇となりました。\n'
    test_stt_words = [{'word': '今日', 'start': 0.0, 'end': 0.5, 'confidence': 0.9}, {'word': 'は', 'start': 0.5, 'end': 0.7, 'confidence': 0.8}, {'word': '重要', 'start': 0.7, 'end': 1.2, 'confidence': 0.9}, {'word': 'な', 'start': 1.2, 'end': 1.3, 'confidence': 0.7}, {'word': '経済', 'start': 1.3, 'end': 1.8, 'confidence': 0.9}, {'word': 'ニュース', 'start': 1.8, 'end': 2.3, 'confidence': 0.9}, {'word': 'について', 'start': 2.3, 'end': 2.8, 'confidence': 0.8}, {'word': '話します', 'start': 2.8, 'end': 3.5, 'confidence': 0.9}, {'word': '日経', 'start': 4.0, 'end': 4.5, 'confidence': 0.9}, {'word': '平均', 'start': 4.5, 'end': 5.0, 'confidence': 0.8}, {'word': '株価', 'start': 5.0, 'end': 5.5, 'confidence': 0.9}, {'word': 'が', 'start': 5.5, 'end': 5.7, 'confidence': 0.7}, {'word': '大幅', 'start': 5.7, 'end': 6.2, 'confidence': 0.8}, {'word': 'に', 'start': 6.2, 'end': 6.4, 'confidence': 0.7}, {'word': '上昇', 'start': 6.4, 'end': 6.9, 'confidence': 0.9}, {'word': 'しました', 'start': 6.9, 'end': 7.5, 'confidence': 0.8}]
    try:
        aligner = SubtitleAligner()
        subtitles = aligner.align_script_with_stt(test_script, test_stt_words)
        print(f'Generated {len(subtitles)} subtitle items:')
        for subtitle in subtitles:
            print(f"  [{subtitle['start']:.1f}s-{subtitle['end']:.1f}s] {subtitle['text']}")
        srt_content = aligner.to_srt_format(subtitles)
        print('\nSRT format:')
        print(srt_content[:200] + '...' if len(srt_content) > 200 else srt_content)
        stats = aligner.get_subtitle_stats(subtitles)
        print(f'\nStatistics: {stats}')
    except Exception as e:
        print(f'Test failed: {e}')