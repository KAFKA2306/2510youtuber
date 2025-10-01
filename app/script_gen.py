"""
台本生成モジュール

ニュース要約から対談形式の台本を生成します。
"""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
import google.generativeai as genai
from app.config import cfg

logger = logging.getLogger(__name__)

class ScriptGenerator:
    """台本生成クラス"""

    def __init__(self):
        self.client = None
        self._setup_client()

    def _setup_client(self):
        """Gemini APIクライアントを初期化"""
        try:
            if not cfg.gemini_api_key:
                raise ValueError("Gemini API key not configured")

            genai.configure(api_key=cfg.gemini_api_key)
            self.client = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("Script generator initialized with Gemini")

        except Exception as e:
            logger.error(f"Failed to initialize script generator: {e}")
            raise

    def generate_dialogue(self, news_items: List[Dict[str, Any]],
                         prompt_b: str,
                         target_duration_minutes: int = 30) -> str:
        """
        ニュース項目から対談台本を生成

        Args:
            news_items: ニュース項目のリスト
            prompt_b: 台本生成用プロンプト
            target_duration_minutes: 目標動画長（分）

        Returns:
            対談形式の台本テキスト
        """
        try:
            news_summary = self._format_news_for_script(news_items)
            full_prompt = self._build_script_prompt(
                news_summary, prompt_b, target_duration_minutes
            )
            script = self._call_gemini_for_script(full_prompt)
            cleaned_script = self._clean_script(script)

            if self._validate_script_quality(cleaned_script, target_duration_minutes):
                logger.info(f"Generated script: {len(cleaned_script)} characters")
                return cleaned_script
            else:
                logger.warning("Script quality validation failed, using fallback")
                return self._get_fallback_script(news_items)

        except Exception as e:
            logger.error(f"Failed to generate script: {e}")
            return self._get_fallback_script(news_items)

    def _format_news_for_script(self, news_items: List[Dict[str, Any]]) -> str:
        """ニュース項目を台本生成用に整形"""
        formatted_sections = []
        for i, item in enumerate(news_items, 1):
            section = f"""
【ニュース{i}】{item.get('title', '無題')}
出典: {item.get('source', '不明')} ({item.get('url', '')})
影響度: {item.get('impact_level', 'medium')}
カテゴリ: {item.get('category', '経済')}

要約:
{item.get('summary', '')}

重要ポイント:
"""
            key_points = item.get('key_points', [])
            for point in key_points:
                section += f"- {point}\n"
            formatted_sections.append(section)
        return "\n".join(formatted_sections)

    def _build_script_prompt(self, news_summary: str,
                           base_prompt: str,
                           target_duration: int) -> str:
        """台本生成用の詳細プロンプトを構築"""
        target_chars = target_duration * 300
        full_prompt = f"""
{base_prompt}

【今回のニュース情報】
{news_summary}

【台本作成要件】
1. 目標時間: {target_duration}分（約{target_chars}文字）
2. 構成: オープニング → ニュース解説 → まとめ
3. 話者: 田中氏（経済専門家）、鈴木氏（金融アナリスト）
4. トーン: 専門的だが理解しやすい、時々軽妙な掛け合い

【重要な制約】
- 出典を必ず明記（「○○によると」「○○の報道では」等）
- 数値やデータは具体的に言及
- 推測と事実を明確に区別
- 聞き手の理解を助ける解説を含める
- 自然な会話の流れを保つ

【台本フォーマット】
田中: [発言内容]
鈴木: [発言内容]

【構成例】
1. オープニング（2-3分）: 今日のトピック紹介
2. ニュース1解説（8-10分）: 詳細分析と背景
3. ニュース2解説（8-10分）: 詳細分析と背景
4. ニュース3解説（5-7分）: 簡潔な解説
5. 全体まとめ（3-5分）: 今日のポイント整理

現在の日時: {datetime.now().strftime('%Y年%m月%d日 %H時')}

上記の要件に従って、自然で情報価値の高い対談台本を作成してください。
"""
        return full_prompt

    def _call_gemini_for_script(self, prompt: str, max_retries: int = 3) -> str:
        """台本生成用Gemini API呼び出し"""
        import time
        import random

        for attempt in range(max_retries):
            try:
                response = self.client.generate_content(prompt)
                content = response.text
                logger.debug(f"Generated script length: {len(content)}")
                return content
            except Exception as e:
                if "rate_limit" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Rate limit hit, waiting {wait_time:.2f}s...")
                    time.sleep(wait_time)
                    continue
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    logger.warning(f"Script generation error, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                    continue
                raise
        raise Exception("Max retries exceeded for script generation")

    def _clean_script(self, raw_script: str) -> str:
        """台本テキストのクリーニング"""
        script = raw_script.strip()
        patterns_to_remove = [
            r'^.*?以下.*?台本.*?[:：]\s*',
            r'^.*?対談.*?[:：]\s*',
            r'^.*?スクリプト.*?[:：]\s*',
        ]
        for pattern in patterns_to_remove:
            script = re.sub(pattern, '', script, flags=re.IGNORECASE | re.MULTILINE)
        script = re.sub(r'田中[氏さん]*[:：]', '田中:', script)
        script = re.sub(r'鈴木[氏さん]*[:：]', '鈴木:', script)
        script = re.sub(r'\n\s*\n\s*\n+', '\n\n', script)
        script = re.sub(r'[^\w\s\n\r！？。、：（）「」『』【】\-\+\*\/\%\$\&\#\.]+', '', script)
        return script.strip()

    def _validate_script_quality(self, script: str, target_duration: int) -> bool:
        """台本の品質を検証"""
        try:
            min_chars = target_duration * 200
            max_chars = target_duration * 400
            if not (min_chars <= len(script) <= max_chars):
                logger.warning(f"Script length {len(script)} not in range {min_chars}-{max_chars}")
                return False
            tanaka_lines = len(re.findall(r'^田中:', script, re.MULTILINE))
            suzuki_lines = len(re.findall(r'^鈴木:', script, re.MULTILINE))
            if tanaka_lines < 5 or suzuki_lines < 5:
                logger.warning(f"Insufficient dialogue lines: 田中={tanaka_lines}, 鈴木={suzuki_lines}")
                return False
            if max(tanaka_lines, suzuki_lines) == 0:
                return False
            line_ratio = min(tanaka_lines, suzuki_lines) / max(tanaka_lines, suzuki_lines)
            if line_ratio < 0.3:
                logger.warning(f"Unbalanced dialogue ratio: {line_ratio}")
                return False
            required_elements = [
                r'(今日|本日)',
                r'(によると|報道|発表)',
                r'(パーセント|％|\d+%)',
            ]
            missing_elements = []
            for element in required_elements:
                if not re.search(element, script):
                    missing_elements.append(element)
            if missing_elements:
                logger.warning(f"Missing required elements: {missing_elements}")
                if len(missing_elements) > 1:
                    return False
            return True
        except Exception as e:
            logger.error(f"Script validation error: {e}")
            return False

    def _get_fallback_script(self, news_items: List[Dict[str, Any]]) -> str:
        """フォールバック用の基本台本"""
        current_date = datetime.now().strftime('%Y年%m月%d日')
        script = f"""田中: 皆さん、こんにちは。{current_date}の経済ニュース分析をお届けします。今日は私、田中と、

鈴木: 金融アナリストの鈴木がお送りします。今日は重要なニュースがいくつか入ってきていますね。

田中: そうですね。では早速、今日のトピックを見ていきましょう。
"""
        for i, item in enumerate(news_items, 1):
            title = item.get('title', f'ニュース{i}')
            summary = item.get('summary', 'システムエラーにより詳細を取得できませんでした。')
            source = item.get('source', '情報源不明')
            script += f"""
田中: {i}番目のニュースです。{title}について、{source}からの報道です。

鈴木: {summary[:100]}...という内容ですね。

田中: この件については、詳細な分析が必要ですが、現在システムに問題が発生しているため、手動での確認をお願いします。

鈴木: 視聴者の皆様には、信頼できる情報源からの正確な情報をご確認いただくことをお勧めします。
"""
        script += """
田中: 本日は技術的な問題により、通常の詳細な分析をお届けできず申し訳ありませんでした。

鈴木: 次回はより詳細な経済分析をお届けしますので、引き続きご視聴ください。

田中: それでは、今日はこの辺りで。ありがとうございました。

鈴木: ありがとうございました。
"""
        return script

    def generate_short_script(self, topic: str, duration_minutes: int = 10) -> str:
        """短尺の特定トピック用台本を生成"""
        prompt = f"""
以下のトピックについて、{duration_minutes}分程度の対談形式台本を作成してください：

トピック: {topic}

要件:
- 田中氏と鈴木氏の対談形式
- 約{duration_duration_minutes * 300}文字程度
- 専門的だが理解しやすい内容
- 具体的なデータや事例を含める

台本形式:
田中: [発言内容]
鈴木: [発言内容]
"""
        try:
            response = self._call_gemini_for_script(prompt)
            return self._clean_script(response)
        except Exception as e:
            logger.error(f"Failed to generate short script for '{topic}': {e}")
            return self._get_fallback_script([{
                'title': topic,
                'summary': f'{topic}に関する詳細な情報をお届けする予定でしたが、システムエラーが発生しました。',
                'source': 'システム'
            }])

# グローバルインスタンス
script_generator = ScriptGenerator() if cfg.gemini_api_key else None

def generate_dialogue(news_items: List[Dict[str, Any]],
                     prompt_b: str,
                     target_duration: int = 30) -> str:
    """台本生成の簡易関数"""
    if script_generator:
        return script_generator.generate_dialogue(news_items, prompt_b, target_duration)
    else:
        logger.warning("Script generator not available, using fallback")
        return ScriptGenerator()._get_fallback_script(news_items)

def generate_short_script(topic: str, duration_minutes: int = 10) -> str:
    """短尺台本生成の簡易関数"""
    if script_generator:
        return script_generator.generate_short_script(topic, duration_minutes)
    else:
        logger.warning("Script generator not available, using fallback")
        return ScriptGenerator()._get_fallback_script([{
            'title': topic,
            'summary': f'{topic}について',
            'source': 'システム'
        }])

if __name__ == "__main__":
    print("Testing script generation...")
    if cfg.gemini_api_key:
        test_news = [
            {
                'title': '日経平均株価が年初来高値を更新',
                'summary': '東京株式市場で日経平均株価が前日比2.1%上昇し、年初来高値を更新した。好調な企業決算と海外投資家の買いが支えとなった。',
                'source': '日本経済新聞',
                'url': 'https://example.com/news1',
                'key_points': ['年初来高値更新', '2.1%上昇', '好調な企業決算'],
                'impact_level': 'high',
                'category': '金融'
            },
            {
                'title': '新興企業の資金調達が過去最高に',
                'summary': 'スタートアップ企業による資金調達額が第3四半期で過去最高の1兆円を突破。AI関連企業への投資が特に活発。',
                'source': 'TechCrunch Japan',
                'url': 'https://example.com/news2',
                'key_points': ['資金調達額過去最高', '1兆円突破', 'AI関連投資活発'],
                'impact_level': 'medium',
                'category': '企業'
            }
        ]
        try:
            generator = ScriptGenerator()
            test_prompt = """
以下のニュース要約をもとに、二人の専門家による対談形式の台本を作成してください。
自然な会話の流れで、視聴者にとって理解しやすく、情報価値の高い内容にしてください。
"""
            script = generator.generate_dialogue(test_news, test_prompt, 15)
            print(f"Generated script ({len(script)} characters):")
            print("=" * 50)
            print(script[:500] + "..." if len(script) > 500 else script)
            print("=" * 50)
        except Exception as e:
            print(f"Test failed: {e}")
    else:
        print("Gemini API not configured, skipping test")
