#!/usr/bin/env python3
"""
快速測試 CrewAI Memory cache.set() 功能
"""

import sys

sys.path.append("/Users/sacahan/Documents/workspace/TrailTag")

from src.api.cache.cache_provider import get_cache
import json


def test_cache():
    cache = get_cache()

    # 測試簡單的 cache set/get
    test_key = "job:test-123"
    test_data = {
        "job_id": "test-123",
        "video_id": "abc123",
        "status": "running",
        "phase": "metadata",
        "progress": 25,
        "created_at": "2025-09-07T06:29:03.410707+00:00",
        "updated_at": "2025-09-07T06:29:03.410707+00:00",
    }

    print("🧪 測試 cache.set() 和 cache.get()")
    print(f"🔑 Key: {test_key}")
    print(f"📊 Data: {json.dumps(test_data, indent=2)}")

    # 嘗試寫入
    print("\n=== 寫入測試 ===")
    result = cache.set(test_key, test_data)
    print(f"📝 set() 結果: {result}")

    # 立即讀取
    print("\n=== 讀取測試 ===")
    retrieved = cache.get(test_key)
    print(f"📖 get() 結果: {json.dumps(retrieved, indent=2) if retrieved else 'None'}")

    # 比較
    print("\n=== 比較 ===")
    if retrieved:
        matches = retrieved.get("status") == test_data.get("status")
        print(f"🎯 狀態匹配: {matches}")
        print(f"   期望: {test_data.get('status')}")
        print(f"   實際: {retrieved.get('status')}")
    else:
        print("❌ 無法讀取資料")

    # 檢查 CrewAI Memory 內部狀態
    print("\n=== CrewAI Memory 內部狀態 ===")
    memory = cache.memory.memory_storage
    print(f"總記憶條目數: {len(memory.memories)}")

    # 搜尋測試記錄
    cache_entries = []
    for memory_id, memory_entry in memory.memories.items():
        metadata = memory_entry.metadata
        if metadata.get("type") == "cache" and not metadata.get("deleted", False):
            if metadata.get("original_query") == test_key:
                cache_entries.append(
                    {
                        "memory_id": memory_id,
                        "metadata": metadata,
                        "content_preview": (
                            memory_entry.content[:100] + "..."
                            if len(memory_entry.content) > 100
                            else memory_entry.content
                        ),
                    }
                )

    print(f"找到 {len(cache_entries)} 個匹配的快取條目:")
    for entry in cache_entries:
        print(f"  ID: {entry['memory_id']}")
        print(f"  Query: {entry['metadata'].get('original_query')}")
        print(f"  Content: {entry['content_preview']}")


if __name__ == "__main__":
    test_cache()
