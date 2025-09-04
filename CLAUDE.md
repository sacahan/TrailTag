# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TrailTag is a YouTube travel vlog analysis system that converts videos into interactive map data and route visualizations. It extracts meaningful places, timestamps, and routes from travel videos using crewAI agents, FastAPI backend, and a browser extension.

## Core Architecture

- **src/trailtag/** - crewAI crew implementation with agents and tools for video analysis
- **src/api/** - FastAPI backend with async task management, caching, and SSE support
- **src/extension/** - Chrome browser extension (TypeScript) for YouTube integration
- **tests/** - Unit tests

The system follows an agent-based architecture where specialized crewAI agents handle different aspects of video analysis (metadata extraction, place detection, geocoding, route generation).

## Development Commands

### Backend Development

```bash
# Start development server
uvicorn src.api.main:app --host 0.0.0.0 --port 8010 --reload

# Run CLI crew for single video processing
python -m src.trailtag.main VIDEO_ID
# or
uv run python -m src.trailtag.main VIDEO_ID
```

### Testing

#### Unit Tests

```bash
# Python tests
pytest
# or with uv
uv run pytest

# Extension tests
cd src/extension && npm test
```

#### Integration Tests

```bash
# Memory Migration Validation Tests (C1.2)
uv run pytest tests/integration/test_memory_migration.py -v

# Specific memory test categories
uv run pytest tests/integration/test_memory_migration.py::TestDataMigrationValidation -v
uv run pytest tests/integration/test_memory_migration.py::TestPerformanceComparison -v
uv run pytest tests/integration/test_memory_migration.py::TestMemorySystemFunctionality -v
```

#### End-to-End (E2E) Tests

```bash
# Run comprehensive E2E test suite
uv run python run_e2e_tests.py

# Quick smoke tests
uv run python run_e2e_tests.py --quick

# Test specific components
uv run python run_e2e_tests.py --api-only         # API endpoints
uv run python run_e2e_tests.py --memory-only      # Memory system integration
uv run python run_e2e_tests.py --workflow-only    # Complete workflows
uv run python run_e2e_tests.py --performance      # Performance benchmarks
uv run python run_e2e_tests.py --error-handling   # Error scenarios

# Generate reports
uv run python run_e2e_tests.py --coverage --html-report

# Direct pytest usage for specific tests
uv run pytest tests/integration/test_e2e.py::TestAPIEndpoints -v
```

The test suites validate:

- **E2E Tests**: Complete video analysis workflow (YouTube URL → GeoJSON output)
- **Memory System Tests**: CrewAI Memory system functionality and performance validation
- **Integration Tests**: Memory system functionality, data consistency, and concurrent operations
- **Performance Tests**: Benchmarking and optimization validation
- **Error Handling Tests**: Edge case scenarios and failure recovery

### Extension Development

```bash
cd src/extension
npm install
npm test
npm run build    # Build TypeScript and copy assets
npm run package  # Create dist/extension.zip
```

### Memory System Management

```bash
# Clean up any legacy Redis data files (if needed)
uv run python scripts/cleanup_redis_data.py

# The system now uses CrewAI Memory exclusively - no migration needed
# Legacy migration script is deprecated and preserved for historical reference only
```

### Docker Deployment

```bash
# Start backend service
docker-compose up -d

# Backend runs on port 8010
# Uses CrewAI Memory system exclusively - no external cache dependencies
```

## Key Environment Variables

Required for API functionality:

- `OPENAI_API_KEY` - OpenAI API access for crewAI agents
- `GOOGLE_API_KEY` - Google geocoding API
- `API_HOST` (default: 0.0.0.0)
- `API_PORT` (default: 8010)

CrewAI Memory system is used exclusively for caching - no external cache configuration needed.

## Project Structure Specifics

### crewAI Implementation

- **src/trailtag/crew.py** - Main crew definition with agents and tasks
- **src/trailtag/main.py** - CLI entry point with caching logic
- **src/trailtag/tools/** - Custom tools for YouTube metadata, geocoding, place extraction
- **src/trailtag/models.py** - Pydantic models for crew outputs
- **src/trailtag/memory/manager.py** - CrewAI Memory system manager
- **src/trailtag/memory/models.py** - Memory system data models and types
- **src/trailtag/observers.py** - CrewAI event listeners for monitoring
- **src/trailtag/progress_tracker.py** - Task progress tracking system

### API Layer

- **src/api/main.py** - FastAPI app with CORS for extension support
- **src/api/routes.py** - Video analysis endpoints with async task management
- **src/api/sse.py** - Server-sent events for real-time progress updates
- **src/api/cache/cache_manager.py** - CrewAI Memory-based caching system
- **src/api/metrics.py** - Performance monitoring and observability
- **src/api/observability.py** - Langtrace integration for tracing
- **src/api/crew_executor.py** - Async crew execution management
- **src/api/execution_state.py** - Job state persistence and recovery
- **src/api/webhooks.py** - Callback system for external integrations

### Data Flow

1. Input: YouTube video ID → crewAI agents extract metadata/subtitles
2. Processing: Place extraction → geocoding → route generation (with smart subtitle chunking)
3. Output: GeoJSON FeatureCollection with routes (LineString) and POIs (Points)
4. Memory: Results stored in CrewAI Memory system with vector search capabilities
5. Monitoring: Full observability with Langtrace and performance metrics

### Advanced Features

- **Subtitle Detection**: Automatic detection and warning for videos without subtitles
- **Token Management**: Smart chunking for long videos to handle token limits
- **Memory System**: Pure CrewAI Memory system with enhanced semantic capabilities
- **Multi-source Data**: Chapter extraction, comment mining, and description analysis
- **Performance Monitoring**: Langtrace integration with execution metrics
- **State Management**: Persistent task state with recovery mechanisms

## Common Issues

- **Missing dependencies**: Use `uv add` to install Python packages
- **Extension CORS**: Extension uses `chrome-extension://` origins - CORS configured in main.py
- **Memory system**: Pure CrewAI Memory system with no external dependencies
- **Video processing timeouts**: Long videos may require chunking (handled by crew logic)

## API Endpoints

### Core Analysis

- POST `/api/analyze` - Submit video analysis job (returns task_id)
- GET `/api/status/{task_id}` - Check job status and progress
- GET `/api/results/{task_id}` - Download GeoJSON results
- GET `/api/map/{task_id}.geojson` - Direct GeoJSON file access

### System Health & Monitoring

- GET `/health` - Service health check with cache status
- GET `/metrics` - Performance metrics and system stats
- GET `/api/memory/stats` - CrewAI Memory system statistics

### Administrative

- POST `/api/webhooks` - Webhook endpoint for external notifications
- GET `/api/execution/{task_id}` - Detailed task execution information

## CrewAI

- 有關crewai相關的程式碼，應該優先使用context7檢索crewai相關內容
