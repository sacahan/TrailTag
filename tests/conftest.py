"""
Test configuration and fixtures for TrailTag E2E tests
"""

import pytest
import os
import asyncio
from unittest.mock import patch


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment variables"""
    test_env = {
        "OPENAI_API_KEY": "test-key-for-testing",
        "GOOGLE_API_KEY": "test-key-for-testing",
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379",
        "API_HOST": "127.0.0.1",
        "API_PORT": "8010",
        "OTEL_SDK_DISABLED": "true",
        "CREWAI_DISABLE_TELEMETRY": "true",
    }

    # Set test environment variables
    for key, value in test_env.items():
        os.environ[key] = value

    yield

    # Cleanup is handled per test


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Global mock for external services to avoid real API calls during testing
@pytest.fixture(autouse=True)
def mock_external_services():
    """Mock external services by default to prevent real API calls during testing"""
    with patch(
        "src.trailtag.tools.youtube_metadata_tool.YoutubeMetadataTool._run"
    ) as mock_youtube:
        # Set a default return value that won't break tests
        mock_youtube.return_value = None
        yield mock_youtube
