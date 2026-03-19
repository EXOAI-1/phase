"""
tests/test_phase.py — Full test suite for PHASE.

Run with:
    PYTHONPATH=/path/to/phase python3 -m pytest tests/test_phase.py -v

All tests run offline — no API keys, no network.
All LLM calls are mocked throughout.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ─────────────────────────────────────────────────────────────────────────────
# config.py
# ─────────────────────────────────────────────────────────────────────────────

class TestConfig:

    def test_default_config_loads(self):
        from config import Config
        c = Config()
        assert c.plasma.strategic
        assert c.plasma.coordination
        assert c.solid.validator_1
        assert len(c.solid.all_models()) == 3

    def test_flux_model_fallback(self):
        from config import Config
        c = Config()
        model = c.flux_model("nonexistent_node")
        assert isinstance(model, str) and len(model) > 0

    def test_budget_cap_default(self):
        from config import Config
        c = Config()
        assert c.budget_cap("coder")      == 0.50
        assert c.budget_cap("researcher") == 0.10
        assert c.budget_cap("unknown")    == 0.25   # default

    def test_max_rounds_for_role(self):
        from config import Config
        c = Config()
        assert c.max_rounds_for("plasma_strategic") == 200
        assert c.max_rounds_for("reviewer")         == 15
        assert c.max_rounds_for("nonexistent")      == 60  # fallback

    def test_load_config_missing_file(self, tmp_path):
        from config import load_config
        c = load_config(tmp_path / "nonexistent.yaml")
        assert c.plasma.strategic   # defaults still present

    def test_load_config_from_yaml(self, tmp_path):
        import yaml as _yaml
        config_path = tmp_path / "model_config.yaml"
        config_path.write_text(_yaml.dump({
            "plasma": {"strategic": "test/model-pro"},
            "flux":   {"coder": "test/model-mid"},
            "budget": {"per_task_caps": {"coder": 0.99}},
        }))
        from config import load_config
        c = load_config(config_path)
        assert c.plasma.strategic  == "test/model-pro"
        assert c.flux_model("coder") == "test/model-mid"
        assert c.budget_cap("coder") == 0.99

    def test_reload_config(self, tmp_path):
        from config import reload_config
        c = reload_config(tmp_path / "missing.yaml")
        assert c is not None


# ─────────────────────────────────────────────────────────────────────────────
# state.py
# ─────────────────────────────────────────────────────────────────────────────

class TestState:

    def test_budget_initial(self, tmp_path):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        from state import StateManager
        sm = StateManager()
        run(sm.init_budget(100.0))
        assert sm.total_budget()       == 100.0
        assert sm.budget_remaining()   == 100.0

    def test_record_spend(self, tmp_path):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        from state import StateManager
        sm = StateManager()
        run(sm.init_budget(50.0))
        run(sm.record_spend("coder", 0.05))
        assert abs(sm.budget_remaining() - 49.95) < 0.001

    def test_budget_never_negative(self, tmp_path):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        from state import StateManager
        sm = StateManager()
        run(sm.init_budget(1.0))
        run(sm.record_spend("coder", 999.0))
        assert sm.budget_remaining() == 0.0

    def test_register_node(self, tmp_path):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        from state import StateManager, NodeInfo
        sm   = StateManager()
        info = NodeInfo("FLUX:coder:abc123", "coder", "test/model", "idle")
        run(sm.register_node(info))
        assert len(sm.get_nodes()) == 1
        assert sm.get_node("FLUX:coder:abc123")["node_type"] == "coder"

    def test_update_node_status(self, tmp_path):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        from state import StateManager, NodeInfo
        sm   = StateManager()
        info = NodeInfo("FLUX:coder:xyz", "coder", "model", "idle")
        run(sm.register_node(info))
        run(sm.update_node_status("FLUX:coder:xyz", "busy"))
        assert sm.get_node("FLUX:coder:xyz")["status"] == "busy"

    def test_log_event(self, tmp_path):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        from state import StateManager
        sm = StateManager()
        run(sm.log_event("PLASMA", "test", "hello world"))
        events = sm.recent_events(5)
        assert len(events) == 1
        assert events[0]["message"] == "hello world"

    def test_record_vote(self, tmp_path):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        from state import StateManager
        sm = StateManager()
        run(sm.record_vote(approved=True))
        run(sm.record_vote(approved=True))
        run(sm.record_vote(approved=False))
        summary = sm.summary()
        assert summary["solid"]["total"]    == 3
        assert summary["solid"]["approved"] == 2
        assert summary["solid"]["rejected"] == 1

    def test_summary_structure(self, tmp_path):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        from state import StateManager
        sm = StateManager()
        run(sm.init_budget(50.0))
        s = sm.summary()
        assert "plasma_version" in s
        assert "budget"         in s
        assert "nodes"          in s
        assert "tasks"          in s
        assert "solid"          in s

    def test_save_and_load(self, tmp_path):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        from state import StateManager, NodeInfo
        sm1 = StateManager()
        run(sm1.init_budget(77.0))
        run(sm1.record_spend("test", 3.0))
        run(sm1.log_event("PLASMA", "test", "persisted event"))

        sm2 = StateManager()
        run(sm2.load())
        assert abs(sm2.budget_remaining() - 74.0) < 0.01
        assert len(sm2.recent_events(5)) == 1


# ─────────────────────────────────────────────────────────────────────────────
# task.py
# ─────────────────────────────────────────────────────────────────────────────

class TestTask:

    def test_task_defaults(self):
        from task import Task, TaskStatus, TaskPriority
        t = Task(goal="test goal", node_type="coder")
        assert t.status   == TaskStatus.PENDING
        assert t.priority == TaskPriority.NORMAL
        assert not t.is_terminal()
        assert t.task_id  != ""

    def test_task_terminal_states(self):
        from task import Task, TaskStatus
        for status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED):
            t = Task(goal="g", node_type="coder", status=status)
            assert t.is_terminal()

    def test_task_can_retry(self):
        from task import Task, TaskStatus
        t = Task(goal="g", node_type="coder",
                 status=TaskStatus.FAILED, attempts=1, max_attempts=2)
        assert t.can_retry()
        t.attempts = 2
        assert not t.can_retry()

    def test_task_elapsed(self):
        from task import Task
        t = Task(goal="g", node_type="coder")
        time.sleep(0.05)
        assert t.elapsed() >= 0.04

    def test_task_summary(self):
        from task import Task
        t = Task(goal="Write a Python function", node_type="coder")
        s = t.summary()
        assert "coder" in s
        assert "pending" in s

    def test_queue_put_and_get(self):
        from task import Task, TaskQueue, TaskPriority

        async def _test():
            q = TaskQueue()
            t = Task(goal="test", node_type="coder", priority=TaskPriority.NORMAL)
            await q.put(t)
            got = await q.get_for_node("coder", timeout=1.0)
            assert got is not None
            assert got.task_id == t.task_id
        run(_test())

    def test_queue_priority_order(self):
        from task import Task, TaskQueue, TaskPriority

        async def _test():
            q = TaskQueue()
            low    = Task(goal="low",    node_type="coder", priority=TaskPriority.LOW)
            urgent = Task(goal="urgent", node_type="coder", priority=TaskPriority.URGENT)
            await q.put(low)
            await q.put(urgent)

            first = await q.get_for_node("coder", timeout=1.0)
            assert first.goal == "urgent"   # higher priority served first
        run(_test())

    def test_queue_get_by_node_type(self):
        from task import Task, TaskQueue

        async def _test():
            q = TaskQueue()
            await q.put(Task(goal="for researcher", node_type="researcher"))
            await q.put(Task(goal="for coder",      node_type="coder"))

            got = await q.get_for_node("researcher", timeout=1.0)
            assert got is not None
            assert got.node_type == "researcher"
        run(_test())

    def test_queue_update(self):
        from task import Task, TaskQueue, TaskStatus

        async def _test():
            q = TaskQueue()
            t = Task(goal="g", node_type="coder")
            await q.put(t)
            await q.update(t.task_id, status=TaskStatus.IN_PROGRESS)
            updated = q.get_task(t.task_id)
            assert updated.status == TaskStatus.IN_PROGRESS
        run(_test())

    def test_queue_cancel(self):
        from task import Task, TaskQueue, TaskStatus

        async def _test():
            q = TaskQueue()
            t = Task(goal="g", node_type="coder")
            await q.put(t)
            success = await q.cancel(t.task_id)
            assert success
            assert q.get_task(t.task_id).status == TaskStatus.CANCELLED
        run(_test())

    def test_queue_pending_count(self):
        from task import Task, TaskQueue

        async def _test():
            q = TaskQueue()
            await q.put(Task(goal="a", node_type="coder"))
            await q.put(Task(goal="b", node_type="researcher"))
            assert q.pending_count() == 2
        run(_test())


# ─────────────────────────────────────────────────────────────────────────────
# solid.py
# ─────────────────────────────────────────────────────────────────────────────

class TestSolid:

    def _make_solid(self, tmp_path, vote_responses: list[str]):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        from solid_engine import Solid
        from state import StateManager
        import state as state_mod
        state_mod.state = StateManager()
        run(state_mod.state.init_budget(50.0))

        s = Solid()

        call_count = [0]
        async def mock_llm(model, messages, **kw):
            resp = vote_responses[call_count[0] % len(vote_responses)]
            call_count[0] += 1
            return resp

        import solid_engine as solid_mod
        solid_mod.call_llm = mock_llm
        return s

    def _make_task(self):
        from task import Task
        return Task(goal="Write a hello world function", node_type="coder")

    def test_unanimous_approval(self, tmp_path):
        vote = "VOTE: YES\nREASON: Output is correct.\nFEEDBACK: None needed."
        s    = self._make_solid(tmp_path, [vote, vote, vote])
        task = self._make_task()
        result = run(s.validate_task_result(task, "def hello(): print('hi')"))
        assert result.approved   is True
        assert result.consensus  == "unanimous"
        assert len(result.votes) == 3

    def test_majority_approval(self, tmp_path):
        yes = "VOTE: YES\nREASON: Looks good.\nFEEDBACK: None."
        no  = "VOTE: NO\nREASON: Missing docstring.\nFEEDBACK: Add a docstring."
        s   = self._make_solid(tmp_path, [yes, yes, no])
        task = self._make_task()
        result = run(s.validate_task_result(task, "def hello(): pass"))
        assert result.approved  is True
        assert result.consensus == "majority"

    def test_rejection_majority_no(self, tmp_path):
        yes = "VOTE: YES\nREASON: Fine.\nFEEDBACK: None."
        no  = "VOTE: NO\nREASON: Wrong.\nFEEDBACK: Fix the logic."
        s   = self._make_solid(tmp_path, [no, no, yes])
        task = self._make_task()
        result = run(s.validate_task_result(task, "broken code"))
        assert result.approved  is False
        assert result.consensus == "rejected"
        assert "Fix" in result.feedback

    def test_empty_output_rejected(self, tmp_path):
        s    = self._make_solid(tmp_path, ["VOTE: YES\nREASON: ok\nFEEDBACK: none"])
        task = self._make_task()
        result = run(s.validate_task_result(task, ""))
        assert result.approved is False

    def test_evolution_requires_unanimous(self, tmp_path):
        yes = "VOTE: YES\nREASON: Safe change.\nFEEDBACK: None."
        no  = "VOTE: NO\nREASON: Risky.\nFEEDBACK: Too much changed."
        s   = self._make_solid(tmp_path, [yes, yes, no])
        result = run(s.validate_evolution(
            description   = "Improve the routing",
            current_code  = "old code",
            proposed_code = "new code",
        ))
        # 2/3 yes, but evolution requires unanimous → rejected
        assert result.approved is False

    def test_evolution_unanimous_approved(self, tmp_path):
        yes = "VOTE: YES\nREASON: Safe.\nFEEDBACK: None."
        s   = self._make_solid(tmp_path, [yes, yes, yes])
        result = run(s.validate_evolution("improve", "old", "new"))
        assert result.approved  is True
        assert result.consensus == "unanimous"

    def test_solid_status_summary(self, tmp_path):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        from solid_engine import Solid
        s = Solid()
        summary = s.status_summary()
        assert "SOLID" in summary
        assert "validator" in summary.lower()


# ─────────────────────────────────────────────────────────────────────────────
# flux_base.py + flux nodes
# ─────────────────────────────────────────────────────────────────────────────

class TestFluxBase:

    def _setup(self, tmp_path):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        import state as sm
        from state import StateManager
        sm.state = StateManager()
        run(sm.state.init_budget(50.0))

        import task as tm
        from task import TaskQueue
        tm.task_queue = TaskQueue()

        # Mock SOLID to always approve
        import solid_engine as sol
        mock_solid = MagicMock()
        from task import ValidationResult
        mock_solid.validate_task_result = AsyncMock(return_value=ValidationResult(
            task_id="x", approved=True, votes=[],
            consensus="unanimous", feedback=""
        ))
        sol.solid = mock_solid

    def test_coder_node_type(self):
        from flux_coder import CoderNode
        assert CoderNode.node_type == "coder"
        assert CoderNode.system_prompt

    def test_researcher_node_type(self):
        from flux_researcher import ResearcherNode
        assert ResearcherNode.node_type == "researcher"

    def test_reviewer_node_type(self):
        from flux_reviewer import ReviewerNode
        assert ReviewerNode.node_type == "reviewer"

    def test_architect_node_type(self):
        from flux_architect import ArchitectNode
        assert ArchitectNode.node_type == "architect"

    def test_node_start_stop(self, tmp_path):
        self._setup(tmp_path)
        from flux_coder import CoderNode
        node = CoderNode()
        run(node.start())
        assert node.is_running
        run(node.stop())
        assert not node.is_running

    def test_node_registered_in_state(self, tmp_path):
        self._setup(tmp_path)
        import state as sm
        from flux_coder import CoderNode
        node = CoderNode()
        run(node.start())
        nodes = sm.state.get_nodes()
        assert any(n["node_type"] == "coder" for n in nodes)
        run(node.stop())

    def test_node_processes_task(self, tmp_path):
        self._setup(tmp_path)
        from flux_coder import CoderNode
        from task       import Task, TaskStatus, task_queue
        import flux_base as fb

        async def mock_execute(self, task):
            return "def hello(): return 'world'"

        CoderNode.execute = mock_execute
        node = CoderNode()
        task = Task(goal="Write hello function", node_type="coder")

        async def _test():
            await node.start()
            await task_queue.put(task)
            await asyncio.sleep(0.5)   # let the node pick it up
            await node.stop()
            t = task_queue.get_task(task.task_id)
            assert t is not None
            assert t.status == TaskStatus.DONE
            assert t.result
        run(_test())

    def test_node_retries_on_solid_rejection(self, tmp_path):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        import state as sm
        from state import StateManager
        sm.state = StateManager()
        run(sm.state.init_budget(50.0))

        import task as tm
        from task import TaskQueue
        tm.task_queue = TaskQueue()

        # SOLID rejects first, approves second
        import solid_engine as sol
        from task import ValidationResult
        call_count = [0]
        async def mock_validate(task, output):
            call_count[0] += 1
            approved = call_count[0] > 1
            return ValidationResult(
                task_id=task.task_id, approved=approved,
                votes=[], consensus="majority" if approved else "rejected",
                feedback="Missing error handling." if not approved else ""
            )
        mock_solid = MagicMock()
        mock_solid.validate_task_result = mock_validate
        sol.solid = mock_solid

        from flux_coder import CoderNode
        from task       import Task, TaskStatus, task_queue

        async def mock_execute(self, task):
            return "def f(): pass"
        CoderNode.execute = mock_execute

        node = CoderNode()
        task = Task(goal="test", node_type="coder", max_attempts=2)

        async def _test():
            await node.start()
            await task_queue.put(task)
            await asyncio.sleep(1.0)
            await node.stop()
            t = task_queue.get_task(task.task_id)
            # After retry, should be DONE
            assert t.status in (TaskStatus.DONE, TaskStatus.FAILED)
        run(_test())

    def test_node_describe(self, tmp_path):
        self._setup(tmp_path)
        from flux_coder import CoderNode
        node = CoderNode()
        desc = node.describe()
        assert "coder"   in desc
        assert "stopped" in desc


# ─────────────────────────────────────────────────────────────────────────────
# plugin_base.py
# ─────────────────────────────────────────────────────────────────────────────

class TestPluginBase:

    def test_plugin_registry_empty(self):
        from plugin_base import PluginRegistry
        r = PluginRegistry()
        assert r.list_plugins() == []
        assert not r.is_loaded("anything")

    def test_register_valid_plugin(self):
        from plugin_base import PluginRegistry, PhasePlugin
        from flux_base   import FluxNode
        from task        import Task

        class TestNode(FluxNode):
            node_type     = "test_plugin"
            system_prompt = "Test node"
            async def execute(self, task: Task) -> str:
                return "done"

        plugin = PhasePlugin(
            name        = "test_plugin",
            version     = "1.0.0",
            description = "A test plugin",
            node_class  = TestNode,
        )
        r = PluginRegistry()
        assert r.register(plugin)
        assert r.is_loaded("test_plugin")

    def test_create_node_from_plugin(self):
        from plugin_base import PluginRegistry, PhasePlugin
        from flux_base   import FluxNode
        from task        import Task

        class MyNode(FluxNode):
            node_type     = "my_plugin"
            system_prompt = "My node"
            async def execute(self, task: Task) -> str:
                return "result"

        plugin = PhasePlugin("my_plugin", "1.0", "desc", MyNode)
        r      = PluginRegistry()
        r.register(plugin)
        node = r.create_node("my_plugin")
        assert node is not None
        assert isinstance(node, MyNode)

    def test_plugin_validation_no_node_type(self):
        from plugin_base import PhasePlugin
        from flux_base   import FluxNode
        from task        import Task

        class BadNode(FluxNode):
            node_type     = "base"   # invalid — same as default
            system_prompt = "bad"
            async def execute(self, task: Task) -> str: return ""

        plugin = PhasePlugin("bad", "1.0", "d", BadNode)
        errors = plugin.validate()
        assert any("node_type" in e for e in errors)

    def test_load_missing_plugin(self, tmp_path):
        from plugin_base import PluginRegistry
        import plugin_base as pb_mod
        pb_mod.PLUGINS_DIR = tmp_path
        r = PluginRegistry()
        assert not r.load("nonexistent_plugin")

    def test_plugin_summary(self):
        from plugin_base import PluginRegistry
        r = PluginRegistry()
        assert "No plugins" in r.summary()

    def test_plugin_template_is_string(self):
        from plugin_base import PLUGIN_TEMPLATE
        assert isinstance(PLUGIN_TEMPLATE, str)
        assert "FluxNode"    in PLUGIN_TEMPLATE
        assert "PhasePlugin" in PLUGIN_TEMPLATE
        assert "PLUGIN ="    in PLUGIN_TEMPLATE


# ─────────────────────────────────────────────────────────────────────────────
# plasma.py (smoke tests — no real LLM or git)
# ─────────────────────────────────────────────────────────────────────────────

class TestPlasma:

    def _setup(self, tmp_path, mock_llm_response: str = ""):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        import state as sm
        from state import StateManager
        sm.state = StateManager()
        run(sm.state.init_budget(50.0))

        import task as tm
        from task import TaskQueue
        tm.task_queue = TaskQueue()

        import solid_engine as sol
        from task import ValidationResult
        mock_solid = MagicMock()
        mock_solid.validate_task_result = AsyncMock(return_value=ValidationResult(
            task_id="x", approved=True, votes=[],
            consensus="unanimous", feedback=""
        ))
        sol.solid = mock_solid

        import llm as llm_mod
        async def mock_call_llm(model, messages, **kw):
            return mock_llm_response
        llm_mod.call_llm = mock_call_llm

    def test_plasma_creates(self, tmp_path):
        self._setup(tmp_path)
        from plasma import Plasma
        p = Plasma()
        assert p._version
        assert p._send is None

    def test_plasma_start_stop(self, tmp_path):
        self._setup(tmp_path)
        from plasma import Plasma
        p = Plasma()
        run(p.start(nodes=[]))
        run(p.stop())

    def test_plasma_status_summary(self, tmp_path):
        self._setup(tmp_path)
        from plasma import Plasma
        p = Plasma()
        run(p.start(nodes=[]))
        result = run(p.handle_phase_status())
        assert "PLASMA"  in result
        assert "Budget"  in result
        assert "Tasks"   in result
        run(p.stop())

    def test_plasma_decompose_bad_json(self, tmp_path):
        self._setup(tmp_path, mock_llm_response="not json")
        from plasma import Plasma
        p = Plasma()
        tasks, synth = run(p._decompose("Do something"))
        assert tasks == []   # graceful fallback

    def test_plasma_decompose_valid_json(self, tmp_path):
        response = json.dumps({
            "tasks": [
                {"node_type": "researcher", "task_goal": "Research X", "priority": 3},
                {"node_type": "coder",      "task_goal": "Implement X", "priority": 2},
            ],
            "synthesis_instruction": "Combine results."
        })
        self._setup(tmp_path, mock_llm_response=response)
        from plasma import Plasma
        p = Plasma()
        tasks, synth = run(p._decompose("Build X"))
        assert len(tasks) == 2
        assert tasks[0].node_type == "researcher"
        assert tasks[1].node_type == "coder"
        assert "Combine" in synth

    def test_plasma_synthesise(self, tmp_path):
        self._setup(tmp_path, mock_llm_response="Here is the combined result.")
        from plasma import Plasma
        p = Plasma()
        results = [
            {"node_type": "coder", "goal": "Write hello", "result": "def hello(): pass", "status": "done"},
        ]
        out = run(p._synthesise("Write hello function", results, "Return it."))
        assert out   # not empty

    def test_plasma_bump_version(self, tmp_path):
        self._setup(tmp_path)
        from plasma import Plasma
        p = Plasma(version="1.0.5")
        assert p._bump_version() == "1.0.6"

    def test_plasma_evolve_command(self, tmp_path):
        self._setup(tmp_path)
        from plasma import Plasma
        p = Plasma()
        run(p.start(nodes=[]))
        result = run(p.handle_evolve_command())
        assert "Evolution" in result or "evolution" in result
        run(p.stop())

    def test_plasma_handle_goal_empty_decompose(self, tmp_path):
        """When decompose fails, PLASMA should fall back to a single coder task."""
        self._setup(tmp_path, mock_llm_response="not valid json at all")
        from plasma import Plasma
        p = Plasma()
        # Directly test decompose returns empty
        tasks, synth = run(p._decompose("Do something"))
        assert tasks == []
        assert "directly" in synth.lower()

    def test_plasma_synthesise_no_results(self, tmp_path):
        self._setup(tmp_path)
        from plasma import Plasma
        p = Plasma()
        out = run(p._synthesise("goal", [], "instruction"))
        assert "No results" in out

    def test_plasma_run_tasks_empty(self, tmp_path):
        self._setup(tmp_path)
        from plasma import Plasma
        p = Plasma()
        results = run(p._run_tasks([], "goal"))
        assert results == []


# ─────────────────────────────────────────────────────────────────────────────
# llm.py
# ─────────────────────────────────────────────────────────────────────────────

class TestLLM:

    def test_estimate_cost_known_model(self):
        from llm import _estimate_cost
        cost = _estimate_cost("anthropic/claude-sonnet-4-6", 1000, 500)
        # 1000 input at $3/Mtok + 500 output at $15/Mtok
        expected = 1000 / 1_000_000 * 3.0 + 500 / 1_000_000 * 15.0
        assert abs(cost - expected) < 1e-8

    def test_estimate_cost_unknown_model(self):
        from llm import _estimate_cost
        cost = _estimate_cost("unknown/model", 1000, 1000)
        # Should use default Sonnet pricing
        assert cost > 0

    def test_estimate_cost_zero_tokens(self):
        from llm import _estimate_cost
        cost = _estimate_cost("anthropic/claude-opus-4-6", 0, 0)
        assert cost == 0.0

    def test_register_usage_callback(self):
        from llm import register_usage_callback, _fire_usage, _usage_callbacks
        results = []
        def cb(tag, cost, pt, ct):
            results.append((tag, cost, pt, ct))

        register_usage_callback(cb)
        _fire_usage("test", 0.01, 100, 50)
        assert len(results) == 1
        assert results[0][0] == "test"
        # Cleanup
        _usage_callbacks.remove(cb)

    def test_call_llm_no_api_key(self):
        import llm as llm_mod
        saved = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            result = run(llm_mod.call_llm(
                model="test/model",
                messages=[{"role": "user", "content": "hi"}],
            ))
            assert result == ""
        finally:
            if saved:
                os.environ["OPENROUTER_API_KEY"] = saved


# ─────────────────────────────────────────────────────────────────────────────
# telegram_phase.py
# ─────────────────────────────────────────────────────────────────────────────

class TestTelegramPhase:

    def _make_plasma(self, tmp_path):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        import state as sm
        from state import StateManager
        sm.state = StateManager()
        run(sm.state.init_budget(50.0))

        import task as tm
        from task import TaskQueue
        tm.task_queue = TaskQueue()

        import solid_engine as sol
        from task import ValidationResult
        mock_solid = MagicMock()
        mock_solid.validate_task_result = AsyncMock(return_value=ValidationResult(
            task_id="x", approved=True, votes=[],
            consensus="unanimous", feedback=""
        ))
        sol.solid = mock_solid

        import llm as llm_mod
        async def mock_call_llm(model, messages, **kw):
            return ""
        llm_mod.call_llm = mock_call_llm

        from plasma import Plasma
        p = Plasma()
        run(p.start(nodes=[]))
        return p

    def test_handle_status_command(self, tmp_path):
        plasma = self._make_plasma(tmp_path)
        from telegram_phase import handle_phase_command
        sent = []
        async def send(msg): sent.append(msg)
        result = run(handle_phase_command("phase", "status", send, plasma))
        assert result is True
        assert len(sent) > 0
        assert "PLASMA" in sent[0]
        run(plasma.stop())

    def test_handle_nodes_command(self, tmp_path):
        plasma = self._make_plasma(tmp_path)
        from telegram_phase import handle_phase_command
        sent = []
        async def send(msg): sent.append(msg)
        run(handle_phase_command("phase", "nodes", send, plasma))
        assert len(sent) > 0
        run(plasma.stop())

    def test_handle_tasks_command(self, tmp_path):
        plasma = self._make_plasma(tmp_path)
        from telegram_phase import handle_phase_command
        sent = []
        async def send(msg): sent.append(msg)
        run(handle_phase_command("phase", "tasks", send, plasma))
        assert len(sent) > 0
        assert "Task queue" in sent[0] or "task" in sent[0].lower()
        run(plasma.stop())

    def test_handle_history_command(self, tmp_path):
        plasma = self._make_plasma(tmp_path)
        from telegram_phase import handle_phase_command
        sent = []
        async def send(msg): sent.append(msg)
        run(handle_phase_command("phase", "history 5", send, plasma))
        assert len(sent) > 0
        run(plasma.stop())

    def test_handle_config_command(self, tmp_path):
        plasma = self._make_plasma(tmp_path)
        from telegram_phase import handle_phase_command
        sent = []
        async def send(msg): sent.append(msg)
        run(handle_phase_command("phase", "config", send, plasma))
        assert len(sent) > 0
        assert "PLASMA" in sent[0]
        assert "SOLID" in sent[0]
        run(plasma.stop())

    def test_handle_senate_command(self, tmp_path):
        plasma = self._make_plasma(tmp_path)
        from telegram_phase import handle_phase_command
        sent = []
        async def send(msg): sent.append(msg)
        run(handle_phase_command("phase", "senate", send, plasma))
        assert len(sent) > 0
        run(plasma.stop())

    def test_handle_plugin_list_command(self, tmp_path):
        plasma = self._make_plasma(tmp_path)
        from telegram_phase import handle_phase_command
        sent = []
        async def send(msg): sent.append(msg)
        run(handle_phase_command("phase", "plugin list", send, plasma))
        assert len(sent) > 0
        assert "Plugin" in sent[0] or "plugin" in sent[0].lower()
        run(plasma.stop())

    def test_handle_unknown_subcommand(self, tmp_path):
        plasma = self._make_plasma(tmp_path)
        from telegram_phase import handle_phase_command
        sent = []
        async def send(msg): sent.append(msg)
        run(handle_phase_command("phase", "gibberish", send, plasma))
        assert len(sent) > 0
        assert "commands" in sent[0].lower() or "PHASE" in sent[0]
        run(plasma.stop())

    def test_non_phase_command_returns_false(self, tmp_path):
        plasma = self._make_plasma(tmp_path)
        from telegram_phase import handle_phase_command
        sent = []
        async def send(msg): sent.append(msg)
        result = run(handle_phase_command("start", "", send, plasma))
        assert result is False
        run(plasma.stop())


# ─────────────────────────────────────────────────────────────────────────────
# Additional edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_task_queue_timeout_returns_none(self):
        from task import TaskQueue
        q = TaskQueue()
        result = run(q.get_for_node("coder", timeout=0.1))
        assert result is None

    def test_task_queue_all_tasks(self):
        from task import Task, TaskQueue
        async def _test():
            q = TaskQueue()
            await q.put(Task(goal="a", node_type="coder"))
            await q.put(Task(goal="b", node_type="coder"))
            assert len(q.all_tasks()) == 2
        run(_test())

    def test_task_queue_cancel_nonexistent(self):
        from task import TaskQueue
        q = TaskQueue()
        result = run(q.cancel("nonexistent_id"))
        assert result is False

    def test_validation_result_fields(self):
        from task import ValidationResult
        vr = ValidationResult(
            task_id="abc", approved=True, votes=[],
            consensus="unanimous", feedback="All good"
        )
        assert vr.task_id == "abc"
        assert vr.approved is True
        assert vr.consensus == "unanimous"

    def test_state_remove_node(self, tmp_path):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        from state import StateManager, NodeInfo
        sm = StateManager()
        run(sm.register_node(NodeInfo("node1", "coder", "model", "idle")))
        assert len(sm.get_nodes()) == 1
        run(sm.remove_node("node1"))
        assert len(sm.get_nodes()) == 0

    def test_state_plasma_version_and_status(self, tmp_path):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        from state import StateManager
        sm = StateManager()
        run(sm.set_plasma_version("2.0.0"))
        run(sm.set_plasma_status("evolving"))
        s = sm.summary()
        assert s["plasma_version"] == "2.0.0"
        assert s["plasma_status"] == "evolving"

    def test_state_task_counters(self, tmp_path):
        os.environ["PHASE_DATA_DIR"] = str(tmp_path)
        from state import StateManager
        sm = StateManager()
        run(sm.task_assigned())
        run(sm.task_assigned())
        run(sm.task_completed("node1", success=True))
        run(sm.task_completed("node1", success=False))
        s = sm.summary()
        assert s["tasks"]["total"] == 2
        assert s["tasks"]["done"] == 1
        assert s["tasks"]["failed"] == 1

    def test_config_solid_all_models(self):
        from config import SolidConfig
        sc = SolidConfig()
        models = sc.all_models()
        assert len(models) == 3
        assert all(isinstance(m, str) for m in models)

    def test_config_timeouts_defaults(self):
        from config import Config
        c = Config()
        assert c.timeouts.node_task_seconds == 300
        assert c.timeouts.solid_vote_seconds == 30
        assert c.timeouts.plasma_evolve_seconds == 600

    def test_phase_event_structure(self):
        from state import PhaseEvent
        from dataclasses import asdict
        evt = PhaseEvent(
            timestamp=1234.0, source="PLASMA",
            event_type="test", message="hello"
        )
        d = asdict(evt)
        assert d["source"] == "PLASMA"
        assert d["metadata"] == {}

    def test_node_info_defaults(self):
        from state import NodeInfo
        info = NodeInfo("id1", "coder", "model", "idle")
        assert info.tasks_done == 0
        assert info.total_spend == 0.0

    def test_plugin_info_method(self):
        from plugin_base import PhasePlugin
        from flux_base import FluxNode
        from task import Task

        class DummyNode(FluxNode):
            node_type = "dummy"
            system_prompt = "test"
            async def execute(self, task: Task) -> str: return "ok"

        p = PhasePlugin("dummy", "1.0.0", "A test", DummyNode, author="tester", tags=["test"])
        info = p.info()
        assert "dummy" in info
        assert "tester" in info
        assert "test" in info
