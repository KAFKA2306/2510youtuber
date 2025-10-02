"""設定管理モジュール

環境変数とYAMLファイルから設定を読み込み、
アプリケーション全体で使用可能にします。
"""

# from .settings import settings, AppSettings  # 一時的にコメントアウト（旧config.py使用中）
from .prompts import load_prompt_template, PromptManager

__all__ = [
    # 'settings',
    # 'AppSettings',
    'load_prompt_template',
    'PromptManager',
]
