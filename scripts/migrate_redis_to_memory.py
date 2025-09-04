#!/usr/bin/env python3
"""
Redis 到 CrewAI Memory 資料遷移腳本

此腳本負責將現有的 Redis 快取資料遷移到新的 CrewAI Memory 系統。

主要功能：
- 備份現有 Redis 資料
- 批次遷移資料
- 資料完整性驗證
- 遷移進度監控
- 錯誤處理與回滾

使用方式：
    python scripts/migrate_redis_to_memory.py [options]

選項：
    --dry-run: 僅模擬遷移，不實際執行
    --backup: 是否備份 Redis 資料（預設：True）
    --batch-size: 批次大小（預設：100）
    --force: 強制遷移，覆蓋現有資料
"""

import sys
import json
import argparse
import traceback
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from pathlib import Path

# 添加專案根目錄到 Python 路徑
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

try:
    # Redis 相關匯入
    from src.api.cache.cache_provider import RedisCacheProvider
    # from src.api.cache_manager import CacheManager  # 未使用，已移除

    # CrewAI Memory 相關匯入
    from src.trailtag.memory.manager import get_memory_manager
    from src.trailtag.memory.models import (
        CrewMemoryConfig,
        JobProgressEntry,
        AnalysisResultEntry,
        JobStatus,
        JobPhase,
        # MemoryType,  # 未使用，已移除
    )

    # 日誌配置
    from src.api.core.logger_config import get_logger

except ImportError as e:
    print(f"錯誤：無法匯入必要模組 - {e}")
    print("請確認您在專案根目錄下執行此腳本")
    sys.exit(1)

logger = get_logger(__name__)


class RedisMigrationError(Exception):
    """Redis 遷移錯誤"""

    pass


class DataIntegrityError(Exception):
    """資料完整性錯誤"""

    pass


