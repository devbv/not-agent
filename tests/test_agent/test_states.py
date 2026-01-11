"""Tests for agent loop states."""

import time

import pytest

from not_agent.agent.states import LoopState, TerminationReason, LoopContext


class TestLoopState:
    """LoopState enum 테스트."""

    def test_all_states_defined(self):
        """모든 상태가 정의되어 있는지 확인."""
        expected = [
            "IDLE",
            "RECEIVING_INPUT",
            "CALLING_LLM",
            "PROCESSING_RESPONSE",
            "EXECUTING_TOOLS",
            "CHECKING_CONTEXT",
            "COMPLETED",
            "ERROR",
        ]
        actual = [s.name for s in LoopState]
        assert actual == expected


class TestTerminationReason:
    """TerminationReason enum 테스트."""

    def test_all_reasons_defined(self):
        """모든 종료 사유가 정의되어 있는지 확인."""
        expected = [
            "END_TURN",
            "MAX_TURNS",
            "STOP_REASON",
            "USER_INTERRUPT",
            "ERROR",
            "TOOL_STOP",
        ]
        actual = [r.name for r in TerminationReason]
        assert actual == expected


class TestLoopContext:
    """LoopContext 테스트."""

    def test_initial_state(self):
        """초기 상태 확인."""
        ctx = LoopContext()
        assert ctx.state == LoopState.IDLE
        assert ctx.termination_reason is None
        assert ctx.current_turn == 0
        assert ctx.max_turns == 20
        assert ctx.last_error is None
        assert ctx.total_tool_calls == 0
        assert ctx.total_llm_calls == 0

    def test_is_running(self):
        """is_running() 메서드 테스트."""
        ctx = LoopContext()

        # IDLE 상태 - 실행 중 아님
        assert not ctx.is_running()

        # 실행 중 상태들
        running_states = [
            LoopState.RECEIVING_INPUT,
            LoopState.CALLING_LLM,
            LoopState.PROCESSING_RESPONSE,
            LoopState.EXECUTING_TOOLS,
            LoopState.CHECKING_CONTEXT,
        ]
        for state in running_states:
            ctx.state = state
            assert ctx.is_running(), f"{state.name} should be running"

        # 종료 상태들
        ctx.state = LoopState.COMPLETED
        assert not ctx.is_running()

        ctx.state = LoopState.ERROR
        assert not ctx.is_running()

    def test_is_finished(self):
        """is_finished() 메서드 테스트."""
        ctx = LoopContext()

        # 미완료 상태들
        non_finished_states = [
            LoopState.IDLE,
            LoopState.RECEIVING_INPUT,
            LoopState.CALLING_LLM,
            LoopState.PROCESSING_RESPONSE,
            LoopState.EXECUTING_TOOLS,
            LoopState.CHECKING_CONTEXT,
        ]
        for state in non_finished_states:
            ctx.state = state
            assert not ctx.is_finished(), f"{state.name} should not be finished"

        # 완료 상태
        ctx.state = LoopState.COMPLETED
        assert ctx.is_finished()

        # 에러 상태
        ctx.state = LoopState.ERROR
        assert ctx.is_finished()

    def test_duration_ms(self):
        """duration_ms() 메서드 테스트."""
        ctx = LoopContext()

        # 시작 시간 없으면 None
        assert ctx.duration_ms() is None

        # 시작만 있으면 현재까지 시간
        ctx.start_time = time.time()
        time.sleep(0.01)  # 10ms
        duration = ctx.duration_ms()
        assert duration is not None
        assert duration >= 10  # 최소 10ms

        # 종료 시간도 있으면 정확한 시간
        ctx.end_time = ctx.start_time + 0.1  # 100ms
        assert ctx.duration_ms() == pytest.approx(100, rel=0.01)

    def test_record_state(self):
        """record_state() 메서드 테스트."""
        ctx = LoopContext()
        assert len(ctx._state_history) == 0

        ctx.record_state(LoopState.RECEIVING_INPUT)
        assert ctx.state == LoopState.RECEIVING_INPUT
        assert len(ctx._state_history) == 1

        ctx.record_state(LoopState.CALLING_LLM)
        assert ctx.state == LoopState.CALLING_LLM
        assert len(ctx._state_history) == 2

        # 이력 확인
        assert ctx._state_history[0][1] == LoopState.RECEIVING_INPUT
        assert ctx._state_history[1][1] == LoopState.CALLING_LLM

    def test_reset(self):
        """reset() 메서드 테스트."""
        ctx = LoopContext()

        # 상태 변경
        ctx.state = LoopState.EXECUTING_TOOLS
        ctx.termination_reason = TerminationReason.END_TURN
        ctx.current_turn = 5
        ctx.total_tool_calls = 10
        ctx.total_llm_calls = 3
        ctx.start_time = time.time()
        ctx.end_time = time.time()
        ctx.last_error = Exception("test")
        ctx.record_state(LoopState.COMPLETED)

        # 리셋
        ctx.reset()

        # 초기 상태 확인
        assert ctx.state == LoopState.IDLE
        assert ctx.termination_reason is None
        assert ctx.current_turn == 0
        assert ctx.total_tool_calls == 0
        assert ctx.total_llm_calls == 0
        assert ctx.start_time is None
        assert ctx.end_time is None
        assert ctx.last_error is None
        assert len(ctx._state_history) == 0

    def test_to_dict(self):
        """to_dict() 메서드 테스트."""
        ctx = LoopContext()
        ctx.state = LoopState.COMPLETED
        ctx.termination_reason = TerminationReason.END_TURN
        ctx.current_turn = 3
        ctx.max_turns = 20
        ctx.total_tool_calls = 5
        ctx.total_llm_calls = 2
        ctx.start_time = time.time()
        ctx.end_time = ctx.start_time + 0.5

        result = ctx.to_dict()

        assert result["state"] == "COMPLETED"
        assert result["termination_reason"] == "END_TURN"
        assert result["current_turn"] == 3
        assert result["max_turns"] == 20
        assert result["total_tool_calls"] == 5
        assert result["total_llm_calls"] == 2
        assert result["duration_ms"] == pytest.approx(500, rel=0.01)
        assert result["has_error"] is False

    def test_to_dict_with_error(self):
        """에러가 있을 때 to_dict() 테스트."""
        ctx = LoopContext()
        ctx.last_error = Exception("test error")
        ctx.termination_reason = TerminationReason.ERROR

        result = ctx.to_dict()

        assert result["has_error"] is True
        assert result["termination_reason"] == "ERROR"

    def test_to_dict_no_termination(self):
        """종료 사유가 없을 때 to_dict() 테스트."""
        ctx = LoopContext()

        result = ctx.to_dict()

        assert result["termination_reason"] is None
