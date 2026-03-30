import pytest
from agent_framework import (
    DataResolver, ExecutionContext, TaskResult, AgentStatus, 
    WorkflowExecutor, WorkflowStep, AgentRegistry, BaseAgent
)
from pydantic import BaseModel
from typing import Dict, Any, Type

class DummyInput(BaseModel):
    message: str
    price: float
    mapped_id: str

class DummyOutput(BaseModel):
    completed_msg: str

class EchoAgent(BaseAgent):
    @property
    def input_schema(self) -> Type[BaseModel]:
        return DummyInput
    @property
    def output_schema(self) -> Type[BaseModel]:
        return DummyOutput

    def __init__(self, name="echo"):
        super().__init__(name)

    def _do_execute(self, input_model: DummyInput) -> Dict[str, Any]:
        return {"completed_msg": f"{input_model.message} - {input_model.price} - {input_model.mapped_id}"}

def test_data_resolver():
    ctx = ExecutionContext("hello raw input", {"user_id": "12345"})
    ctx.add_result("step1", "magic_agent", TaskResult(
        agent_name="magic", status=AgentStatus.COMPLETED.value, output={"computed_id": "999"}
    ))

    mapping = {
        "raw": "user_input.raw_message",
        "structured": "user_input.structured.user_id",
        "hardcoded": "literal.foo",
        "chained": "step1.output.computed_id"
    }

    res = DataResolver.resolve(mapping, ctx)
    assert res["raw"] == "hello raw input"
    assert res["structured"] == "12345"
    assert res["hardcoded"] == "foo"
    assert res["chained"] == "999"

def test_resolver_missing_source():
    ctx = ExecutionContext("test")
    mapping = {"missing": "step99.output.id"}
    with pytest.raises(ValueError, match="Mapping source step not found"):
        DataResolver.resolve(mapping, ctx)

def test_workflow_execution_success():
    registry = AgentRegistry()
    registry.register("echo", EchoAgent())
    
    executor = WorkflowExecutor(registry)
    ctx = ExecutionContext("buy this", {"price_val": 500.5})

    workflow = [
        {
            "step_id": "s1",
            "agent": "echo",
            "depends_on": [],
            "input_mapping": {
                "message": "user_input.raw_message",
                "price": "user_input.structured.price_val",
                "mapped_id": "literal.xyz"
            },
            "checks": {
                "required_fields": ["message", "price"]
            }
        }
    ]

    res_ctx = executor.execute_sequential(workflow, ctx)
    s1_res = res_ctx.get_result("s1")
    assert s1_res is not None
    assert s1_res.status == AgentStatus.COMPLETED.value
    assert s1_res.output["completed_msg"] == "buy this - 500.5 - xyz"

def test_workflow_execution_fail_message():
    registry = AgentRegistry()
    registry.register("echo", EchoAgent())
    
    executor = WorkflowExecutor(registry)
    ctx = ExecutionContext("buy this")

    workflow = [
        {
            "step_id": "s1",
            "agent": "echo",
            "depends_on": [],
            "input_mapping": {
                "message": "user_input.raw_message"
                # missing price
            },
            "checks": {
                "required_fields": ["price"],
                "fail_message": "CUSTOM ERROR: Price is missing!"
            }
        }
    ]

    res_ctx = executor.execute_sequential(workflow, ctx)
    s1_res = res_ctx.get_result("s1")
    assert s1_res.status == AgentStatus.FAILED.value
    assert "CUSTOM ERROR: Price is missing!" in s1_res.error