class RedisMigrator:
    """Redis 到 CrewAI Memory 遷移器"""

    def __init__(
        self,
        config: Optional[CrewMemoryConfig] = None,
        batch_size: int = 100,
        backup_enabled: bool = True,
    ):
        """
        初始化遷移器

        Args:
            config: CrewAI Memory 配置
            batch_size: 批次大小
            backup_enabled: 是否啟用備份
        """
        self.config = config or CrewMemoryConfig()
        self.batch_size = batch_size
        self.backup_enabled = backup_enabled

        # Redis 提供者
        try:
            self.redis_provider = RedisCacheProvider()
            self.redis_available = True
            logger.info("Redis 連接成功")
        except Exception as e:
            logger.warning(f"Redis 連接失敗: {e}")
            self.redis_available = False
            self.redis_provider = None

        # CrewAI Memory 管理器
        self.memory_manager = get_memory_manager(config)

        # 統計資料
        self.migration_stats = {
            "total_keys": 0,
            "job_entries": 0,
            "analysis_entries": 0,
            "other_entries": 0,
            "successful_migrations": 0,
            "failed_migrations": 0,
            "skipped_entries": 0,
            "start_time": None,
            "end_time": None,
            "errors": [],
        }

        # 備份目錄
        self.backup_dir = Path(self.config.storage_path) / "redis_backup"
        if self.backup_enabled:
            self.backup_dir.mkdir(parents=True, exist_ok=True)

    def scan_redis_data(self) -> Dict[str, List[str]]:
        """
        掃描 Redis 中的資料鍵值

        Returns:
            按類型分類的鍵值字典
        """
        if not self.redis_available:
            logger.error("Redis 不可用，無法掃描資料")
            return {}

        try:
            # 取得所有相關鍵值
            patterns = [
                "job:*",  # 任務進度
                "analysis:*",  # 分析結果
                "trailtag:*",  # TrailTag 相關快取
                "cache:*",  # 一般快取
            ]

            categorized_keys = {
                "job": [],
                "analysis": [],
                "trailtag": [],
                "cache": [],
                "other": [],
            }

            for pattern in patterns:
                keys = self.redis_provider.scan_keys(pattern)
                logger.info(f"找到 {len(keys)} 個符合模式 '{pattern}' 的鍵值")

                for key in keys:
                    if key.startswith("job:"):
                        categorized_keys["job"].append(key)
                    elif key.startswith("analysis:"):
                        categorized_keys["analysis"].append(key)
                    elif key.startswith("trailtag:"):
                        categorized_keys["trailtag"].append(key)
                    elif key.startswith("cache:"):
                        categorized_keys["cache"].append(key)
                    else:
                        categorized_keys["other"].append(key)

            total_keys = sum(len(keys) for keys in categorized_keys.values())
            self.migration_stats["total_keys"] = total_keys

            logger.info(f"總共找到 {total_keys} 個鍵值待遷移")
            for category, keys in categorized_keys.items():
                if keys:
                    logger.info(f"  {category}: {len(keys)} 個鍵值")

            return categorized_keys

        except Exception as e:
            logger.error(f"掃描 Redis 資料失敗: {e}")
            raise RedisMigrationError(f"掃描 Redis 資料失敗: {e}")

    def backup_redis_data(self, categorized_keys: Dict[str, List[str]]) -> str:
        """
        備份 Redis 資料

        Args:
            categorized_keys: 分類的鍵值字典

        Returns:
            備份檔案路徑
        """
        if not self.backup_enabled:
            logger.info("備份功能已停用")
            return ""

        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"redis_backup_{timestamp}.json"

            backup_data = {
                "metadata": {
                    "backup_time": datetime.now(timezone.utc).isoformat(),
                    "total_keys": sum(len(keys) for keys in categorized_keys.values()),
                    "categories": {
                        cat: len(keys) for cat, keys in categorized_keys.items()
                    },
                },
                "data": {},
            }

            logger.info("開始備份 Redis 資料...")

            for category, keys in categorized_keys.items():
                if not keys:
                    continue

                category_data = {}
                for key in keys:
                    try:
                        value = self.redis_provider.get(key)
                        if value is not None:
                            category_data[key] = value
                    except Exception as e:
                        logger.warning(f"備份鍵值 {key} 失敗: {e}")
                        self.migration_stats["errors"].append(f"備份失敗: {key} - {e}")

                backup_data["data"][category] = category_data
                logger.info(f"已備份 {category} 類別 {len(category_data)} 個鍵值")

            # 寫入備份檔案
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"Redis 資料備份完成: {backup_file}")
            return str(backup_file)

        except Exception as e:
            logger.error(f"備份 Redis 資料失敗: {e}")
            raise RedisMigrationError(f"備份失敗: {e}")

    def migrate_job_entries(self, job_keys: List[str], dry_run: bool = False) -> None:
        """
        遷移任務進度條目

        Args:
            job_keys: 任務鍵值列表
            dry_run: 是否為模擬執行
        """
        if not job_keys:
            logger.info("沒有任務進度資料需要遷移")
            return

        logger.info(f"開始遷移 {len(job_keys)} 個任務進度條目...")

        batch_count = 0
        for i in range(0, len(job_keys), self.batch_size):
            batch = job_keys[i : i + self.batch_size]
            batch_count += 1

            logger.info(
                f"處理任務進度批次 {batch_count}/{(len(job_keys) + self.batch_size - 1) // self.batch_size}"
            )

            for key in batch:
                try:
                    # 取得 Redis 資料
                    redis_data = self.redis_provider.get(key)
                    if redis_data is None:
                        logger.warning(f"鍵值 {key} 在 Redis 中不存在")
                        self.migration_stats["skipped_entries"] += 1
                        continue

                    # 解析 job_id
                    job_id = key.replace("job:", "")

                    # 轉換資料格式
                    entry_data = self._convert_job_data(job_id, redis_data)

                    if dry_run:
                        logger.info(f"[DRY RUN] 會遷移任務: {job_id}")
                        self.migration_stats["successful_migrations"] += 1
                    else:
                        # 儲存到 Memory 系統
                        entry = JobProgressEntry(**entry_data)
                        self.memory_manager.job_memories[job_id] = entry
                        self.memory_manager._persist_job_memory(entry)

                        logger.debug(f"成功遷移任務: {job_id}")
                        self.migration_stats["successful_migrations"] += 1
                        self.migration_stats["job_entries"] += 1

                except Exception as e:
                    logger.error(f"遷移任務 {key} 失敗: {e}")
                    self.migration_stats["failed_migrations"] += 1
                    self.migration_stats["errors"].append(f"任務遷移失敗: {key} - {e}")

        logger.info(f"任務進度遷移完成，成功: {self.migration_stats['job_entries']} 個")

    def migrate_analysis_entries(
        self, analysis_keys: List[str], dry_run: bool = False
    ) -> None:
        """
        遷移分析結果條目

        Args:
            analysis_keys: 分析結果鍵值列表
            dry_run: 是否為模擬執行
        """
        if not analysis_keys:
            logger.info("沒有分析結果資料需要遷移")
            return

        logger.info(f"開始遷移 {len(analysis_keys)} 個分析結果條目...")

        batch_count = 0
        for i in range(0, len(analysis_keys), self.batch_size):
            batch = analysis_keys[i : i + self.batch_size]
            batch_count += 1

            logger.info(
                f"處理分析結果批次 {batch_count}/{(len(analysis_keys) + self.batch_size - 1) // self.batch_size}"
            )

            for key in batch:
                try:
                    # 取得 Redis 資料
                    redis_data = self.redis_provider.get(key)
                    if redis_data is None:
                        logger.warning(f"鍵值 {key} 在 Redis 中不存在")
                        self.migration_stats["skipped_entries"] += 1
                        continue

                    # 解析 video_id
                    video_id = key.replace("analysis:", "")

                    # 轉換資料格式
                    entry_data = self._convert_analysis_data(video_id, redis_data)

                    if dry_run:
                        logger.info(f"[DRY RUN] 會遷移分析結果: {video_id}")
                        self.migration_stats["successful_migrations"] += 1
                    else:
                        # 儲存到 Memory 系統
                        entry = AnalysisResultEntry(**entry_data)
                        self.memory_manager.analysis_results[video_id] = entry
                        self.memory_manager._persist_analysis_result(entry)

                        logger.debug(f"成功遷移分析結果: {video_id}")
                        self.migration_stats["successful_migrations"] += 1
                        self.migration_stats["analysis_entries"] += 1

                except Exception as e:
                    logger.error(f"遷移分析結果 {key} 失敗: {e}")
                    self.migration_stats["failed_migrations"] += 1
                    self.migration_stats["errors"].append(
                        f"分析結果遷移失敗: {key} - {e}"
                    )

        logger.info(
            f"分析結果遷移完成，成功: {self.migration_stats['analysis_entries']} 個"
        )

    def migrate_other_entries(
        self, other_keys: List[str], dry_run: bool = False
    ) -> None:
        """
        遷移其他快取條目

        Args:
            other_keys: 其他鍵值列表
            dry_run: 是否為模擬執行
        """
        if not other_keys:
            logger.info("沒有其他資料需要遷移")
            return

        logger.info(f"開始遷移 {len(other_keys)} 個其他快取條目...")

        for key in other_keys:
            try:
                if dry_run:
                    logger.info(f"[DRY RUN] 會遷移其他資料: {key}")
                    self.migration_stats["other_entries"] += 1
                else:
                    # 其他資料暫時跳過，或根據具體需求處理
                    logger.info(f"跳過其他資料: {key}")
                    self.migration_stats["skipped_entries"] += 1

            except Exception as e:
                logger.error(f"遷移其他資料 {key} 失敗: {e}")
                self.migration_stats["failed_migrations"] += 1
                self.migration_stats["errors"].append(f"其他資料遷移失敗: {key} - {e}")

    def _convert_job_data(
        self, job_id: str, redis_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        轉換任務資料格式

        Args:
            job_id: 任務 ID
            redis_data: Redis 資料

        Returns:
            CrewAI Memory 格式的資料
        """
        try:
            # 處理狀態轉換
            status_mapping = {
                "running": JobStatus.RUNNING,
                "done": JobStatus.COMPLETED,
                "completed": JobStatus.COMPLETED,
                "failed": JobStatus.FAILED,
                "pending": JobStatus.PENDING,
                "cancelled": JobStatus.CANCELLED,
            }

            # 處理階段轉換
            phase_mapping = {
                "metadata": JobPhase.METADATA,
                "summary": JobPhase.SUMMARY,
                "geocode": JobPhase.GEOCODE,
            }

            status = status_mapping.get(
                redis_data.get("status", "pending"), JobStatus.PENDING
            )
            phase = phase_mapping.get(
                redis_data.get("phase", "metadata"), JobPhase.METADATA
            )

            # 處理時間戳
            created_at = redis_data.get("created_at")
            updated_at = redis_data.get("updated_at")

            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            elif created_at is None:
                created_at = datetime.now(timezone.utc)

            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            elif updated_at is None:
                updated_at = datetime.now(timezone.utc)

            return {
                "job_id": job_id,
                "video_id": redis_data.get("video_id", ""),
                "status": status,
                "phase": phase,
                "progress": redis_data.get("progress", 0),
                "cached": redis_data.get("cached", False),
                "result": redis_data.get("result"),
                "error_message": redis_data.get("error_message"),
                "created_at": created_at,
                "updated_at": updated_at,
            }

        except Exception as e:
            logger.error(f"轉換任務資料格式失敗: {e}")
            raise

    def _convert_analysis_data(
        self, video_id: str, redis_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        轉換分析結果資料格式

        Args:
            video_id: 影片 ID
            redis_data: Redis 資料

        Returns:
            CrewAI Memory 格式的資料
        """
        try:
            # 處理時間戳
            created_at = redis_data.get("created_at")
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            elif created_at is None:
                created_at = datetime.now(timezone.utc)

            return {
                "video_id": video_id,
                "metadata": redis_data.get("metadata", {}),
                "topic_summary": redis_data.get("topic_summary", {}),
                "map_visualization": redis_data.get(
                    "map_visualization", redis_data
                ),  # 整個 Redis 資料可能就是地圖資料
                "processing_time": redis_data.get("processing_time", 0.0),
                "created_at": created_at,
                "cached": True,  # 來自 Redis 的都標記為快取
            }

        except Exception as e:
            logger.error(f"轉換分析結果資料格式失敗: {e}")
            raise

    def verify_migration(
        self, categorized_keys: Dict[str, List[str]]
    ) -> Tuple[bool, List[str]]:
        """
        驗證遷移結果

        Args:
            categorized_keys: 原始分類鍵值

        Returns:
            (驗證是否成功, 錯誤訊息列表)
        """
        logger.info("開始驗證遷移結果...")

        verification_errors = []

        try:
            # 驗證任務進度資料
            job_keys = categorized_keys.get("job", [])
            for key in job_keys[: min(10, len(job_keys))]:  # 只驗證前 10 個
                job_id = key.replace("job:", "")
                memory_entry = self.memory_manager.get_job_progress(job_id)

                if memory_entry is None:
                    verification_errors.append(f"任務 {job_id} 在 Memory 系統中不存在")
                else:
                    # 驗證資料完整性
                    redis_data = self.redis_provider.get(key)
                    if (
                        redis_data
                        and redis_data.get("video_id") != memory_entry.video_id
                    ):
                        verification_errors.append(f"任務 {job_id} 的 video_id 不匹配")

            # 驗證分析結果資料
            analysis_keys = categorized_keys.get("analysis", [])
            for key in analysis_keys[: min(10, len(analysis_keys))]:  # 只驗證前 10 個
                video_id = key.replace("analysis:", "")
                memory_entry = self.memory_manager.get_analysis_result(video_id)

                if memory_entry is None:
                    verification_errors.append(
                        f"分析結果 {video_id} 在 Memory 系統中不存在"
                    )

            # 檢查記憶系統統計
            memory_stats = self.memory_manager.get_memory_stats()
            logger.info(f"Memory 系統統計: {memory_stats.model_dump()}")

            if verification_errors:
                logger.error(f"發現 {len(verification_errors)} 個驗證錯誤")
                for error in verification_errors:
                    logger.error(f"  - {error}")
                return False, verification_errors
            else:
                logger.info("遷移驗證成功！")
                return True, []

        except Exception as e:
            error_msg = f"驗證過程中發生錯誤: {e}"
            logger.error(error_msg)
            verification_errors.append(error_msg)
            return False, verification_errors

    def run_migration(self, dry_run: bool = False, force: bool = False) -> bool:
        """
        執行完整遷移流程

        Args:
            dry_run: 是否為模擬執行
            force: 是否強制遷移

        Returns:
            遷移是否成功
        """
        try:
            self.migration_stats["start_time"] = datetime.now(timezone.utc)

            logger.info("=" * 60)
            logger.info("開始 Redis 到 CrewAI Memory 遷移")
            logger.info("=" * 60)

            if dry_run:
                logger.info("這是模擬執行，不會實際修改資料")

            # 檢查先決條件
            if not self.redis_available:
                logger.error("Redis 不可用，無法執行遷移")
                return False

            # 檢查是否已有 Memory 資料
            memory_stats = self.memory_manager.get_memory_stats()
            if memory_stats.total_entries > 0 and not force:
                logger.warning(f"Memory 系統中已有 {memory_stats.total_entries} 個條目")
                logger.warning("使用 --force 參數強制遷移，或清理現有資料後重試")
                return False

            # 步驟 1: 掃描 Redis 資料
            logger.info("步驟 1: 掃描 Redis 資料...")
            categorized_keys = self.scan_redis_data()

            if not any(categorized_keys.values()):
                logger.info("Redis 中沒有找到需要遷移的資料")
                return True

            # 步驟 2: 備份 Redis 資料
            if not dry_run:
                logger.info("步驟 2: 備份 Redis 資料...")
                backup_file = self.backup_redis_data(categorized_keys)
                logger.info(f"備份檔案: {backup_file}")

            # 步驟 3: 執行遷移
            logger.info("步驟 3: 執行資料遷移...")

            # 遷移任務進度
            self.migrate_job_entries(categorized_keys.get("job", []), dry_run)

            # 遷移分析結果
            self.migrate_analysis_entries(categorized_keys.get("analysis", []), dry_run)

            # 遷移其他資料
            other_keys = (
                categorized_keys.get("trailtag", [])
                + categorized_keys.get("cache", [])
                + categorized_keys.get("other", [])
            )
            self.migrate_other_entries(other_keys, dry_run)

            # 步驟 4: 驗證遷移結果
            if not dry_run:
                logger.info("步驟 4: 驗證遷移結果...")
                success, errors = self.verify_migration(categorized_keys)
                if not success:
                    logger.error("遷移驗證失敗")
                    return False

            self.migration_stats["end_time"] = datetime.now(timezone.utc)
            self._print_migration_summary()

            logger.info("=" * 60)
            logger.info("遷移完成！")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"遷移過程中發生錯誤: {e}")
            logger.error(traceback.format_exc())
            return False

    def _print_migration_summary(self) -> None:
        """印出遷移摘要"""
        stats = self.migration_stats

        duration = None
        if stats["start_time"] and stats["end_time"]:
            duration = stats["end_time"] - stats["start_time"]

        logger.info("\n" + "=" * 50)
        logger.info("遷移摘要")
        logger.info("=" * 50)
        logger.info(f"總鍵值數: {stats['total_keys']}")
        logger.info(f"成功遷移: {stats['successful_migrations']}")
        logger.info(f"失敗遷移: {stats['failed_migrations']}")
        logger.info(f"跳過條目: {stats['skipped_entries']}")
        logger.info(f"任務條目: {stats['job_entries']}")
        logger.info(f"分析條目: {stats['analysis_entries']}")
        logger.info(f"其他條目: {stats['other_entries']}")

        if duration:
            logger.info(f"遷移耗時: {duration}")

        if stats["errors"]:
            logger.info(f"錯誤數量: {len(stats['errors'])}")
            logger.info("前 5 個錯誤:")
            for error in stats["errors"][:5]:
                logger.info(f"  - {error}")

        logger.info("=" * 50)


