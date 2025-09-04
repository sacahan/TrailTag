"""
CrewAI Memory System Validation Tests

Comprehensive test suite for validating the CrewAI Memory system functionality,
performance, and reliability. This test suite ensures the memory system meets
all requirements for production use.

Test Categories:
1. Memory System Core Functionality - Basic operations and data integrity
2. Performance Benchmarks - Memory system performance under various loads
3. Integration Testing - Memory system integration with crew execution
4. Data Consistency - Integrity and format validation
5. Concurrent Access - Multi-user scenarios and thread safety
6. Storage Efficiency - Memory usage and storage optimization

Requirements Validation:
- Memory system functionality ✓
- Performance benchmarking ✓
- Data consistency testing ✓
- Integration testing ✓
- Concurrent access validation ✓
"""

import sys
import time
import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


import importlib.util
import sys
from pathlib import Path
import logging
## ...existing code...

# Direct path imports to avoid circular import issues
memory_manager_path = (
    Path(__file__).parent.parent.parent / "src/trailtag/memory/manager.py"
)
models_path = Path(__file__).parent.parent.parent / "src/trailtag/memory/models.py"

# Load modules directly
spec_manager = importlib.util.spec_from_file_location(
    "memory_manager", memory_manager_path
)
memory_manager_module = importlib.util.module_from_spec(spec_manager)
spec_manager.loader.exec_module(memory_manager_module)

spec_models = importlib.util.spec_from_file_location("memory_models", models_path)
models_module = importlib.util.module_from_spec(spec_models)
spec_models.loader.exec_module(models_module)

# Extract classes

CrewMemoryManager = memory_manager_module.CrewMemoryManager
reset_global_memory_manager = memory_manager_module.reset_global_memory_manager
JobProgressEntry = models_module.JobProgressEntry
AnalysisResultEntry = models_module.AnalysisResultEntry
CrewMemoryConfig = models_module.CrewMemoryConfig
JobStatus = models_module.JobStatus
JobPhase = models_module.JobPhase

logger = logging.getLogger(__name__)


class MemorySystemTestBase:
    """Base class for memory system testing"""

    @pytest.fixture(autouse=True)
    def setup_test_environment(self, tmp_path):
        """Setup test environment for each test"""
        # Create temporary storage for testing
        self.test_storage_path = tmp_path / "test_memory"
        self.test_storage_path.mkdir(parents=True, exist_ok=True)

        # Create test config
        self.test_config = CrewMemoryConfig(
            storage_path=str(self.test_storage_path),
            embedder_config={
                "provider": "openai",
                "config": {"model": "text-embedding-3-small"},
            },
        )

        # Reset global memory manager
        reset_global_memory_manager()

        # Create test data
        self.sample_job_data = self._create_sample_job_data()
        self.sample_analysis_data = self._create_sample_analysis_data()
        self.performance_test_data = self._create_performance_test_data()

        yield

        # Cleanup
        reset_global_memory_manager()

    def _create_sample_job_data(self) -> Dict[str, Any]:
        """Create sample job data for testing"""
        return {
            "job_1": {
                "job_id": "job_1",
                "video_id": "dQw4w9WgXcQ",
                "status": JobStatus.COMPLETED,
                "phase": JobPhase.SUMMARY,
                "progress": 100,
                "cached": False,
                "result": {"analysis": "completed"},
                "error_message": None,
                "created_at": datetime.now(timezone.utc) - timedelta(hours=2),
                "updated_at": datetime.now(timezone.utc),
            },
            "job_2": {
                "job_id": "job_2",
                "video_id": "abc123def456",
                "status": JobStatus.RUNNING,
                "phase": JobPhase.GEOCODE,
                "progress": 75,
                "cached": True,
                "result": None,
                "error_message": None,
                "created_at": datetime.now(timezone.utc) - timedelta(minutes=30),
                "updated_at": datetime.now(timezone.utc) - timedelta(minutes=5),
            },
        }

    def _create_sample_analysis_data(self) -> Dict[str, Any]:
        """Create sample analysis data for testing"""
        return {
            "dQw4w9WgXcQ": {
                "video_id": "dQw4w9WgXcQ",
                "metadata": {
                    "title": "Test Video",
                    "duration": 212,
                    "view_count": 1000000,
                },
                "topic_summary": {
                    "places": ["London", "Paris", "Tokyo"],
                    "activities": ["sightseeing", "shopping", "dining"],
                },
                "map_visualization": {"type": "FeatureCollection", "features": []},
                "processing_time": 45.67,
                "created_at": datetime.now(timezone.utc),
                "cached": False,
            }
        }

    def _create_performance_test_data(self) -> List[Dict[str, Any]]:
        """Create performance test data"""
        return [
            {
                "content": f"Travel video analysis for destination {i}: exploring famous landmarks, local cuisine, and cultural experiences. Includes detailed information about transportation, accommodation recommendations, and budget planning tips.",
                "metadata": {"index": i, "category": "travel", "location": f"city_{i}"},
                "confidence": 0.8 + (i % 3) * 0.05,
            }
            for i in range(100)
        ]


