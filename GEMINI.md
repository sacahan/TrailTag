# TrailTag Project Analysis

## Project Overview

This project, "TrailTag," is a comprehensive system designed to convert YouTube travel vlogs into interactive map data. It extracts timestamps, places, and routes from videos, geocodes them, and provides the data through a FastAPI backend. The system also includes a command-line interface (CLI) for processing videos and a browser extension for interacting with the service directly from YouTube.

The project is a monorepo containing two main sub-projects:

1.  **Backend & Core Logic:** A Python project using FastAPI and `crewAI`.
2.  **Frontend:** A browser extension built with TypeScript and managed as a Node.js project.

**Key Technologies:**

- **Backend:** Python, FastAPI, Uvicorn
- **Core Logic:** crewAI
- **Frontend:** TypeScript, Node.js, Jest (for testing)
- **Containerization:** Docker
- **Package Management:** Hatch (for Python), npm (for the extension)
- **Testing:** pytest, Jest
- **Linting/Formatting:** Ruff, pre-commit

## Building and Running

### Backend

To run the backend server in development mode:

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8010 --reload
```

### CLI

To run the TrailTag crew for a single video:

```bash
python -m src.trailtag.main <YOUTUBE_VIDEO_ID>
```

### Browser Extension

The browser extension is a separate Node.js project located in `src/extension`.

To develop and package the extension:

```bash
cd src/extension
npm install
npm test
npm run package
```

### Docker

To run the backend service using Docker:

```bash
docker-compose up
```

## Development Conventions

- **Monorepo Structure:** The project is organized as a monorepo with separate backend and frontend projects.
- **Dependency Management:**
  - Python dependencies are managed with Hatch and are listed in `pyproject.toml`.
  - The browser extension's dependencies are managed with npm and are listed in `src/extension/package.json`.
- **Testing:**
  - Python tests are run with `pytest`.
  - The browser extension's tests are run with Jest (`npm test` in `src/extension`). The Jest configuration is in `src/extension/config/jest.config.cjs`.
- **Code Quality:** The project uses `pre-commit` with `Ruff` to enforce code quality and formatting for the Python code.
- **Environment Variables:** The project uses a `.env` file for managing environment variables. A `.env.simple` file is provided as a template.

## Directory Overview

- `src/api`: Contains the FastAPI backend, including routes, middleware, and services.
- `src/trailtag`: Contains the core `crewAI` implementation, including the crew definition, agents, and tasks.
- `src/extension`: Contains the source code for the browser extension. This is a self-contained Node.js project.
  - `src/extension/src`: TypeScript source code for the extension.
  - `src/extension/config`: Configuration files for the extension, including `jest.config.cjs` and `build.mjs`.
  - `src/extension/package.json`: Defines the dependencies and scripts for the extension.
- `tests`: Contains the Python test suites for the project.
- `docker-compose.yml`: Defines the Docker services for the project.
- `pyproject.toml`: Defines the Python project metadata and dependencies.
- `README.md`: Provides a detailed overview of the project.
