"""
phase/task.py — Task definitions and queue management.

A Task flows through PHASE like this:

  PLASMA creates Task (PENDING)
       ↓
  Assigned to a FLUX node (ASSIGNED)
       ↓
  FLUX node works on it (IN_PROGRESS)
       ↓
  FLUX returns a result (AWAITING_VALIDATION)
       ↓
  SOLID votes (APPROVED or REJECTED)
       ↓
  PLASMA receives final result (DONE or FAILED)

All task state transitions are logged to phase/state.py.

Usage:
    from task import Task, TaskQueue, TaskStatus

    queue = TaskQueue()
    task  = Task(
        goal="Write a Python function that parses JSON",
        node_type="coder",
        priority=1,
    )
    await queue.put(task)
    next_task = await queue.get_for_node("coder")
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TaskStatus(str, Enum):
    PENDING             = "pending"
    ASSIGNED            = "assigned"
    IN_PROGRESS         = "in_progress"
    AWAITING_VALIDATION = "awaiting_validation"
    APPROVED            = "approved"
    REJECTED            = "rejected"
    DONE                = "done"
    FAILED              = "failed"
    CANCELLED           = "cancelled"


class TaskPriority(int, Enum):
    URGENT  = 1
    HIGH    = 2
    NORMAL  = 3
    LOW     = 4


@dataclass
class Task:
    goal:           str
    node_type:      str                     # target FLUX node type
    priority:       int          = TaskPriority.NORMAL
    task_id:        str          = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_task_id: Optional[str]= None    # for sub-tasks spawned by PLASMA
    status:         TaskStatus   = TaskStatus.PENDING
    created_at:     float        = field(default_factory=time.time)
    assigned_at:    Optional[float] = None
    completed_at:   Optional[float] = None
    assigned_node:  Optional[str]   = None
    result:         Optional[str]   = None
    error:          Optional[str]   = None
    attempts:       int          = 0
    max_attempts:   int          = 2
    context:        dict         = field(default_factory=dict)  # extra metadata

    def elapsed(self) -> float:
        if self.completed_at:
            return self.completed_at - self.created_at
        return time.time() - self.created_at

    def is_terminal(self) -> bool:
        return self.status in (
            TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED
        )

    def can_retry(self) -> bool:
        return (
            self.status == TaskStatus.FAILED
            and self.attempts < self.max_attempts
        )

    def summary(self) -> str:
        goal_short = self.goal[:60] + "…" if len(self.goal) > 60 else self.goal
        return (
            f"[{self.task_id}] {self.node_type} | {self.status.value} | "
            f"pri={self.priority} | '{goal_short}'"
        )


@dataclass
class ValidationResult:
    task_id:   str
    approved:  bool
    votes:     list[dict]    # [{"validator": "v1", "vote": True, "reason": "..."}]
    consensus: str           # "unanimous" | "majority" | "split" | "rejected"
    feedback:  str           # aggregated feedback for FLUX node improvement


class TaskQueue:
    """
    Priority queue for PHASE tasks.
    PLASMA enqueues. FLUX nodes dequeue by type.
    """

    def __init__(self):
        self._queue:    asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._pending:  dict[str, Task]       = {}   # task_id -> Task
        self._lock:     asyncio.Lock          = asyncio.Lock()

    async def put(self, task: Task) -> None:
        async with self._lock:
            self._pending[task.task_id] = task
        # PriorityQueue sorts by first element of tuple
        await self._queue.put((task.priority, task.created_at, task))

    async def get_for_node(self, node_type: str, timeout: float = 5.0) -> Optional[Task]:
        """
        Get next task for a specific node type.
        Returns None if no matching task within timeout.
        """
        # Collect all items, take the first match, re-queue the rest
        found:    Optional[Task] = None
        requeue:  list           = []

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                pri, ts, task = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.2)
                continue

            if task.node_type == node_type and not task.is_terminal():
                found = task
                break
            else:
                requeue.append((pri, ts, task))

        # Put non-matching tasks back
        for item in requeue:
            await self._queue.put(item)

        if found:
            async with self._lock:
                if found.task_id in self._pending:
                    self._pending[found.task_id].status      = TaskStatus.ASSIGNED
                    self._pending[found.task_id].assigned_at = time.time()
        return found

    async def update(self, task_id: str, **kwargs) -> None:
        async with self._lock:
            if task_id in self._pending:
                for k, v in kwargs.items():
                    if hasattr(self._pending[task_id], k):
                        setattr(self._pending[task_id], k, v)

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._pending.get(task_id)

    def pending_count(self) -> int:
        return sum(
            1 for t in self._pending.values()
            if t.status in (TaskStatus.PENDING, TaskStatus.ASSIGNED)
        )

    def all_tasks(self) -> list[Task]:
        return list(self._pending.values())

    async def cancel(self, task_id: str) -> bool:
        async with self._lock:
            if task_id in self._pending:
                self._pending[task_id].status = TaskStatus.CANCELLED
                return True
        return False


# ── Global queue singleton ────────────────────────────────────────────────────
task_queue = TaskQueue()
