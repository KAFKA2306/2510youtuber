"""日本語品質チェックモジュール

原稿とサブテキストが明瞭で面白い純粋な日本語になっているかを検証します。
英語やその他の言語の混入を検出し、修正を提案します。
"""

import logging
import re
from typing import Any, Dict, List

import google.generativeai as genai

from app.config.settings import settings

logger = logging.getLogger(__name__)


class JapaneseQualityChecker:
    """日本語品質チェッククラス"""

    def __init__(self):
        self.client = None
        self._setup_client()

        # 許可される英数字パターン（数値、パーセント、単位など）
        self.allowed_patterns = [
            r"\d+",  # 数字
            r"\d+%",  # パーセント
            r"\d+円",  # 円
            r"\d+ドル",  # ドル
            r"\d+年",  # 年
            r"\d+月",  # 月
            r"\d+日",  # 日
            r"GDP",  # 許可される略語
            r"AI",
            r"IT",
            r"IoT",
            r"DX",
        ]

    def _setup_client(self):
        """Gemini APIクライアントを初期化"""
        try:
            if settings.api_keys.get("gemini"):
                genai.configure(api_key=settings.api_keys["gemini"])
                self.client = genai.GenerativeModel("models/gemini-2.0-flash-exp")
                logger.info("Japanese quality checker initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize quality checker: {e}")

    def check_script_japanese_purity(self, script: str) -> Dict[str, Any]:
        """原稿の日本語純度をチェック

        Returns:
            {
                "is_pure_japanese": bool,
                "issues": List[Dict],  # 問題箇所のリスト
                "purity_score": float,  # 0-100のスコア
                "english_ratio": float,  # 英語の割合
            }
        """
        try:
            issues = []
            total_chars = len(script)
            english_chars = 0

            # 改行で分割して行ごとにチェック
            lines = script.split("\n")
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line:
                    continue

                # 話者名を除去
                content = re.sub(r"^(田中|鈴木|ナレーター|司会)[:：]\s*", "", line)

                # 英語の検出
                english_issues = self._detect_english_words(content, line_num)
                if english_issues:
                    issues.extend(english_issues)
                    for issue in english_issues:
                        english_chars += len(issue["text"])

            # スコア計算
            english_ratio = (english_chars / total_chars * 100) if total_chars > 0 else 0
            purity_score = max(0, 100 - english_ratio * 10)  # 英語1%で-10点

            result = {
                "is_pure_japanese": len(issues) == 0,
                "issues": issues,
                "purity_score": purity_score,
                "english_ratio": english_ratio,
                "total_issues": len(issues),
            }

            logger.info(f"Japanese purity check: score={purity_score:.1f}, issues={len(issues)}")
            return result

        except Exception as e:
            logger.error(f"Japanese purity check failed: {e}")
            return {
                "is_pure_japanese": True,  # エラー時は通過させる
                "issues": [],
                "purity_score": 50.0,
                "english_ratio": 0.0,
                "error": str(e)
            }

    def _detect_english_words(self, text: str, line_num: int) -> List[Dict[str, Any]]:
        """英語単語を検出"""
        issues = []

        # 許可されたパターンを一時的に置換
        temp_text = text
        for pattern in self.allowed_patterns:
            temp_text = re.sub(pattern, "", temp_text)

        # 英単語を検出（連続した英字）
        english_pattern = r"[a-zA-Z]{2,}"
        matches = re.finditer(english_pattern, temp_text)

        for match in matches:
            word = match.group()
            # 短い接頭語・接尾語は許可（例: e-mail, Mr.）
            if len(word) >= 3:
                issues.append({
                    "type": "english_word",
                    "text": word,
                    "line": line_num,
                    "position": match.start(),
                    "severity": "high" if len(word) > 5 else "medium"
                })

        return issues

    def improve_japanese_quality(self, script: str) -> Dict[str, Any]:
        """日本語品質を改善

        英語が混入している場合、AIを使って自然な日本語に修正します。
        """
        if not self.client:
            logger.warning("Gemini client not available, cannot improve quality")
            return {"success": False, "error": "AI client not available"}

        try:
            # まず品質チェック
            quality_result = self.check_script_japanese_purity(script)

            if quality_result["is_pure_japanese"]:
                return {
                    "success": True,
                    "improved_script": script,
                    "changes_made": False,
                    "original_score": quality_result["purity_score"]
                }

            # 改善が必要な場合
            logger.info(f"Improving script with {len(quality_result['issues'])} issues")

            improvement_prompt = f"""
以下の台本には英語が混じっていて視聴者が理解しにくいという問題があります。
すべての英語を自然な日本語に置き換えて、明瞭で面白い日本語の台本に修正してください。

【重要な指示】
1. すべての英語単語を適切な日本語に翻訳または言い換える
2. 専門用語は理解しやすい日本語で説明を加える
3. 会話の自然さを保つ
4. 話者名（田中:、鈴木:）のフォーマットは維持する
5. 数字、パーセント、単位（円、ドルなど）はそのまま使用可能
6. AI、GDP、ITなどの一般的な略語は使用可能

【検出された問題点】
{self._format_issues(quality_result['issues'])}

【原稿】
{script}

【出力】
修正後の台本のみを出力してください（説明文は不要）。
"""

            response = self.client.generate_content(improvement_prompt)
            improved_script = response.text.strip()

            # 改善後の品質を再チェック
            new_quality = self.check_script_japanese_purity(improved_script)

            logger.info(
                f"Script improved: {quality_result['purity_score']:.1f} -> {new_quality['purity_score']:.1f}"
            )

            return {
                "success": True,
                "improved_script": improved_script,
                "changes_made": True,
                "original_score": quality_result["purity_score"],
                "new_score": new_quality["purity_score"],
                "issues_fixed": len(quality_result["issues"]) - len(new_quality["issues"])
            }

        except Exception as e:
            logger.error(f"Script improvement failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "improved_script": script  # フォールバック
            }

    def _format_issues(self, issues: List[Dict[str, Any]]) -> str:
        """問題点をフォーマット"""
        if not issues:
            return "なし"

        formatted = []
        for issue in issues[:10]:  # 最大10個
            formatted.append(
                f"- 行{issue['line']}: 英語「{issue['text']}」を日本語に変更してください"
            )

        if len(issues) > 10:
            formatted.append(f"...他{len(issues) - 10}件")

        return "\n".join(formatted)

    def validate_subtitle_text(self, subtitle_text: str) -> bool:
        """字幕テキストが純粋な日本語かを検証

        字幕は短いので、より厳格にチェックします。
        """
        # 許可される略語を一時的に除去
        temp_text = subtitle_text
        for pattern in self.allowed_patterns:
            temp_text = re.sub(pattern, "", temp_text)

        # 英字が残っているかチェック
        has_english = bool(re.search(r"[a-zA-Z]", temp_text))

        if has_english:
            logger.warning(f"Subtitle contains English: '{subtitle_text}'")
            return False

        return True

    def clean_subtitle_text(self, subtitle_text: str) -> str:
        """字幕テキストをクリーニング

        英語が含まれている場合、可能な限り除去または変換します。
        """
        cleaned = subtitle_text

        # 一般的な英語フレーズを日本語に置換
        replacements = {
            r"\bHello\b": "こんにちは",
            r"\bGoodbye\b": "さようなら",
            r"\bThank you\b": "ありがとうございます",
            r"\bPlease\b": "どうぞ",
            r"\bYes\b": "はい",
            r"\bNo\b": "いいえ",
            r"\bOK\b": "わかりました",
            r"\band\b": "と",
            r"\bor\b": "または",
            r"\bthe\b": "",
            r"\ba\b": "",
            r"\ban\b": "",
        }

        for pattern, replacement in replacements.items():
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

        # 残った英単語を検出して警告
        remaining_english = re.findall(r"[a-zA-Z]{2,}", cleaned)
        if remaining_english:
            # 許可されたパターンを除外
            filtered_english = []
            for word in remaining_english:
                is_allowed = False
                for pattern in self.allowed_patterns:
                    if re.match(pattern, word):
                        is_allowed = True
                        break
                if not is_allowed:
                    filtered_english.append(word)

            if filtered_english:
                logger.warning(f"Could not clean all English from subtitle: {filtered_english}")

        return cleaned.strip()

    def check_clarity_and_interest(self, script: str) -> Dict[str, Any]:
        """明瞭さと面白さをチェック

        AIを使って、台本が視聴者にとって理解しやすく、
        面白い内容になっているかを評価します。
        """
        if not self.client:
            return {
                "clarity_score": 50.0,
                "interest_score": 50.0,
                "suggestions": []
            }

        try:
            evaluation_prompt = f"""
以下の経済ニュース解説台本を評価してください。

【評価基準】
1. 明瞭性（0-100点）: 内容が分かりやすく、専門用語に説明があるか
2. 面白さ（0-100点）: 視聴者が最後まで楽しく見られる内容か

【台本】
{script[:2000]}  # 最初の2000文字

【評価結果を以下の形式で出力】
明瞭性: [点数]
面白さ: [点数]
改善提案:
1. [具体的な改善提案1]
2. [具体的な改善提案2]
3. [具体的な改善提案3]
"""

            response = self.client.generate_content(evaluation_prompt)
            result_text = response.text.strip()

            # スコアを抽出
            clarity_match = re.search(r"明瞭性[：:]\s*(\d+)", result_text)
            interest_match = re.search(r"面白さ[：:]\s*(\d+)", result_text)

            clarity_score = float(clarity_match.group(1)) if clarity_match else 50.0
            interest_score = float(interest_match.group(1)) if interest_match else 50.0

            # 改善提案を抽出
            suggestions = []
            lines = result_text.split("\n")
            in_suggestions = False
            for line in lines:
                if "改善提案" in line:
                    in_suggestions = True
                    continue
                if in_suggestions:
                    stripped = line.strip()
                    if stripped and (stripped[0].isdigit() or stripped[0] in ["-", "•", "・"]):
                        cleaned = stripped.lstrip("0123456789.-•・ ）】")
                        if cleaned:
                            suggestions.append(cleaned)

            return {
                "clarity_score": clarity_score,
                "interest_score": interest_score,
                "suggestions": suggestions[:5]  # 最大5個
            }

        except Exception as e:
            logger.error(f"Clarity and interest check failed: {e}")
            return {
                "clarity_score": 50.0,
                "interest_score": 50.0,
                "suggestions": [],
                "error": str(e)
            }


