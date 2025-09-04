#!/usr/bin/env python3
"""
Memory System Validation Test Runner

This script runs comprehensive validation tests for the CrewAI Memory system migration,
providing detailed reports on performance, functionality, and data integrity.

Usage:
    python scripts/run_memory_validation_tests.py [options]

Options:
    --test-class CLASS_NAME  Run specific test class
    --performance-only       Run only performance comparison tests
    --integration-only       Run only integration tests
    --report-file FILE       Save detailed report to file
    --verbose               Enable verbose output
    --parallel              Run tests in parallel (where possible)
"""

import sys
import argparse
import subprocess
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# Add project root to Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))


class MemoryValidationTestRunner:
    """Test runner for memory system validation"""

    def __init__(self, verbose: bool = False, report_file: Optional[str] = None):
        self.verbose = verbose
        self.report_file = report_file
        self.test_results = {}
        self.performance_metrics = {}
        self.start_time = datetime.now(timezone.utc)

        # Available test classes
        self.test_classes = {
            "data_migration": "TestDataMigrationValidation",
            "performance": "TestPerformanceComparison",
            "functionality": "TestMemorySystemFunctionality",
            "concurrent": "TestConcurrentAccess",
            "consistency": "TestDataConsistency",
            "failover": "TestFailoverScenarios",
            "integration": "TestIntegrationWithCrews",
            "resource_mgmt": "TestResourceManagement",
        }

        # Test file path
        self.test_file = (
            project_root / "tests" / "integration" / "test_memory_migration.py"
        )

    def run_test_class(
        self, class_name: str, capture_output: bool = True
    ) -> Dict[str, Any]:
        """Run a specific test class and capture results"""
        if self.verbose:
            print(f"Running test class: {class_name}")

        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "pytest",
            f"{self.test_file}::{class_name}",
            "-v",
            "--tb=short",
            "--durations=10",
        ]

        if not capture_output:
            cmd.append("-s")  # Don't capture output for real-time viewing

        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                cwd=project_root,
                capture_output=capture_output,
                text=True,
                timeout=300,  # 5 minute timeout per test class
            )

            duration = time.time() - start_time

            # Parse output for basic test information
            report_data = {}
            if result.stdout:
                # Extract basic info from pytest output
                lines = result.stdout.split("\n")
                for line in lines:
                    if "passed" in line and "failed" in line:
                        # Try to extract test counts from summary line
                        import re

                        match = re.search(r"(\d+) passed.*?(\d+) failed", line)
                        if match:
                            report_data["summary"] = {
                                "passed": int(match.group(1)),
                                "failed": int(match.group(2)),
                                "total": int(match.group(1)) + int(match.group(2)),
                            }

            return {
                "class_name": class_name,
                "return_code": result.returncode,
                "duration": duration,
                "stdout": result.stdout if capture_output else "",
                "stderr": result.stderr if capture_output else "",
                "passed": result.returncode == 0,
                "report_data": report_data,
            }

        except subprocess.TimeoutExpired:
            return {
                "class_name": class_name,
                "return_code": -1,
                "duration": time.time() - start_time,
                "stdout": "",
                "stderr": "Test timed out after 5 minutes",
                "passed": False,
                "report_data": {},
            }
        except Exception as e:
            return {
                "class_name": class_name,
                "return_code": -2,
                "duration": time.time() - start_time,
                "stdout": "",
                "stderr": f"Exception running test: {str(e)}",
                "passed": False,
                "report_data": {},
            }

    def run_all_tests(
        self, test_filter: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Run all or filtered test classes"""
        results = {}

        # Filter test classes if specified
        classes_to_run = self.test_classes
        if test_filter:
            if test_filter == "performance":
                classes_to_run = {
                    k: v
                    for k, v in self.test_classes.items()
                    if "performance" in k or "concurrent" in k
                }
            elif test_filter == "integration":
                classes_to_run = {
                    k: v
                    for k, v in self.test_classes.items()
                    if "integration" in k or "functionality" in k
                }
            elif test_filter in self.test_classes:
                classes_to_run = {test_filter: self.test_classes[test_filter]}

        print(f"Running {len(classes_to_run)} test classes...")
        print("=" * 60)

        for test_key, class_name in classes_to_run.items():
            print(f"\n🔍 Running {test_key} ({class_name})...")

            result = self.run_test_class(class_name, capture_output=not self.verbose)
            results[test_key] = result

            # Print immediate results
            status = "✅ PASSED" if result["passed"] else "❌ FAILED"
            print(f"   {status} in {result['duration']:.1f}s")

            if not result["passed"] and self.verbose:
                print(f"   Error: {result['stderr'][:200]}...")

        return results

    def extract_performance_metrics(
        self, results: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract performance metrics from test results"""
        metrics = {}

        for test_key, result in results.items():
            if not result["passed"]:
                continue

            # Extract performance data from stdout if available
            stdout = result.get("stdout", "")

            # Look for specific performance patterns in output
            if "performance" in test_key.lower():
                # Extract timing information
                import re

                # Look for timing patterns like "avg: 12.34ms", "throughput: 123.45 ops/sec"
                timing_patterns = [
                    r"avg[^:]*:\s*([0-9.]+)\s*ms",
                    r"throughput[^:]*:\s*([0-9.]+)\s*ops/sec",
                    r"memory[^:]*:\s*([0-9.]+)\s*MB",
                ]

                for pattern in timing_patterns:
                    matches = re.findall(pattern, stdout, re.IGNORECASE)
                    if matches:
                        metrics[f"{test_key}_timing"] = [float(m) for m in matches]

            # Store test duration as a metric
            metrics[f"{test_key}_duration"] = result["duration"]

        return metrics

    def generate_report(self, results: Dict[str, Dict[str, Any]]) -> str:
        """Generate comprehensive validation report"""
        report_lines = []

        # Header
        report_lines.extend(
            [
                "=" * 80,
                "CREWAI MEMORY SYSTEM VALIDATION REPORT",
                "=" * 80,
                f"Generated: {datetime.now(timezone.utc).isoformat()}",
                f"Total Duration: {(datetime.now(timezone.utc) - self.start_time).total_seconds():.1f}s",
                "",
            ]
        )

        # Summary
        total_tests = len(results)
        passed_tests = sum(1 for r in results.values() if r["passed"])
        failed_tests = total_tests - passed_tests

        report_lines.extend(
            [
                "SUMMARY",
                "-" * 40,
                f"Total Test Classes: {total_tests}",
                f"Passed: {passed_tests}",
                f"Failed: {failed_tests}",
                f"Success Rate: {(passed_tests/total_tests)*100:.1f}%",
                "",
            ]
        )

        # Detailed results
        report_lines.extend(["DETAILED RESULTS", "-" * 40])

        for test_key, result in results.items():
            class_name = result["class_name"]
            status = "PASSED" if result["passed"] else "FAILED"
            duration = result["duration"]

            report_lines.extend(
                [
                    f"{test_key.upper()} ({class_name})",
                    f"  Status: {status}",
                    f"  Duration: {duration:.2f}s",
                ]
            )

            if not result["passed"]:
                error_msg = result.get("stderr", "Unknown error")[:300]
                report_lines.append(f"  Error: {error_msg}")

            # Add performance metrics if available
            if "report_data" in result and result["report_data"]:
                report_data = result["report_data"]
                if "summary" in report_data:
                    summary = report_data["summary"]
                    report_lines.extend(
                        [
                            f"  Tests Run: {summary.get('total', 'N/A')}",
                            f"  Tests Passed: {summary.get('passed', 'N/A')}",
                            f"  Tests Failed: {summary.get('failed', 'N/A')}",
                        ]
                    )

            report_lines.append("")

        # Performance metrics
        metrics = self.extract_performance_metrics(results)
        if metrics:
            report_lines.extend(["PERFORMANCE METRICS", "-" * 40])

            for metric_name, value in metrics.items():
                if isinstance(value, list):
                    avg_value = sum(value) / len(value)
                    report_lines.append(
                        f"{metric_name}: {avg_value:.2f} (avg of {len(value)} measurements)"
                    )
                else:
                    report_lines.append(f"{metric_name}: {value:.2f}")

            report_lines.append("")

        # Recommendations
        report_lines.extend(["RECOMMENDATIONS", "-" * 40])

        if failed_tests == 0:
            report_lines.append(
                "✅ All memory system validation tests passed successfully!"
            )
            report_lines.append(
                "✅ The CrewAI Memory system is ready for production use."
            )
        else:
            report_lines.append(
                f"⚠️  {failed_tests} test class(es) failed - review issues before deployment."
            )

        if "performance" in results and results["performance"]["passed"]:
            report_lines.append(
                "✅ Performance comparison tests passed - memory system meets benchmarks."
            )

        if "data_migration" in results and results["data_migration"]["passed"]:
            report_lines.append(
                "✅ Data migration validation passed - migration script is reliable."
            )

        if "concurrent" in results and results["concurrent"]["passed"]:
            report_lines.append(
                "✅ Concurrent access tests passed - system handles multi-threading well."
            )

        report_lines.extend(["", "END OF REPORT", "=" * 80])

        return "\n".join(report_lines)

    def save_report(self, report: str) -> None:
        """Save report to file"""
        if self.report_file:
            with open(self.report_file, "w", encoding="utf-8") as f:
                f.write(report)
            print(f"Report saved to: {self.report_file}")

    def run_validation(self, test_filter: Optional[str] = None) -> bool:
        """Run complete validation and return success status"""
        print("🚀 Starting CrewAI Memory System Validation...")
        print(f"Test file: {self.test_file}")

        # Verify test file exists
        if not self.test_file.exists():
            print(f"❌ Test file not found: {self.test_file}")
            return False

        # Run tests
        results = self.run_all_tests(test_filter)

        # Generate and display report
        report = self.generate_report(results)
        print("\n" + report)

        # Save report if requested
        if self.report_file:
            self.save_report(report)

        # Return overall success
        return all(r["passed"] for r in results.values())


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Run CrewAI Memory System Validation Tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Test Classes Available:
  data_migration    - Test Redis to CrewAI Memory migration
  performance      - Performance comparison tests
  functionality    - Core memory system functionality
  concurrent       - Concurrent access testing
  consistency      - Data consistency validation
  failover         - Error handling and recovery
  integration      - CrewAI integration testing
  resource_mgmt    - Resource management and cleanup

Examples:
  # Run all tests
  python scripts/run_memory_validation_tests.py

  # Run only performance tests
  python scripts/run_memory_validation_tests.py --performance-only

  # Run specific test class
  python scripts/run_memory_validation_tests.py --test-class data_migration

  # Generate detailed report
  python scripts/run_memory_validation_tests.py --report-file memory_validation_report.txt --verbose
        """,
    )

    parser.add_argument(
        "--test-class",
        choices=[
            "data_migration",
            "performance",
            "functionality",
            "concurrent",
            "consistency",
            "failover",
            "integration",
            "resource_mgmt",
        ],
        help="Run specific test class",
    )

    parser.add_argument(
        "--performance-only",
        action="store_true",
        help="Run only performance-related tests",
    )

    parser.add_argument(
        "--integration-only", action="store_true", help="Run only integration tests"
    )

    parser.add_argument("--report-file", type=str, help="Save detailed report to file")

    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel (not implemented yet)",
    )

    args = parser.parse_args()

    # Determine test filter
    test_filter = None
    if args.test_class:
        test_filter = args.test_class
    elif args.performance_only:
        test_filter = "performance"
    elif args.integration_only:
        test_filter = "integration"

    # Create and run test runner
    runner = MemoryValidationTestRunner(
        verbose=args.verbose, report_file=args.report_file
    )

    try:
        success = runner.run_validation(test_filter)

        print(
            f"\n{'🎉' if success else '❌'} Validation {'completed successfully' if success else 'completed with failures'}"
        )

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n❌ Validation interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Validation failed with error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
