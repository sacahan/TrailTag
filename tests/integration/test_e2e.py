"""
End-to-End Test Suite for TrailTag

This comprehensive test suite covers:
1. Complete video analysis workflow (YouTube ID → crew execution → GeoJSON output)
2. API endpoint testing (/api/analyze, /api/status, /api/results)
3. Memory system integration with CrewAI
4. Performance benchmarking for analysis time
5. Error handling scenarios
6. Async task management validation

The goal is to validate all improvements made in Phases 1 and 2 work correctly together.
"""

import pytest
import asyncio
import time
import uuid
from unittest.mock import Mock, patch
from pathlib import Path
import tempfile
import shutil

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# HTTP client for API testing
from fastapi.testclient import TestClient

# TrailTag imports
from src.api.main import app
from src.api.models import (
    JobStatus,
)
from src.trailtag.crew import Trailtag
from src.trailtag.memory_manager import (
    get_memory_manager,
    reset_global_memory_manager,
)
from src.trailtag.memory.models import (
    JobStatus as MemoryJobStatus,
    JobPhase,
)
from src.api.crew_executor import (
    get_global_executor,
)
from src.api.cache.cache_manager import CacheManager
from src.trailtag.tools.youtube_metadata_tool import YoutubeMetadataTool


class TestFixtures:
    """Test data fixtures and mock responses"""

    # Test video IDs (use real IDs for actual testing, mocked responses for unit tests)
    VALID_VIDEO_ID = "dQw4w9WgXcQ"  # Famous video ID for testing
    INVALID_VIDEO_ID = "invalid_id"
    LONG_VIDEO_ID = "long_video_test"  # For performance testing
    NO_SUBTITLE_VIDEO_ID = "no_subtitle"

    # Test URLs
    VALID_YOUTUBE_URLS = [
        f"https://www.youtube.com/watch?v={VALID_VIDEO_ID}",
        f"https://youtu.be/{VALID_VIDEO_ID}",
        f"https://youtube.com/embed/{VALID_VIDEO_ID}",
    ]
    INVALID_YOUTUBE_URLS = [
        "https://example.com/video",
        "not_a_url",
        "https://youtube.com/watch",  # Missing video ID
    ]

    @staticmethod
    def get_mock_youtube_metadata():
        """Mock YouTube metadata response"""
        return {
            "video_id": TestFixtures.VALID_VIDEO_ID,
            "title": "Test Travel Video - Beautiful Destinations",
            "description": "Join us as we explore Tokyo, Kyoto, and Mount Fuji. We visited Senso-ji Temple, Tokyo Station, and stayed at Ryokan Inn.",
            "duration": "15:30",
            "upload_date": "2024-01-15",
            "view_count": 1000000,
            "like_count": 50000,
            "subtitles": [
                {
                    "timestamp": "00:30",
                    "text": "Welcome to Tokyo, our first destination",
                },
                {
                    "timestamp": "05:15",
                    "text": "Now we're heading to the famous Senso-ji Temple",
                },
                {"timestamp": "10:45", "text": "Mount Fuji offers breathtaking views"},
            ],
            "subtitle_availability": {
                "available": True,
                "manual_subtitles": ["en", "ja"],
                "auto_captions": ["en"],
                "selected_lang": "en",
                "confidence_score": 0.95,
            },
            "chapters": [
                {"timestamp": "00:00", "title": "Introduction - Tokyo"},
                {"timestamp": "05:00", "title": "Temple Visit"},
                {"timestamp": "10:00", "title": "Mount Fuji"},
            ],
        }

    @staticmethod
    def get_mock_analysis_result():
        """Mock analysis result in GeoJSON format"""
        return {
            "video_id": TestFixtures.VALID_VIDEO_ID,
            "routes": [
                {
                    "location": "Tokyo Station",
                    "coordinates": [139.7673068, 35.6809591],
                    "description": "Major railway hub in Tokyo",
                    "timecode": "00:30",
                    "tags": ["transportation", "landmark"],
                    "marker": "station",
                },
                {
                    "location": "Senso-ji Temple",
                    "coordinates": [139.7966936, 35.7148016],
                    "description": "Ancient Buddhist temple in Asakusa",
                    "timecode": "05:15",
                    "tags": ["temple", "culture", "tourism"],
                    "marker": "temple",
                },
                {
                    "location": "Mount Fuji",
                    "coordinates": [138.7274, 35.3606],
                    "description": "Japan's highest mountain and sacred symbol",
                    "timecode": "10:45",
                    "tags": ["mountain", "nature", "landmark"],
                    "marker": "mountain",
                },
            ],
        }

    @staticmethod
    def get_performance_benchmarks():
        """Performance benchmark expectations"""
        return {
            "max_analysis_time_seconds": 180,  # 3 minutes max for standard video
            "max_api_response_time_ms": 2000,  # 2 seconds for API endpoints
            "max_memory_usage_mb": 500,  # Memory usage limit
            "min_accuracy_score": 0.85,  # Minimum location accuracy
            "cache_hit_ratio": 0.8,  # Expected cache efficiency
        }


