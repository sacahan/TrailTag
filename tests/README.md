# TrailTag End-to-End Test Suite

This document describes the comprehensive End-to-End (E2E) test suite for TrailTag, implementing **Task C1.1** from the development roadmap.

## Overview

The E2E test suite validates all improvements made in Phases 1 and 2 of the TrailTag project, ensuring that the complete system works correctly from video input to map output.

## Test Coverage

### 🔵 Core Functionality Tests

- **Complete Video Analysis Workflow**: YouTube URL → crew execution → GeoJSON output
- **API Endpoint Testing**: All routes (`/api/analyze`, `/api/status`, `/api/results`, etc.)
- **Caching Behavior**: Cache hits, misses, and fallback scenarios
- **Subtitle Detection**: Various subtitle availability scenarios

### 🟡 System Integration Tests

- **Memory System Integration**: CrewAI Memory system replacing Redis
- **Async Task Management**: Concurrent job execution and state persistence
- **Error Handling**: Invalid inputs, service failures, and edge cases
- **Performance Benchmarking**: Analysis time reduction validation

### 🟢 Advanced Features

- **Multi-source Data Extraction**: Subtitle, description, comment mining integration
- **Token Limit Handling**: Smart chunking and processing validation
- **Webhook Callbacks**: State persistence and recovery mechanisms
- **Observability**: Monitoring and metrics collection

## Test Structure

### Test Classes

```
tests/integration/test_e2e.py
├── TestCompleteWorkflow          # End-to-end video analysis tests
├── TestAPIEndpoints             # API endpoint validation
├── TestMemorySystemIntegration  # CrewAI Memory system tests
├── TestAsyncTaskManagement      # Async task execution tests
├── TestErrorHandlingAndEdgeCases # Error scenarios and edge cases
└── TestPerformanceBenchmarking  # Performance validation tests
```

### Test Fixtures and Utilities

- **TestFixtures**: Mock data, test video IDs, performance benchmarks
- **E2ETestBase**: Common setup, cleanup, and utility methods
- **Mock Services**: YouTube API, external service mocking
- **Performance Tracking**: Metrics collection and reporting

## Running Tests

### Quick Start

```bash
# Run all E2E tests
uv run python run_e2e_tests.py

# Quick smoke tests
uv run python run_e2e_tests.py --quick

# API tests only
uv run python run_e2e_tests.py --api-only
```

### Test Categories

```bash
# Memory system integration
uv run python run_e2e_tests.py --memory-only

# Complete workflow validation
uv run python run_e2e_tests.py --workflow-only

# Performance benchmarking
uv run python run_e2e_tests.py --performance

# Error handling scenarios
uv run python run_e2e_tests.py --error-handling

# Async task management
uv run python run_e2e_tests.py --async-tasks
```

### Advanced Options

```bash
# Generate performance report
uv run python run_e2e_tests.py --report

# Run with coverage
uv run python run_e2e_tests.py --coverage

# Generate HTML report
uv run python run_e2e_tests.py --html-report

# Run all tests including slow ones
uv run python run_e2e_tests.py --full
```

### Direct pytest Usage

```bash
# Run specific test class
uv run pytest tests/integration/test_e2e.py::TestAPIEndpoints -v

# Run with specific markers
uv run pytest tests/integration/test_e2e.py -m "not slow" -v

# Run single test
uv run pytest tests/integration/test_e2e.py::TestMemorySystemIntegration::test_memory_system_initialization -v
```

## Performance Benchmarks

The test suite validates the following performance improvements:

| Metric                  | Target                   | Validation                  |
| ----------------------- | ------------------------ | --------------------------- |
| Analysis Time           | < 180 seconds            | Complete workflow timing    |
| API Response            | < 2000ms                 | Endpoint response times     |
| Memory Operations       | < 100ms save, < 50ms get | Memory system performance   |
| Cache Hit Ratio         | > 80%                    | Cache efficiency validation |
| Concurrent Success Rate | > 90%                    | Load handling capability    |

## Test Data and Mocking

### Mock Video Data

- Valid YouTube URLs with different formats
- Test video with subtitles, chapters, descriptions
- Invalid video IDs and edge cases
- Videos without subtitles for error testing

