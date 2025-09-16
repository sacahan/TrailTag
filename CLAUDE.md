# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TrailTag is a YouTube travel vlog analysis system that converts videos into interactive map data and route visualizations. It extracts meaningful places, timestamps, and routes from travel videos using crewAI agents, FastAPI backend, and a browser extension.

## Core Architecture

- **src/trailtag/** - crewAI crew implementation with agents and tools for video analysis
- **src/api/** - FastAPI backend with async task management, caching, and SSE support
- **src/extension/** - Chrome browser extension (TypeScript) for YouTube integration
- **tests/** - Comprehensive test suites (unit, integration, e2e)

The system follows an agent-based architecture where specialized crewAI agents handle different aspects of video analysis (metadata extraction, place detection, geocoding, route generation).

### Key Architectural Patterns

- **Async Task Management**: Jobs submitted via API return task_id, with status polling and SSE updates
- **Multi-layered Processing**: YouTube → Metadata/Subtitles → Place Extraction → Geocoding → GeoJSON
- **Memory-first Caching**: CrewAI Memory system with vector search for intelligent result reuse
- **Extension Integration**: Chrome extension triggers analysis directly from YouTube UI

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

# Development build (compiles TypeScript and copies assets)
npm run build

# Production package (creates dist/extension.zip)
npm run package
# or
npm run zip

# Individual build steps
npm run clean           # Clean build directories
npm run inject:config   # Inject configuration
npm run ts:build        # Compile TypeScript only
npm run copy:static     # Copy static assets only
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

### Memory System (CrewAI)

- `CREW_MEMORY_STORAGE_PATH` - CrewAI Memory storage location (default: ./memory_storage)
- `CREW_MEMORY_EMBEDDER_PROVIDER` - embedding provider (default: openai)

### Observability & Monitoring

- `LANGTRACE_API_KEY` - Langtrace API key for performance tracing
- `ENABLE_PERFORMANCE_MONITORING` - enable/disable monitoring (default: true)

CrewAI Memory system is used exclusively for caching - no external cache configuration needed.

## Project Structure Specifics

### crewAI Implementation (src/trailtag/)

- **crew.py** - Main crew definition with agents and tasks
- **main.py** - CLI entry point with caching logic
- **models.py** - Pydantic models for crew outputs
- **observers.py** - CrewAI event listeners for monitoring
- **progress_tracker.py** - Task progress tracking system
- **memory/** - CrewAI Memory system components
  - **manager.py** - Memory system manager with vector search
  - **models.py** - Memory data models and types
- **tools/** - Categorized tool suite for different processing stages
  - **data_extraction/** - YouTube metadata, chapters, comments, descriptions
  - **processing/** - Subtitle processing, compression, token management
  - **geocoding/** - Geographic coordinate resolution

### API Layer (src/api/)

- **main.py** - FastAPI app with CORS for extension support
- **core/** - Core API components and models
- **routes/** - Video analysis endpoints with async task management
- **middleware/** - SSE, CORS, and request handling middleware
- **services/** - Business logic services
  - **crew_executor.py** - Async crew execution management
  - **execution_state.py** - Job state persistence and recovery
  - **webhooks.py** - Callback system for external integrations
- **cache/** - CrewAI Memory-based caching system
- **monitoring/** - Performance monitoring and observability (Langtrace integration)

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
- **Badge Notification System**: Real-time visual indicators on extension icon showing TrailTag availability

## Extension Badge Notification System

### Badge System Architecture

The TrailTag extension implements a sophisticated badge notification system that provides visual feedback about video analysis availability directly on the extension icon.

#### Key Components

- **background.js** - Service worker that manages badge states and coordinates with content scripts
- **content.js** - Content script that monitors YouTube page changes and subtitle detection
- **badge-manager.ts** - TypeScript utility class for badge state management
- **Enhanced popup controller** - Integrates badge status with popup UI

#### Badge States

| State         | Badge Text | Badge Color      | Tooltip                          | Trigger                   |
| ------------- | ---------- | ---------------- | -------------------------------- | ------------------------- |
| `AVAILABLE`   | ✓          | Green (#4CAF50)  | TrailTag 可用 - 可以分析此影片   | Subtitles detected        |
| `UNAVAILABLE` | !          | Orange (#FF9800) | TrailTag 不可用 - 此影片沒有字幕 | No subtitles found        |
| `CHECKING`    | ...        | Blue (#2196F3)   | TrailTag 檢查中...               | Detection in progress     |
| `NOT_YOUTUBE` | (empty)    | Default          | TrailTag - 旅遊影片地圖化        | Not on YouTube video page |

#### Implementation Details

**Background Script (background.js)**:

- Listens for tab updates and activations
- Checks if current page is a YouTube video
- Calls subtitle availability API
- Updates badge text, color, and tooltip
- Handles messages from content script

**Content Script (content.js)**:

- Monitors YouTube SPA navigation changes
- Detects video player elements and subtitle buttons
- Sends video change notifications to background script
- Performs DOM-based subtitle detection as fallback

**Badge Manager (badge-manager.ts)**:

- Provides TypeScript interface for badge communication
- Integrates with popup controller
- Maintains state synchronization between components
- Offers utility methods for badge status queries

#### API Integration

The badge system integrates with the existing subtitle detection API:

- Endpoint: `GET /api/videos/{video_id}/subtitles/check`
- Returns: `{ available: boolean, manual_subtitles: string[], auto_captions: string[], confidence_score: number }`
- Used by both background script and popup for consistent results

#### Performance Optimizations

- **Debounced Updates**: Prevents excessive API calls during rapid navigation
- **Caching**: Stores recent subtitle check results to avoid redundant requests
- **Lazy Loading**: Only checks subtitle availability when on YouTube video pages
- **Error Handling**: Graceful fallback to unknown state on API failures

#### Build Integration

The badge system files are automatically included in the extension build:

- `background.js` and `content.js` are copied to the dist directory
- Manifest v3 permissions include `activeTab` for badge functionality
- TypeScript compilation includes badge-manager utilities

## Extension Build System

The extension uses a multi-step build process:

1. **Configuration Injection**: `inject:config` - Injects runtime config into TypeScript
2. **TypeScript Compilation**: `ts:build` - Compiles `.ts` files to `dist_ts/`
3. **Static Asset Copy**: `copy:static` - Copies compiled JS, HTML, CSS, manifest to `../../dist/extension/`
4. **Bootstrap Integration**: `popup.bootstrap.mjs` loads compiled modules dynamically

**Important**: The bootstrap file references compiled JavaScript in `dist_ts/`, not source TypeScript files.

## Common Issues

- **Missing dependencies**: Use `uv add` to install Python packages
- **Extension CORS**: Extension uses `chrome-extension://` origins - CORS configured in main.py
- **Memory system**: Pure CrewAI Memory system with no external dependencies
- **Video processing timeouts**: Long videos may require chunking (handled by crew logic)
- **Extension import errors**: Check that `npm run build` completed and `dist_ts/` contains compiled JS files

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

## Extension State Management System

### Complete State Transition Analysis

The TrailTag Chrome extension implements a comprehensive state management system to handle video analysis workflows. The system coordinates between local extension states, API job states, and user interface views.

#### State Definitions

| Extension State  | Description                              | UI View          | Storage Persistence |
| ---------------- | ---------------------------------------- | ---------------- | ------------------- |
| `IDLE`           | No active job, ready for new analysis    | `home-view`      | No                  |
| `CHECKING_CACHE` | Checking if video already analyzed       | `loading-view`   | No                  |
| `ANALYZING`      | Analysis in progress, polling job status | `analyzing-view` | Yes (jobId)         |
| `MAP_READY`      | Analysis complete, displaying results    | `map-view`       | Yes (results)       |
| `ERROR`          | Error occurred during analysis           | `error-view`     | No                  |

#### API Job Status Integration

| API Job Status | API Phase             | Extension Action                  | Next State            |
| -------------- | --------------------- | --------------------------------- | --------------------- |
| `pending`      | `null` or `analyzing` | Start polling, show progress      | `ANALYZING`           |
| `running`      | Various phases        | Continue polling, update progress | `ANALYZING`           |
| `completed`    | `completed`           | Fetch location data               | `MAP_READY` or `IDLE` |
| `failed`       | `failed`              | Show error message                | `ERROR`               |

#### Critical State Transition Logic

```typescript
// Key fix in handleJobCompleted() - popup-controller.ts:549-582
if (locations && typeof locations === "object" && (locations as any).detail) {
  const detail = String((locations as any).detail || "");
  if (/找不到影片地點資料|not\s*found/i.test(detail)) {
    // 404 response indicates no location data - return to IDLE
    changeState(AppState.IDLE, {
      videoId: state.videoId,
      mapVisualization: null,
      jobId: null,
      progress: 0,
      phase: null,
    });
    return;
  }
}
```

#### State Transition Validation Rules

| From State       | To State         | Valid Triggers               | Validation             |
| ---------------- | ---------------- | ---------------------------- | ---------------------- |
| `IDLE`           | `CHECKING_CACHE` | User clicks "Analyze" button | Video ID present       |
| `CHECKING_CACHE` | `IDLE`           | Cache miss, no existing data | Clear storage          |
| `CHECKING_CACHE` | `MAP_READY`      | Cache hit, locations found   | Valid location data    |
| `CHECKING_CACHE` | `ANALYZING`      | New analysis job created     | Valid job ID           |
| `ANALYZING`      | `MAP_READY`      | Job completed with data      | Valid GeoJSON data     |
| `ANALYZING`      | `IDLE`           | Job completed, no data       | 404 response handling  |
| `ANALYZING`      | `ERROR`          | Job failed or API error      | Error message present  |
| `MAP_READY`      | `IDLE`           | User starts new analysis     | Clear previous results |
| `ERROR`          | `IDLE`           | User retries or starts new   | Reset error state      |

#### Phase Text Mapping

The extension maps API phases to user-friendly Chinese text:

```typescript
function getPhaseText(phase: string | null): string {
  const phaseMap: { [key: string]: string } = {
    analyzing: "分析影片內容",
    extracting_places: "提取地點資訊",
    geocoding: "地理編碼處理",
    generating_routes: "生成路線資料",
    completed: "分析完成",
    failed: "分析失敗",
  };
  return phaseMap[phase || "analyzing"] || "處理中...";
}
```

#### Common State Management Issues & Solutions

1. **Problem**: Extension jumping to map-view instead of analyzing-view

   - **Root Cause**: 404 API responses treated as valid location data
   - **Solution**: Explicit error response detection and state cleanup

2. **Problem**: Stale job states persisting across sessions

   - **Root Cause**: Chrome storage not cleared on job completion without data
   - **Solution**: Comprehensive state cleanup in error scenarios

3. **Problem**: Phase text misalignment with API responses
   - **Root Cause**: Extension expected more granular phases than API provided
   - **Solution**: Simplified phase mapping to match actual API phases

#### Debugging State Transitions

Enable debug logging to trace state changes:

```javascript
// In popup-controller.ts
console.log("State transition:", currentState, "->", newState, data);
```

Monitor these key events:

- `changeState()` calls with transition details
- `handleJobCompleted()` API response handling
- Chrome storage read/write operations
- Job polling lifecycle events

## Important Notes

- 有關crewai相關的程式碼，應該優先使用context7檢索crewai相關內容
- Python version requirement: >=3.10, <3.14 (see pyproject.toml)
- Follow TypeScript conventions: camelCase for functions/methods, PascalCase for types, prefer arrow functions
- Use spaces for indentation, not tabs
- Use `uv` for Python package management and execution when possible
