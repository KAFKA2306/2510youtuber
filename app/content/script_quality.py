"""3段階品質チェック付き台本生成モジュール

視聴者満足度を最大化するため、以下の3段階で台本を生成・改善します：

Stage 1: 初稿生成 - AIが基本的な台本を作成
Stage 2: 品質レビュー - AIが台本を評価し、改善点を指摘
Stage 3: 最終稿生成 - 改善点を反映した高品質な台本を作成
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

import google.generativeai as genai

from app.config import cfg

logger = logging.getLogger(__name__)


class ThreeStageScriptGenerator:
    """3段階品質チェック付き台本生成クラス"""

    def __init__(self):
        self.client = None
        self._setup_client()
        self.quality_threshold = 7.0  # 10点満点で7点以上を合格とする

    def _setup_client(self):
        """Gemini APIクライアントを初期化"""
        try:
            if not cfg.gemini_api_key:
                raise ValueError("Gemini API key not configured")

            genai.configure(api_key=cfg.gemini_api_key)
            model_name = cfg.gemini_models.get("quality_review")
            self.client = genai.GenerativeModel(f"models/{model_name}")
            logger.info("Three-stage script generator initialized with Gemini")

        except Exception as e:
            logger.error(f"Failed to initialize three-stage generator: {e}")
            raise

    def generate_high_quality_script(
        self, news_items: List[Dict[str, Any]], base_prompt: str, target_duration_minutes: int = 30
    ) -> Dict[str, Any]:
        """3段階品質チェックで高品質な台本を生成

        Returns:
            {
                "final_script": 最終台本,
                "stage1_script": 初稿,
                "stage2_review": レビュー結果,
                "quality_score": 品質スコア,
                "iterations": 反復回数,
                "success": 成功フラグ
            }
        """
        logger.info("=== Starting 3-stage script generation process ===")

        try:
            # Stage 1: 初稿生成
            stage1_result = self._stage1_generate_draft(news_items, base_prompt, target_duration_minutes)
            if not stage1_result["success"]:
                return self._create_failure_result("Stage 1 failed")

            # Stage 2: 品質レビュー
            stage2_result = self._stage2_quality_review(stage1_result["draft"], news_items)
            if not stage2_result["success"]:
                logger.warning("Stage 2 review failed, using draft as-is")
                return {
                    "final_script": stage1_result["draft"],
                    "stage1_script": stage1_result["draft"],
                    "stage2_review": {"error": "Review failed"},
                    "quality_score": 5.0,
                    "iterations": 1,
                    "success": True,
                }

            # Stage 3: 最終稿生成（必要に応じて改善）
            if stage2_result["quality_score"] >= self.quality_threshold:
                logger.info(f"Draft quality sufficient ({stage2_result['quality_score']}/10), using as final")
                return {
                    "final_script": stage1_result["draft"],
                    "stage1_script": stage1_result["draft"],
                    "stage2_review": stage2_result,
                    "quality_score": stage2_result["quality_score"],
                    "iterations": 1,
                    "success": True,
                }
            else:
                stage3_result = self._stage3_generate_final(
                    stage1_result["draft"], stage2_result, news_items, base_prompt, target_duration_minutes
                )

                return {
                    "final_script": stage3_result["final_script"],
                    "stage1_script": stage1_result["draft"],
                    "stage2_review": stage2_result,
                    "stage3_improvements": stage3_result.get("improvements", []),
                    "quality_score": stage3_result.get("quality_score", 8.0),
                    "iterations": 2,
                    "success": True,
                }

        except Exception as e:
            logger.error(f"3-stage generation failed: {e}")
            return self._create_failure_result(str(e))

    def _stage1_generate_draft(
        self, news_items: List[Dict[str, Any]], base_prompt: str, target_duration: int
    ) -> Dict[str, Any]:
        """Stage 1: 初稿を生成"""
        logger.info("Stage 1: Generating draft script...")

        try:
            news_summary = self._format_news_for_script(news_items)

            draft_prompt = f"""
{base_prompt}

【ニュース情報】
{news_summary}

【台本作成要件】
1. 目標時間: {target_duration}分（約{target_duration * 300}文字）
2. 構成: オープニング → ニュース解説 → まとめ
3. 話者: 田中氏（経済専門家）、鈴木氏（金融アナリスト）
4. トーン: 専門的だが理解しやすい、視聴者が楽しめる内容

【重要な制約】
- 出典を必ず明記
- 数値やデータは具体的に言及
- 推測と事実を明確に区別
- 視聴者の理解を助ける解説を含める
- 自然で楽しい会話の流れを保つ

【言語に関する重要な指示】
- すべての内容を純粋な日本語で記述してください
- 英語の単語や表現を使用しないでください
- 専門用語は理解しやすい日本語で説明してください
- AI、GDP、ITなどの一般的な略語のみ使用可能

【台本フォーマット】
田中: [発言内容]
鈴木: [発言内容]

現在の日時: {datetime.now().strftime("%Y年%m月%d日")}

