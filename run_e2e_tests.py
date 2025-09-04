#!/usr/bin/env python3
"""
TrailTag E2E Test Runner

This script runs the comprehensive End-to-End test suite for TrailTag.
It provides options for running different test groups and generating performance reports.

Usage:
    python run_e2e_tests.py [options]

Examples:
    python run_e2e_tests.py                    # Run all tests
    python run_e2e_tests.py --api-only         # Run only API tests
    python run_e2e_tests.py --memory-only      # Run only memory system tests
    python run_e2e_tests.py --performance      # Run performance benchmarks
    python run_e2e_tests.py --quick            # Run quick smoke tests
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path


def run_pytest(test_path: str, extra_args: list = None) -> int:
    """Run pytest with the specified path and arguments"""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
    ]

    # Add test paths (can be multiple)
    if isinstance(test_path, str):
        if " " in test_path:
            # Multiple test paths separated by space
            cmd.extend(test_path.split())
        else:
            cmd.append(test_path)
    else:
        cmd.extend(test_path)

    if extra_args:
        cmd.extend(extra_args)

    print(f"Running: {' '.join(cmd)}")
    print("=" * 80)

    return subprocess.run(cmd).returncode


def main():
    parser = argparse.ArgumentParser(description="TrailTag E2E Test Runner")

    # Test selection options
    parser.add_argument(
        "--api-only", action="store_true", help="Run only API endpoint tests"
    )
    parser.add_argument(
        "--memory-only",
        action="store_true",
        help="Run only memory system integration tests",
    )
    parser.add_argument(
        "--workflow-only", action="store_true", help="Run only complete workflow tests"
    )
    parser.add_argument(
        "--performance", action="store_true", help="Run performance benchmarking tests"
    )
    parser.add_argument(
        "--error-handling",
        action="store_true",
        help="Run error handling and edge case tests",
    )
    parser.add_argument(
        "--async-tasks", action="store_true", help="Run async task management tests"
    )

    # Run modes
    parser.add_argument(
        "--quick", action="store_true", help="Run quick smoke tests only"
    )
    parser.add_argument(
        "--full", action="store_true", help="Run all tests including long-running ones"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel using pytest-xdist",
    )

    # Output options
    parser.add_argument(
        "--report", action="store_true", help="Generate detailed performance report"
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Generate coverage report"
    )
    parser.add_argument(
        "--html-report", action="store_true", help="Generate HTML test report"
    )

    args = parser.parse_args()

    # Determine test path based on arguments
    base_path = "tests/integration/test_e2e.py"
    test_path = base_path

    if args.api_only:
        test_path = f"{base_path}::TestAPIEndpoints"
    elif args.memory_only:
        test_path = f"{base_path}::TestMemorySystemIntegration"
    elif args.workflow_only:
        test_path = f"{base_path}::TestCompleteWorkflow"
    elif args.performance:
        test_path = f"{base_path}::TestPerformanceBenchmarking"
    elif args.error_handling:
        test_path = f"{base_path}::TestErrorHandlingAndEdgeCases"
    elif args.async_tasks:
        test_path = f"{base_path}::TestAsyncTaskManagement"
    elif args.quick:
        # Quick smoke tests
        test_path = f"{base_path}::TestAPIEndpoints::test_health_endpoint {base_path}::TestMemorySystemIntegration::test_memory_system_initialization"

    # Build extra arguments
    extra_args = []

    if args.parallel:
        extra_args.extend(["-n", "auto"])

    if args.coverage:
        extra_args.extend(["--cov=src", "--cov-report=term-missing"])

    if args.html_report:
        extra_args.extend(["--html=reports/test_report.html", "--self-contained-html"])

    if not args.full:
        # Skip long-running tests by default
        extra_args.extend(["-m", "not slow"])

    # Ensure reports directory exists
    if args.html_report:
        Path("reports").mkdir(exist_ok=True)

    # Set environment variables for testing
    os.environ["TESTING"] = "1"
    os.environ["PYTHONPATH"] = str(Path.cwd())

    print("TrailTag E2E Test Suite")
    print("=" * 80)
    print(f"Test Selection: {test_path}")
    print(f"Extra Arguments: {extra_args}")
    print()

    # Run the tests
    exit_code = run_pytest(test_path, extra_args)

    if exit_code == 0:
        print("\n" + "=" * 80)
        print("🎉 ALL TESTS PASSED! 🎉")
        print("=" * 80)

        if args.report:
            print("\nGenerating performance report...")
            # The test suite itself generates performance reports
            print("Performance metrics are displayed in test output above.")
    else:
        print("\n" + "=" * 80)
        print("❌ SOME TESTS FAILED")
        print("=" * 80)
        print("Check the test output above for details.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
