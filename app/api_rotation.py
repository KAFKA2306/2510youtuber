"""API Key Rotation Manager

複数のAPIキー（Gemini, Perplexity等）をプール管理し、
障害時の自動切替とRate limit対策を実現します。
"""

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class APIKey:
    """APIキー情報"""
    key: str
    provider: str  # "gemini", "perplexity", etc.
    failure_count: int = 0
    last_failure: Optional[datetime] = None
    last_success: Optional[datetime] = None
    rate_limit_until: Optional[datetime] = None
    total_calls: int = 0
    total_successes: int = 0

    @property
    def is_available(self) -> bool:
        """キーが使用可能か判定"""
        if self.rate_limit_until and datetime.now() < self.rate_limit_until:
            return False
        # 連続失敗5回以上は10分間休止
        if self.failure_count >= 5:
            if self.last_failure and datetime.now() - self.last_failure < timedelta(minutes=10):
                return False
            # 10分経過したらリセット
            self.failure_count = 0
        return True

    @property
    def success_rate(self) -> float:
        """成功率を計算"""
        if self.total_calls == 0:
            return 1.0
        return self.total_successes / self.total_calls

    def mark_success(self):
        """成功を記録"""
        self.last_success = datetime.now()
        self.total_calls += 1
        self.total_successes += 1
        self.failure_count = 0  # リセット

    def mark_failure(self, is_rate_limit: bool = False):
        """失敗を記録"""
        self.last_failure = datetime.now()
        self.total_calls += 1
        self.failure_count += 1

        if is_rate_limit:
            # Rate limitの場合は5分間待機
            self.rate_limit_until = datetime.now() + timedelta(minutes=5)
            logger.warning(f"{self.provider} key rate limited until {self.rate_limit_until}")


class APIKeyRotationManager:
    """APIキーローテーション管理クラス"""

    def __init__(self):
        self.key_pools: Dict[str, List[APIKey]] = {}
        self.current_indices: Dict[str, int] = {}
        self.gemini_daily_quota_limit: int = 0
        self.gemini_daily_calls: int = 0
        self.last_quota_reset_date: Optional[datetime] = None

    def _check_and_reset_daily_quota(self):
        """日次クォータをチェックし、必要であればリセットする"""
        now = datetime.now()
        # UTC午前0時にリセットされると仮定
        if (
            self.last_quota_reset_date is None
            or self.last_quota_reset_date.date() < now.date()
        ):
            logger.info("Resetting Gemini daily quota.")
            self.gemini_daily_calls = 0
            self.last_quota_reset_date = now

    def set_gemini_daily_quota_limit(self, limit: int):
        """Gemini APIの日次クォータ制限を設定する"""
        self.gemini_daily_quota_limit = limit
        logger.info(f"Gemini daily quota limit set to {limit}")

    def register_keys(self, provider: str, keys: List[str]):
        """APIキーを登録

        Args:
            provider: プロバイダー名 ("gemini", "perplexity", etc.)
            keys: APIキーのリスト
        """
        if not keys:
            logger.warning(f"No keys provided for {provider}")
            return

        self.key_pools[provider] = [
            APIKey(key=key, provider=provider) for key in keys if key
        ]
        self.current_indices[provider] = 0
        logger.info(f"Registered {len(self.key_pools[provider])} keys for {provider}")

    def get_best_key(self, provider: str) -> Optional[APIKey]:
        """最適なキーを取得（成功率と可用性を考慮）

        Args:
            provider: プロバイダー名

        Returns:
            最適なAPIKey、なければNone
        """
        if provider not in self.key_pools or not self.key_pools[provider]:
            logger.error(f"No keys registered for {provider}")
            return None

        available_keys = [k for k in self.key_pools[provider] if k.is_available]

        if not available_keys:
            logger.warning(f"All {provider} keys are unavailable, trying anyway...")
            # 全キーが使用不可の場合、最も古い失敗のキーを返す
            available_keys = sorted(
                self.key_pools[provider],
                key=lambda k: k.last_failure or datetime.min
            )

        # 成功率が高いキーを優先（ランダム要素も加える）
        if len(available_keys) > 1:
            # 上位80%から選択（探索的選択）
            sorted_keys = sorted(available_keys, key=lambda k: k.success_rate, reverse=True)
            top_80_count = max(1, int(len(sorted_keys) * 0.8))
            selected_key = random.choice(sorted_keys[:top_80_count])
        else:
            selected_key = available_keys[0]

        logger.debug(
            f"Selected {provider} key (success_rate: {selected_key.success_rate:.2%}, "
            f"total_calls: {selected_key.total_calls})"
        )
        return selected_key

    def execute_with_rotation(
        self,
        provider: str,
        api_call: Callable[[str], Any],
        max_attempts: int = None,
    ) -> Any:
        """キーローテーションを使用してAPI呼び出しを実行

        Args:
            provider: プロバイダー名
            api_call: API呼び出し関数 (引数: api_key, 戻り値: Any)
            max_attempts: 最大試行回数（Noneの場合はキー数と同じ）

        Returns:
            API呼び出しの結果

        Raises:
            Exception: すべてのキーで失敗した場合
        """
        if provider not in self.key_pools or not self.key_pools[provider]:
            raise ValueError(f"No keys registered for {provider}")

        if max_attempts is None:
            max_attempts = len(self.key_pools[provider])

        last_exception = None
        attempted_keys = set()

        # Gemini APIの場合、日次クォータをチェック
        if provider == "gemini":
            self._check_and_reset_daily_quota()
            if (
                self.gemini_daily_quota_limit > 0
                and self.gemini_daily_calls >= self.gemini_daily_quota_limit
            ):
                error_msg = (
                    f"Gemini daily quota ({self.gemini_daily_quota_limit}) exceeded. "
                    f"Current calls: {self.gemini_daily_calls}. "
                    f"Will reset on {self.last_quota_reset_date.date() + timedelta(days=1)}"
                )
                logger.error(error_msg)
                raise Exception(error_msg)

        for attempt in range(max_attempts):
            key_obj = self.get_best_key(provider)

            if not key_obj or key_obj.key in attempted_keys:
                # すべてのキーを試した
                logger.warning(f"All {provider} keys attempted, retrying from start")
                attempted_keys.clear()
                key_obj = self.get_best_key(provider)

            if not key_obj:
                raise Exception(f"No available keys for {provider}")

            attempted_keys.add(key_obj.key)

            try:
                logger.info(f"Attempting API call with {provider} (attempt {attempt + 1}/{max_attempts})")
                result = api_call(key_obj.key)
                key_obj.mark_success()
                logger.info(f"API call succeeded with {provider}")

                if provider == "gemini":
                    self.gemini_daily_calls += 1
                    logger.debug(f"Gemini daily calls: {self.gemini_daily_calls}/{self.gemini_daily_quota_limit}")

                return result

            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = any(
                    keyword in error_str
                    for keyword in ["429", "rate limit", "quota", "too many requests"]
                )

                key_obj.mark_failure(is_rate_limit=is_rate_limit)
                last_exception = e

                logger.warning(
                    f"{provider} API call failed (attempt {attempt + 1}/{max_attempts}): {e}"
                )

                # Rate limitでない場合、短い待機
                if not is_rate_limit and attempt < max_attempts - 1:
                    wait_time = min(2 ** attempt, 10)  # 最大10秒
                    logger.info(f"Waiting {wait_time}s before next attempt...")
                    time.sleep(wait_time)

        # すべての試行が失敗
        logger.error(f"All {provider} API attempts failed")
        raise last_exception or Exception(f"All {provider} keys exhausted")

    def get_stats(self, provider: str = None) -> Dict[str, Any]:
        """統計情報を取得

        Args:
            provider: 特定のプロバイダー（Noneの場合は全体）

        Returns:
            統計情報の辞書
        """
        if provider:
            if provider not in self.key_pools:
                return {}

            keys = self.key_pools[provider]
            return {
                "provider": provider,
                "total_keys": len(keys),
                "available_keys": sum(1 for k in keys if k.is_available),
                "total_calls": sum(k.total_calls for k in keys),
                "total_successes": sum(k.total_successes for k in keys),
                "average_success_rate": sum(k.success_rate for k in keys) / len(keys) if keys else 0,
                "keys": [
                    {
                        "success_rate": k.success_rate,
                        "total_calls": k.total_calls,
                        "failure_count": k.failure_count,
                        "is_available": k.is_available,
                    }
                    for k in keys
                ],
            }
        else:
            return {
                provider_name: self.get_stats(provider_name)
                for provider_name in self.key_pools.keys()
            }