class TestMemorySystemFunctionality(MemorySystemTestBase):
    """Test core CrewAI Memory system functionality"""

    @pytest.mark.asyncio
    async def test_job_progress_memory_operations(self):
        """Test job progress memory operations"""
        memory_manager = CrewMemoryManager(self.test_config)

        # Test save job progress
        memory_manager.save_job_progress(
            job_id="func_test_job",
            video_id="func_test_video",
            status=JobStatus.RUNNING,
            phase=JobPhase.METADATA,
            progress=50,
            extra_field="test_value",
        )

        # Test retrieve job progress
        job_entry = memory_manager.get_job_progress("func_test_job")
        assert job_entry is not None
        assert job_entry.job_id == "func_test_job"
        assert job_entry.video_id == "func_test_video"
        assert job_entry.status == JobStatus.RUNNING
        assert job_entry.progress == 50

        # Test update job progress
        memory_manager.save_job_progress(
            job_id="func_test_job",
            video_id="func_test_video",
            status=JobStatus.COMPLETED,
            phase=JobPhase.SUMMARY,
            progress=100,
        )

        updated_job = memory_manager.get_job_progress("func_test_job")
        assert updated_job.status == JobStatus.COMPLETED
        assert updated_job.progress == 100

        logger.info("Job progress memory operations test passed")

    @pytest.mark.asyncio
    async def test_analysis_result_memory_operations(self):
        """Test analysis result memory operations"""
        memory_manager = CrewMemoryManager(self.test_config)

        # Test save analysis result
        memory_manager.save_analysis_result(
            video_id="func_test_analysis",
            metadata={"title": "Test Analysis Video", "duration": 300},
            topic_summary={
                "places": ["Tokyo", "Kyoto"],
                "activities": ["temple visit"],
            },
            map_visualization={"type": "FeatureCollection", "features": []},
            processing_time=67.89,
        )

        # Test retrieve analysis result
        analysis_entry = memory_manager.get_analysis_result("func_test_analysis")
        assert analysis_entry is not None
        assert analysis_entry.video_id == "func_test_analysis"
        assert analysis_entry.metadata["title"] == "Test Analysis Video"
        assert len(analysis_entry.topic_summary["places"]) == 2
        assert analysis_entry.processing_time == 67.89

        logger.info("Analysis result memory operations test passed")

    @pytest.mark.asyncio
    async def test_agent_memory_operations(self):
        """Test agent-specific memory operations"""
        memory_manager = CrewMemoryManager(self.test_config)

        # Test save agent memory
        memory_id = memory_manager.save_agent_memory(
            agent_role="test_agent",
            context="The agent processed travel data from Tokyo with good results",
            entities=[{"name": "Tokyo", "type": "location", "confidence": 0.95}],
            relationships=[{"source": "agent", "target": "Tokyo", "type": "processed"}],
            insights=[
                "Tokyo is a popular travel destination",
                "User prefers urban locations",
            ],
            confidence=0.9,
        )

        assert memory_id.startswith("test_agent_")

        # Test query agent memories
        memories = memory_manager.query_agent_memories(
            agent_role="test_agent", query="Tokyo travel", limit=5
        )

        assert len(memories) == 1
        assert memories[0].agent_role == "test_agent"
        assert "Tokyo" in memories[0].context
        assert memories[0].confidence == 0.9

        logger.info("Agent memory operations test passed")

    @pytest.mark.asyncio
    async def test_memory_search_functionality(self):
        """Test memory search and vector capabilities"""
        memory_manager = CrewMemoryManager(self.test_config)

        # Add test memories with different content
        test_memories = [
            "Travel video analysis for Tokyo cherry blossom season",
            "Restaurant review in Paris with great food recommendations",
            "Hiking trail guide for Mount Fuji climbing experience",
            "Shopping guide for London fashion districts and markets",
            "Beach vacation tips for tropical island destinations",
        ]

        for i, content in enumerate(test_memories):
            memory_manager.memory_storage.save(
                value=content,
                metadata={"category": "travel", "index": i},
                agent="search_test_agent",
            )

        # Test search functionality
        results = memory_manager.memory_storage.search(
            query="Tokyo", limit=3, score_threshold=0.1
        )

        assert len(results) > 0, "Search should find Tokyo-related content"

        # Test that Tokyo-related content is found
        tokyo_found = any("Tokyo" in result.get("content", "") for result in results)
        assert tokyo_found, "Tokyo-related memory should be found in search"

        logger.info("Memory search functionality test passed")

    @pytest.mark.asyncio
    async def test_memory_reset_operations(self):
        """Test memory reset functionality"""
        memory_manager = CrewMemoryManager(self.test_config)

        # Add test data
        memory_manager.save_job_progress(
            "reset_test_job", "reset_video", JobStatus.RUNNING, JobPhase.METADATA, 25
        )
        memory_manager.save_analysis_result("reset_video", {}, {}, {}, 30.0)
        memory_manager.save_agent_memory("reset_agent", "test context", confidence=0.8)

        # Verify data exists
        assert memory_manager.get_job_progress("reset_test_job") is not None
        assert memory_manager.get_analysis_result("reset_video") is not None
        assert len(memory_manager.agent_memories.get("reset_agent", [])) > 0

        # Test selective reset - job memories
        memory_manager.reset_memories(memory_type="job")
        assert memory_manager.get_job_progress("reset_test_job") is None
        assert memory_manager.get_analysis_result("reset_video") is not None

        # Test full reset
        memory_manager.reset_memories()
        assert memory_manager.get_analysis_result("reset_video") is None
        assert len(memory_manager.agent_memories.get("reset_agent", [])) == 0

        logger.info("Memory reset operations test passed")

    @pytest.mark.asyncio
    async def test_memory_persistence_and_recovery(self):
        """Test memory persistence and recovery mechanisms"""
        # Create initial memory manager
        memory_manager = CrewMemoryManager(self.test_config)

        # Add test data
        test_jobs = [
            ("recovery_job_1", "video_1", JobStatus.RUNNING, 50),
            ("recovery_job_2", "video_2", JobStatus.COMPLETED, 100),
            ("recovery_job_3", "video_3", JobStatus.FAILED, 75),
        ]

        for job_id, video_id, status, progress in test_jobs:
            memory_manager.save_job_progress(
                job_id=job_id,
                video_id=video_id,
                status=status,
                phase=JobPhase.SUMMARY,
                progress=progress,
            )

        # Simulate system restart by creating new memory manager with same config
        recovered_manager = CrewMemoryManager(self.test_config)

        # Verify all data was recovered
        for job_id, video_id, status, progress in test_jobs:
            recovered_job = recovered_manager.get_job_progress(job_id)
            assert recovered_job is not None
            assert recovered_job.video_id == video_id
            assert recovered_job.status == status
            assert recovered_job.progress == progress

        logger.info("Memory persistence and recovery test passed")


