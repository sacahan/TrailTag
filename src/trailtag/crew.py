from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List


@CrewBase
class Trailtag:
    """Trailtag crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    @agent
    def joke_generator(self) -> Agent:
        return Agent(
            config=self.agents_config["joke_generator"],
            verbose=True,  # type: ignore[index]
        )

    @agent
    def joke_reviewer(self) -> Agent:
        return Agent(
            config=self.agents_config["joke_reviewer"],  # type: ignore[index]
            verbose=True,
        )

    @task
    def make_joke_task(self) -> Task:
        return Task(
            config=self.tasks_config["make_joke_task"],  # type: ignore[index]
        )

    @task
    def review_joke_task(self) -> Task:
        return Task(
            config=self.tasks_config["review_joke_task"],  # type: ignore[index]
            output_file="outputs/jokes.md",
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Trailtag crew"""

        return Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,  # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )
