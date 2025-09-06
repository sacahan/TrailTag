#!/usr/bin/env python3
"""
字幕檢測系統測試腳本

用於驗證 A3 任務完成後的字幕檢測準確率
需要達到 > 90% 的檢查點 G1 要求
"""

import sys
import os
import json
from datetime import datetime

# 添加項目根目錄到 Python 路徑
sys.path.append(os.path.abspath("."))

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.trailtag.tools.youtube_metadata_tool import YoutubeMetadataTool


class SubtitleDetectionTester:
    """字幕檢測測試器"""

    def __init__(self):
        self.tool = YoutubeMetadataTool()
        self.test_videos = [
            # 有手動字幕的影片
            {
                "video_id": "jNQXAC9IVRw",  # "Me at the zoo" - YouTube 第一個影片
                "expected": True,
                "description": "YouTube 第一個影片 (應該有字幕)",
            },
            # YouTube 官方影片，通常有多語言字幕
            {
                "video_id": "9bZkp7q19f0",  # "Gangnam Style" - 知名影片
                "expected": True,
                "description": "知名音樂影片 (應該有多語言字幕)",
            },
            # 音樂影片，可能有自動字幕
            {
                "video_id": "kJQP7kiw5Fk",  # "Despacito" - 非常受歡迎的音樂影片
                "expected": True,
                "description": "受歡迎音樂影片 (應該有自動字幕)",
            },
            # 新聞影片，通常有字幕
            {
                "video_id": "dQw4w9WgXcQ",  # Rick Roll - 經典影片
                "expected": True,
                "description": "經典影片 (應該有字幕)",
            },
            # 較小的頻道影片，可能沒有字幕
            {
                "video_id": "invalid_video",  # 無效的影片 ID
                "expected": False,
                "description": "無效影片 ID (應該檢測為無字幕)",
            },
        ]

    def test_single_video(self, video_info):
        """測試單個影片的字幕檢測"""
        video_id = video_info["video_id"]
        expected = video_info["expected"]
        description = video_info["description"]

        try:
            print(f"測試影片: {video_id} - {description}")

            # 使用工具檢測字幕
            metadata = self.tool._run(video_id)

            if metadata is None:
                # 工具返回 None，表示檢測失敗
                actual_available = False
                confidence_score = 0.0
            elif (
                hasattr(metadata, "subtitle_availability")
                and metadata.subtitle_availability
            ):
                actual_available = metadata.subtitle_availability.available
                confidence_score = metadata.subtitle_availability.confidence_score

                # 詳細信息
                print(f"  手動字幕: {metadata.subtitle_availability.manual_subtitles}")
                print(f"  自動字幕: {metadata.subtitle_availability.auto_captions}")
                print(f"  選擇語言: {metadata.subtitle_availability.selected_lang}")
                print(f"  信心分數: {confidence_score}")
            else:
                # 舊版格式，檢查是否有字幕內容
                actual_available = bool(
                    metadata.subtitles if hasattr(metadata, "subtitles") else False
                )
                confidence_score = 0.5 if actual_available else 0.0

            # 比較結果
            is_correct = actual_available == expected
            print(f"  預期: {'有字幕' if expected else '無字幕'}")
            print(f"  實際: {'有字幕' if actual_available else '無字幕'}")
            print(f"  結果: {'✅ 正確' if is_correct else '❌ 錯誤'}")
            print(f"  信心分數: {confidence_score:.2f}")

            return {
                "video_id": video_id,
                "description": description,
                "expected": expected,
                "actual": actual_available,
                "correct": is_correct,
                "confidence": confidence_score,
            }

        except Exception as e:
            print(f"  ❌ 測試失敗: {str(e)}")
            return {
                "video_id": video_id,
                "description": description,
                "expected": expected,
                "actual": False,
                "correct": False,
                "confidence": 0.0,
                "error": str(e),
            }

    def run_all_tests(self):
        """運行所有測試"""
        print("=" * 60)
        print("字幕檢測系統測試")
        print("=" * 60)

        results = []

        for video_info in self.test_videos:
            result = self.test_single_video(video_info)
            results.append(result)
            print("-" * 40)

        return self.analyze_results(results)

    def analyze_results(self, results):
        """分析測試結果"""
        total_tests = len(results)
        correct_predictions = sum(1 for r in results if r["correct"])
        accuracy = (correct_predictions / total_tests) * 100

        # 計算平均信心分數 (只包括正確預測的)
        correct_results = [r for r in results if r["correct"]]
        avg_confidence = (
            sum(r["confidence"] for r in correct_results) / len(correct_results)
            if correct_results
            else 0
        )

        print("=" * 60)
        print("測試結果摘要")
        print("=" * 60)
        print(f"總測試數: {total_tests}")
        print(f"正確預測: {correct_predictions}")
        print(f"準確率: {accuracy:.1f}%")
        print(f"平均信心分數: {avg_confidence:.2f}")
        print()

        # 檢查是否達到 G1 要求 (> 90%)
        g1_passed = accuracy > 90.0
        print(f"檢查點 G1 (準確率 > 90%): {'✅ 通過' if g1_passed else '❌ 未通過'}")

        # 詳細結果
        print("\n詳細結果:")
        for result in results:
            status = "✅" if result["correct"] else "❌"
            print(f"  {status} {result['video_id']}: {result['description']}")
            if "error" in result:
                print(f"      錯誤: {result['error']}")

        # 生成 JSON 報告
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": total_tests,
            "correct_predictions": correct_predictions,
            "accuracy": accuracy,
            "average_confidence": avg_confidence,
            "g1_checkpoint_passed": g1_passed,
            "detailed_results": results,
        }

        with open("subtitle_detection_test_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print("\n詳細報告已儲存至: subtitle_detection_test_report.json")

        return g1_passed


def main():
    """主要執行函數"""
    tester = SubtitleDetectionTester()
    g1_passed = tester.run_all_tests()

    # 返回適當的 exit code
    sys.exit(0 if g1_passed else 1)


if __name__ == "__main__":
    main()
