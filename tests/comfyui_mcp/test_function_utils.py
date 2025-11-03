import asyncio
from json import dumps

import pytest

from comfyui_mcp.argument_parser import ArgsComfyUI, ArgsGenerate
from comfyui_mcp.base_types import (
    WorkflowParamType,
    WorkflowType,
    WrappedFunctionType,
)
from comfyui_mcp.function_utils import wrap_fn
from tests.comfyui_mcp.payloads import (
    valid_workflow_payload_base,
    valid_workflow_payload_image,
    workflow_params_modified_base,
    workflow_params_modified_image,
)


class TestFunctionUtils:
    @pytest.mark.parametrize(
        ("expected_workflow_params", "workflow_payload"),
        [
            (workflow_params_modified_base, valid_workflow_payload_base),
            (workflow_params_modified_image, valid_workflow_payload_image),
        ],
    )
    def test_wrap_fn(self, expected_workflow_params: WorkflowParamType, workflow_payload: WorkflowType):
        """
        Test that wrap_fn correctly builds a callable whose invocation passes
        ArgsComfyUI, ArgsGenerate, workflow, and params to the wrapped coroutine.
        Run the wrapper via asyncio.run() so async defs are properly executed.
        """
        argscomfyui = ArgsComfyUI()
        argsgenerate = ArgsGenerate()

        async def test_funct(
            _argscomfyui: ArgsComfyUI,
            _argsgenerate: ArgsGenerate,
            workflow: WorkflowType,
            workflow_params: WorkflowParamType,
        ) -> str:
            assert workflow == workflow_payload
            # ensure all expected params were forwarded
            for k, v in expected_workflow_params.items():
                assert workflow_params[k] == v
            assert "submit_batch" in workflow_params
            assert "batch_by_time" in workflow_params
            return dumps(workflow, indent=4, sort_keys=True)

        wrapped_fn: WrappedFunctionType = wrap_fn(
            argscomfyui=argscomfyui,
            argsgenerate=argsgenerate,
            name="test_funct",
            workflow=workflow_payload,
            wrapped_fn=test_funct,
        )

        # Always run through asyncio to avoid "async def not supported" failures
        result = asyncio.run(wrapped_fn(**expected_workflow_params))
        assert result == dumps(workflow_payload, indent=4, sort_keys=True)

        # confirm metadata on the wrapper
        assert wrapped_fn.__name__ == "test_funct"
        assert "submit_batch" in wrapped_fn.__annotations__
        assert "batch_by_time" in wrapped_fn.__annotations__
