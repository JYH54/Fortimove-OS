import logging
from typing import Dict, Any

from agent_framework import TaskResult, ExecutionContext
from approval_queue import ApprovalQueueManager

logger = logging.getLogger(__name__)

def approval_queue_hook(step_id: str, agent_name: str, mapped_input: Dict[str, Any], result: TaskResult, context: ExecutionContext):
    """
    Post-execution hook for WorkflowExecutor.
    Submits to the Approval Queue ONLY if:
    1. It is a product_registration task.
    2. The status is 'hold' or 'reject', OR 'ready' but needs_human_review=True.
    """
    if not result.is_success() or not result.output:
        return

    # Specific business rule: Only queue product registration results
    if agent_name != "product_registration":
        return

    reg_status = result.output.get("registration_status")
    needs_review = result.output.get("needs_human_review", False)
    
    if reg_status in ["hold", "reject"] or (reg_status == "ready" and needs_review):
        try:
            aq = ApprovalQueueManager()
            source_title = mapped_input.get("source_title", "Unknown Source Title")
            
            review_id = aq.create_item(
                source_type=agent_name,
                source_title=source_title,
                agent_output=result.output,
                source_data=mapped_input
            )
            logger.info(f"📝 큐(Approval Queue) 등록 완료: [{review_id}] {agent_name} -> {reg_status}")
        except Exception as e:
            # We explicitly raise it here so the engine loop can catch it, log it as warning, 
            # and NOT crash the workflow, maintaining engine isolation.
            raise RuntimeError(f"ApprovalQueue Insert Failed: {e}")