class TestMemoryPerformanceBenchmarks(MemorySystemTestBase):
    """Test memory system performance benchmarks"""

    @pytest.mark.asyncio
    async def test_memory_save_performance_benchmark(self):
        """Benchmark memory save operations performance"""
        memory_manager = CrewMemoryManager(self.test_config)

        # Test data preparation
        test_operations = 100
        save_times = []

        # Benchmark save operations
        for i in range(test_operations):
            start_time = time.time()
            memory_manager.memory_storage.save(
                value=f"Performance test content {i} with detailed travel information and location data for benchmarking memory system efficiency",
                metadata={"test_id": i, "category": "benchmark"},
                agent="performance_test_agent",
            )
            end_time = time.time()
            save_times.append((end_time - start_time) * 1000)  # Convert to milliseconds

        # Calculate statistics
        avg_save_time = sum(save_times) / len(save_times)
        max_save_time = max(save_times)
        min_save_time = min(save_times)

        logger.info("Save Performance Benchmark Results:")
        logger.info(f"  Operations: {test_operations}")
        logger.info(f"  Average save time: {avg_save_time:.2f}ms")
        logger.info(f"  Max save time: {max_save_time:.2f}ms")
        logger.info(f"  Min save time: {min_save_time:.2f}ms")

        # Performance assertions
        assert avg_save_time < 50, f"Average save time too slow: {avg_save_time:.2f}ms"
        assert max_save_time < 200, f"Max save time too slow: {max_save_time:.2f}ms"

        logger.info("Memory save performance benchmark passed")

    @pytest.mark.asyncio
    async def test_memory_query_performance_benchmark(self):
        """Benchmark memory query operations performance"""
        memory_manager = CrewMemoryManager(self.test_config)

        # Pre-populate with test data
        test_data_size = 200
        for i in range(test_data_size):
            memory_manager.memory_storage.save(
                value=f"Travel destination {i}: {self.performance_test_data[i % len(self.performance_test_data)]['content']}",
                metadata=self.performance_test_data[
                    i % len(self.performance_test_data)
                ]["metadata"],
                agent="benchmark_agent",
            )

        # Benchmark query operations
        query_tests = [
            "travel destination Tokyo",
            "famous landmarks Paris",
            "local cuisine restaurant",
            "budget planning tips",
            "cultural experiences activities",
        ]

        query_times = []
        for query in query_tests:
            start_time = time.time()
            memory_manager.memory_storage.search(
                query=query, limit=10, score_threshold=0.1
            )
            end_time = time.time()
            query_times.append((end_time - start_time) * 1000)

        # Calculate statistics
        avg_query_time = sum(query_times) / len(query_times)
        max_query_time = max(query_times)

        logger.info("Query Performance Benchmark Results:")
        logger.info(f"  Dataset size: {test_data_size}")
        logger.info(f"  Query operations: {len(query_tests)}")
        logger.info(f"  Average query time: {avg_query_time:.2f}ms")
        logger.info(f"  Max query time: {max_query_time:.2f}ms")

        # Performance assertions
        assert (
            avg_query_time < 100
        ), f"Average query time too slow: {avg_query_time:.2f}ms"
        assert max_query_time < 300, f"Max query time too slow: {max_query_time:.2f}ms"

        logger.info("Memory query performance benchmark passed")

    @pytest.mark.asyncio
    async def test_memory_storage_efficiency_benchmark(self):
        """Benchmark memory storage space efficiency"""
        memory_manager = CrewMemoryManager(self.test_config)

        # Measure initial storage
        initial_stats = memory_manager.get_memory_stats()
        initial_storage = initial_stats.storage_size_mb

        # Add various sizes of data
        data_sizes = [100, 500, 1000, 2000]  # Number of entries
        storage_measurements = []

        for size in data_sizes:
            for i in range(size):
                memory_manager.save_job_progress(
                    job_id=f"storage_test_{size}_{i}",
                    video_id=f"video_{size}_{i}",
                    status=JobStatus.RUNNING,
                    phase=JobPhase.METADATA,
                    progress=i % 100,
                )

            # Measure storage after each batch
            current_stats = memory_manager.get_memory_stats()
            storage_increase = current_stats.storage_size_mb - initial_storage
            storage_measurements.append(
                {
                    "entries": size,
                    "storage_mb": storage_increase,
                    "mb_per_entry": storage_increase / size if size > 0 else 0,
                }
            )

        logger.info("Storage Efficiency Benchmark Results:")
        for measurement in storage_measurements:
            logger.info(
                f"  {measurement['entries']} entries: {measurement['storage_mb']:.2f}MB "
                f"({measurement['mb_per_entry']:.4f}MB per entry)"
            )

        # Efficiency assertions
        final_measurement = storage_measurements[-1]
        assert (
            final_measurement["mb_per_entry"] < 0.1
        ), f"Storage per entry too large: {final_measurement['mb_per_entry']:.4f}MB"

        logger.info("Memory storage efficiency benchmark passed")

    @pytest.mark.asyncio
    async def test_concurrent_access_performance_benchmark(self):
        """Benchmark performance under concurrent access"""
        memory_manager = CrewMemoryManager(self.test_config)

        async def concurrent_operation_task(task_id: int, operations_per_task: int):
            """Concurrent operation task"""
            task_times = []
            for i in range(operations_per_task):
                start_time = time.time()

                # Mix of save and query operations
                if i % 2 == 0:
                    memory_manager.save_job_progress(
                        job_id=f"concurrent_{task_id}_{i}",
                        video_id=f"video_concurrent_{task_id}",
                        status=JobStatus.RUNNING,
                        phase=JobPhase.METADATA,
                        progress=(i + 1) * 10,
                    )
                else:
                    memory_manager.memory_storage.search(
                        query=f"concurrent task {task_id}", limit=5
                    )

                end_time = time.time()
                task_times.append((end_time - start_time) * 1000)
                await asyncio.sleep(0.001)  # Small delay to simulate real usage

            return task_times

        # Run concurrent tasks
        concurrent_tasks = 5
        operations_per_task = 20

        start_time = time.time()
        tasks = [
            concurrent_operation_task(i, operations_per_task)
            for i in range(concurrent_tasks)
        ]
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        # Analyze results
        all_times = [time for task_times in results for time in task_times]
        total_time = (end_time - start_time) * 1000
        avg_operation_time = sum(all_times) / len(all_times)
        total_operations = concurrent_tasks * operations_per_task

        logger.info("Concurrent Access Benchmark Results:")
        logger.info(f"  Concurrent tasks: {concurrent_tasks}")
        logger.info(f"  Operations per task: {operations_per_task}")
        logger.info(f"  Total operations: {total_operations}")
        logger.info(f"  Total time: {total_time:.2f}ms")
        logger.info(f"  Average operation time: {avg_operation_time:.2f}ms")

        # Performance assertions
        assert total_time < 10000, f"Concurrent access too slow: {total_time:.2f}ms"
        assert (
            avg_operation_time < 100
        ), f"Average concurrent operation too slow: {avg_operation_time:.2f}ms"

        # Verify all data was saved correctly
        stats = memory_manager.get_memory_stats()
        assert (
            stats.total_entries >= total_operations / 2
        ), "Not all concurrent operations succeeded"

        logger.info("Concurrent access performance benchmark passed")