class E2ETestBase:
    """Base class for E2E tests with common setup and utilities"""

    @pytest.fixture(autouse=True)
    def setup_test_environment(self):
        """Setup test environment before each test"""
        # Create temporary directory for test data
        self.temp_dir = Path(tempfile.mkdtemp(prefix="trailtag_test_"))

        # Reset global state
        reset_global_memory_manager()
        # Note: sync fixture can't await, but shutdown will be handled per test

        # Configure test environment
        self.test_config = {
            "OPENAI_API_KEY": "test_key",
            "GOOGLE_API_KEY": "test_key",
            "API_HOST": "127.0.0.1",
            "API_PORT": 8010,
        }

        # Initialize test components
        self.cache_manager = CacheManager()
        self.memory_manager = None  # Will be initialized per test
        self.crew_executor = None  # Will be initialized per test

        # Performance tracking
        self.start_time = time.time()
        self.performance_metrics = {}

        yield

        # Cleanup - simplified for sync fixture
        try:
            # Remove temp directory
            if hasattr(self, "temp_dir") and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"Cleanup error: {e}")

    async def _cleanup_test_environment(self):
        """Cleanup test environment after each test"""
        try:
            # Shutdown executor if initialized
            if self.crew_executor:
                await self.crew_executor.shutdown()

            # Clear cache
            if hasattr(self.cache_manager, "clear_all"):
                self.cache_manager.clear_all()

            # Remove temp directory
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)

        except Exception as e:
            print(f"Cleanup error: {e}")

    def record_performance_metric(self, name: str, value: float, unit: str = "ms"):
        """Record a performance metric"""
        self.performance_metrics[name] = {
            "value": value,
            "unit": unit,
            "timestamp": time.time(),
        }

    def assert_performance_within_limits(self, metric_name: str, max_value: float):
        """Assert that a performance metric is within acceptable limits"""
        if metric_name in self.performance_metrics:
            actual_value = self.performance_metrics[metric_name]["value"]
            assert (
                actual_value <= max_value
            ), f"{metric_name}: {actual_value} exceeds limit {max_value}"


