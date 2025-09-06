#!/usr/bin/env python3
"""
清理 CrewAI 記憶系統腳本

此腳本可以清理 TrailTag 項目中的 CrewAI 記憶條目和執行狀態，
解決卡住的任務和過多記憶條目的問題。
"""

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from typing import Dict, List


def main():
    """主函數"""
    print("🔍 TrailTag CrewAI 記憶系統清理工具")
    print("=" * 50)

    # 確認我們在正確的專案目錄
    if not os.path.exists("crewai_storage"):
        print("❌ 錯誤: 未找到 crewai_storage 目錄")
        print("請確認在 TrailTag 專案根目錄下執行此腳本")
        sys.exit(1)

    # 顯示當前記憶狀態
    show_memory_status()

    # 詢問用戶要執行的操作
    print("\n選擇要執行的操作:")
    print("1. 清理卡住的任務 (推薦)")
    print("2. 清理舊記憶條目 (7天前)")
    print("3. 完全重置記憶系統 (危險)")
    print("4. 僅顯示統計信息")
    print("0. 退出")

    choice = input("\n請選擇 (0-4): ").strip()

    if choice == "1":
        cleanup_stuck_jobs()
    elif choice == "2":
        cleanup_old_memories()
    elif choice == "3":
        if confirm_reset():
            full_reset()
    elif choice == "4":
        pass  # 已經顯示了統計信息
    elif choice == "0":
        print("👋 退出")
    else:
        print("❌ 無效選擇")


def show_memory_status():
    """顯示記憶系統狀態"""
    print("\n📊 當前記憶系統狀態:")

    # 檢查各個記憶檔案
    files_info = {
        "agent_memories.json": "代理記憶",
        "job_memories.json": "任務記憶",
        "analysis_results.json": "分析結果",
        "crew_memory/memories.json": "Crew記憶",
    }

    total_entries = 0

    for file_path, description in files_info.items():
        full_path = f"crewai_storage/{file_path}"
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, list):
                    count = len(data)
                elif isinstance(data, dict):
                    count = sum(
                        len(v) if isinstance(v, list) else 1 for v in data.values()
                    )
                else:
                    count = 1

                file_size = os.path.getsize(full_path) / 1024  # KB
                print(f"  • {description}: {count} 條目 ({file_size:.1f}KB)")
                total_entries += count

                # 檢查卡住的任務
                if file_path == "job_memories.json":
                    check_stuck_jobs(data)

            except Exception as e:
                print(f"  • {description}: 讀取錯誤 - {e}")
        else:
            print(f"  • {description}: 檔案不存在")

    print(f"\n📈 總記憶條目: {total_entries}")


def check_stuck_jobs(job_data: List[Dict]):
    """檢查卡住的任務"""
    if not job_data:
        return

    current_time = datetime.now(timezone.utc)
    stuck_jobs = []

    for job in job_data:
        if job.get("status") == "running":
            try:
                updated_at = datetime.fromisoformat(
                    job.get("updated_at", "").replace("Z", "+00:00")
                )
                time_diff = current_time - updated_at
                if time_diff.days > 0:  # 超過1天的運行任務
                    stuck_jobs.append(
                        {
                            "job_id": job.get("job_id"),
                            "video_id": job.get("video_id"),
                            "days_stuck": time_diff.days,
                        }
                    )
            except Exception:
                pass

    if stuck_jobs:
        print(f"  ⚠️  發現 {len(stuck_jobs)} 個卡住的任務:")
        for job in stuck_jobs:
            print(
                f"     - {job['job_id'][:8]}... (影片: {job['video_id']}, 卡住 {job['days_stuck']} 天)"
            )


def cleanup_stuck_jobs():
    """清理卡住的任務"""
    print("\n🧹 清理卡住的任務...")

    job_file = "crewai_storage/job_memories.json"
    if not os.path.exists(job_file):
        print("✅ 沒有任務記憶檔案需要清理")
        return

    try:
        with open(job_file, "r", encoding="utf-8") as f:
            jobs = json.load(f)

        original_count = len(jobs)
        current_time = datetime.now(timezone.utc)
        cleaned_jobs = []

        for job in jobs:
            if job.get("status") == "running":
                try:
                    updated_at = datetime.fromisoformat(
                        job.get("updated_at", "").replace("Z", "+00:00")
                    )
                    time_diff = current_time - updated_at
                    if time_diff.days > 0:  # 超過1天就標記為失敗
                        job["status"] = "failed"
                        job["error_message"] = (
                            f"任務卡住超過 {time_diff.days} 天，自動清理"
                        )
                        job["updated_at"] = current_time.isoformat()
                except Exception:
                    # 無效的時間格式也標記為失敗
                    job["status"] = "failed"
                    job["error_message"] = "無效的更新時間，自動清理"
                    job["updated_at"] = current_time.isoformat()

            cleaned_jobs.append(job)

        # 備份原始檔案
        backup_path = f"{job_file}.backup.{int(current_time.timestamp())}"
        shutil.copy2(job_file, backup_path)
        print(f"✅ 原始檔案已備份到: {backup_path}")

        # 寫入清理後的資料
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(cleaned_jobs, f, ensure_ascii=False, indent=2)

        cleaned_count = original_count - len(
            [j for j in cleaned_jobs if j.get("status") == "running"]
        )
        print(f"✅ 已清理 {cleaned_count} 個卡住的任務")

    except Exception as e:
        print(f"❌ 清理失敗: {e}")