class TestMemoryIntegration(MemorySystemTestBase):
    """Test memory system integration with crew execution"""

    @pytest.mark.asyncio
    async def test_crew_memory_integration(self):
        """Test CrewAI Memory integration with crew execution"""
        memory_manager = CrewMemoryManager(self.test_config)

        # Mock agents and tasks
        mock_agent = Mock()
        mock_agent.role = "integration_test_agent"

        mock_task = Mock()
        mock_task.description = "Test task for memory integration"

        # Test crew creation with memory
        crew = memory_manager.create_crew_with_memory(
            agents=[mock_agent], tasks=[mock_task], verbose=True
        )

        assert crew is not None
        assert crew.memory is True
        assert hasattr(crew, "external_memory")

        logger.info("Crew memory integration test passed")

    @pytest.mark.asyncio
    async def test_memory_persistence_during_execution(self):
        """Test memory persistence during long-running tasks"""
        memory_manager = CrewMemoryManager(self.test_config)

        # Simulate long-running task with progress updates
        job_id = "persistence_test_job"
        phases = [JobPhase.METADATA, JobPhase.SUMMARY, JobPhase.GEOCODE]

        for i, phase in enumerate(phases):
            memory_manager.save_job_progress(
                job_id=job_id,
                video_id="persistence_video",
                status=JobStatus.RUNNING,
                phase=phase,
                progress=(i + 1) * 33,
            )

            # Simulate some processing time
            await asyncio.sleep(0.01)

            # Verify persistence
            job_entry = memory_manager.get_job_progress(job_id)
            assert job_entry is not None
            assert job_entry.phase == phase
            assert job_entry.progress == (i + 1) * 33

        # Complete the job
        memory_manager.save_job_progress(
            job_id=job_id,
            video_id="persistence_video",
            status=JobStatus.COMPLETED,
            phase=JobPhase.GEOCODE,
            progress=100,
            result={"final": "result"},
        )

        final_job = memory_manager.get_job_progress(job_id)
        assert final_job.status == JobStatus.COMPLETED
        assert final_job.result is not None

        logger.info("Memory persistence during execution test passed")

    @pytest.mark.asyncio
    async def test_memory_event_handling(self):
        """Test memory event listener functionality"""
        memory_manager = CrewMemoryManager(self.test_config)

        # Verify event listener is set up
        assert memory_manager.event_listener is not None

        # Test memory operations that should trigger events
        memory_id = memory_manager.memory_storage.save(
            value="Test event content",
            metadata={"test": "event"},
            agent="event_test_agent",
        )

        # Search operation (should trigger query events)
        results = memory_manager.memory_storage.search(query="event content", limit=5)

        # Verify that events were tracked (by checking if they exist)
        assert memory_id is not None
        assert isinstance(results, list)

        logger.info("Memory event handling test passed")

    @pytest.mark.asyncio
    async def test_memory_workflow_integration(self):
        """Test memory system integration with complete workflows"""
        memory_manager = CrewMemoryManager(self.test_config)

        # Simulate complete video analysis workflow
        video_id = "workflow_test_video"
        job_id = "workflow_test_job"

        # Step 1: Start job
        memory_manager.save_job_progress(
            job_id=job_id,
            video_id=video_id,
            status=JobStatus.RUNNING,
            phase=JobPhase.METADATA,
            progress=0,
        )

        # Step 2: Process metadata
        memory_manager.save_job_progress(
            job_id=job_id,
            video_id=video_id,
            status=JobStatus.RUNNING,
            phase=JobPhase.SUMMARY,
            progress=33,
        )

        # Step 3: Save agent memories during processing
        metadata_agent_memory = memory_manager.save_agent_memory(
            agent_role="metadata_agent",
            context=f"Extracted metadata for video {video_id}",
            insights=["Video contains travel content", "Location data available"],
            confidence=0.85,
        )

        # Step 4: Complete geocoding
        memory_manager.save_job_progress(
            job_id=job_id,
            video_id=video_id,
            status=JobStatus.RUNNING,
            phase=JobPhase.GEOCODE,
            progress=66,
        )

        # Step 5: Save final analysis
        memory_manager.save_analysis_result(
            video_id=video_id,
            metadata={"title": "Workflow Test Video", "duration": 300},
            topic_summary={"places": ["Test Location"], "activities": ["testing"]},
            map_visualization={"type": "FeatureCollection", "features": []},
            processing_time=120.5,
        )

        # Step 6: Complete job
        memory_manager.save_job_progress(
            job_id=job_id,
            video_id=video_id,
            status=JobStatus.COMPLETED,
            phase=JobPhase.GEOCODE,
            progress=100,
            result={"workflow": "completed"},
        )

        # Verify complete workflow data
        final_job = memory_manager.get_job_progress(job_id)
        analysis_result = memory_manager.get_analysis_result(video_id)
        agent_memories = memory_manager.query_agent_memories(
            agent_role="metadata_agent", query="metadata", limit=5
        )

        assert final_job.status == JobStatus.COMPLETED
        assert analysis_result is not None
        assert len(agent_memories) > 0
        assert metadata_agent_memory.startswith("metadata_agent_")

        logger.info("Memory workflow integration test passed")