# グローバルインスタンス
_rotation_manager = None


def get_rotation_manager() -> APIKeyRotationManager:
    """グローバルローテーションマネージャーを取得"""
    global _rotation_manager
    if _rotation_manager is None:
        _rotation_manager = APIKeyRotationManager()
    return _rotation_manager


def initialize_from_config():
    """設定ファイルからキーを初期化"""
    from .config import cfg

    manager = get_rotation_manager()

    # Gemini keys
    gemini_keys = cfg.gemini_api_keys
    if gemini_keys:
        manager.register_keys("gemini", gemini_keys)
    
    # Gemini daily quota limit
    if cfg.gemini_daily_quota_limit > 0:
        manager.set_gemini_daily_quota_limit(cfg.gemini_daily_quota_limit)

    # Perplexity keys (単一キーを配列化)
    perplexity_keys = [cfg.perplexity_api_key] if cfg.perplexity_api_key else []
    # 環境変数から複数キーを取得（PERPLEXITY_API_KEY_2, PERPLEXITY_API_KEY_3等）
    import os
    for i in range(2, 10):
        extra_key = os.getenv(f"PERPLEXITY_API_KEY_{i}")
        if extra_key:
            perplexity_keys.append(extra_key)

    if perplexity_keys:
        manager.register_keys("perplexity", perplexity_keys)

    logger.info("API key rotation initialized from config")
    return manager


if __name__ == "__main__":
    # テスト
    print("Testing API Key Rotation Manager...")

    manager = APIKeyRotationManager()

    # テスト用のダミーキーを登録
    manager.register_keys("test_api", ["key1", "key2", "key3"])

    # テスト用API呼び出し（ランダムに失敗）
    def mock_api_call(api_key: str):
        print(f"  Calling API with {api_key}")
        if random.random() < 0.3:  # 30%の確率で失敗
            raise Exception("Random failure")
        return f"Success with {api_key}"

    # ローテーションテスト
    for i in range(10):
        try:
            result = manager.execute_with_rotation("test_api", mock_api_call, max_attempts=5)
            print(f"✓ Call {i + 1}: {result}")
        except Exception as e:
            print(f"✗ Call {i + 1}: Failed - {e}")

    # 統計表示
    stats = manager.get_stats("test_api")
    print("\n=== Statistics ===")
    print(f"Total keys: {stats['total_keys']}")
    print(f"Available keys: {stats['available_keys']}")
    print(f"Total calls: {stats['total_calls']}")
    print(f"Total successes: {stats['total_successes']}")
    print(f"Average success rate: {stats['average_success_rate']:.2%}")
