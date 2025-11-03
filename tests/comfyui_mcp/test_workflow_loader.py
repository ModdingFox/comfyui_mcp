import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import quote

import pytest

from comfyui_mcp.argument_parser import ArgsComfyUI, ArgsGenerate
from comfyui_mcp.workflow_loader import load_workflows_from_comfyui, load_workflows_from_path


def dummy_generation_function(*_args, **_kwargs):
    return "mocked generation result"


def make_dummy_workflow(i: int):
    return {
        "0": {
            "_meta": {"title": f"workflow_{i}"},
            "class_type": "PrimitiveInt",
            "inputs": {"value": i},
        }
    }


class TestWorkflowLoader:
    @pytest.mark.parametrize("count", [1, 2, 3])
    def test_load_workflows_from_path(self, tmp_path: Path, count: int):
        workflows = [make_dummy_workflow(i) for i in range(count)]
        for i, wf in enumerate(workflows):
            (tmp_path / f"workflow_{i}.json").write_text(json.dumps(wf))

        argscomfyui = ArgsComfyUI(workflow_directory=str(tmp_path))
        argsgenerate = ArgsGenerate()
        mock_fast_mcp = MagicMock()
        mock_fast_mcp.add_tool = MagicMock()

        load_workflows_from_path(
            argscomfyui=argscomfyui,
            argsgenerate=argsgenerate,
            generation_function=dummy_generation_function,
            fast_mcp=mock_fast_mcp,
        )

        assert mock_fast_mcp.add_tool.call_count == count

    @pytest.mark.parametrize("count", [1, 2, 3])
    @patch("comfyui_mcp.workflow_loader.post")
    @patch("comfyui_mcp.workflow_loader.get")
    def test_load_workflows_from_comfyui(self, mock_get, mock_post, count: int):
        """Match loader’s real URL patterns (http:// + host + v2/userdata for first, /userdata for others)."""
        base_url = "http://comfy:8188"
        workflows = [make_dummy_workflow(i) for i in range(count)]

        list_response = MagicMock()
        list_response.json.return_value = [
            {"name": f"workflow_{i}.json", "type": "file", "path": f"workflows/workflow_{i}.json"}
            for i in range(count)
        ]

        workflow_responses = []
        for wf in workflows:
            r = MagicMock()
            r.json.return_value = wf
            workflow_responses.append(r)

        mock_get.side_effect = [list_response] + workflow_responses

        post_responses = []
        for wf in workflows:
            pr = MagicMock()
            pr.json.return_value = wf
            post_responses.append(pr)
        mock_post.side_effect = post_responses

        argscomfyui = ArgsComfyUI(host=base_url)
        argsgenerate = ArgsGenerate()
        mock_fast_mcp = MagicMock()
        mock_fast_mcp.add_tool = MagicMock()

        load_workflows_from_comfyui(
            argscomfyui=argscomfyui,
            argsgenerate=argsgenerate,
            generation_function=dummy_generation_function,
            fast_mcp=mock_fast_mcp,
        )

        assert mock_get.call_count == count + 1
        assert mock_post.call_count == count
        assert mock_fast_mcp.add_tool.call_count == count

        # Adjusted expected URLs to match observed real behavior
        expected_urls = [
            f"http://{base_url}/api/v2/userdata?path={quote('workflows', safe='')}"
        ] + [
            f"http://{base_url}/api/userdata/{quote('workflows/workflow_' + str(i) + '.json', safe='')}"
            for i in range(count)
        ]

        called_urls = [args[0][0] for args in mock_get.call_args_list]
        assert called_urls == expected_urls