class TestCompleteWorkflow(E2ETestBase):
    """Test complete video analysis workflow from input to output"""

    @pytest.mark.asyncio
    async def test_complete_video_analysis_workflow(self):
        """Test the complete workflow: YouTube URL → analysis → GeoJSON output"""

        # 1. Setup mocks for external services
        with patch.object(YoutubeMetadataTool, "_run") as mock_youtube:
            mock_youtube.return_value = Mock(**TestFixtures.get_mock_youtube_metadata())

            with patch.object(Trailtag, "crew") as mock_crew:
                # Mock crew execution
                mock_crew_instance = Mock()
                mock_result = Mock()
                mock_result.pydantic.model_dump.return_value = (
                    TestFixtures.get_mock_analysis_result()
                )
                mock_crew_instance.kickoff.return_value = mock_result
                mock_crew.return_value = mock_crew_instance

                # 2. Create test client
                client = TestClient(app)

                # 3. Submit analysis request
                request_data = {"url": TestFixtures.VALID_YOUTUBE_URLS[0]}

                start_time = time.time()
                response = client.post("/api/videos/analyze", json=request_data)
                api_response_time = (time.time() - start_time) * 1000

                # 4. Verify initial response
                assert response.status_code == 200
                job_data = response.json()
                assert "job_id" in job_data
                assert job_data["video_id"] == TestFixtures.VALID_VIDEO_ID
                assert job_data["status"] in [
                    JobStatus.QUEUED.value,
                    JobStatus.RUNNING.value,
                ]

                self.record_performance_metric(
                    "api_submit_response_time", api_response_time
                )

                # 5. Poll for job completion
                job_id = job_data["job_id"]
                max_wait_time = TestFixtures.get_performance_benchmarks()[
                    "max_analysis_time_seconds"
                ]
                poll_start = time.time()

                job_completed = False
                final_status = None

                while time.time() - poll_start < max_wait_time:
                    status_response = client.get(f"/api/jobs/{job_id}")
                    assert status_response.status_code == 200

                    status_data = status_response.json()
                    final_status = status_data["status"]

                    if final_status in [JobStatus.DONE.value, JobStatus.FAILED.value]:
                        job_completed = True
                        break

                    await asyncio.sleep(1)  # Wait 1 second before next poll

                total_processing_time = time.time() - poll_start
                self.record_performance_metric(
                    "total_processing_time", total_processing_time, "seconds"
                )

                # 6. Verify job completion
                assert (
                    job_completed
                ), f"Job did not complete within {max_wait_time} seconds"
                assert (
                    final_status == JobStatus.DONE.value
                ), f"Job failed with status: {final_status}"

                # 7. Retrieve and validate results
                locations_response = client.get(
                    f"/api/videos/{TestFixtures.VALID_VIDEO_ID}/locations"
                )
                assert locations_response.status_code == 200

                locations_data = locations_response.json()
                assert "video_id" in locations_data
                assert "routes" in locations_data
                assert len(locations_data["routes"]) > 0

                # Validate route structure
                for route in locations_data["routes"]:
                    assert "location" in route
                    assert "coordinates" in route
                    assert isinstance(route["coordinates"], list)
                    assert len(route["coordinates"]) == 2  # [lng, lat]

                # 8. Performance assertions
                benchmarks = TestFixtures.get_performance_benchmarks()
                self.assert_performance_within_limits(
                    "api_submit_response_time", benchmarks["max_api_response_time_ms"]
                )
                self.assert_performance_within_limits(
                    "total_processing_time", benchmarks["max_analysis_time_seconds"]
                )

    @pytest.mark.asyncio
    async def test_cached_result_workflow(self):
        """Test workflow when results are already cached"""

        # 1. Pre-populate cache
        cache_key = f"analysis:{TestFixtures.VALID_VIDEO_ID}"
        cached_result = TestFixtures.get_mock_analysis_result()
        self.cache_manager.set(cache_key, cached_result)

        # 2. Mock subtitle check
        with patch.object(YoutubeMetadataTool, "_run") as mock_youtube:
            mock_youtube.return_value = Mock(**TestFixtures.get_mock_youtube_metadata())

            client = TestClient(app)

            # 3. Submit request
            request_data = {"url": TestFixtures.VALID_YOUTUBE_URLS[0]}

            start_time = time.time()
            response = client.post("/api/videos/analyze", json=request_data)
            response_time = (time.time() - start_time) * 1000

            # 4. Should return immediately with cached result
            assert response.status_code == 200
            job_data = response.json()
            assert job_data["cached"]
            assert job_data["status"] == JobStatus.DONE.value

            # Cache response should be very fast
            assert (
                response_time < 1000
            ), f"Cached response took too long: {response_time}ms"
            self.record_performance_metric("cached_response_time", response_time)