def cleanup_old_memories():
    """清理舊記憶條目"""
    print("\n🧹 清理 7 天前的記憶條目...")

    current_time = datetime.now(timezone.utc)
    cutoff_days = 7

    # 清理各個記憶檔案
    files_to_clean = [
        "crewai_storage/agent_memories.json",
        "crewai_storage/crew_memory/memories.json",
    ]

    for file_path in files_to_clean:
        if not os.path.exists(file_path):
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            original_count = 0
            cleaned_data = None

            if isinstance(data, list):
                original_count = len(data)
                cleaned_data = [
                    item
                    for item in data
                    if not should_remove_by_age(item, current_time, cutoff_days)
                ]
            elif isinstance(data, dict):
                cleaned_data = {}
                for key, value in data.items():
                    if isinstance(value, list):
                        original_count += len(value)
                        cleaned_value = [
                            item
                            for item in value
                            if not should_remove_by_age(item, current_time, cutoff_days)
                        ]
                        if cleaned_value:  # 只保留非空的列表
                            cleaned_data[key] = cleaned_value
                    else:
                        original_count += 1
                        if not should_remove_by_age(value, current_time, cutoff_days):
                            cleaned_data[key] = value

            # 備份並寫入清理後的資料
            if cleaned_data is not None:
                backup_path = f"{file_path}.backup.{int(current_time.timestamp())}"
                shutil.copy2(file_path, backup_path)

                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

                new_count = count_items(cleaned_data)
                removed_count = original_count - new_count
                print(
                    f"✅ {file_path}: 移除 {removed_count} 個舊條目 (剩餘 {new_count} 個)"
                )

        except Exception as e:
            print(f"❌ 清理 {file_path} 失敗: {e}")


def should_remove_by_age(item: Dict, current_time: datetime, cutoff_days: int) -> bool:
    """判斷條目是否應該因為年齡而被移除"""
    time_fields = ["created_at", "updated_at", "stored_at"]

    for field in time_fields:
        if field in item:
            try:
                if field == "stored_at":
                    # stored_at 是時間戳格式
                    item_time = datetime.fromtimestamp(
                        float(item[field]), tz=timezone.utc
                    )
                else:
                    # 其他是 ISO 格式
                    time_str = item[field].replace("Z", "+00:00")
                    item_time = datetime.fromisoformat(time_str)

                time_diff = current_time - item_time
                return time_diff.days > cutoff_days
            except Exception:
                continue

    return False  # 如果無法解析時間，保留條目


def count_items(data) -> int:
    """計算資料中的條目數量"""
    if isinstance(data, list):
        return len(data)
    elif isinstance(data, dict):
        return sum(len(v) if isinstance(v, list) else 1 for v in data.values())
    else:
        return 1


def confirm_reset() -> bool:
    """確認完全重置操作"""
    print("\n⚠️  警告: 完全重置將刪除所有記憶條目!")
    print("這將:")
    print("  • 刪除所有代理記憶")
    print("  • 刪除所有任務記憶")
    print("  • 刪除所有分析結果")
    print("  • 刪除所有 Crew 記憶")

    confirmation = input("\n輸入 'DELETE' 確認完全重置: ")
    return confirmation == "DELETE"


def full_reset():
    """完全重置記憶系統"""
    print("\n🔥 執行完全重置...")

    current_time = datetime.now(timezone.utc)
    backup_dir = f"crewai_storage_backup_{int(current_time.timestamp())}"

    try:
        # 備份整個 crewai_storage 目錄
        if os.path.exists("crewai_storage"):
            shutil.copytree("crewai_storage", backup_dir)
            print(f"✅ 完整備份已保存到: {backup_dir}")

        # 刪除並重建 crewai_storage
        if os.path.exists("crewai_storage"):
            shutil.rmtree("crewai_storage")

        os.makedirs("crewai_storage", exist_ok=True)
        os.makedirs("crewai_storage/crew_memory", exist_ok=True)

        # 創建空的記憶檔案
        empty_files = {
            "crewai_storage/agent_memories.json": {},
            "crewai_storage/job_memories.json": [],
            "crewai_storage/analysis_results.json": [],
            "crewai_storage/crew_memory/memories.json": [],
        }

        for file_path, empty_content in empty_files.items():
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(empty_content, f, ensure_ascii=False, indent=2)

        print("✅ 記憶系統已完全重置")
        print(f"✅ 原始資料備份在: {backup_dir}")

    except Exception as e:
        print(f"❌ 重置失敗: {e}")


if __name__ == "__main__":
    main()
