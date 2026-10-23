from __future__ import annotations

import json
import asyncio
from collections import Counter
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, Literal
from uuid import UUID

from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from parameterized import parameterized

from products.posthog_ai.eval_harness.config import SandboxedEvalCase
from products.posthog_ai.eval_harness.runner import WorkflowCleanupError
from products.posthog_ai.eval_harness.scorers.contract import Score
from products.signals.evals import scout_runner
from products.signals.evals.first_report_fixture import CURRENT_VERSION, upload_events
from products.signals.evals.first_report_scorers import (
    GroundedCloseout,
    PlantedIssueRecall,
    ReportQuality,
    ScoutOutcome,
)
from products.tasks.backend.facade.agents import CustomPromptSandboxContext


class TestFirstReportFixture(TestCase):
    @parameterized.expand([("regression", 140, 560), ("control", 560, 0)])
    def test_regression_and_control_have_matched_mature_cohorts(
        self, scenario: Literal["regression", "control"], uploads: int, errors: int
    ) -> None:
        anchor = datetime(2026, 1, 1, tzinfo=UTC)
        events = upload_events(anchor, scenario=scenario)
        counts = Counter(
            (event.properties["$browser"], event.properties["app_version"], event.event) for event in events
        )
        self.assertEqual(counts[("Safari", CURRENT_VERSION, "signed_up")], 700)
        self.assertEqual(counts[("Safari", CURRENT_VERSION, "uploaded_file")], uploads)
        self.assertEqual(counts[("Safari", CURRENT_VERSION, "$exception")], errors)
        self.assertEqual(counts[("Chrome", CURRENT_VERSION, "uploaded_file")], 560)
        self.assertTrue(all(anchor - event.timestamp > timedelta(days=1) for event in events))
        signups = {event.person_id: event.timestamp for event in events if event.event == "signed_up"}
        self.assertTrue(
            all(
                event.timestamp > signups[event.person_id]
                for event in events
                if event.event in ("uploaded_file", "$exception")
            )
        )
        self.assertEqual(
            {event.person_id for event in events if event.event == "$identify"},
            set(signups),
        )
        self.assertTrue(all(str(UUID(event.distinct_id)) == event.distinct_id for event in events))

    def test_sparse_project_has_data_but_no_evidence_of_a_regression(self) -> None:
        events = upload_events(datetime(2026, 1, 1, tzinfo=UTC), scenario="sparse")
        self.assertEqual(Counter(event.event for event in events), {"signed_up": 4})
        self.assertEqual(len({event.person_id for event in events}), 4)


class TestFirstReportScorers(TestCase):
    @parameterized.expand(
        [
            ("Four signups are insufficient to establish a regression.", True),
            ("This project has no recorded events.", True),
            ("This project has no recorded events.", False),
        ]
    )
    def test_closeout_judge_receives_final_explanation(self, summary: str, persisted_summary: bool) -> None:
        output: dict[str, Any] = {
            "exit_code": 0,
            "outcome": "insufficient_data",
            "checked_products": ["product_analytics"],
            "missing_data": ["More mature signup cohorts"],
            "seed": {"scenario": "sparse", "cohorts": [{"signups": 4}]},
            "last_message": summary if persisted_summary else None,
            "raw_log": json.dumps(
                {
                    "type": "notification",
                    "notification": {
                        "method": "session/update",
                        "params": {
                            "update": {
                                "sessionUpdate": "agent_message",
                                "content": {
                                    "type": "text",
                                    "text": "Earlier progress" if persisted_summary else summary,
                                },
                            }
                        },
                    },
                }
            ),
        }
        prepared = GroundedCloseout()._prepare(output, {"scenario": "sparse"})
        self.assertIsInstance(prepared, dict)
        assert isinstance(prepared, dict)
        payload = json.loads(prepared["output"])
        self.assertEqual(payload["closeout"], summary)
        self.assertEqual(payload["oracle"]["cohorts"], [{"signups": 4}])

    @parameterized.expand(
        [
            ("regression", "report_created", "ready", 1, True, 1.0),
            ("regression", "report_created", "candidate", 1, True, 0.0),
            ("regression", "report_created", "ready", 0, True, 0.0),
            ("regression", "report_created", "ready", 2, True, 0.0),
            ("regression", "no_actionable_finding", "ready", 0, True, 0.0),
            ("control", "no_actionable_finding", "ready", 0, True, 1.0),
            ("sparse", "insufficient_data", "ready", 0, True, 1.0),
            ("sparse", "insufficient_data", "ready", 1, True, 0.0),
            ("sparse", "insufficient_data", "ready", 0, False, 0.0),
        ]
    )
    def test_outcome_requires_persisted_visible_report_or_honest_abstention(
        self, scenario: str, outcome: str, status: str, reports: int, explanation: bool, expected: float
    ) -> None:
        output: dict[str, Any] = {
            "exit_code": 0,
            "outcome": outcome,
            "reports": [{"status": status, "summary": "An actionable finding", "visible_after_seconds": 20}] * reports,
            "checked_products": ["product_analytics"],
            "missing_data": ["More mature signup cohorts"] if explanation else [],
        }
        self.assertEqual(ScoutOutcome().eval(output, {"scenario": scenario}).score, expected)

    @parameterized.expand([(None,), ({},), ({"exit_code": 1, "outcome": "insufficient_data"},)])
    def test_missing_or_failed_agent_outputs_do_not_disappear_from_scores(self, output: dict[str, Any] | None) -> None:
        for scorer in [GroundedCloseout(), ReportQuality(), PlantedIssueRecall()]:
            prepared = scorer._prepare(output, {"scenario": "regression"})
            self.assertIsInstance(prepared, Score)
            assert isinstance(prepared, Score)
            self.assertEqual(prepared.score, 0.0)
        self.assertEqual(ScoutOutcome().eval(output, {"scenario": "regression"}).score, 0.0)

    @parameterized.expand([(299, True), (300, True), (301, False), (None, False), (-1, False)])
    def test_fast_delivery_still_requires_quality_judgment(self, seconds: float | None, should_judge: bool) -> None:
        output: dict[str, Any] = {
            "exit_code": 0,
            "outcome": "report_created",
            "first_report_seconds": seconds,
            "reports": [{"status": "ready", "summary": "A report"}],
            "seed": {"scenario": "regression", "cohorts": [{"signups": 700}]},
        }
        prepared = ReportQuality(deadline_seconds=300)._prepare(output, {"scenario": "regression"})
        if should_judge:
            self.assertIsInstance(prepared, dict)
            assert isinstance(prepared, dict)
            self.assertIn('"signups": 700', prepared["output"])
        else:
            self.assertIsInstance(prepared, Score)
            assert isinstance(prepared, Score)
            self.assertEqual(prepared.score, 0.0)


