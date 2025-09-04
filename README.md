# TrailTag

Convert YouTube travel vlogs into interactive map data and route visualizations.

TrailTag extracts meaningful places, timestamps, and routes from travel videos so viewers and developers can replay journeys on a map, inspect points-of-interest (POIs), and consume concise topic summaries.

![TrailTag Screenshot](https://github.com/user-attachments/assets/77dae24a-d77e-48e7-a376-db48e372a55c)

[TrailTag Demo](https://youtu.be/DzmGJXYH4-g)

## Who this is for

- Developers and data engineers who want to automatically convert travel videos into geospatial data
- Frontend or product engineers who need map-ready GeoJSON for visualization
- Contributors evaluating the project on GitHub

## Quick summary of capabilities

- Ingest a YouTube video (ID or URL) or supplied subtitles/metadata
- Extract timestamps, named places and POIs mentioned in subtitles/descriptions
- Geocode place names to coordinates (configurable provider) and assemble routes (LineString)
- Output GeoJSON for routes and points with useful properties (time, label, confidence)
- Provide a FastAPI backend, CLI crew for offline processing, and a browser extension to trigger analyses from the YouTube UI
- Support caching (in-memory or Redis) and asynchronous task status reporting

## Contract (brief)

- Input: a YouTube video ID / URL, or pre-parsed subtitles + timestamps JSON
- Output: asynchronous task_id; final result available as JSON/GeoJSON
  - route: LineString
  - points: FeatureCollection of Point features
  - status: pending | running | done | failed

## Detailed features

1. **Video fetching and pre-processing**

   - Download or parse YouTube metadata (title, description, upload date)
   - Retrieve subtitles (auto-generated or uploaded) and normalize timestamped text and chapters
   - **Subtitle detection** with user warnings for videos without available subtitles

2. **Topic extraction and time-aligned summaries**

   - Lightweight NLP to extract main topics, key sentences and keywords
   - Produce short, time-aligned summaries useful for map popups
   - **Smart token management** with intelligent chunking for long videos

3. **POI extraction and geocoding**

   - Detect place names, addresses and landmarks from subtitles, descriptions and chapters
   - Support configurable geocoding providers (e.g. Nominatim, Google Geocoding)
   - Return coordinates, provider source and confidence score
   - **Multi-source data extraction** from video descriptions, chapters, and comments

4. **Route reconstruction**

   - Merge time-ordered POIs and detected locations into one or multiple LineStrings
   - Include properties such as start_time, end_time, duration and source_video_time on features

5. **Backend API and task management**

   - Submit jobs asynchronously (returns task_id)
   - Poll status and download results (JSON/GeoJSON)
   - Optional SSE or WebSocket progress updates for real-time UI
   - **Enhanced state management** with persistent job tracking and recovery

6. **Memory and persistence**

   - **CrewAI Memory system** as primary storage with vector search capabilities
   - Optional Redis fallback for backward compatibility
   - **Performance monitoring** with Langtrace integration and detailed metrics

7. **Browser extension**

   - A popup UI to request analysis while watching YouTube and view the returned GeoJSON on a map
   - Integrates with the backend API to fetch and render GeoJSON layers
   - **Improved map performance** with marker clustering and optimized rendering

8. **CLI and automation**
   - A `crew`-style CLI to run single-video jobs programmatically
   - Suitable for CI or scheduled cron jobs
   - **Migration tools** for transitioning from Redis to CrewAI Memory

## API Reference

### Core Analysis Endpoints

- **POST /api/analyze**

  - Description: Submit a video analysis job
  - Example request body:

  ```json
  {
    "video_id": "YOUTUBE_VIDEO_ID",
    "callback_url": "https://example.com/webhook",
    "options": {}
  }
  ```

  - Example response:

  ```json
  {
    "task_id": "...",
    "status": "pending"
  }
  ```

- **GET /api/status/{task_id}**

  - Description: Check job status with detailed progress
  - Example response:

  ```json
  {
    "task_id": "...",
    "status": "running",
    "progress": 75,
    "phase": "geocoding",
    "subtitle_availability": "available",
    "estimated_completion": "2024-01-01T12:30:00Z"
  }
  ```

- **GET /api/results/{task_id}**

  - Description: Download job results (JSON/GeoJSON)
  - Returns a GeoJSON FeatureCollection containing route and points

- **GET /api/map/{task_id}.geojson**
  - Description: Directly fetch a map-ready GeoJSON file

### System Health & Monitoring

- **GET /health**

  - Description: Service health check with comprehensive system status
  - Example response:

  ```json
  {
    "status": "healthy",
    "memory_system": "operational",
    "redis_status": "fallback_to_memory",
    "subtitle_detection": "active",
    "performance_monitoring": "enabled"
  }
  ```

- **GET /metrics**

  - Description: Performance metrics and system statistics
  - Example response:

  ```json
  {
    "total_jobs_processed": 1247,
    "average_processing_time": 45.7,
    "memory_usage_mb": 512,
    "active_jobs": 3,
    "uptime_hours": 72,
    "langtrace_enabled": true
  }
  ```

- **GET /api/memory/stats**
  - Description: CrewAI Memory system statistics
  - Returns memory usage, entry counts, and performance metrics

### Administrative Endpoints

- **POST /api/webhooks**

  - Description: Webhook endpoint for external notifications
  - Supports job completion, error alerts, and system events

- **GET /api/execution/{task_id}**
  - Description: Detailed task execution information
  - Returns execution timeline, agent performance, and debugging data

(Actual endpoints and parameters are implemented in `src/api/routes.py` — consult code for the canonical contract.)

## Data format examples (GeoJSON)

- Route (LineString) example properties:

```json
{
  "type":"Feature",
  "geometry":{
    "type":"LineString",
    "coordinates":[...]
  },
  "properties":{
    "video_id":"abc",
    "start_time":"00:01:30",
    "end_time":"00:12:45",
    "source":"detected"
  }
}
```

- POI (Point) example properties:

```json
{
  "type":"Feature",
  "geometry":{
    "type":"Point",
    "coordinates":[lng, lat]
  },
  "properties":{
    "title":"Eiffel Tower",
    "time":"00:05:22",
    "confidence":0.89,
    "source":"subtitle"
  }
}
```

## Quick start (development)

Prerequisites

- Python 3.11+ (see `pyproject.toml`)
- Node.js + npm (for the browser extension)
- Optional: Redis (for shared caching)

Start the backend in development mode (uvicorn):

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8010 --reload
```

Run the Trailtag crew CLI for a single video:

```bash
python -m src.trailtag.main VIDEO_ID
```

Develop and package the extension:

```bash
cd src/extension
npm install
npm test
npm run package
```

Run tests

- **Unit tests**: `pytest` (Python) or `cd src/extension && npm test` (Extension)
- **Integration tests**: `uv run pytest tests/integration/test_memory_migration.py -v` (Memory system validation)
- **End-to-end tests**: `uv run python run_e2e_tests.py` (Complete workflow validation)
- **Migration testing**: `uv run python scripts/migrate_redis_to_memory.py --dry-run` (Data migration)

## Environment variables (common)

### Core Configuration

- `API_HOST` (default: 0.0.0.0)
- `API_PORT` (default: 8010)
- `OPENAI_API_KEY` — for accessing the OpenAI API
- `GOOGLE_API_KEY` — for accessing the Google API

### Memory System (CrewAI)

- `CREW_MEMORY_STORAGE_PATH` — CrewAI Memory storage location (default: ./memory_storage)
- `CREW_MEMORY_EMBEDDER_PROVIDER` — embedding provider (default: openai)

### Observability & Monitoring

- `LANGTRACE_API_KEY` — Langtrace API key for performance tracing
- `ENABLE_PERFORMANCE_MONITORING` — enable/disable monitoring (default: true)

### Legacy Redis Support (Optional)

- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD` — Redis configuration
- `REDIS_EXPIRY_DAYS` — cache expiry in days

## Deployment notes

- Small test deployment: a single uvicorn instance with optional Redis (docker-compose or local)
- Production: containerize (Docker), run multiple instances behind a load balancer, use shared Redis
- Geocoding providers often have rate limits — use caching and provider API keys appropriately

## Code locations (Updated Architecture)

### Backend Components

- `src/api/` — **Modular FastAPI Backend**
  - `src/api/core/` — Core API components (models, logging)
  - `src/api/routes/` — API endpoints and route handlers
  - `src/api/middleware/` — Middleware (SSE, CORS handling)
  - `src/api/services/` — Business logic services (CrewAI execution, state management, webhooks)
  - `src/api/cache/` — Caching system (Redis + in-memory fallback)
  - `src/api/monitoring/` — Performance monitoring and observability

### CrewAI System

- `src/trailtag/` — **Enhanced CrewAI Implementation**
  - `src/trailtag/core/` — Core system (crew definition, models, observers)
  - `src/trailtag/memory/` — CrewAI Memory system (manager, progress tracking)
  - `src/trailtag/tools/` — **Categorized Tool Suite**
    - `src/trailtag/tools/data_extraction/` — YouTube metadata, chapters, comments, descriptions
    - `src/trailtag/tools/processing/` — Subtitle processing, compression, token management
    - `src/trailtag/tools/geocoding/` — Geographic coordinate resolution

### Frontend Extension

- `src/extension/` — **Restructured Chrome Extension**
  - `src/extension/src/core/` — Core functionality (map rendering, popup control, subtitle detection)
  - `src/extension/src/services/` — API communication services
  - `src/extension/src/utils/` — Utility functions and optimization tools
  - `src/extension/ui/` — User interface components and styles
  - `src/extension/config/` — Build and configuration files
  - `src/extension/tests/` — Test suites

### Testing & Documentation

- `tests/` — **Comprehensive Test Suites**
  - `tests/integration/` — Integration tests (E2E, memory migration validation)
  - Unit tests distributed across modules
- `scripts/` — Migration and utility scripts

## Edge cases and operational behavior

- Missing or low-quality subtitles: the system will fall back to video description or chapter metadata; if nothing is available it may return partial results or mark the job as `needs_human_review`.
- Long videos: jobs can be chunked and parallelized; caching reduces repeated work.
- Unresolved geocoding: place names that cannot be geocoded are returned as unresolved with the original string for manual review.

## Inputs / Outputs (compact)

- Inputs: `{ video_id: string }` or pre-parsed subtitle/timestamps JSON
- Outputs: `{ task_id, status }`, final results are GeoJSON files available via the API

## Testing & quality gates

- Add unit tests in `tests/` for core transformation and geocoding logic
- Update tests when changing public API behavior

## Contributing

- Pull requests and issues are welcome. Follow the repo's coding style and include tests for new behavior.

## License

- See the `LICENSE` file at the repository root for the project license.
