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

1. Video fetching and pre-processing

   - Download or parse YouTube metadata (title, description, upload date)
   - Retrieve subtitles (auto-generated or uploaded) and normalize timestamped text and chapters

2. Topic extraction and time-aligned summaries

   - Lightweight NLP to extract main topics, key sentences and keywords
   - Produce short, time-aligned summaries useful for map popups

3. POI extraction and geocoding

   - Detect place names, addresses and landmarks from subtitles, descriptions and chapters
   - Support configurable geocoding providers (e.g. Nominatim, Google Geocoding)
   - Return coordinates, provider source and confidence score

4. Route reconstruction

   - Merge time-ordered POIs and detected locations into one or multiple LineStrings
   - Include properties such as start_time, end_time, duration and source_video_time on features

5. Backend API and task management

   - Submit jobs asynchronously (returns task_id)
   - Poll status and download results (JSON/GeoJSON)
   - Optional SSE or WebSocket progress updates for real-time UI

6. Caching and persistence

   - In-memory cache by default; optional Redis integration to share caches between instances
   - Configurable cache expiry (days)

7. Browser extension

   - A popup UI to request analysis while watching YouTube and view the returned GeoJSON on a map
   - Integrates with the backend API to fetch and render GeoJSON layers

8. CLI and automation
   - A `crew`-style CLI to run single-video jobs programmatically
   - Suitable for CI or scheduled cron jobs

## API preview (examples)

- POST /analyze

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

- GET /status/{task_id}

  - Description: Check job status
  - Example response:

  ```json
  {
    "task_id": "...",
    "status": "done",
    "progress": 100
  }
  ```

- GET /results/{task_id}

  - Description: Download job results (JSON/GeoJSON)
  - Returns a GeoJSON FeatureCollection containing route and points

- GET /map/{task_id}.geojson
  - Description: Directly fetch a map-ready GeoJSON file

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

- Python tests: from repo root run `pytest`
- Extension tests: `cd src/extension && npm test`

## Environment variables (common)

- `API_HOST` (default: 0.0.0.0)
- `API_PORT` (default: 8010)
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD` — Redis configuration
- `REDIS_EXPIRY_DAYS` — cache expiry in days
- `OPENAI_API_KEY` — for accessing the OpenAI API
- `GOOGLE_API_KEY` — for accessing the Google API

## Deployment notes

- Small test deployment: a single uvicorn instance with optional Redis (docker-compose or local)
- Production: containerize (Docker), run multiple instances behind a load balancer, use shared Redis
- Geocoding providers often have rate limits — use caching and provider API keys appropriately

## Code locations

- `src/api/` — FastAPI app, routes, models and logging
- `src/trailtag/` — crew, agents, tools and CLI
- `src/extension/` — browser extension source & tests
- `tests/` — unit tests

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
