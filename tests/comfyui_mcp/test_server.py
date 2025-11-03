import asyncio
from json import dumps
from unittest.mock import AsyncMock, patch

import pytest
from comfyui_utils.comfy import Callbacks  # type: ignore[import-untyped]

from comfyui_mcp.argument_parser import ArgsComfyUI, ArgsGenerate
from comfyui_mcp.base_types import WorkflowType
from comfyui_mcp.server import generate_image
from tests.comfyui_mcp.payloads import (
    valid_workflow_payload_base,
    valid_workflow_payload_modified_base,
    workflow_params_modified_base,
)


class TestServer:
    @pytest.mark.parametrize(
        (
            "generated_images",
            "submit_batch",
            "workflow_params_modified",
            "workflow_payload",
            "workflow_payload_expected",
        ),
        [
            ([], 1, workflow_params_modified_base, valid_workflow_payload_base, valid_workflow_payload_modified_base),
            ([], 2, workflow_params_modified_base, valid_workflow_payload_base, valid_workflow_payload_modified_base),
            ([{"filename": "image_0.png"}], 1, workflow_params_modified_base, valid_workflow_payload_base, valid_workflow_payload_modified_base),
            ([{"filename": "image_0.png"}], 2, workflow_params_modified_base, valid_workflow_payload_base, valid_workflow_payload_modified_base),
            ([{"filename": "image_0.png"}, {"filename": "image_1.png"}], 1, workflow_params_modified_base, valid_workflow_payload_base, valid_workflow_payload_modified_base),
            ([{"filename": "image_0.png"}, {"filename": "image_1.png"}], 2, workflow_params_modified_base, valid_workflow_payload_base, valid_workflow_payload_modified_base),
        ],
    )
    @patch("comfyui_mcp.server.SystemRandom.randint", return_value=0)
    @patch("comfyui_mcp.workflow_utils.ComfyAPI")
    def test_generate_image(
        self,
        mock_comfy_api,
        mock_randint,
        generated_images,
        submit_batch,
        workflow_params_modified,
        workflow_payload,
        workflow_payload_expected,
    ):
        """Ensure generate_image behaves deterministically and matches expected markdown output."""

        async def submit_side_effect(workflow: WorkflowType, callbacks: Callbacks) -> None:
            assert workflow == workflow_payload_expected
            await callbacks.queue_position(0)
            await callbacks.in_progress(0, 100, len(generated_images))
            await callbacks.completed({"images": generated_images}, cached=False)

        mock_comfy_api_instance = AsyncMock()
        mock_comfy_api_instance.submit.side_effect = submit_side_effect
        mock_comfy_api.return_value = mock_comfy_api_instance

        argscomfyui = ArgsComfyUI()
        argsgenerate = ArgsGenerate()

        # build params
        generation_params = {
            **workflow_params_modified,
            "seed": 1,
            "submit_batch": submit_batch,
            "batch_by_time": False,
        }

        result = asyncio.run(generate_image(argscomfyui, argsgenerate, workflow_payload, dict(generation_params)))

        # ---- expected output reconstruction ----
        if not generated_images:
            expected = argsgenerate.nothing_generated_message
        else:
            params_copy = dict(generation_params)
            image_list = []
            index = 0
            for _ in range(submit_batch):
                for img in generated_images:
                    url = f"http://{argscomfyui.host}/api/view?filename={img['filename']}"
                    image_list.append(argsgenerate.image_url_template.format(index=index, url=url))
                    index += 1

            if submit_batch <= 1:
                params_copy["seed"] = 1
            else:
                params_copy["seeds"] = [params_copy["seed"], 0]
                del params_copy["seed"]

            workflow_json = dumps(
                params_copy,
                indent=argsgenerate.reply_workflow_format_indent,
                sort_keys=argsgenerate.reply_workflow_format_sort_keys,
            )

            expected = argsgenerate.result_generated_message_template.format(
                image_list="".join(image_list)
            )
            expected += argsgenerate.reply_workflow_template.format(workflow_params=workflow_json)

        assert result == expected
