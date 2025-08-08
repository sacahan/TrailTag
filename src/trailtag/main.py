#!/usr/bin/env python
import sys
import os
import agentops
import warnings
from dotenv import load_dotenv
from trailtag.crew import Trailtag


warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")
os.makedirs("outputs", exist_ok=True)
load_dotenv(override=True)

AGENTOPS_API_KEY = os.getenv("AGENTOPS_API_KEY")


def run():
    """
    Run the crew.
    """

    agentops.init(
        api_key=AGENTOPS_API_KEY, auto_start_session=False
    )  # Initialize AgentOps with the API key
    trace_context = agentops.start_trace(trace_name="TrailTag Workflow")

    try:
        inputs = {
            "youtube_video_url": "https://www.youtube.com/watch?v=SlRSbihlytQ",
            "video_subject": "景點與美食",
        }
        Trailtag().crew().kickoff(inputs=inputs)

        agentops.end_trace(trace_context=trace_context, end_state="SUCCESS")
    except Exception as e:
        agentops.end_trace(trace_context=trace_context, end_state="FAILED")
        raise Exception(f"An error occurred while running the crew: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage: python main.py")
        print("Run the Trailtag crew with the default inputs.")
    else:
        run()
        print("Trailtag crew has been successfully executed.")
        print("Check the output file 'report.md' for the results.")
