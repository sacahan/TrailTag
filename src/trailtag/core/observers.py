"""
TrailTag CrewAI Observers 模組
提供 CrewAI 執行過程的監控和觀測功能
"""

import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field

from crewai.agent import Agent
from crewai.task import Task
from crewai.crew import Crew

# 移除不存在的 CrewAI 內部導入，使用通用事件處理
from src.api.logger_config import get_logger
from src.api.observability import trace, record_metric

logger = get_logger(__name__)


@dataclass
class AgentExecutionMetric:
    """Agent 執行指標數據模型"""

    agent_name: str
    task_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    status: str = "running"
    token_usage: Dict[str, int] = field(default_factory=dict)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def complete(self, status: str = "completed", error: str = None):
        """標記執行完成"""
        self.end_time = datetime.now(timezone.utc)
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        self.status = status
        if error:
            self.error_message = error


@dataclass
class CrewExecutionSummary:
    """Crew 執行摘要"""

    crew_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration: float = 0.0
    agent_metrics: List[AgentExecutionMetric] = field(default_factory=list)
    total_tokens: Dict[str, int] = field(
        default_factory=lambda: {"prompt": 0, "completion": 0, "total": 0}
    )
    status: str = "running"


class AgentObserver:
    """CrewAI Agent 觀察者 - 監控 Agent 執行過程"""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.current_executions: Dict[str, AgentExecutionMetric] = {}
        self.execution_history: List[AgentExecutionMetric] = []
        self.crew_summary: Optional[CrewExecutionSummary] = None
        logger.info(
            f"AgentObserver 初始化完成 - 監控狀態: {'啟用' if enabled else '停用'}"
        )

    def on_crew_start(self, crew: Crew, inputs: Dict[str, Any] = None):
        """Crew 開始執行時的回調"""
        if not self.enabled:
            return

        crew_name = getattr(crew, "name", "TrailTagCrew")
        self.crew_summary = CrewExecutionSummary(
            crew_name=crew_name, start_time=datetime.now(timezone.utc)
        )

        logger.info(f"開始監控 Crew 執行: {crew_name}")
        record_metric(
            "crew.started", 1, {"crew_name": crew_name, "inputs": inputs or {}}
        )

    def on_crew_complete(self, crew: Crew, result: Any = None, error: str = None):
        """Crew 執行完成時的回調"""
        if not self.enabled or not self.crew_summary:
            return

        self.crew_summary.end_time = datetime.now(timezone.utc)
        self.crew_summary.total_duration = (
            self.crew_summary.end_time - self.crew_summary.start_time
        ).total_seconds()

        # 統計總 token 使用量
        for metric in self.crew_summary.agent_metrics:
            for key, value in metric.token_usage.items():
                if key in self.crew_summary.total_tokens:
                    self.crew_summary.total_tokens[key] += value

        # 設置最終狀態
        self.crew_summary.status = "error" if error else "completed"

        logger.info(
            f"Crew 執行完成: {self.crew_summary.crew_name} - "
            f"耗時: {self.crew_summary.total_duration:.2f}s - "
            f"狀態: {self.crew_summary.status}"
        )

        # 記錄 Crew 級別指標
        record_metric(
            "crew.completed",
            1,
            {
                "crew_name": self.crew_summary.crew_name,
                "duration": self.crew_summary.total_duration,
                "status": self.crew_summary.status,
                "total_tokens": self.crew_summary.total_tokens,
                "agent_count": len(self.crew_summary.agent_metrics),
            },
        )

    def on_agent_start(self, agent: Agent, task: Task):
        """Agent 開始執行任務時的回調"""
        if not self.enabled:
            return

        agent_name = getattr(agent, "role", agent.__class__.__name__)
        task_name = getattr(task, "description", task.__class__.__name__)[:50]

        execution_id = f"{agent_name}_{task_name}_{int(time.time())}"

        metric = AgentExecutionMetric(
            agent_name=agent_name,
            task_name=task_name,
            start_time=datetime.now(timezone.utc),
            metadata={
                "execution_id": execution_id,
                "agent_config": getattr(agent, "config", {}),
                "task_config": getattr(task, "config", {}),
            },
        )

        self.current_executions[execution_id] = metric

        logger.info(f"Agent 開始執行: {agent_name} -> {task_name}")
        record_metric(
            "agent.task.started", 1, {"agent_name": agent_name, "task_name": task_name}
        )

    def on_agent_complete(
        self, agent: Agent, task: Task, result: Any = None, error: str = None
    ):
        """Agent 完成任務時的回調"""
        if not self.enabled:
            return

        agent_name = getattr(agent, "role", agent.__class__.__name__)
        task_name = getattr(task, "description", task.__class__.__name__)[:50]

        # 找到對應的執行記錄
        execution_metric = None
        for exec_id, metric in self.current_executions.items():
            if metric.agent_name == agent_name and metric.task_name == task_name:
                execution_metric = metric
                break

        if not execution_metric:
            logger.warning(f"找不到對應的執行記錄: {agent_name} -> {task_name}")
            return

        # 完成執行記錄
        status = "error" if error else "completed"
        execution_metric.complete(status=status, error=error)

        # 嘗試提取 token 使用量（如果可用）
        if result and hasattr(result, "token_usage"):
            execution_metric.token_usage = result.token_usage
        elif hasattr(task, "token_usage"):
            execution_metric.token_usage = getattr(task, "token_usage", {})

        # 移動到歷史記錄
        self.execution_history.append(execution_metric)
        if self.crew_summary:
            self.crew_summary.agent_metrics.append(execution_metric)

        # 從當前執行中移除
        execution_id = execution_metric.metadata.get("execution_id")
        if execution_id in self.current_executions:
            del self.current_executions[execution_id]

        logger.info(
            f"Agent 執行完成: {agent_name} -> {task_name} - "
            f"耗時: {execution_metric.duration_seconds:.2f}s - "
            f"狀態: {status}"
        )

        # 記錄 Agent 級別指標
        record_metric(
            "agent.task.completed",
            1,
            {
                "agent_name": agent_name,
                "task_name": task_name,
                "duration": execution_metric.duration_seconds,
                "status": status,
                "token_usage": execution_metric.token_usage,
            },
        )

    def on_agent_event(self, event: Dict[str, Any]):
        """處理 Agent 事件"""
        if not self.enabled:
            return

        event_type = event.get("type", "unknown")
        agent_name = event.get("agent_name", "unknown")

        logger.debug(f"Agent 事件: {agent_name} - {event_type}")

        # 記錄特定事件指標
        if event_type == "tool_usage":
            tool_name = event.get("tool_name", "unknown")
            record_metric(
                "agent.tool.used", 1, {"agent_name": agent_name, "tool_name": tool_name}
            )
        elif event_type == "reasoning":
            reasoning_steps = event.get("steps", 0)
            record_metric(
                "agent.reasoning.steps", reasoning_steps, {"agent_name": agent_name}
            )

    def get_current_status(self) -> Dict[str, Any]:
        """獲取當前執行狀態"""
        return {
            "enabled": self.enabled,
            "crew_summary": asdict(self.crew_summary) if self.crew_summary else None,
            "active_executions": len(self.current_executions),
            "completed_executions": len(self.execution_history),
            "current_executions": [
                asdict(metric) for metric in self.current_executions.values()
            ],
        }

    def get_execution_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """獲取執行歷史記錄"""
        recent_history = (
            self.execution_history[-limit:] if limit > 0 else self.execution_history
        )
        return [asdict(metric) for metric in recent_history]

    def get_performance_summary(self) -> Dict[str, Any]:
        """獲取性能摘要統計"""
        if not self.execution_history:
            return {"message": "暫無執行記錄"}

        # 按 Agent 分組統計
        agent_stats = {}
        total_duration = 0
        total_tokens = {"prompt": 0, "completion": 0, "total": 0}

        for metric in self.execution_history:
            agent_name = metric.agent_name
            if agent_name not in agent_stats:
                agent_stats[agent_name] = {
                    "total_executions": 0,
                    "successful_executions": 0,
                    "failed_executions": 0,
                    "total_duration": 0,
                    "avg_duration": 0,
                    "token_usage": {"prompt": 0, "completion": 0, "total": 0},
                }

            stats = agent_stats[agent_name]
            stats["total_executions"] += 1
            stats["total_duration"] += metric.duration_seconds
            total_duration += metric.duration_seconds

            if metric.status == "completed":
                stats["successful_executions"] += 1
            else:
                stats["failed_executions"] += 1

            # 統計 token 使用量
            for key, value in metric.token_usage.items():
                if key in stats["token_usage"]:
                    stats["token_usage"][key] += value
                if key in total_tokens:
                    total_tokens[key] += value

        # 計算平均值
        for stats in agent_stats.values():
            if stats["total_executions"] > 0:
                stats["avg_duration"] = (
                    stats["total_duration"] / stats["total_executions"]
                )

        return {
            "total_executions": len(self.execution_history),
            "total_duration": total_duration,
            "total_tokens": total_tokens,
            "agent_statistics": agent_stats,
            "crew_summary": asdict(self.crew_summary) if self.crew_summary else None,
        }


