import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List
import google.generativeai as genai
from .api_rotation import get_rotation_manager
from .config import cfg
from .llm_logging import llm_logging_context, record_llm_interaction
from app.constants.prompts import DEFAULT_VIDEO_MODE_CONTEXT, METADATA_MODE_CONTEXT, METADATA_OTHER_POLICIES_LINES, METADATA_REQUIREMENTS_LINES, METADATA_TITLE_AVOID_EXAMPLES, METADATA_TITLE_POLICY_LINES, METADATA_TITLE_SUCCESS_EXAMPLES, indent_lines, join_lines
logger = logging.getLogger(__name__)

class MetadataGenerator:

    def __init__(self):
        self.client = None
        self._setup_client()

    def _setup_client(self):
        try:
            self.client = None
            logger.info('Metadata generator ready (using shared rotation manager)')
        except Exception as e:
            logger.error(f'Failed to initialize metadata generator: {e}')
            raise

    def generate_youtube_metadata(self, news_items: List[Dict[str, Any]], script_content: str='', mode: str='daily') -> Dict[str, Any]:
        try:
            with llm_logging_context(component='metadata_generation', mode=mode):
                prompt = self._build_metadata_prompt(news_items, script_content, mode)
                response = self._call_gemini_for_metadata(prompt)
                metadata = self._parse_metadata_response(response)
                validated_metadata = self._validate_metadata(metadata, news_items)
                logger.info(f'Generated metadata for {mode} video')
                return validated_metadata
        except Exception as e:
            logger.error(f'Failed to generate metadata: {e}')
            return self._get_fallback_metadata(news_items, mode)

    def _build_metadata_prompt(self, news_items: List[Dict[str, Any]], script_content: str, mode: str) -> str:
        current_date = datetime.now().strftime('%Y年%m月%d日')
        news_summary = self._create_news_summary(news_items)
        mode_description = METADATA_MODE_CONTEXT.get(mode, DEFAULT_VIDEO_MODE_CONTEXT)
        requirements = join_lines(METADATA_REQUIREMENTS_LINES)
        title_policy = join_lines(METADATA_TITLE_POLICY_LINES)
        success_examples = indent_lines(METADATA_TITLE_SUCCESS_EXAMPLES, prefix='  - ')
        avoid_examples = indent_lines(METADATA_TITLE_AVOID_EXAMPLES, prefix='  - ')
        other_policies = join_lines(METADATA_OTHER_POLICIES_LINES)
        prompt = f"""\n以下の経済ニュース内容から、YouTube動画用のメタデータを生成してください。\n\n【動画タイプ】{mode_description}\n【配信日】{current_date}\n\n【ニュース内容】\n{news_summary}\n\n【台本抜粋】\n{(script_content[:500] if script_content else '台本データなし')}...\n\n【要件】\n{requirements}\n\n【タイトル作成の重要方針】\n{title_policy}\n\n✅ **成功例:**\n{success_examples}\n\n❌ **避けるべき例:**\n{avoid_examples}\n\n【その他の方針】\n{other_policies}\n\n以下のJSON形式で厳密に回答してください：\n```json\n{{\n  "title": "動画タイトル（50文字以内）",\n  "description": "動画説明文（改行を\\nで表現）",\n  "tags": ["タグ1", "タグ2", "タグ3", ...],\n  "category": "YouTube カテゴリ",\n  "thumbnail_text": "サムネイル用テキスト",\n  "seo_keywords": ["SEOキーワード1", "SEOキーワード2", ...],\n  "target_audience": "ターゲット視聴者層",\n  "estimated_watch_time": "推定視聴時間（分）"\n}}\n```\n\n注意事項：\n- 必ず有効なJSONフォーマットで回答\n- タイトルは魅力的だが誇張しない\n- 説明文には出典情報を含める\n- タグは具体的で検索性の高いものを選択\n"""
        return prompt

    def _create_news_summary(self, news_items: List[Dict[str, Any]]) -> str:
        if not news_items:
            return 'ニュースデータが取得できませんでした。'
        summaries = []
        for i, item in enumerate(news_items, 1):
            summary = f"\n【ニュース{i}】{item.get('title', '無題')}\n出典: {item.get('source', '不明')}\n要約: {item.get('summary', '')[:200]}...\n影響度: {item.get('impact_level', 'medium')}\n"
            summaries.append(summary)
        return '\n'.join(summaries)

    def _call_gemini_for_metadata(self, prompt: str, max_retries: int=3) -> str:
        rotation_manager = get_rotation_manager()

        def api_call_with_key(api_key: str) -> str:
            try:
                genai.configure(api_key=api_key)
                model_name = cfg.gemini_models.get('metadata_generation')
                client = genai.GenerativeModel(f'models/{model_name}')
                generation_config = genai.GenerationConfig(temperature=0.7, top_p=0.95, top_k=40, max_output_tokens=4096)
                response = client.generate_content(prompt, generation_config=generation_config)
                content = response.text
                logger.debug(f'Generated metadata response length: {len(content)}')
                try:
                    record_llm_interaction(provider='gemini', model=f'models/{model_name}', prompt={'text': prompt, 'generation_config': {'temperature': getattr(generation_config, 'temperature', None), 'top_p': getattr(generation_config, 'top_p', None), 'top_k': getattr(generation_config, 'top_k', None), 'max_output_tokens': getattr(generation_config, 'max_output_tokens', None)}}, response={'text': content}, metadata={'component': 'metadata_generation'})
                except Exception:
                    logger.debug('Failed to log metadata generation interaction', exc_info=True)
                return content
            except Exception as e:
                error_str = str(e).lower()
                if any((kw in error_str for kw in ['429', 'rate limit', 'quota'])):
                    logger.warning(f'Gemini rate limit detected: {e}')
                    raise
                if any((kw in error_str for kw in ['504', 'deadline exceeded', 'timeout'])):
                    logger.warning(f'Gemini timeout detected: {e}')
                    raise
                logger.warning(f'Gemini API error: {e}')
                raise
        try:
            return rotation_manager.execute_with_rotation(provider='gemini', api_call=api_call_with_key, max_attempts=max_retries)
        except Exception as e:
            logger.error(f'All Gemini API attempts failed for metadata generation: {e}')
            raise Exception('Gemini API failed with all keys for metadata generation')

    def _parse_metadata_response(self, response: str) -> Dict[str, Any]:
        try:
            match = re.search('```json\\n(.*?)\\n```', response, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                start = response.find('{')
                end = response.rfind('}')
                if start != -1 and end != -1:
                    json_str = response[start:end + 1]
                else:
                    raise ValueError('No JSON structure found')
            metadata = json.loads(json_str)
            return metadata
        except json.JSONDecodeError as e:
            logger.error(f'Failed to parse metadata JSON: {e}')
            logger.debug(f'Raw response: {response[:500]}...')
            return {}
        except Exception as e:
            logger.error(f'Error parsing metadata response: {e}')
            return {}

    def _validate_metadata(self, metadata: Dict[str, Any], news_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        validated = {}
        try:
            title = str(metadata.get('title', '')).strip()
            if len(title) > 50:
                title = title[:47] + '...'
            validated['title'] = title or self._generate_fallback_title(news_items)
            description = str(metadata.get('description', '')).strip()
            description = description.replace('\\n', '\n')
            if len(description) < 100:
                description = self._enhance_description(description, news_items)
            validated['description'] = description
            tags = metadata.get('tags', [])
            if isinstance(tags, list):
                cleaned_tags = []
                for tag in tags[:20]:
                    clean_tag = str(tag).strip()
                    if clean_tag and len(clean_tag) <= 50:
                        cleaned_tags.append(clean_tag)
                validated['tags'] = cleaned_tags
            else:
                validated['tags'] = self._generate_fallback_tags(news_items)
            validated['category'] = str(metadata.get('category', 'News & Politics'))
            validated['thumbnail_text'] = str(metadata.get('thumbnail_text', '経済ニュース'))
            validated['seo_keywords'] = metadata.get('seo_keywords', [])
            validated['target_audience'] = str(metadata.get('target_audience', '経済に関心のある視聴者'))
            validated['estimated_watch_time'] = str(metadata.get('estimated_watch_time', '15-30分'))
            validated['generated_at'] = datetime.now().isoformat()
            validated['news_count'] = len(news_items)
            return validated
        except Exception as e:
            logger.error(f'Metadata validation error: {e}')
            return self._get_fallback_metadata(news_items, 'daily')

    def _generate_fallback_title(self, news_items: List[Dict[str, Any]]) -> str:
        current_date = datetime.now().strftime('%m/%d')
        if news_items and len(news_items) > 0:
            main_topic = news_items[0].get('title', '経済ニュース')
            wow_keywords = self._extract_wow_elements(main_topic)
            keywords = self._extract_keywords(main_topic)
            if wow_keywords:
                return f"【速報】{wow_keywords[0]}！注目の{(keywords[0] if keywords else '経済ニュース')}"
            elif keywords:
                return f'【{current_date}】{keywords[0]}が動く！今日の重要ニュース'
        return f'【{current_date}速報】今日の経済市場で何が起きた？'

    def _extract_wow_elements(self, text: str) -> List[str]:
        wow_elements = []
        percent_match = re.search('([+\\-]?\\d+\\.?\\d*[%％])', text)
        if percent_match:
            wow_elements.append(f'{percent_match.group(1)}変動')
        bai_match = re.search('(\\d+\\.?\\d*倍)', text)
        if bai_match:
            wow_elements.append(bai_match.group(1))
        trend_patterns = ['急騰', '暴落', '急落', '高騰', '急上昇', '急降下', '史上最高', '最安値', '年初来高値', '年初来安値']
        for pattern in trend_patterns:
            if pattern in text:
                wow_elements.append(pattern)
                break
        urgent_patterns = ['速報', '緊急', '衝撃', '警告', '注目', '重大']
        for pattern in urgent_patterns:
            if pattern in text:
                wow_elements.append(pattern)
                break
        return wow_elements[:2]

    def _enhance_description(self, description: str, news_items: List[Dict[str, Any]]) -> str:
        current_date = datetime.now().strftime('%Y年%m月%d日')
        enhanced = f'{description}\n\n' if description else ''
        enhanced += f'\n【{current_date} 経済ニュース解説】\n\n本日の重要な経済ニュースを専門家が分かりやすく解説します。\n\n📈 今日のトピック：\n'
        for i, item in enumerate(news_items, 1):
            enhanced += f"{i}. {item.get('title', '無題')}\n"
        enhanced += '\n\n🎯 この動画で学べること：\n• 最新の経済動向と市場への影響\n• 専門家による詳細分析と解説\n• 今後の注目ポイントと投資判断材料\n\n📊 信頼できる情報源：\n'
        sources = set()
        for item in news_items:
            source = item.get('source')
            if source and source != 'システム':
                sources.add(source)
        for source in list(sources)[:5]:
            enhanced += f'• {source}\n'
        enhanced += '\n\n⚠️ 免責事項：\n本動画の内容は情報提供を目的としており、投資勧誘ではありません。\n投資判断は自己責任で行ってください。\n\n#経済ニュース #投資 #株式市場 #金融 #経済解説\n'
        return enhanced

    def _generate_fallback_tags(self, news_items: List[Dict[str, Any]]) -> List[str]:
        base_tags = ['経済ニュース', '投資', '株式市場', '金融', '経済解説', 'マーケット', '経済分析', 'ニュース解説']
        for item in news_items:
            title = item.get('title', '')
            keywords = self._extract_keywords(title)
            base_tags.extend(keywords[:3])
        unique_tags = []
        for tag in base_tags:
            if tag not in unique_tags and len(tag) <= 50:
                unique_tags.append(tag)
        return unique_tags[:15]

    def _extract_keywords(self, text: str) -> List[str]:
        economic_patterns = ['日経平均', 'TOPIX', 'ダウ', 'ナスダック', '金利', 'インフレ', 'GDP', '失業率', '中央銀行', '日銀', 'FRB', 'ECB', '株価', '為替', '円安', '円高', '企業決算', '業績', '売上', '利益', '新規上場', 'IPO', 'M&A', '買収']
        keywords = []
        for pattern in economic_patterns:
            if re.search(pattern, text):
                keywords.append(pattern.replace('\\b', '').replace('\\\\', ''))
        return keywords[:5]

    def _get_fallback_metadata(self, news_items: List[Dict[str, Any]], mode: str) -> Dict[str, Any]:
        current_date = datetime.now().strftime('%Y年%m月%d日')
        fallback_title = self._generate_fallback_title(news_items)
        return {'title': fallback_title, 'description': f'\n【{current_date} 経済ニュース解説】\n\n本日の重要な経済ニュースを専門家が分かりやすく解説します。\n\n📈 今日のトピック：\n' + '\n'.join([f"• {item.get('title', '無題')}" for item in news_items[:3]]) + '\n\n🎯 この動画で学べること：\n• 最新の経済動向と市場への影響\n• 専門家による詳細分析と解説\n• 今後の注目ポイント\n\n⚠️ 免責事項：\n本動画の内容は情報提供を目的としており、投資勧誘ではありません。\n\n#経済ニュース #投資 #株式市場 #金融 #経済解説', 'tags': self._generate_fallback_tags(news_items), 'category': 'News & Politics', 'thumbnail_text': '経済ニュース解説', 'seo_keywords': ['経済ニュース', '投資', '株式市場', '金融'], 'target_audience': '経済に関心のある視聴者', 'estimated_watch_time': '15-30分', 'generated_at': datetime.now().isoformat(), 'news_count': len(news_items), 'fallback': True}

    def create_short_form_metadata(self, topic: str, duration_minutes: int=1) -> Dict[str, Any]:
        prompt = f'\n以下のトピックについて、YouTube Shorts用のメタデータを生成してください：\n\nトピック: {topic}\n動画長: {duration_minutes}分\n\n要件：\n- タイトル: 30文字以内、インパクト重視\n- 説明文: 500文字以内、簡潔で興味を引く\n- タグ: ショート動画向け、10個程度\n- ハッシュタグ: トレンド性重視\n\nJSON形式で回答してください：\n{{\n  "title": "ショート動画タイトル",\n  "description": "簡潔な説明文",\n  "tags": ["タグ1", "タグ2", ...],\n  "hashtags": ["#ハッシュタグ1", "#ハッシュタグ2", ...],\n  "category": "News & Politics"\n}}\n'
        try:
            response = self._call_gemini_for_metadata(prompt)
            metadata = self._parse_metadata_response(response)
            if metadata:
                metadata['video_type'] = 'shorts'
                metadata['estimated_watch_time'] = f'{duration_minutes}分'
                metadata['generated_at'] = datetime.now().isoformat()
            return metadata or self._get_fallback_shorts_metadata(topic)
        except Exception as e:
            logger.error(f'Failed to generate shorts metadata: {e}')
            return self._get_fallback_shorts_metadata(topic)

    def _get_fallback_shorts_metadata(self, topic: str) -> Dict[str, Any]:
        return {'title': f'【速報】{topic}', 'description': f'{topic}について1分で解説\n\n#経済ニュース #投資 #ショート動画', 'tags': ['経済ニュース', '投資', 'ショート', '速報', topic], 'hashtags': ['#経済ニュース', '#投資', '#ショート動画', '#速報'], 'category': 'News & Politics', 'video_type': 'shorts', 'estimated_watch_time': '1分', 'generated_at': datetime.now().isoformat(), 'fallback': True}
metadata_generator = MetadataGenerator() if cfg.gemini_api_key else None

def generate_youtube_metadata(news_items: List[Dict[str, Any]], script_content: str='', mode: str='daily') -> Dict[str, Any]:
    if metadata_generator:
        return metadata_generator.generate_youtube_metadata(news_items, script_content, mode)
    else:
        logger.warning('Metadata generator not available, using fallback')
        return MetadataGenerator()._get_fallback_metadata(news_items, mode)

def create_shorts_metadata(topic: str, duration_minutes: int=1) -> Dict[str, Any]:
    if metadata_generator:
        return metadata_generator.create_short_form_metadata(topic, duration_minutes)
    else:
        logger.warning('Metadata generator not available, using fallback')
        return MetadataGenerator()._get_fallback_shorts_metadata(topic)
if __name__ == '__main__':
    print('Testing metadata generation...')
    if cfg.gemini_api_key:
        test_news = [{'title': '日経平均株価が3日連続で上昇、年初来高値を更新', 'summary': '東京株式市場で日経平均株価が前日比1.8%上昇し、3日連続の上昇となった。好調な企業決算と海外投資家の買いが支えとなり、年初来高値を更新した。', 'source': '日本経済新聞', 'impact_level': 'high', 'category': '金融'}, {'title': '中央銀行が政策金利を0.25%引き上げ', 'summary': '日本銀行は金融政策決定会合で政策金利を0.25%引き上げることを決定。インフレ抑制を目的とした措置で、市場は事前に織り込んでいた。', 'source': 'Bloomberg', 'impact_level': 'high', 'category': '政策'}]
        try:
            generator = MetadataGenerator()
            print('\n=== 通常動画メタデータ生成テスト ===')
            metadata = generator.generate_youtube_metadata(test_news, '', 'daily')
            print(f"タイトル: {metadata.get('title')}")
            print(f"タグ数: {len(metadata.get('tags', []))}")
            print(f"説明文長: {len(metadata.get('description', ''))}")
            print(f"カテゴリ: {metadata.get('category')}")
            print('\n=== ショート動画メタデータ生成テスト ===')
            shorts_metadata = generator.create_short_form_metadata('日経平均高値更新', 1)
            print(f"ショートタイトル: {shorts_metadata.get('title')}")
            print(f"ハッシュタグ: {shorts_metadata.get('hashtags')}")
            print(f"動画タイプ: {shorts_metadata.get('video_type')}")
        except Exception as e:
            print(f'Test failed: {e}')
    else:
        print('Gemini API not configured, skipping test')
    print('\n=== フォールバック機能テスト ===')
    fallback_generator = MetadataGenerator()
    fallback_metadata = fallback_generator._get_fallback_metadata([], 'daily')
    print(f"フォールバックタイトル: {fallback_metadata.get('title')}")
    print(f"フォールバックタグ数: {len(fallback_metadata.get('tags', []))}")