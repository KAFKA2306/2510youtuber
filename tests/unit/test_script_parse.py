"""Test script to verify TTS parsing works correctly"""

import sys

sys.path.insert(0, "/home/kafka/projects/youtuber")

from app.tts import tts_manager

# Test with proper script format (what CrewAI should generate)
test_script = """
## オープニング

ナレーター: こんにちは。今回は日銀の金融政策について解説します。

武宏: 結論から言うと、日銀が政策金利を引き上げる可能性が高まっています。
(字幕: 政策金利引き上げ)

つむぎ: え、それって私たちの生活にも影響があるってことですか？

武宏: その通りです。詳しく見ていきましょう。

## 本編

武宏: まず第一の要因として、インフレ率の上昇が挙げられます。

つむぎ: なるほど。具体的にどれくらい上昇しているんですか？

武宏: 前年比で2.5パーセントの上昇となっています。
(字幕: 2.5%上昇)

ナレーター: 今回のポイントをまとめます。
"""

print("Testing TTS text splitting...")
print(f"Original script length: {len(test_script)} characters\n")

chunks = tts_manager.split_text_for_tts(test_script)

print(f"Number of chunks: {len(chunks)}")
print()

for chunk in chunks:
    print(f"Chunk ID: {chunk['id']}")
    print(f"Speaker: {chunk['speaker']}")
    print(f"Text: {chunk['text'][:100]}...")
    print(f"Order: {chunk['order']}")
    print()

if len(chunks) == 0:
    print("❌ ERROR: No chunks generated!")
    print("This means the script format is not being recognized.")
else:
    print(f"✅ SUCCESS: {len(chunks)} chunks generated successfully!")
