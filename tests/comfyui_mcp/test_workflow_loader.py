import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from comfyui_mcp.argument_parser import ArgsComfyUI, ArgsGenerate
from comfyui_mcp.workflow_loader import load_workflows_from_comfyui, load_workflows_from_path


def dummy_generation_function(*_args, **_kwargs):
    """Dummy generation function for testing."""
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
    @patch("comfyui_mcp.workflow_loader.ComfyUIClient")
    def test_load_workflows_from_comfyui(self, mock_client_class, count: int):
        """Test workflow loading using mocked ComfyUIClient."""
        workflows = [make_dummy_workflow(i) for i in range(count)]
        # Mock the client instance
        mock_client = MagicMock()
        mock_client.list_workflows.return_value = [
            {"name": f"workflow_{i}.json", "type": "file", "path": f"workflows/workflow_{i}.json"}
            for i in range(count)
        ]
        # Setup get_workflow to return workflows in sequence
        mock_client.get_workflow.side_effect = workflows
        # Setup convert_workflow to return the same workflows
        mock_client.convert_workflow.side_effect = workflows
        mock_client_class.return_value = mock_client
        argscomfyui = ArgsComfyUI(host="comfy:8188")
        argsgenerate = ArgsGenerate()
        mock_fast_mcp = MagicMock()
        mock_fast_mcp.add_tool = MagicMock()
        load_workflows_from_comfyui(
            argscomfyui=argscomfyui,
            argsgenerate=argsgenerate,
            generation_function=dummy_generation_function,
            fast_mcp=mock_fast_mcp,
        )
        assert mock_client.list_workflows.call_count == 1
        assert mock_client.get_workflow.call_count == count
        assert mock_client.convert_workflow.call_count == count
        assert mock_fast_mcp.add_tool.call_count == count

    @patch("comfyui_mcp.workflow_loader.ComfyUIClient")
    def test_load_workflows_from_comfyui_with_non_file_types(self, mock_client_class):
        """Test that non-file workflow types are skipped."""
        # Mock the client instance
        mock_client = MagicMock()
        mock_client.list_workflows.return_value = [
            {"name": "workflow_0.json", "type": "file", "path": "workflows/workflow_0.json"},
            {"name": "workflow_dir", "type": "directory", "path": "workflows/workflow_dir"},
            {"name": "workflow_1.json", "type": "file", "path": "workflows/workflow_1.json"},
            {"name": "workflow_link", "type": "symlink", "path": "workflows/workflow_link"},
        ]

        workflows = [make_dummy_workflow(0), make_dummy_workflow(1)]
        mock_client.get_workflow.side_effect = workflows
        mock_client.convert_workflow.side_effect = workflows
        mock_client_class.return_value = mock_client

        argscomfyui = ArgsComfyUI(host="comfy:8188")
        argsgenerate = ArgsGenerate()
        mock_fast_mcp = MagicMock()

        load_workflows_from_comfyui(
            argscomfyui=argscomfyui,
            argsgenerate=argsgenerate,
            generation_function=dummy_generation_function,
            fast_mcp=mock_fast_mcp,
        )

        # Only 2 file-type workflows should be processed
        assert mock_client.get_workflow.call_count == 2
        assert mock_client.convert_workflow.call_count == 2
        assert mock_fast_mcp.add_tool.call_count == 2

    @pytest.mark.parametrize("count", [0])
    def test_load_workflows_from_path_empty_directory(self, tmp_path: Path, count: int):
        """Test loading from an empty directory."""
        argscomfyui = ArgsComfyUI(workflow_directory=str(tmp_path))
        argsgenerate = ArgsGenerate()
        mock_fast_mcp = MagicMock()

        load_workflows_from_path(
            argscomfyui=argscomfyui,
            argsgenerate=argsgenerate,
            generation_function=dummy_generation_function,
            fast_mcp=mock_fast_mcp,
        )

        assert mock_fast_mcp.add_tool.call_count == count

    @patch("comfyui_mcp.workflow_loader.ComfyUIClient")
    def test_load_workflows_from_comfyui_empty_list(self, mock_client_class):
        """Test loading when no workflows are available."""
        mock_client = MagicMock()
        mock_client.list_workflows.return_value = []
        mock_client_class.return_value = mock_client

        argscomfyui = ArgsComfyUI(host="comfy:8188")
        argsgenerate = ArgsGenerate()
        mock_fast_mcp = MagicMock()

        load_workflows_from_comfyui(
            argscomfyui=argscomfyui,
            argsgenerate=argsgenerate,
            generation_function=dummy_generation_function,
            fast_mcp=mock_fast_mcp,
        )

        assert mock_client.list_workflows.call_count == 1
        assert mock_client.get_workflow.call_count == 0
        assert mock_fast_mcp.add_tool.call_count == 0