class TestScoutEvalCleanup(IsolatedAsyncioTestCase):
    @parameterized.expand([("agent_message",), ("agent_message_chunk",)])
    def test_progress_time_uses_first_text_not_prior_tool_call(self, message_kind: str) -> None:
        started = datetime(2026, 1, 1, tzinfo=UTC)
        log = "invalid JSON\n" + "\n".join(
            json.dumps(
                {
                    "timestamp": (started + timedelta(seconds=seconds)).isoformat(),
                    "notification": {
                        "params": {
                            "update": {"sessionUpdate": kind, "content": {"type": "text", "text": "Investigating"}}
                        }
                    },
                }
            )
            for seconds, kind in [(10, "tool_call"), (20, message_kind), (30, message_kind)]
        )
        self.assertEqual(scout_runner.first_progress_seconds(log, started), 20)

    @parameterized.expand(
        [
            (None, True),
            (RuntimeError("Scout failed"), False),
            (asyncio.CancelledError(), False),
            (None, False),
            (None, True, "connect"),
            (None, True, "finish"),
        ]
    )
    async def test_scout_reclaims_sandbox_and_preserves_failure(
        self, error: BaseException | None, cleanup_confirmed: bool, cancel_during: str | None = None
    ) -> None:
        task = SimpleNamespace(id="run", task_id="task", workflow_id="workflow")
        client = MagicMock()
        provider = MagicMock()
        result = SimpleNamespace(status="completed", run_id="scout", last_message=None)
        cleanup_started = asyncio.Event()
        release_cleanup = asyncio.Event()
        workflow_finished = asyncio.Event()

        async def connect() -> MagicMock:
            if cancel_during == "connect":
                cleanup_started.set()
                await release_cleanup.wait()
            return client

        async def finish(*args: object, **kwargs: object) -> bool:
            if cancel_during == "finish":
                cleanup_started.set()
                await release_cleanup.wait()
            workflow_finished.set()
            return cleanup_confirmed

        with (
            patch.object(scout_runner, "prepare_scout", return_value="Server inventory"),
            patch.object(scout_runner, "latest_scout_task", return_value=task),
            patch.object(scout_runner, "arun_signals_scout", AsyncMock(return_value=result, side_effect=error)),
            patch.object(scout_runner.tasks_api, "read_task_run_conversation_logs", return_value=""),
            patch.object(
                scout_runner,
                "first_report_state",
                return_value={"status": "insufficient_data", "missing_data": ["More cohorts"]},
            ),
            patch.object(scout_runner, "collect_reports", return_value=[]),
            patch.object(scout_runner, "async_connect", connect),
            patch.object(scout_runner, "_finish_workflow", finish),
        ):
            invocation = scout_runner.run_first_report_scout(
                SandboxedEvalCase(name="sparse", prompt="Run the scout"),
                CustomPromptSandboxContext(team_id=1, user_id=2),
                provider=provider,
                on_cleanup=AsyncMock(side_effect=BrokenPipeError("Reporter disconnected")),
            )
            if cancel_during is not None:
                running = asyncio.create_task(invocation)
                await cleanup_started.wait()
                provider.cleanup_case.assert_not_called()
                running.cancel()
                release_cleanup.set()
                with self.assertRaises(asyncio.CancelledError):
                    await running
            elif error is not None:
                with self.assertRaises(type(error)) as raised:
                    await invocation
                self.assertIs(raised.exception, error)
            elif not cleanup_confirmed:
                with self.assertRaises(WorkflowCleanupError):
                    await invocation
            else:
                completed = await invocation
                self.assertEqual(completed.artifacts.model_dump()["missing_data"], ["More cohorts"])
        self.assertTrue(workflow_finished.is_set())
        provider.cleanup_case.assert_called_once_with("task")