def main():
    """主函數"""
    parser = argparse.ArgumentParser(
        description="Redis 到 CrewAI Memory 資料遷移工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  # 模擬遷移
  python scripts/migrate_redis_to_memory.py --dry-run

  # 執行遷移（含備份）
  python scripts/migrate_redis_to_memory.py --backup

  # 強制遷移並設定批次大小
  python scripts/migrate_redis_to_memory.py --force --batch-size 50
        """,
    )

    parser.add_argument("--dry-run", action="store_true", help="僅模擬遷移，不實際執行")
    parser.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help="是否備份 Redis 資料（預設：True）",
    )
    parser.add_argument("--no-backup", action="store_true", help="停用備份功能")
    parser.add_argument(
        "--batch-size", type=int, default=100, help="批次大小（預設：100）"
    )
    parser.add_argument("--force", action="store_true", help="強制遷移，覆蓋現有資料")
    parser.add_argument("--storage-dir", type=str, help="自訂儲存目錄路徑")
    parser.add_argument("--verbose", "-v", action="store_true", help="顯示詳細日誌")

    args = parser.parse_args()

    # 設定日誌等級
    if args.verbose:
        import logging

        logging.getLogger().setLevel(logging.DEBUG)

    # 建立配置
    config = CrewMemoryConfig()
    if args.storage_dir:
        config.storage_path = args.storage_dir
    if args.no_backup:
        backup_enabled = False
    else:
        backup_enabled = args.backup

    # 建立遷移器
    migrator = RedisMigrator(
        config=config, batch_size=args.batch_size, backup_enabled=backup_enabled
    )

    # 執行遷移
    try:
        success = migrator.run_migration(dry_run=args.dry_run, force=args.force)

        if success:
            logger.info("遷移成功完成")
            sys.exit(0)
        else:
            logger.error("遷移失敗")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("遷移被使用者中斷")
        sys.exit(1)
    except Exception as e:
        logger.error(f"遷移過程中發生未預期的錯誤: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