### Mock Analysis Results

- GeoJSON format with coordinates, timestamps
- Route items with locations, descriptions, tags
- Performance timing data
- Error scenarios and failure cases

### External Service Mocking

- YouTube Metadata Tool responses
- Google Geocoding API responses
- CrewAI execution simulation
- Network failure scenarios

## Key Test Scenarios

### 1. Complete Workflow Validation

- ✅ Submit video analysis request
- ✅ Monitor job progress through phases
- ✅ Validate GeoJSON output structure
- ✅ Verify coordinate accuracy and completeness
- ✅ Check performance within benchmarks

### 2. Memory System Validation

- ✅ CrewAI Memory initialization and configuration
- ✅ Job progress storage and retrieval
- ✅ Analysis result caching and persistence
- ✅ Agent memory management
- ✅ Performance comparison with Redis (if available)

### 3. Error Handling Validation

- ✅ Invalid YouTube URLs
- ✅ Videos without subtitles
- ✅ CrewAI execution failures
- ✅ External service timeouts
- ✅ Memory system failures with graceful degradation

### 4. Performance Validation

- ✅ End-to-end analysis timing
- ✅ API response time benchmarks
- ✅ Memory system operation speed
- ✅ Concurrent load handling
- ✅ Resource usage monitoring

## Environment Setup

### Required Environment Variables

```bash
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key
REDIS_HOST=localhost      # Optional, for Redis comparison
REDIS_PORT=6379          # Optional
API_HOST=127.0.0.1
API_PORT=8010
```

### Test Environment

```bash
TESTING=1                 # Set automatically during test runs
OTEL_SDK_DISABLED=true    # Disable telemetry during testing
CREWAI_DISABLE_TELEMETRY=true
```

## Troubleshooting

### Common Issues

**Import Errors**

- Ensure all dependencies installed: `uv add pytest pytest-asyncio pytest-mock httpx`
- Check Python path configuration

**Redis Connection Warnings**

- Expected in test environment without Redis
- Tests fall back to in-memory caching automatically

**External Service Calls**

- Tests use mocking by default to avoid real API calls
- Set `TESTING=1` to ensure mock usage

**Performance Test Failures**

- Adjust benchmarks in `TestFixtures.get_performance_benchmarks()` if needed
- Consider system resources and load during testing

### Debug Mode

```bash
# Run with detailed debugging
uv run pytest tests/integration/test_e2e.py -v -s --tb=long

# Run specific failing test
uv run pytest tests/integration/test_e2e.py::TestClass::test_method -v -s
```

## Contributing to Tests

### Adding New Tests

1. Follow the existing test structure and naming conventions
2. Use the `E2ETestBase` class for common setup/teardown
3. Add appropriate mocking for external services
4. Include performance metrics where relevant
5. Update this documentation

### Test Guidelines

- **Isolation**: Each test should be independent
- **Deterministic**: Tests should produce consistent results
- **Fast**: Keep tests under reasonable time limits
- **Readable**: Use descriptive names and clear assertions
- **Maintainable**: Mock external dependencies appropriately

## Reports and Metrics

The test suite generates comprehensive reports including:

- **Performance Metrics**: Response times, processing duration, throughput
- **Coverage Reports**: Code coverage analysis (with --coverage flag)
- **HTML Reports**: Detailed test execution reports (with --html-report flag)
- **System Metrics**: Memory usage, CPU utilization during tests

Example performance report output:

```
TRAILTAG E2E PERFORMANCE REPORT
============================================================
api_submit_response_time         45.23 ms        ✓ PASS
total_processing_time            2.34 seconds    ✓ PASS
memory_save_per_op               12.45 ms        ✓ PASS
concurrent_success_rate          95.0 percent    ✓ PASS
============================================================
```

## Integration with CI/CD

The test suite is designed for integration with continuous integration systems:

```yaml
# GitHub Actions example
- name: Run E2E Tests
  run: |
    uv run python run_e2e_tests.py --full --coverage --html-report

- name: Upload Reports
  uses: actions/upload-artifact@v3
  with:
    name: test-reports
    path: reports/
```

This comprehensive E2E test suite ensures that all TrailTag improvements work correctly together, providing confidence in system reliability and performance.