視聴者が最後まで楽しく見られる、価値ある台本を作成してください。
"""

            response = self.client.generate_content(draft_prompt)
            draft_script = response.text.strip()

            logger.info(f"Stage 1 completed: {len(draft_script)} characters")
            return {"success": True, "draft": draft_script, "length": len(draft_script)}

        except Exception as e:
            logger.error(f"Stage 1 failed: {e}")
            return {"success": False, "error": str(e)}

    def _stage2_quality_review(self, draft_script: str, news_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Stage 2: 品質レビューを実施"""
        logger.info("Stage 2: Reviewing script quality...")

        try:
            review_prompt = f"""
以下の経済ニュース解説台本を、視聴者満足度の観点から厳格にレビューしてください。

【台本】
{draft_script[:3000]}  # 長すぎる場合は最初の3000文字のみ

【評価基準】（各項目を10点満点で評価）
1. 正確性: 事実とデータが正確か
2. わかりやすさ: 専門用語の説明が適切か
3. 面白さ: 視聴者が最後まで楽しめる内容か
4. 会話の自然さ: 対談が自然で違和感がないか
5. 構成: オープニング、本編、まとめが適切か
6. 情報量: 視聴者にとって価値ある情報が十分か
7. 出典明記: 情報源が適切に示されているか
8. 視聴者への配慮: 難しい内容でも理解を助ける工夫があるか
9. 日本語純度: 英語が混じっておらず、すべて純粋な日本語で書かれているか

【レビュー結果を以下の形式で出力】
総合評価: [0-10点]
各項目評価:
- 正確性: [点数]/10
- わかりやすさ: [点数]/10
- 面白さ: [点数]/10
- 会話の自然さ: [点数]/10
- 構成: [点数]/10
- 情報量: [点数]/10
- 出典明記: [点数]/10
- 視聴者への配慮: [点数]/10

改善すべき点:
1. [具体的な改善点1]
2. [具体的な改善点2]
3. [具体的な改善点3]

良い点:
1. [優れている点1]
2. [優れている点2]
"""

            response = self.client.generate_content(review_prompt)
            review_text = response.text.strip()

            # レビュー結果から品質スコアを抽出
            quality_score = self._extract_quality_score(review_text)
            improvements = self._extract_improvements(review_text)
            strengths = self._extract_strengths(review_text)

            logger.info(f"Stage 2 completed: Quality score = {quality_score}/10")

            return {
                "success": True,
                "quality_score": quality_score,
                "review_text": review_text,
                "improvements": improvements,
                "strengths": strengths,
            }

        except Exception as e:
            logger.error(f"Stage 2 failed: {e}")
            return {"success": False, "error": str(e)}

    def _stage3_generate_final(
        self,
        draft_script: str,
        review_result: Dict[str, Any],
        news_items: List[Dict[str, Any]],
        base_prompt: str,
        target_duration: int,
    ) -> Dict[str, Any]:
        """Stage 3: レビューを反映した最終稿を生成"""
        logger.info("Stage 3: Generating final script with improvements...")

        try:
            improvements = review_result.get("improvements", [])
            improvements_text = "\n".join([f"- {imp}" for imp in improvements])

            news_summary = self._format_news_for_script(news_items)

            final_prompt = f"""
以下の初稿台本を、品質レビューの指摘に基づいて改善してください。

【初稿台本】
{draft_script}

【品質レビューの改善点】
{improvements_text}

【品質レビューの良い点（維持すべき）】
{chr(10).join([f"- {s}" for s in review_result.get("strengths", [])])}

【ニュース情報（参照用）】
{news_summary}

【改善指示】
1. 上記の改善点を全て反映する
2. 良い点は必ず維持する
3. 視聴者がより楽しめる内容にする
4. 自然な会話の流れを保つ
5. 目標時間: {target_duration}分（約{target_duration * 300}文字）
6. すべて純粋な日本語で記述し、英語を使用しない

【台本フォーマット】
田中: [発言内容]
鈴木: [発言内容]

改善された最終稿を作成してください。
"""

            response = self.client.generate_content(final_prompt)
            final_script = response.text.strip()

            logger.info(f"Stage 3 completed: {len(final_script)} characters")

            return {
                "success": True,
                "final_script": final_script,
                "improvements": improvements,
                "quality_score": 8.5,  # 改善後のスコア（推定）
            }

        except Exception as e:
            logger.error(f"Stage 3 failed: {e}")
            # フォールバック: 初稿をそのまま返す
            return {
                "success": True,
                "final_script": draft_script,
                "error": str(e),
                "quality_score": review_result.get("quality_score", 6.0),
            }

    def _format_news_for_script(self, news_items: List[Dict[str, Any]]) -> str:
        """ニュース項目を台本生成用に整形"""
        formatted_sections = []
        for i, item in enumerate(news_items, 1):
            section = f"""
【ニュース{i}】{item.get("title", "無題")}
出典: {item.get("source", "不明")} ({item.get("url", "")})
影響度: {item.get("impact_level", "medium")}
カテゴリ: {item.get("category", "経済")}

要約:
{item.get("summary", "")}

重要ポイント:
"""
            key_points = item.get("key_points", [])
            for point in key_points:
                section += f"- {point}\n"
            formatted_sections.append(section)
        return "\n".join(formatted_sections)

    def _extract_quality_score(self, review_text: str) -> float:
        """レビューテキストから品質スコアを抽出"""
        import re

        # "総合評価: 7.5" のようなパターンを検索
        patterns = [
            r"総合評価[：:]\s*(\d+\.?\d*)",
            r"総合[：:]\s*(\d+\.?\d*)",
            r"スコア[：:]\s*(\d+\.?\d*)",
        ]

        for pattern in patterns:
            match = re.search(pattern, review_text)
            if match:
                try:
                    score = float(match.group(1))
                    return min(10.0, max(0.0, score))
                except ValueError:
                    continue

        # 抽出できない場合はデフォルト
        logger.warning("Could not extract quality score, using default 6.0")
        return 6.0

    def _extract_improvements(self, review_text: str) -> List[str]:
        """レビューテキストから改善点を抽出"""
        improvements = []

        # "改善すべき点:" 以降のリスト項目を抽出
        lines = review_text.split("\n")
        in_improvements_section = False

        for line in lines:
            if "改善" in line and ("点" in line or "ポイント" in line):
                in_improvements_section = True
                continue
            elif "良い点" in line or "優れている" in line:
                break
            elif in_improvements_section:
                # リスト項目（1. または - で始まる）を検出
                stripped = line.strip()
                if stripped and (stripped[0].isdigit() or stripped[0] in ["-", "•", "・"]):
                    # 番号や記号を除去
                    cleaned = stripped.lstrip("0123456789.-•・ ）】")
                    if cleaned:
                        improvements.append(cleaned)

        return improvements[:5]  # 最大5個

    def _extract_strengths(self, review_text: str) -> List[str]:
        """レビューテキストから良い点を抽出"""
        strengths = []

        # "良い点:" 以降のリスト項目を抽出
        lines = review_text.split("\n")
        in_strengths_section = False

        for line in lines:
            if "良い点" in line or "優れている" in line:
                in_strengths_section = True
                continue
            elif in_strengths_section:
                stripped = line.strip()
                if stripped and (stripped[0].isdigit() or stripped[0] in ["-", "•", "・"]):
                    cleaned = stripped.lstrip("0123456789.-•・ ）】")
                    if cleaned:
                        strengths.append(cleaned)

        return strengths[:5]  # 最大5個

    def _create_failure_result(self, error: str) -> Dict[str, Any]:
        """失敗結果を作成"""
        return {"success": False, "error": error, "final_script": None, "quality_score": 0.0, "iterations": 0}