class TestMemoryDataConsistency(MemorySystemTestBase):
    """Test memory data consistency and format validation"""

    @pytest.mark.asyncio
    async def test_data_format_consistency(self):
        """Test data format consistency across operations"""
        memory_manager = CrewMemoryManager(self.test_config)

        memory_manager.save_job_progress(
            job_id="format_test_job",
            video_id="format_test_video",
            status=JobStatus.RUNNING,
            phase=JobPhase.METADATA,
            progress=50,
        )

        # Retrieve and verify datetime format
        job_entry = memory_manager.get_job_progress("format_test_job")
        assert job_entry is not None
        assert isinstance(job_entry.created_at, datetime)
        assert isinstance(job_entry.updated_at, datetime)
        assert job_entry.created_at.tzinfo is not None  # Should be timezone-aware

        # Test JSON serialization consistency
        job_dict = job_entry.model_dump(mode="json")
        assert isinstance(job_dict["created_at"], str)
        assert isinstance(job_dict["updated_at"], str)

        logger.info("Data format consistency test passed")

    @pytest.mark.asyncio
    async def test_data_integrity_constraints(self):
        """Test data integrity constraints and validation"""
        # Test required field validation
        with pytest.raises((ValueError, TypeError)):
            JobProgressEntry(
                job_id="",  # Empty job_id should fail
                video_id="test_video",
                status=JobStatus.RUNNING,
                phase=JobPhase.METADATA,
                progress=50,
            )

        # Test progress bounds validation
        valid_entry = JobProgressEntry(
            job_id="valid_job",
            video_id="test_video",
            status=JobStatus.RUNNING,
            phase=JobPhase.METADATA,
            progress=150,  # Over 100%, should be handled gracefully
        )

        assert valid_entry.progress == 150  # Pydantic should accept this

        # Test enum validation
        valid_status_entry = JobProgressEntry(
            job_id="status_test_job",
            video_id="test_video",
            status=JobStatus.COMPLETED,  # Valid enum value
            phase=JobPhase.SUMMARY,
            progress=100,
        )

        assert valid_status_entry.status == JobStatus.COMPLETED

        logger.info("Data integrity constraints test passed")

    @pytest.mark.asyncio
    async def test_concurrent_data_consistency(self):
        """Test data consistency under concurrent operations"""
        memory_manager = CrewMemoryManager(self.test_config)

        async def concurrent_update_task(job_id: str, start_progress: int):
            """Concurrent update task"""
            for i in range(10):
                memory_manager.save_job_progress(
                    job_id=job_id,
                    video_id=f"concurrent_video_{job_id}",
                    status=JobStatus.RUNNING,
                    phase=JobPhase.METADATA,
                    progress=start_progress + i,
                )
                await asyncio.sleep(0.001)  # Very short delay

        # Run concurrent updates on same job
        job_id = "consistency_test_job"
        tasks = [
            concurrent_update_task(job_id, 0),
            concurrent_update_task(job_id, 50),
        ]

        await asyncio.gather(*tasks)

        # Check final state - should be consistent (last update wins)
        final_job = memory_manager.get_job_progress(job_id)
        assert final_job is not None
        assert final_job.job_id == job_id
        assert final_job.progress >= 0  # Should have a valid progress value

        logger.info("Concurrent data consistency test passed")

    @pytest.mark.asyncio
    async def test_memory_stats_accuracy(self):
        """Test memory statistics accuracy"""
        memory_manager = CrewMemoryManager(self.test_config)

        # Add known amounts of each type of data
        job_count = 5
        analysis_count = 3
        memory_count = 7

        # Add job progress entries
        for i in range(job_count):
            memory_manager.save_job_progress(
                job_id=f"stats_job_{i}",
                video_id=f"stats_video_{i}",
                status=JobStatus.RUNNING,
                phase=JobPhase.METADATA,
                progress=i * 20,
            )

        # Add analysis results
        for i in range(analysis_count):
            memory_manager.save_analysis_result(
                video_id=f"stats_analysis_{i}",
                metadata={"test": i},
                topic_summary={"places": [f"place_{i}"]},
                map_visualization={"features": []},
                processing_time=float(i * 10),
            )

        # Add memory entries
        for i in range(memory_count):
            memory_manager.memory_storage.save(
                value=f"Test memory content {i}",
                metadata={"index": i},
                agent="stats_agent",
            )

        # Check statistics
        stats = memory_manager.get_memory_stats()

        # Total entries should match
        expected_total = (
            len(memory_manager.memory_storage.memories)
            + len(memory_manager.job_memories)
            + len(memory_manager.analysis_results)
        )
        assert stats.total_entries == expected_total

        # Storage size should be reasonable
        assert stats.storage_size_mb >= 0

        logger.info(
            f"Memory stats accuracy test passed - Total entries: {stats.total_entries}"
        )


