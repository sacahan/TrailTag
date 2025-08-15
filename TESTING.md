# Testing guide

This repository contains both a Chrome Extension (frontend JS) and Python backend/tests.

Run extension (Jest) tests locally:

```bash
# from repository root
npm install --prefix src/extension
npm test --prefix src/extension
```

Run Python tests locally:

```bash
# ensure pytest is installed
python -m pip install pytest
pytest -q
```

CI: GitHub Actions workflow is defined at `.github/workflows/ci-test.yml` and runs both Jest and pytest on push/PR to `main`.