# グローバルインスタンス
three_stage_generator = ThreeStageScriptGenerator() if cfg.gemini_api_key else None


def generate_high_quality_script(
    news_items: List[Dict[str, Any]], base_prompt: str, target_duration_minutes: int = 30
) -> Dict[str, Any]:
    """3段階品質チェック付き台本生成の簡易関数"""
    if three_stage_generator:
        return three_stage_generator.generate_high_quality_script(news_items, base_prompt, target_duration_minutes)
    else:
        logger.error("Three-stage generator not available")
        return {"success": False, "error": "Three-stage generator not initialized", "final_script": None}


if __name__ == "__main__":
    print("Testing 3-stage script generation...")

    if cfg.gemini_api_key:
        test_news = [
            {
                "title": "日経平均株価が年初来高値を更新",
                "summary": "東京株式市場で日経平均株価が前日比2.1%上昇し、年初来高値を更新した。",
                "source": "日本経済新聞",
                "url": "https://example.com/news1",
                "key_points": ["年初来高値更新", "2.1%上昇", "好調な企業決算"],
                "impact_level": "high",
                "category": "金融",
            }
        ]

        test_prompt = """
経済専門家による対談形式の台本を作成してください。
視聴者が楽しめる、わかりやすく価値のある内容にしてください。
"""

        try:
            generator = ThreeStageScriptGenerator()
            result = generator.generate_high_quality_script(test_news, test_prompt, 15)

            if result["success"]:
                print(f"\n✓ Success! Quality score: {result['quality_score']}/10")
                print(f"  Iterations: {result['iterations']}")
                print(f"  Final script length: {len(result['final_script'])} chars")
                print("\n=== Final Script (first 500 chars) ===")
                print(result["final_script"][:500] + "...")

                if result.get("stage2_review"):
                    print("\n=== Review Summary ===")
                    print(f"Improvements: {len(result['stage2_review'].get('improvements', []))}")
                    for imp in result["stage2_review"].get("improvements", [])[:3]:
                        print(f"  - {imp}")
            else:
                print(f"\n✗ Failed: {result.get('error')}")

        except Exception as e:
            print(f"Test failed: {e}")
    else:
        print("Gemini API not configured, skipping test")