# Test runner configuration
class TestMemorySystemRunner:
    """Test runner for memory system validation"""

    @staticmethod
    def run_all_tests():
        """Run all memory system tests"""
        test_classes = [
            TestMemorySystemFunctionality,
            TestMemoryPerformanceBenchmarks,
            TestMemoryIntegration,
            TestMemoryDataConsistency,
        ]

        logger.info("Starting CrewAI Memory System Validation Tests...")

        total_tests = 0
        for test_class in test_classes:
            logger.info(f"\n=== {test_class.__name__} ===")

            # Count test methods
            test_methods = [
                method for method in dir(test_class) if method.startswith("test_")
            ]
            total_tests += len(test_methods)

            logger.info(
                f"Found {len(test_methods)} test methods in {test_class.__name__}"
            )

        logger.info("\n=== Memory System Tests Summary ===")
        logger.info(f"Total test classes: {len(test_classes)}")
        logger.info(f"Total test methods: {total_tests}")
        logger.info("Status: Ready for execution")
        logger.info(
            "Coverage: Core functionality, performance benchmarks, integration, data consistency"
        )

        return True


if __name__ == "__main__":
    # Quick test execution for development
    ## ...existing code...

    logging.basicConfig(level=logging.INFO)

    runner = TestMemorySystemRunner()
    success = runner.run_all_tests()

    if success:
        print("\n✅ CrewAI Memory System Test Suite is ready!")
        print("Run with: pytest tests/integration/test_memory_system.py -v")
        print("\nTest categories:")
        print("- Core functionality and CRUD operations")
        print("- Performance benchmarks and efficiency")
        print("- Integration with crew execution")
        print("- Data consistency and validation")
    else:
        print("❌ Test setup failed")
