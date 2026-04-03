import pytest
from unittest.mock import MagicMock, patch
from approval_integration import approval_queue_hook
from agent_framework import TaskResult, ExecutionContext

@pytest.fixture
def mock_aq():
    with patch('approval_integration.ApprovalQueueManager') as mock:
        yield mock.return_value

def test_hook_ignores_non_product_registration(mock_aq):
    result = TaskResult(agent_name="some_other_agent", status="completed", output={"registration_status": "hold"})
    context = MagicMock(spec=ExecutionContext)
    
    approval_queue_hook("step_1", "some_other_agent", {}, result, context)
    
    mock_aq.create_item.assert_not_called()

def test_hook_ignores_ready_without_review(mock_aq):
    result = TaskResult(agent_name="product_registration", status="completed", output={
        "registration_status": "ready",
        "needs_human_review": False
    })
    context = MagicMock(spec=ExecutionContext)
    
    approval_queue_hook("step_1", "product_registration", {"source_title": "test"}, result, context)
    
    mock_aq.create_item.assert_not_called()

def test_hook_queues_hold_result(mock_aq):
    result = TaskResult(agent_name="product_registration", status="completed", output={
        "registration_status": "hold",
        "needs_human_review": True,
        "hold_reason": "Risky wording"
    })
    context = MagicMock(spec=ExecutionContext)
    mapped_input = {"source_title": "Risky Product"}
    
    approval_queue_hook("step_1", "product_registration", mapped_input, result, context)
    
    mock_aq.create_item.assert_called_once_with(
        source_type="product_registration",
        source_title="Risky Product",
        agent_output=result.output
    )

def test_hook_queues_ready_with_review(mock_aq):
    result = TaskResult(agent_name="product_registration", status="completed", output={
        "registration_status": "ready",
        "needs_human_review": True
    })
    context = MagicMock(spec=ExecutionContext)
    mapped_input = {"source_title": "Clean but Sensitive"}
    
    approval_queue_hook("step_1", "product_registration", mapped_input, result, context)
    
    mock_aq.create_item.assert_called_once()

def test_hook_handles_aq_failure_gracefully(mock_aq):
    # This test verifies that the hook raises RuntimeError which is then caught by WorkflowExecutor
    mock_aq.create_item.side_effect = Exception("DB Error")
    result = TaskResult(agent_name="product_registration", status="completed", output={"registration_status": "hold"})
    context = MagicMock(spec=ExecutionContext)
    
    with pytest.raises(RuntimeError, match="ApprovalQueue Insert Failed"):
        approval_queue_hook("step_1", "product_registration", {}, result, context)