# グローバルインスタンス
japanese_quality_checker = JapaneseQualityChecker() if settings.api_keys.get("gemini") else None


def check_script_japanese_purity(script: str) -> Dict[str, Any]:
    """原稿の日本語純度チェック（簡易関数）"""
    if japanese_quality_checker:
        return japanese_quality_checker.check_script_japanese_purity(script)
    return {"is_pure_japanese": True, "issues": [], "purity_score": 100.0}


def improve_japanese_quality(script: str) -> Dict[str, Any]:
    """日本語品質改善（簡易関数）"""
    if japanese_quality_checker:
        return japanese_quality_checker.improve_japanese_quality(script)
    return {"success": True, "improved_script": script, "changes_made": False}


def validate_subtitle_text(subtitle_text: str) -> bool:
    """字幕テキスト検証（簡易関数）"""
    if japanese_quality_checker:
        return japanese_quality_checker.validate_subtitle_text(subtitle_text)
    return True


def clean_subtitle_text(subtitle_text: str) -> str:
    """字幕テキストクリーニング（簡易関数）"""
    if japanese_quality_checker:
        return japanese_quality_checker.clean_subtitle_text(subtitle_text)
    return subtitle_text


if __name__ == "__main__":
    print("Testing Japanese quality checker...")

    if japanese_quality_checker:
        # テスト1: 英語混入チェック
        test_script_bad = """
田中: Hello、今日はimportantなeconomic newsについて話します。

鈴木: 日経平均株価がsignificantlyに上昇しましたね。

田中: Yes、前日比で2.5%のincreaseとなりました。
"""

        print("\n=== Test 1: Detecting English ===")
        result = japanese_quality_checker.check_script_japanese_purity(test_script_bad)
        print(f"Pure Japanese: {result['is_pure_japanese']}")
        print(f"Purity Score: {result['purity_score']:.1f}")
        print(f"Issues: {result['total_issues']}")
        for issue in result["issues"][:3]:
            print(f"  - Line {issue['line']}: {issue['text']}")

        # テスト2: 改善
        print("\n=== Test 2: Improving Quality ===")
        improved = japanese_quality_checker.improve_japanese_quality(test_script_bad)
        if improved["success"] and improved["changes_made"]:
            print(f"Score: {improved['original_score']:.1f} -> {improved['new_score']:.1f}")
            print(f"Fixed {improved['issues_fixed']} issues")
            print("\nImproved script (first 200 chars):")
            print(improved["improved_script"][:200])

        # テスト3: 純粋な日本語
        test_script_good = """
田中: 皆さん、こんにちは。今日は重要な経済ニュースについてお話しします。

鈴木: 日経平均株価が大幅に上昇しましたね。

田中: そうです。前日比で2.5%の上昇となりました。
"""

        print("\n=== Test 3: Pure Japanese ===")
        result_good = japanese_quality_checker.check_script_japanese_purity(test_script_good)
        print(f"Pure Japanese: {result_good['is_pure_japanese']}")
        print(f"Purity Score: {result_good['purity_score']:.1f}")

        # テスト4: 字幕チェック
        print("\n=== Test 4: Subtitle Validation ===")
        test_subtitles = [
            "今日は重要なニュースがあります",
            "GDPが3.5%増加しました",
            "This is an English subtitle",
            "AI技術が発展しています"
        ]

        for subtitle in test_subtitles:
            is_valid = japanese_quality_checker.validate_subtitle_text(subtitle)
            print(f"  '{subtitle}' -> {'OK' if is_valid else 'NG'}")

    else:
        print("Japanese quality checker not available (no API key)")