class CrewObserverMixin:
    """CrewAI Crew 觀察者混入類別 - 為 Crew 添加觀察能力"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.observer = AgentObserver()

    @trace("crew.kickoff")
    def kickoff(self, inputs: Dict[str, Any] = None):
        """覆蓋 kickoff 方法以添加觀察功能"""
        self.observer.on_crew_start(self, inputs)

        try:
            result = super().kickoff(inputs)
            self.observer.on_crew_complete(self, result)
            return result
        except Exception as e:
            self.observer.on_crew_complete(self, error=str(e))
            raise

    @trace("crew.kickoff_async")
    async def kickoff_async(self, inputs: Dict[str, Any] = None):
        """覆蓋 async kickoff 方法以添加觀察功能"""
        self.observer.on_crew_start(self, inputs)

        try:
            result = await super().kickoff_async(inputs)
            self.observer.on_crew_complete(self, result)
            return result
        except Exception as e:
            self.observer.on_crew_complete(self, error=str(e))
            raise


# 全域觀察者實例
global_observer = AgentObserver()


def get_global_observer() -> AgentObserver:
    """獲取全域觀察者實例"""
    return global_observer


def create_observer(enabled: bool = True) -> AgentObserver:
    """創建新的觀察者實例"""
    return AgentObserver(enabled=enabled)