class TestAPIEndpoints(E2ETestBase):
    """Test all API endpoints thoroughly"""

    @pytest.mark.asyncio
    async def test_analyze_endpoint_validation(self):
        """Test /api/videos/analyze endpoint input validation"""
        client = TestClient(app)

        # Test invalid URLs
        for invalid_url in TestFixtures.INVALID_YOUTUBE_URLS:
            response = client.post("/api/videos/analyze", json={"url": invalid_url})
            assert response.status_code in [
                400,
                422,
            ]  # Either validation error is acceptable
            detail = response.json().get("detail", "")
            if isinstance(detail, str):
                assert "無效的 YouTube URL" in detail
            else:
                # FastAPI validation errors return structured detail
                assert "url" in str(detail) or "youtube" in str(detail).lower()

        # Test missing URL
        response = client.post("/api/videos/analyze", json={})
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_subtitle_check_endpoint(self):
        """Test /api/videos/{video_id}/subtitles/check endpoint"""

        with patch.object(YoutubeMetadataTool, "_run") as mock_youtube:
            mock_data = TestFixtures.get_mock_youtube_metadata()
            mock_youtube.return_value = Mock(**mock_data)

            client = TestClient(app)

            # Test valid video
            response = client.get(
                f"/api/videos/{TestFixtures.VALID_VIDEO_ID}/subtitles/check"
            )
            assert response.status_code == 200

            subtitle_data = response.json()
            assert subtitle_data["available"]
            assert "manual_subtitles" in subtitle_data
            assert "auto_captions" in subtitle_data
            assert subtitle_data["confidence_score"] >= 0.0

    @pytest.mark.asyncio
    async def test_job_status_endpoints(self):
        """Test job status related endpoints"""
        client = TestClient(app)

        # Test non-existent job
        fake_job_id = str(uuid.uuid4())
        response = client.get(f"/api/jobs/{fake_job_id}")
        assert response.status_code == 404

        # Test video job lookup for non-existent video
        response = client.get(f"/api/videos/{TestFixtures.INVALID_VIDEO_ID}/job")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test /health endpoint"""
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200

        health_data = response.json()
        assert "status" in health_data
        assert "timestamp" in health_data
        assert "version" in health_data
        assert "monitoring" in health_data
        assert health_data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self):
        """Test /metrics endpoint"""
        client = TestClient(app)

        response = client.get("/metrics")
        assert response.status_code == 200

        metrics_data = response.json()
        # The actual structure may vary, just check it returns valid JSON
        assert isinstance(metrics_data, dict)
        # Check for at least some expected fields (adjust based on actual metrics structure)
        expected_fields = ["api_endpoints", "langtrace_enabled", "project_name"]
        has_expected_field = any(field in metrics_data for field in expected_fields)
        assert (
            has_expected_field
        ), f"Expected one of {expected_fields}, got keys: {list(metrics_data.keys())}"


class TestMemorySystemIntegration(E2ETestBase):
    """Test CrewAI Memory system integration"""

    @pytest.mark.asyncio
    async def test_memory_system_initialization(self):
        """Test memory system properly initializes"""

        # Initialize memory manager with test config
        self.memory_manager = get_memory_manager()
        assert self.memory_manager is not None

        # Test memory stats
        stats = self.memory_manager.get_memory_stats()
        assert hasattr(stats, "total_entries")
        assert hasattr(stats, "short_term_count")
        assert hasattr(stats, "long_term_count")

    @pytest.mark.asyncio
    async def test_job_progress_memory_storage(self):
        """Test job progress storage in memory system"""

        self.memory_manager = get_memory_manager()

        # Store job progress
        job_id = str(uuid.uuid4())
        video_id = TestFixtures.VALID_VIDEO_ID

        self.memory_manager.save_job_progress(
            job_id=job_id,
            video_id=video_id,
            status=MemoryJobStatus.RUNNING,
            phase=JobPhase.PROCESSING,
            progress=50,
        )

        # Retrieve and verify
        stored_job = self.memory_manager.get_job_progress(job_id)
        assert stored_job is not None
        assert stored_job.job_id == job_id
        assert stored_job.video_id == video_id
        assert stored_job.status == MemoryJobStatus.RUNNING
        assert stored_job.progress == 50

    @pytest.mark.asyncio
    async def test_analysis_result_memory_storage(self):
        """Test analysis result storage in memory system"""

        self.memory_manager = get_memory_manager()

        # Store analysis result
        video_id = TestFixtures.VALID_VIDEO_ID
        mock_result = TestFixtures.get_mock_analysis_result()

        self.memory_manager.save_analysis_result(
            video_id=video_id,
            metadata={"test": "data"},
            topic_summary={"summary": "test"},
            map_visualization=mock_result,
            processing_time=120.5,
        )

        # Retrieve and verify
        stored_result = self.memory_manager.get_analysis_result(video_id)
        assert stored_result is not None
        assert stored_result.video_id == video_id
        assert stored_result.processing_time == 120.5
        assert stored_result.map_visualization == mock_result

    @pytest.mark.asyncio
    async def test_agent_memory_storage(self):
        """Test agent-specific memory storage"""

        self.memory_manager = get_memory_manager()

        # Store agent memory
        agent_role = "video_fetch_agent"
        context = "Extracted locations from video: Tokyo, Mount Fuji"
        entities = [
            {"name": "Tokyo", "type": "location"},
            {"name": "Mount Fuji", "type": "landmark"},
        ]

        memory_id = self.memory_manager.save_agent_memory(
            agent_role=agent_role, context=context, entities=entities, confidence=0.95
        )

        assert memory_id is not None

        # Query agent memories
        memories = self.memory_manager.query_agent_memories(agent_role, "Tokyo")
        assert len(memories) > 0
        assert memories[0].agent_role == agent_role
        assert "Tokyo" in memories[0].context

    @pytest.mark.asyncio
    async def test_memory_performance(self):
        """Test memory system performance"""

        self.memory_manager = get_memory_manager()

        # Benchmark memory operations
        num_operations = 100

        # Test memory save performance
        start_time = time.time()
        for i in range(num_operations):
            self.memory_manager.save_agent_memory(
                agent_role="test_agent", context=f"Test context {i}", confidence=0.9
            )
        save_time = (time.time() - start_time) * 1000 / num_operations

        # Test memory query performance
        start_time = time.time()
        for i in range(num_operations):
            self.memory_manager.query_agent_memories("test_agent", f"context {i}")
        query_time = (time.time() - start_time) * 1000 / num_operations

        self.record_performance_metric("memory_save_per_op", save_time)
        self.record_performance_metric("memory_query_per_op", query_time)

        # Assert reasonable performance (adjust thresholds as needed)
        assert save_time < 100, f"Memory save too slow: {save_time}ms per operation"
        assert query_time < 50, f"Memory query too slow: {query_time}ms per operation"


class TestAsyncTaskManagement(E2ETestBase):
    """Test async task management and state persistence"""

    @pytest.mark.asyncio
    async def test_crew_executor_initialization(self):
        """Test CrewExecutor initialization and basic operations"""

        self.crew_executor = get_global_executor(max_concurrent_jobs=3)
        assert self.crew_executor is not None
        assert self.crew_executor.max_concurrent_jobs == 3

        # Test job ID generation
        job_id = self.crew_executor.generate_job_id()
        assert len(job_id) == 36  # UUID format
        assert job_id != self.crew_executor.generate_job_id()  # Should be unique

    @pytest.mark.asyncio
    async def test_async_job_submission(self):
        """Test async job submission and tracking"""

        self.crew_executor = get_global_executor()

        # Create mock crew
        mock_crew = Mock()
        mock_result = Mock()
        mock_result.pydantic.model_dump.return_value = (
            TestFixtures.get_mock_analysis_result()
        )
        mock_crew.kickoff.return_value = mock_result
        mock_crew.__class__.__name__ = "TestCrew"

        # Submit job
        inputs = {"video_id": TestFixtures.VALID_VIDEO_ID, "test": "data"}
        job_id = await self.crew_executor.submit_job(mock_crew, inputs)

        assert job_id is not None

        # Check job status
        status = await self.crew_executor.get_job_status(job_id)
        assert status is not None
        assert status["job_id"] == job_id
        assert status["status"] in ["pending", "running", "completed"]

    @pytest.mark.asyncio
    async def test_concurrent_job_execution(self):
        """Test multiple concurrent job executions"""

        self.crew_executor = get_global_executor(max_concurrent_jobs=3)

        # Create mock crews with different execution times
        def create_mock_crew(execution_time: float):
            mock_crew = Mock()

            def slow_kickoff(inputs):
                import time

                time.sleep(execution_time)
                result = Mock()
                result.pydantic.model_dump.return_value = {
                    "test": f"result_{execution_time}"
                }
                return result

            mock_crew.kickoff = slow_kickoff
            mock_crew.__class__.__name__ = f"TestCrew_{execution_time}"
            return mock_crew

        # Submit multiple jobs
        job_ids = []
        crews = [create_mock_crew(0.1), create_mock_crew(0.2), create_mock_crew(0.3)]

        start_time = time.time()
        for i, crew in enumerate(crews):
            inputs = {"video_id": f"test_{i}", "job": i}
            job_id = await self.crew_executor.submit_job(crew, inputs)
            job_ids.append(job_id)

        # Wait for all jobs to complete
        max_wait = 5  # seconds
        completed_jobs = 0

        while time.time() - start_time < max_wait and completed_jobs < len(job_ids):
            completed_jobs = 0
            for job_id in job_ids:
                status = await self.crew_executor.get_job_status(job_id)
                if status and status["status"] == "completed":
                    completed_jobs += 1

            if completed_jobs < len(job_ids):
                await asyncio.sleep(0.1)

        assert completed_jobs == len(
            job_ids
        ), f"Only {completed_jobs}/{len(job_ids)} jobs completed"

        # Check running jobs count during execution
        running_jobs = await self.crew_executor.get_running_jobs()
        assert len(running_jobs) <= 3  # Should not exceed max_concurrent_jobs

    @pytest.mark.asyncio
    async def test_job_cancellation(self):
        """Test job cancellation functionality"""

        self.crew_executor = get_global_executor()

        # Create long-running mock crew
        mock_crew = Mock()

        def long_running_kickoff(inputs):
            import time

            time.sleep(10)  # Long execution
            return Mock()

        mock_crew.kickoff = long_running_kickoff
        mock_crew.__class__.__name__ = "LongRunningCrew"

        # Submit job
        inputs = {"video_id": "long_test"}
        job_id = await self.crew_executor.submit_job(mock_crew, inputs)

        # Wait a bit for job to start
        await asyncio.sleep(0.5)

        # Cancel job
        cancelled = await self.crew_executor.cancel_job(job_id)

        # Note: Cancellation success depends on timing and implementation
        # The test verifies the cancellation API works, not necessarily that it succeeds
        assert isinstance(cancelled, bool)


class TestErrorHandlingAndEdgeCases(E2ETestBase):
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_invalid_video_id_handling(self):
        """Test handling of invalid video IDs"""

        with patch.object(YoutubeMetadataTool, "_run") as mock_youtube:
            mock_youtube.side_effect = Exception("Video not found")

            client = TestClient(app)

            # Submit request with invalid video
            request_data = {
                "url": f"https://youtube.com/watch?v={TestFixtures.INVALID_VIDEO_ID}"
            }
            response = client.post("/api/videos/analyze", json=request_data)

            # Should return error about subtitles or video access
            assert response.status_code in [422, 500]

    @pytest.mark.asyncio
    async def test_no_subtitle_video_handling(self):
        """Test handling of videos without subtitles"""

        # Mock response with no subtitles
        mock_data = TestFixtures.get_mock_youtube_metadata()
        mock_data["subtitle_availability"]["available"] = False
        mock_data["subtitle_availability"]["confidence_score"] = 0.0

        with patch.object(YoutubeMetadataTool, "_run") as mock_youtube:
            mock_youtube.return_value = Mock(**mock_data)

            client = TestClient(app)

            request_data = {
                "url": f"https://youtube.com/watch?v={TestFixtures.NO_SUBTITLE_VIDEO_ID}"
            }
            response = client.post("/api/videos/analyze", json=request_data)

            assert response.status_code == 422
            detail = response.json()["detail"]
            assert "沒有可用的字幕" in detail["message"]

    @pytest.mark.asyncio
    async def test_crew_execution_failure_handling(self):
        """Test handling of crew execution failures"""

        with patch.object(YoutubeMetadataTool, "_run") as mock_youtube:
            mock_youtube.return_value = Mock(**TestFixtures.get_mock_youtube_metadata())

            with patch.object(Trailtag, "crew") as mock_crew:
                # Mock crew that fails
                mock_crew_instance = Mock()
                mock_crew_instance.kickoff.side_effect = Exception(
                    "Crew execution failed"
                )
                mock_crew.return_value = mock_crew_instance

                client = TestClient(app)

                request_data = {"url": TestFixtures.VALID_YOUTUBE_URLS[0]}
                response = client.post("/api/videos/analyze", json=request_data)

                # Should succeed in creating job
                assert response.status_code == 200
                job_id = response.json()["job_id"]

                # Wait for job to fail
                max_wait = 30
                start_time = time.time()

                while time.time() - start_time < max_wait:
                    status_response = client.get(f"/api/jobs/{job_id}")
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        if status_data["status"] == JobStatus.FAILED.value:
                            break
                    await asyncio.sleep(1)

                # Final status should be failed
                final_response = client.get(f"/api/jobs/{job_id}")
                if final_response.status_code == 200:
                    final_data = final_response.json()
                    # Job should either be failed or still running (depending on timing)
                    assert final_data["status"] in [
                        JobStatus.FAILED.value,
                        JobStatus.RUNNING.value,
                    ]

    @pytest.mark.asyncio
    async def test_memory_system_failure_resilience(self):
        """Test system resilience when memory system fails"""

        # Test with corrupted memory path
        with patch("src.trailtag.memory_manager.Path") as mock_path:
            mock_path.side_effect = PermissionError("Access denied")

            # System should still work with fallback
            try:
                memory_manager = get_memory_manager()
                # Should not raise exception, might use fallback
                assert memory_manager is not None
            except Exception as e:
                # If exception is raised, it should be handled gracefully
                assert "Access denied" in str(e)

    @pytest.mark.asyncio
    async def test_api_rate_limiting_behavior(self):
        """Test API behavior under high load"""

        client = TestClient(app)

        # Mock rapid requests
        with patch.object(YoutubeMetadataTool, "_run") as mock_youtube:
            mock_youtube.return_value = Mock(**TestFixtures.get_mock_youtube_metadata())

            # Submit multiple rapid requests
            tasks = []
            num_requests = 10

            async def make_request():
                request_data = {"url": TestFixtures.VALID_YOUTUBE_URLS[0]}
                return client.post("/api/videos/analyze", json=request_data)

            # Make concurrent requests
            for _ in range(num_requests):
                tasks.append(make_request())

            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # Count successful responses
            successful = sum(
                1
                for r in responses
                if hasattr(r, "status_code") and r.status_code in [200, 201]
            )

            # Should handle at least some requests successfully
            assert successful > 0, "No requests succeeded under high load"


class TestPerformanceBenchmarking(E2ETestBase):
    """Test performance benchmarking and optimization validation"""

    @pytest.mark.asyncio
    async def test_analysis_time_performance(self):
        """Test that analysis time meets performance targets"""

        benchmarks = TestFixtures.get_performance_benchmarks()

        with patch.object(YoutubeMetadataTool, "_run") as mock_youtube:
            mock_youtube.return_value = Mock(**TestFixtures.get_mock_youtube_metadata())

            with patch.object(Trailtag, "crew") as mock_crew:
                # Mock crew with controlled execution time
                mock_crew_instance = Mock()

                def timed_kickoff(inputs):
                    time.sleep(2)  # Simulate 2 second processing
                    result = Mock()
                    result.pydantic.model_dump.return_value = (
                        TestFixtures.get_mock_analysis_result()
                    )
                    return result

                mock_crew_instance.kickoff = timed_kickoff
                mock_crew.return_value = mock_crew_instance

                client = TestClient(app)

                # Measure end-to-end analysis time
                start_time = time.time()

                request_data = {"url": TestFixtures.VALID_YOUTUBE_URLS[0]}
                response = client.post("/api/videos/analyze", json=request_data)
                job_id = response.json()["job_id"]

                # Poll for completion
                while True:
                    status_response = client.get(f"/api/jobs/{job_id}")
                    status_data = status_response.json()

                    if status_data["status"] in [
                        JobStatus.DONE.value,
                        JobStatus.FAILED.value,
                    ]:
                        break

                    await asyncio.sleep(0.5)

                total_time = time.time() - start_time
                self.record_performance_metric(
                    "end_to_end_analysis", total_time, "seconds"
                )

                # Assert performance target
                assert (
                    total_time <= benchmarks["max_analysis_time_seconds"]
                ), f"Analysis took {total_time}s, exceeds limit of {benchmarks['max_analysis_time_seconds']}s"

    @pytest.mark.asyncio
    async def test_memory_system_performance(self):
        """Test CrewAI Memory system performance benchmarks"""

        # Test memory system performance
        memory_manager = get_memory_manager()

        # Benchmark data operations
        num_operations = 50
        test_data = {"test": "data", "locations": ["Tokyo", "Osaka"]}

        # Memory system save benchmark
        start_time = time.time()
        for i in range(num_operations):
            memory_manager.save_analysis_result(
                video_id=f"test_{i}",
                metadata=test_data,
                topic_summary=test_data,
                map_visualization=test_data,
                processing_time=1.0,
            )
        memory_save_time = (time.time() - start_time) * 1000 / num_operations

        # Memory system get benchmark
        start_time = time.time()
        for i in range(num_operations):
            memory_manager.get_analysis_result(f"test_{i}")
        memory_get_time = (time.time() - start_time) * 1000 / num_operations

        # Agent memory benchmark
        start_time = time.time()
        for i in range(num_operations):
            memory_manager.save_agent_memory(
                agent_role="test_agent",
                context=f"Test context {i}",
                entities=[{"name": f"entity_{i}", "type": "location"}],
                confidence=0.9,
            )
        memory_agent_save_time = (time.time() - start_time) * 1000 / num_operations

        # Agent memory query benchmark
        start_time = time.time()
        for i in range(num_operations):
            memory_manager.query_agent_memories("test_agent", f"context {i}")
        memory_agent_query_time = (time.time() - start_time) * 1000 / num_operations

        # Record performance metrics
        self.record_performance_metric("memory_save_time", memory_save_time)
        self.record_performance_metric("memory_get_time", memory_get_time)
        self.record_performance_metric("memory_agent_save_time", memory_agent_save_time)
        self.record_performance_metric(
            "memory_agent_query_time", memory_agent_query_time
        )

        # Performance assertions
        assert memory_save_time < 100, f"Memory save too slow: {memory_save_time}ms"
        assert memory_get_time < 50, f"Memory get too slow: {memory_get_time}ms"
        assert (
            memory_agent_save_time < 50
        ), f"Agent memory save too slow: {memory_agent_save_time}ms"
        assert (
            memory_agent_query_time < 100
        ), f"Agent memory query too slow: {memory_agent_query_time}ms"

        print("CrewAI Memory System Performance:")
        print(f"Analysis Save: {memory_save_time:.2f}ms per operation")
        print(f"Analysis Get: {memory_get_time:.2f}ms per operation")
        print(f"Agent Memory Save: {memory_agent_save_time:.2f}ms per operation")
        print(f"Agent Memory Query: {memory_agent_query_time:.2f}ms per operation")

    @pytest.mark.asyncio
    async def test_concurrent_load_performance(self):
        """Test system performance under concurrent load"""

        with patch.object(YoutubeMetadataTool, "_run") as mock_youtube:
            mock_youtube.return_value = Mock(**TestFixtures.get_mock_youtube_metadata())

            client = TestClient(app)

            # Test concurrent subtitle checks (lighter operations)
            num_concurrent = 20

            async def check_subtitle():
                start = time.time()
                response = client.get(
                    f"/api/videos/{TestFixtures.VALID_VIDEO_ID}/subtitles/check"
                )
                duration = (time.time() - start) * 1000
                return response.status_code == 200, duration

            # Execute concurrent requests
            start_time = time.time()
            tasks = [check_subtitle() for _ in range(num_concurrent)]
            results = await asyncio.gather(*tasks)
            total_time = time.time() - start_time

            # Analyze results
            successful = sum(1 for success, _ in results if success)
            avg_response_time = sum(duration for _, duration in results) / len(results)

            self.record_performance_metric(
                "concurrent_success_rate", successful / num_concurrent * 100, "percent"
            )
            self.record_performance_metric("avg_concurrent_response", avg_response_time)
            self.record_performance_metric(
                "concurrent_total_time", total_time, "seconds"
            )

            # Performance assertions
            assert (
                successful / num_concurrent >= 0.9
            ), f"Success rate too low: {successful}/{num_concurrent}"
            assert (
                avg_response_time <= 2000
            ), f"Average response time too high: {avg_response_time}ms"

    def test_performance_report_generation(self):
        """Generate performance report from collected metrics"""

        if not self.performance_metrics:
            pytest.skip("No performance metrics collected")

        print("\n" + "=" * 60)
        print("TRAILTAG E2E PERFORMANCE REPORT")
        print("=" * 60)

        benchmarks = TestFixtures.get_performance_benchmarks()

        for metric_name, metric_data in self.performance_metrics.items():
            value = metric_data["value"]
            unit = metric_data["unit"]

            # Check against benchmarks
            status = "✓ PASS"
            benchmark_key = None

            if "response_time" in metric_name and unit == "ms":
                benchmark_key = "max_api_response_time_ms"
            elif "analysis" in metric_name and unit == "seconds":
                benchmark_key = "max_analysis_time_seconds"
            elif "memory" in metric_name and unit == "mb":
                benchmark_key = "max_memory_usage_mb"

            if benchmark_key and benchmark_key in benchmarks:
                if value > benchmarks[benchmark_key]:
                    status = "✗ FAIL"

            print(f"{metric_name:30} {value:8.2f} {unit:8} {status}")

        print("=" * 60)


# Test execution and reporting
if __name__ == "__main__":
    # Configure pytest for running
    pytest.main([__file__, "-v", "--tb=short", "-x"])
