import pytest

import os
from unittest.mock import patch, MagicMock
from trailtag.main import run

from dotenv import load_dotenv

load_dotenv(override=True)

AGENTOPS_API_KEY = os.getenv("AGENTOPS_API_KEY")


@pytest.fixture
def mock_environment(monkeypatch):
    """
    Fixture to mock environment variables required for tests.

    Sets the AGENTOPS_API_KEY environment variable to ensure the tested functions
    have access to the necessary API key during execution.
    Raises an error if AGENTOPS_API_KEY is not set.
    """
    # Mock environment variables
    if AGENTOPS_API_KEY is None:
        raise RuntimeError("AGENTOPS_API_KEY is not set in the environment.")
    monkeypatch.setenv("AGENTOPS_API_KEY", AGENTOPS_API_KEY)


@patch("trailtag.main.agentops")
@patch("trailtag.main.Trailtag")
def test_run_success(mock_trailtag, mock_agentops, mock_environment):
    # Mock AgentOps methods
    mock_agentops.init = MagicMock()
    mock_agentops.start_trace = MagicMock(return_value="mock_trace_context")
    mock_agentops.end_trace = MagicMock()

    # Mock Trailtag methods
    mock_crew = MagicMock()
    mock_crew.kickoff = MagicMock()
    mock_trailtag.return_value.crew.return_value = mock_crew

    # Run the function
    run()

    # Assertions
    mock_agentops.init.assert_called_once_with(
        api_key=AGENTOPS_API_KEY, auto_start_session=False
    )
    mock_agentops.start_trace.assert_called_once_with(
        trace_name="Joke Generator Workflow"
    )
    mock_crew.kickoff.assert_called_once_with(inputs={"topic": "律師"})
    mock_agentops.end_trace.assert_called_once_with(
        trace_context="mock_trace_context", end_state="SUCCESS"
    )


@patch("trailtag.main.agentops")
@patch("trailtag.main.Trailtag")
def test_run_failure(mock_trailtag, mock_agentops, mock_environment):
    # Mock AgentOps methods
    mock_agentops.init = MagicMock()
    mock_agentops.start_trace = MagicMock(return_value="mock_trace_context")
    mock_agentops.end_trace = MagicMock()

    # Mock Trailtag methods to raise an exception
    mock_crew = MagicMock()
    mock_crew.kickoff = MagicMock(side_effect=Exception("Test exception"))
    mock_trailtag.return_value.crew.return_value = mock_crew

    # Run the function and assert exception
    with pytest.raises(
        Exception, match="An error occurred while running the crew: Test exception"
    ):
        run()

    # Assertions
    mock_agentops.init.assert_called_once_with(
        api_key=AGENTOPS_API_KEY, auto_start_session=False
    )
    mock_agentops.start_trace.assert_called_once_with(
        trace_name="Joke Generator Workflow"
    )
    mock_crew.kickoff.assert_called_once_with(inputs={"topic": "律師"})
    mock_agentops.end_trace.assert_called_once_with(
        trace_context="mock_trace_context", end_state="FAILED"
    )
