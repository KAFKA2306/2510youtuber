"""Google Sheetsプロンプトのローカルキャッシュ管理

Sheets接続失敗時のフォールバックとして、プロンプトをローカルにキャッシュします。
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PromptCache:
    """プロンプトキャッシュマネージャー"""

    def __init__(self, cache_dir: str = "cache", ttl_hours: int = 24):
        """
        Args:
            cache_dir: キャッシュディレクトリ
            ttl_hours: キャッシュの有効期限（時間）
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        self.cache_file = self.cache_dir / "prompts_cache.json"

        logger.info(f"Prompt cache initialized (dir: {self.cache_dir}, TTL: {ttl_hours}h)")

    def get_cache_path(self, mode: str) -> Path:
        """モード別のキャッシュファイルパスを取得"""
        return self.cache_dir / f"prompts_{mode}.json"

    def save_prompts(self, mode: str, prompts: Dict[str, str]) -> bool:
        """プロンプトをキャッシュに保存

        Args:
            mode: 実行モード (daily/special/test)
            prompts: プロンプトの辞書 (prompt_a, prompt_b等)

        Returns:
            保存成功の可否
        """
        try:
            cache_data = {
                "mode": mode,
                "prompts": prompts,
                "cached_at": datetime.now().isoformat(),
                "ttl_hours": self.ttl.total_seconds() / 3600,
            }

            cache_path = self.get_cache_path(mode)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved prompts to cache: {cache_path} (mode: {mode})")
            return True

        except Exception as e:
            logger.error(f"Failed to save prompts to cache: {e}")
            return False

    def load_prompts(self, mode: str) -> Optional[Dict[str, str]]:
        """キャッシュからプロンプトを読み込み

        Args:
            mode: 実行モード

        Returns:
            プロンプトの辞書、またはNone（キャッシュなし/期限切れの場合）
        """
        try:
            cache_path = self.get_cache_path(mode)

            if not cache_path.exists():
                logger.debug(f"No cache found for mode: {mode}")
                return None

            with open(cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            # TTLチェック
            cached_at = datetime.fromisoformat(cache_data["cached_at"])
            age = datetime.now() - cached_at

            if age > self.ttl:
                logger.warning(
                    f"Cache expired for mode {mode} "
                    f"(age: {age.total_seconds()/3600:.1f}h, TTL: {self.ttl.total_seconds()/3600:.1f}h)"
                )
                return None

            prompts = cache_data["prompts"]
            logger.info(f"Loaded prompts from cache: {cache_path} (age: {age.total_seconds()/3600:.1f}h)")
            return prompts

        except Exception as e:
            logger.error(f"Failed to load prompts from cache: {e}")
            return None

    def invalidate_cache(self, mode: str = None) -> bool:
        """キャッシュを無効化（削除）

        Args:
            mode: 特定のモード（Noneの場合は全キャッシュ）

        Returns:
            削除成功の可否
        """
        try:
            if mode:
                # 特定のモードのみ削除
                cache_path = self.get_cache_path(mode)
                if cache_path.exists():
                    cache_path.unlink()
                    logger.info(f"Invalidated cache for mode: {mode}")
            else:
                # 全キャッシュを削除
                for cache_file in self.cache_dir.glob("prompts_*.json"):
                    cache_file.unlink()
                logger.info("Invalidated all prompt caches")

            return True

        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")
            return False

    def get_cache_status(self) -> Dict[str, Any]:
        """キャッシュの状態を取得

        Returns:
            キャッシュ状態の情報
        """
        status = {
            "cache_dir": str(self.cache_dir),
            "ttl_hours": self.ttl.total_seconds() / 3600,
            "cached_modes": [],
        }

        try:
            for cache_file in self.cache_dir.glob("prompts_*.json"):
                mode = cache_file.stem.replace("prompts_", "")

                with open(cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)

                cached_at = datetime.fromisoformat(cache_data["cached_at"])
                age = datetime.now() - cached_at
                is_valid = age <= self.ttl

                status["cached_modes"].append({
                    "mode": mode,
                    "cached_at": cache_data["cached_at"],
                    "age_hours": age.total_seconds() / 3600,
                    "is_valid": is_valid,
                    "has_prompt_a": "prompt_a" in cache_data["prompts"],
                    "has_prompt_b": "prompt_b" in cache_data["prompts"],
                })

        except Exception as e:
            logger.error(f"Failed to get cache status: {e}")

        return status


# グローバルインスタンス
_prompt_cache = None


def get_prompt_cache() -> PromptCache:
    """グローバルプロンプトキャッシュを取得"""
    global _prompt_cache
    if _prompt_cache is None:
        _prompt_cache = PromptCache()
    return _prompt_cache


if __name__ == "__main__":
    # テスト
    print("Testing Prompt Cache Manager...")

    cache = PromptCache(cache_dir="test_cache", ttl_hours=1)

    # テスト用プロンプト
    test_prompts = {
        "prompt_a": "今日の経済ニュースを収集してください。",
        "prompt_b": "対談形式の台本を作成してください。",
    }

    # 保存テスト
    print("\n=== Save Test ===")
    success = cache.save_prompts("daily", test_prompts)
    print(f"Save result: {success}")

    # 読み込みテスト
    print("\n=== Load Test ===")
    loaded = cache.load_prompts("daily")
    if loaded:
        print(f"Loaded prompts: {loaded}")
    else:
        print("No cache found or expired")

    # ステータス確認
    print("\n=== Cache Status ===")
    status = cache.get_cache_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))

    # 無効化テスト
    print("\n=== Invalidation Test ===")
    cache.invalidate_cache("daily")
    print("Cache invalidated")

    # 再読み込み（失敗するはず）
    loaded = cache.load_prompts("daily")
    print(f"Load after invalidation: {loaded}")

    # クリーンアップ
    import shutil
    if os.path.exists("test_cache"):
        shutil.rmtree("test_cache")
        print("\nTest cache directory cleaned up")
