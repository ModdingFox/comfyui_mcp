import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import pytest
import requests

from comfyui_mcp.argument_parser import ArgsComfyUI
from comfyui_mcp.base_types import (
    ComfyResult,
    HistoryEntry,
    HistoryResponse,
    NodeOutput,
    OutputFile,
    QueueResponse,
)
from comfyui_mcp.exceptions import (
    ExecutionFailedError,
    JobLostError,
    PromptValidationError,
    QueueValidationError,
    TimeoutError,
)
from comfyui_mcp.workflow_utils import (
    ComfyUIClient,
    call_workflow,
    get_params_from_workflow,
    prepare_workflow,
)


def test_call_workflow():
    """Run call_workflow with a mocked ComfyUIClient."""
    # Create mock history entry with outputs
    mock_output_file = OutputFile(filename="test.png", subfolder="", type="output")
    mock_node_output = MagicMock(spec=NodeOutput)
    mock_node_output.get_all_outputs.return_value = {"images": [mock_output_file]}
    mock_entry = MagicMock(spec=HistoryEntry)
    mock_entry.outputs = {"101": mock_node_output}
    with patch("comfyui_mcp.workflow_utils.ComfyUIClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.execute_workflow = AsyncMock(return_value=mock_entry)
        mock_client_class.return_value = mock_client
        argscomfyui = ArgsComfyUI(host="localhost:8188")
        workflow = {"nodes": {"0": {"class_type": "ImageSaver"}}}
        result = asyncio.run(call_workflow(argscomfyui, workflow))
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == ComfyResult(
            media_type="images",
            filename="http://localhost:8188/api/view?filename=test.png",
        )
        mock_client.execute_workflow.assert_called_once_with(workflow)


def test_call_workflow_multiple_outputs():
    """Test call_workflow with multiple output types from multiple nodes."""
    mock_image = OutputFile(filename="image.png", subfolder="", type="output")
    mock_audio = OutputFile(filename="audio.mp3", subfolder="", type="output")

    # Create two node outputs - one for images, one for audio
    mock_node_output1 = Mock()
    mock_node_output1.get_all_outputs.return_value = {"images": [mock_image]}

    mock_node_output2 = Mock()
    mock_node_output2.get_all_outputs.return_value = {"audio": [mock_audio]}

    # Create a mock entry with outputs as a plain dict
    mock_entry = Mock()
    # Use type() to create a simple object with an outputs attribute
    outputs_dict = {"101": mock_node_output1, "102": mock_node_output2}
    type(mock_entry).outputs = PropertyMock(return_value=outputs_dict)

    with patch("comfyui_mcp.workflow_utils.ComfyUIClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.execute_workflow = AsyncMock(return_value=mock_entry)
        mock_client_class.return_value = mock_client
        argscomfyui = ArgsComfyUI(host="localhost:8188")
        workflow = {"nodes": {"0": {"class_type": "ImageSaver"}}}
        result = asyncio.run(call_workflow(argscomfyui, workflow))
        assert len(result) == 2
        media_types = [r.media_type for r in result]
        assert "images" in media_types
        assert "audio" in media_types


def test_get_params_from_workflow():
    """Ensure parameter extraction matches real keying by _meta.title."""
    workflow_payload = {
        "0": {
            "_meta": {"title": "Node0"},
            "class_type": "PrimitiveInt",
            "inputs": {"value": 42},
        },
        "1": {
            "_meta": {"title": "Node1"},
            "class_type": "ImageResize",
            "inputs": {"width": 1280, "height": 720},
        },
    }
    result = get_params_from_workflow(workflow_payload)
    expected = {"Node0": 42}
    assert result == expected


def test_get_params_from_workflow_loadimageoutput():
    """Covers the LoadImageOutput branch (empty string result)."""
    workflow_payload = {
        "0": {
            "_meta": {"title": "Loader"},
            "class_type": "LoadImageOutput",
            "inputs": {"image": "path/to/image.png"},
        }
    }
    result = get_params_from_workflow(workflow_payload)
    assert result == {"Loader": ""}


def test_get_params_from_workflow_primitive_float():
    """Test PrimitiveFloat extraction."""
    workflow_payload = {
        "0": {
            "_meta": {"title": "Scale"},
            "class_type": "PrimitiveFloat",
            "inputs": {"value": 1.5},
        }
    }
    result = get_params_from_workflow(workflow_payload)
    assert result == {"Scale": 1.5}


def test_get_params_from_workflow_primitive_without_value():
    """Test Primitive node without 'value' in inputs (None case)."""
    workflow_payload = {
        "0": {
            "_meta": {"title": "NoValue"},
            "class_type": "PrimitiveInt",
            "inputs": {},  # No 'value' key
        }
    }
    result = get_params_from_workflow(workflow_payload)
    # Should not include this node since inputs_value is None
    assert result == {}


def test_get_params_from_workflow_primitive_float_without_value():
    """Test PrimitiveFloat node without 'value' in inputs (None case)."""
    workflow_payload = {
        "0": {
            "_meta": {"title": "FloatNoValue"},
            "class_type": "PrimitiveFloat",
            "inputs": {},  # No 'value' key
        }
    }
    result = get_params_from_workflow(workflow_payload)
    # Should not include this node since inputs_value is None
    assert result == {}


def test_prepare_workflow():
    """Ensure prepare_workflow updates prompt and preserves structure."""
    workflow_payload = {
        "0": {
            "_meta": {"title": "Example"},
            "class_type": "ImageGenerator",
            "inputs": {"prompt": "old prompt"},
        }
    }
    # Modify directly to simulate input update
    workflow_payload["0"]["inputs"]["prompt"] = "new prompt"
    result = prepare_workflow(workflow_payload)
    assert "0" in result
    assert "inputs" in result["0"]
    assert result["0"]["inputs"]["prompt"] == "new prompt"
    assert result["0"]["class_type"] == "ImageGenerator"


def test_prepare_workflow_primitive_update():
    """Ensure prepare_workflow replaces Primitive inputs correctly."""
    workflow_payload = {
        "0": {
            "_meta": {"title": "Height"},
            "class_type": "PrimitiveInt",
            "inputs": {"value": 720},
        }
    }
    updated = prepare_workflow(workflow_payload, Height=1080)
    assert updated["0"]["inputs"]["value"] == 1080


def test_prepare_workflow_loadimageoutput(tmp_path: Path):
    """Covers LoadImageOutput handling with static [output] tag."""
    image_path = tmp_path / "photo.png"
    image_path.write_text("fake")
    workflow_payload = {
        "0": {
            "_meta": {"title": "Loader"},
            "class_type": "LoadImageOutput",
            "inputs": {"image": ""},
        }
    }
    updated = prepare_workflow(workflow_payload, Loader=str(image_path))
    expected_value = f"{image_path} [output]"
    assert updated["0"]["inputs"]["image"] == expected_value


def test_prepare_workflow_no_matching_kwargs():
    """Test prepare_workflow when no kwargs match node titles."""
    workflow_payload = {
        "0": {
            "_meta": {"title": "Height"},
            "class_type": "PrimitiveInt",
            "inputs": {"value": 720},
        }
    }
    # Pass kwargs that don't match any node title
    updated = prepare_workflow(workflow_payload, Width=1080)
    # Should remain unchanged
    assert updated["0"]["inputs"]["value"] == 720


def test_prepare_workflow_primitive_other_than_startswith():
    """Test prepare_workflow with PrimitiveFloat to cover the elif branch."""
    workflow_payload = {
        "0": {
            "_meta": {"title": "Scale"},
            "class_type": "PrimitiveFloat",
            "inputs": {"value": 1.0},
        }
    }
    updated = prepare_workflow(workflow_payload, Scale=2.5)
    # PrimitiveFloat starts with "Primitive" so should be updated
    assert updated["0"]["inputs"]["value"] == 2.5


def test_prepare_workflow_non_primitive_non_loadimage():
    """Test prepare_workflow with node that's neither Primitive nor LoadImageOutput."""
    workflow_payload = {
        "0": {
            "_meta": {"title": "OtherNode"},
            "class_type": "SomeOtherClass",
            "inputs": {"param": "value"},
        }
    }
    # Even if we pass matching kwarg, it shouldn't update non-Primitive/non-LoadImage nodes
    updated = prepare_workflow(workflow_payload, OtherNode="newvalue")
    # Should remain unchanged since it doesn't match the if/elif conditions
    assert updated["0"]["inputs"]["param"] == "value"


class TestComfyUIClient:
    """Test ComfyUIClient methods."""

    def test_init(self):
        """Test client initialization."""
        args = ArgsComfyUI(host="localhost:8188")
        client = ComfyUIClient(args)
        assert client.host == "localhost:8188"
        assert client.max_retries == 5
        assert client.request_timeout == 30
        assert client.queue_check_interval == 2.0
        assert client.lost_job_check_limit == 10
        assert client.max_wait_time is None

    @patch("comfyui_mcp.workflow_utils.requests.request")
    def test_make_request_success(self, mock_request):
        """Test successful request."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"status": "ok"}
        mock_request.return_value = mock_response
        args = ArgsComfyUI(host="localhost:8188")
        client = ComfyUIClient(args)
        response = client._make_request("GET", "/test")
        assert response == mock_response
        mock_request.assert_called_once()
        assert mock_request.call_args[0] == ("GET", "http://localhost:8188/test")

    @patch("comfyui_mcp.workflow_utils.requests.request")
    def test_make_request_retry(self, mock_request):
        """Test request retry on failure."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()

        # Fail twice, then succeed
        mock_request.side_effect = [
            requests.RequestException("Connection error"),
            requests.RequestException("Connection error"),
            mock_response,
        ]
        args = ArgsComfyUI(host="localhost:8188", max_retries=3)
        client = ComfyUIClient(args)
        response = client._make_request("GET", "/test")
        assert response == mock_response
        assert mock_request.call_count == 3

    @patch("comfyui_mcp.workflow_utils.requests.request")
    def test_make_request_max_retries_exceeded(self, mock_request):
        """Test request failure after max retries."""
        mock_request.side_effect = requests.RequestException("Connection error")
        args = ArgsComfyUI(host="localhost:8188", max_retries=2)
        client = ComfyUIClient(args)

        with pytest.raises(requests.RequestException):
            client._make_request("GET", "/test")

    @patch.object(ComfyUIClient, "_make_request")
    def test_get_queue_success(self, mock_make_request):
        """Test get_queue with valid response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "queue_running": [],
            "queue_pending": [],
        }
        mock_make_request.return_value = mock_response
        args = ArgsComfyUI(host="localhost:8188")
        client = ComfyUIClient(args)
        queue = client.get_queue()
        assert isinstance(queue, QueueResponse)
        mock_make_request.assert_called_once_with("GET", "/queue")

    @patch.object(ComfyUIClient, "_make_request")
    def test_get_queue_validation_error(self, mock_make_request):
        """Test get_queue with invalid response that fails validation."""
        mock_response = Mock()
        # This will pass initial parsing but fail deeper validation
        mock_response.json.return_value = {
            "queue_running": "invalid_not_a_list",  # Should be a list
            "queue_pending": [],
        }
        mock_make_request.return_value = mock_response
        args = ArgsComfyUI(host="localhost:8188")
        client = ComfyUIClient(args)

        with pytest.raises(QueueValidationError):
            client.get_queue()

    @patch.object(ComfyUIClient, "_make_request")
    def test_get_history_success(self, mock_make_request):
        """Test get_history with valid response."""
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_make_request.return_value = mock_response
        args = ArgsComfyUI(host="localhost:8188")
        client = ComfyUIClient(args)
        history = client.get_history("prompt123")
        assert isinstance(history, HistoryResponse)
        mock_make_request.assert_called_once_with("GET", "/history/prompt123")

    @patch.object(ComfyUIClient, "_make_request")
    def test_get_history_validation_error(self, mock_make_request):
        """Test get_history with validation error in from_api_response."""
        mock_response = Mock()
        # Return data that will fail validation in HistoryResponse.from_api_response
        mock_response.json.return_value = {"invalid": {"structure": "here"}}
        mock_make_request.return_value = mock_response
        args = ArgsComfyUI(host="localhost:8188")
        client = ComfyUIClient(args)

        # The actual code catches Exception in the try-except block
        # So we need to trigger an exception during HistoryResponse.from_api_response
        with patch(
            "comfyui_mcp.workflow_utils.HistoryResponse.from_api_response"
        ) as mock_from_api:
            mock_from_api.side_effect = Exception("Validation failed")
            with pytest.raises(QueueValidationError):
                client.get_history("prompt123")

    @patch.object(ComfyUIClient, "_make_request")
    def test_list_workflows(self, mock_make_request):
        """Test list_workflows."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"name": "workflow1.json"},
            {"name": "workflow2.json"},
        ]
        mock_make_request.return_value = mock_response
        args = ArgsComfyUI(host="localhost:8188")
        client = ComfyUIClient(args)
        workflows = client.list_workflows("/workflows")
        assert len(workflows) == 2
        assert workflows[0]["name"] == "workflow1.json"

    @patch.object(ComfyUIClient, "_make_request")
    def test_get_workflow(self, mock_make_request):
        """Test get_workflow."""
        mock_response = Mock()
        mock_response.json.return_value = {"nodes": {}}
        mock_make_request.return_value = mock_response
        args = ArgsComfyUI(host="localhost:8188")
        client = ComfyUIClient(args)
        workflow = client.get_workflow("/workflows/test.json")
        assert "nodes" in workflow
        mock_make_request.assert_called_once()

    @patch.object(ComfyUIClient, "_make_request")
    def test_convert_workflow(self, mock_make_request):
        """Test convert_workflow."""
        mock_response = Mock()
        mock_response.json.return_value = {"converted": "workflow"}
        mock_make_request.return_value = mock_response
        args = ArgsComfyUI(host="localhost:8188")
        client = ComfyUIClient(args)
        workflow_data = {"ui": "workflow"}
        result = client.convert_workflow(workflow_data)
        assert result == {"converted": "workflow"}
        mock_make_request.assert_called_once_with(
            "POST", "/workflow/convert", json=workflow_data
        )

    @patch.object(ComfyUIClient, "_make_request")
    def test_submit_prompt_success(self, mock_make_request):
        """Test submit_prompt with valid response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "prompt_id": "prompt123",
            "number": 1,
            "node_errors": {},
        }
        mock_make_request.return_value = mock_response
        args = ArgsComfyUI(host="localhost:8188")
        client = ComfyUIClient(args)
        workflow = {"nodes": {}}
        prompt_id = client.submit_prompt(workflow)
        assert prompt_id == "prompt123"

    @patch.object(ComfyUIClient, "_make_request")
    def test_submit_prompt_validation_error(self, mock_make_request):
        """Test submit_prompt with error response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "error": "Invalid workflow",
            "node_errors": {"1": "Missing input"},
        }
        mock_make_request.return_value = mock_response
        args = ArgsComfyUI(host="localhost:8188")
        client = ComfyUIClient(args)
        workflow = {"nodes": {}}

        with pytest.raises(PromptValidationError):
            client.submit_prompt(workflow)

    @patch.object(ComfyUIClient, "get_queue")
    @patch.object(ComfyUIClient, "get_history")
    def test_wait_for_completion_success(self, mock_get_history, mock_get_queue):
        """Test wait_for_completion with successful execution."""
        # First check: job is pending
        mock_queue1 = Mock()
        mock_queue1.find_prompt_position.return_value = ("pending", 1, 2)

        # Second check: job is running
        mock_queue2 = Mock()
        mock_queue2.find_prompt_position.return_value = ("running", 0, 1)

        # Third check: job not in queue
        mock_queue3 = Mock()
        mock_queue3.find_prompt_position.return_value = None

        mock_get_queue.side_effect = [mock_queue1, mock_queue2, mock_queue3]

        # Job found in history as completed
        mock_entry = Mock()
        mock_entry.status.status_str = "success"
        mock_entry.status.is_success.return_value = True
        mock_entry.status.is_failed.return_value = False
        mock_entry.get_output_filenames.return_value = {"101": ["output.png"]}

        mock_history = Mock()
        mock_history.is_empty.return_value = False
        mock_history.get_entry.return_value = mock_entry
        mock_get_history.return_value = mock_history
        args = ArgsComfyUI(host="localhost:8188", queue_check_interval=0.1)
        client = ComfyUIClient(args)

        result = asyncio.run(client.wait_for_completion("prompt123"))

        assert result == mock_entry
        assert mock_get_queue.call_count == 3

    @patch.object(ComfyUIClient, "get_queue")
    @patch.object(ComfyUIClient, "get_history")
    def test_wait_for_completion_failed(self, mock_get_history, mock_get_queue):
        """Test wait_for_completion with failed execution."""
        # Job not in queue
        mock_queue = Mock()
        mock_queue.find_prompt_position.return_value = None
        mock_get_queue.return_value = mock_queue

        # Job found in history as failed
        mock_entry = Mock()
        mock_entry.status.status_str = "error"
        mock_entry.status.is_success.return_value = False
        mock_entry.status.is_failed.return_value = True

        mock_history = Mock()
        mock_history.is_empty.return_value = False
        mock_history.get_entry.return_value = mock_entry
        mock_get_history.return_value = mock_history
        args = ArgsComfyUI(host="localhost:8188", queue_check_interval=0.1)
        client = ComfyUIClient(args)

        with pytest.raises(ExecutionFailedError):
            asyncio.run(client.wait_for_completion("prompt123"))

    @patch.object(ComfyUIClient, "get_queue")
    @patch.object(ComfyUIClient, "get_history")
    @patch("comfyui_mcp.workflow_utils.sleep", new_callable=AsyncMock)
    def test_wait_for_completion_lost_job(
        self, mock_sleep, mock_get_history, mock_get_queue
    ):
        """Test wait_for_completion with lost job."""
        # Job not in queue
        mock_queue = Mock()
        mock_queue.find_prompt_position.return_value = None
        mock_get_queue.return_value = mock_queue

        # Job not in history either
        mock_history = Mock()
        mock_history.is_empty.return_value = True
        mock_get_history.return_value = mock_history
        args = ArgsComfyUI(
            host="localhost:8188", lost_job_check_limit=2, queue_check_interval=0.1
        )
        client = ComfyUIClient(args)

        with pytest.raises(JobLostError):
            asyncio.run(client.wait_for_completion("prompt123"))

    @patch.object(ComfyUIClient, "get_queue")
    @patch("comfyui_mcp.workflow_utils.time.time")
    def test_wait_for_completion_timeout(self, mock_time, mock_get_queue):
        """Test wait_for_completion with timeout."""
        # Simulate time passing
        mock_time.side_effect = [0, 100, 200]

        # Job still pending
        mock_queue = Mock()
        mock_queue.find_prompt_position.return_value = ("pending", 1, 2)
        mock_get_queue.return_value = mock_queue
        args = ArgsComfyUI(
            host="localhost:8188", max_wait_time=50, queue_check_interval=0.1
        )
        client = ComfyUIClient(args)

        with pytest.raises(TimeoutError):
            asyncio.run(client.wait_for_completion("prompt123"))

    @patch.object(ComfyUIClient, "get_queue")
    @patch.object(ComfyUIClient, "get_history")
    @patch("comfyui_mcp.workflow_utils.sleep", new_callable=AsyncMock)
    def test_wait_for_completion_unknown_status(
        self, mock_sleep, mock_get_history, mock_get_queue
    ):
        """Test wait_for_completion with unknown status that eventually succeeds."""
        # First check: job not in queue
        mock_queue1 = Mock()
        mock_queue1.find_prompt_position.return_value = None

        # Second check: still not in queue
        mock_queue2 = Mock()
        mock_queue2.find_prompt_position.return_value = None

        mock_get_queue.side_effect = [mock_queue1, mock_queue2]

        # First history check: unknown status
        mock_entry1 = Mock()
        mock_entry1.status.status_str = "unknown"
        mock_entry1.status.is_success.return_value = False
        mock_entry1.status.is_failed.return_value = False

        mock_history1 = Mock()
        mock_history1.is_empty.return_value = False
        mock_history1.get_entry.return_value = mock_entry1

        # Second history check: success
        mock_entry2 = Mock()
        mock_entry2.status.status_str = "success"
        mock_entry2.status.is_success.return_value = True
        mock_entry2.get_output_filenames.return_value = {}

        mock_history2 = Mock()
        mock_history2.is_empty.return_value = False
        mock_history2.get_entry.return_value = mock_entry2

        mock_get_history.side_effect = [mock_history1, mock_history2]
        args = ArgsComfyUI(host="localhost:8188", queue_check_interval=0.1)
        client = ComfyUIClient(args)

        result = asyncio.run(client.wait_for_completion("prompt123"))
        assert result == mock_entry2

    @patch.object(ComfyUIClient, "submit_prompt")
    @patch.object(ComfyUIClient, "wait_for_completion", new_callable=AsyncMock)
    def test_execute_workflow_success(self, mock_wait, mock_submit):
        """Test execute_workflow success."""
        mock_submit.return_value = "prompt123"
        mock_entry = Mock()
        mock_wait.return_value = mock_entry
        args = ArgsComfyUI(host="localhost:8188")
        client = ComfyUIClient(args)
        workflow = {"nodes": {}}

        result = asyncio.run(client.execute_workflow(workflow))

        assert result == mock_entry
        mock_submit.assert_called_once_with(workflow)
        mock_wait.assert_called_once_with("prompt123")

    @patch.object(ComfyUIClient, "submit_prompt")
    @patch.object(ComfyUIClient, "wait_for_completion", new_callable=AsyncMock)
    def test_execute_workflow_keyboard_interrupt(self, mock_wait, mock_submit):
        """Test execute_workflow with keyboard interrupt."""
        mock_submit.return_value = "prompt123"
        mock_wait.side_effect = KeyboardInterrupt()
        args = ArgsComfyUI(host="localhost:8188")
        client = ComfyUIClient(args)
        workflow = {"nodes": {}}

        with pytest.raises(KeyboardInterrupt):
            asyncio.run(client.execute_workflow(workflow))

    @patch.object(ComfyUIClient, "submit_prompt")
    def test_execute_workflow_keyboard_interrupt_before_submit(self, mock_submit):
        """Test execute_workflow with keyboard interrupt before submission."""
        mock_submit.side_effect = KeyboardInterrupt()
        args = ArgsComfyUI(host="localhost:8188")
        client = ComfyUIClient(args)
        workflow = {"nodes": {}}

        with pytest.raises(KeyboardInterrupt):
            asyncio.run(client.execute_workflow(workflow))

    @patch.object(ComfyUIClient, "get_queue")
    @patch.object(ComfyUIClient, "get_history")
    @patch("comfyui_mcp.workflow_utils.sleep", new_callable=AsyncMock)
    def test_wait_for_completion_job_lost_then_found(
        self, mock_sleep, mock_get_history, mock_get_queue
    ):
        """Test wait_for_completion when job is temporarily lost then found."""
        # Job not in queue
        mock_queue = Mock()
        mock_queue.find_prompt_position.return_value = None
        mock_get_queue.return_value = mock_queue

        # First check: not in history
        mock_history1 = Mock()
        mock_history1.is_empty.return_value = True

        # Second check: found in history
        mock_entry = Mock()
        mock_entry.status.status_str = "success"
        mock_entry.status.is_success.return_value = True
        mock_entry.get_output_filenames.return_value = {}

        mock_history2 = Mock()
        mock_history2.is_empty.return_value = False
        mock_history2.get_entry.return_value = mock_entry

        mock_get_history.side_effect = [mock_history1, mock_history2]
        args = ArgsComfyUI(
            host="localhost:8188", lost_job_check_limit=3, queue_check_interval=0.1
        )
        client = ComfyUIClient(args)

        result = asyncio.run(client.wait_for_completion("prompt123"))
        assert result == mock_entry

    @patch.object(ComfyUIClient, "get_queue")
    @patch.object(ComfyUIClient, "get_history")
    @patch("comfyui_mcp.workflow_utils.sleep", new_callable=AsyncMock)
    def test_wait_for_completion_entry_not_in_history(
        self, mock_sleep, mock_get_history, mock_get_queue
    ):
        """Test wait_for_completion when history exists but entry is None."""
        # Job not in queue
        mock_queue = Mock()
        mock_queue.find_prompt_position.return_value = None
        mock_get_queue.return_value = mock_queue

        # History not empty but get_entry returns None
        mock_history = Mock()
        mock_history.is_empty.return_value = False
        mock_history.get_entry.return_value = None
        mock_get_history.return_value = mock_history
        args = ArgsComfyUI(
            host="localhost:8188", lost_job_check_limit=2, queue_check_interval=0.1
        )
        client = ComfyUIClient(args)

        with pytest.raises(JobLostError):
            asyncio.run(client.wait_for_completion("prompt123"))

    @patch.object(ComfyUIClient, "get_queue")
    @patch.object(ComfyUIClient, "get_history")
    @patch("comfyui_mcp.workflow_utils.sleep", new_callable=AsyncMock)
    @patch("comfyui_mcp.workflow_utils.time.time")
    def test_wait_for_completion_no_timeout_with_none(
        self, mock_time, mock_sleep, mock_get_history, mock_get_queue
    ):
        """Test wait_for_completion continues when max_wait_time is None."""
        # Job is pending on first check
        mock_queue1 = Mock()
        mock_queue1.find_prompt_position.return_value = ("pending", 1, 2)

        # Job not in queue on subsequent checks
        mock_queue_none = Mock()
        mock_queue_none.find_prompt_position.return_value = None

        # Provide enough queue responses
        mock_get_queue.side_effect = [mock_queue1] + [mock_queue_none] * 20

        # Mock time being called but max_wait_time is None so no timeout
        mock_time.side_effect = list(range(0, 2000, 100))

        # History is empty for multiple checks
        mock_history_empty = Mock()
        mock_history_empty.is_empty.return_value = True
        mock_history_empty.get_entry.return_value = None

        # Provide enough empty history responses (will hit lost_job_check_limit)
        mock_get_history.side_effect = [mock_history_empty] * 20

        args = ArgsComfyUI(
            host="localhost:8188",
            max_wait_time=None,
            lost_job_check_limit=11,
            queue_check_interval=0.1,
        )
        client = ComfyUIClient(args)

        # Will eventually raise JobLostError since job keeps not being found
        # But the point is it won't raise TimeoutError even with elapsed time
        with pytest.raises(JobLostError):
            asyncio.run(client.wait_for_completion("prompt123"))

    @patch.object(ComfyUIClient, "get_queue")
    @patch.object(ComfyUIClient, "get_history")
    @patch("comfyui_mcp.workflow_utils.sleep", new_callable=AsyncMock)
    def test_wait_for_completion_lost_job_counter_reset(
        self, mock_sleep, mock_get_history, mock_get_queue
    ):
        """Test that lost_job_counter resets when job is found in queue after being lost."""
        # First check: job not in queue
        mock_queue1 = Mock()
        mock_queue1.find_prompt_position.return_value = None

        # Second check: job found in queue (should reset counter)
        mock_queue2 = Mock()
        mock_queue2.find_prompt_position.return_value = ("pending", 1, 2)

        # Third check: job not in queue again
        mock_queue3 = Mock()
        mock_queue3.find_prompt_position.return_value = None

        mock_get_queue.side_effect = [mock_queue1, mock_queue2, mock_queue3]

        # First history check: empty (increments lost_job_counter)
        mock_history1 = Mock()
        mock_history1.is_empty.return_value = True

        # Second history check: job found as success
        mock_entry = Mock()
        mock_entry.status.status_str = "success"
        mock_entry.status.is_success.return_value = True
        mock_entry.get_output_filenames.return_value = {}

        mock_history2 = Mock()
        mock_history2.is_empty.return_value = False
        mock_history2.get_entry.return_value = mock_entry

        mock_get_history.side_effect = [mock_history1, mock_history2]

        args = ArgsComfyUI(
            host="localhost:8188", lost_job_check_limit=5, queue_check_interval=0.1
        )
        client = ComfyUIClient(args)

        result = asyncio.run(client.wait_for_completion("prompt123"))
        assert result == mock_entry
        # Verify lost_job_counter was reset when job was found in queue
        assert mock_get_queue.call_count == 3

    @patch.object(ComfyUIClient, "get_queue")
    @patch.object(ComfyUIClient, "get_history")
    @patch("comfyui_mcp.workflow_utils.sleep", new_callable=AsyncMock)
    def test_wait_for_completion_found_in_history_resets_counter(
        self, mock_sleep, mock_get_history, mock_get_queue
    ):
        """Test that lost_job_counter resets when job is found in history."""
        # Job not in queue
        mock_queue = Mock()
        mock_queue.find_prompt_position.return_value = None
        mock_get_queue.return_value = mock_queue

        # First check: not in history (increments counter)
        mock_history1 = Mock()
        mock_history1.is_empty.return_value = True

        # Second check: found in history with unknown status (resets counter)
        mock_entry_unknown = Mock()
        mock_entry_unknown.status.status_str = "unknown"
        mock_entry_unknown.status.is_success.return_value = False
        mock_entry_unknown.status.is_failed.return_value = False

        mock_history2 = Mock()
        mock_history2.is_empty.return_value = False
        mock_history2.get_entry.return_value = mock_entry_unknown

        # Third check: success
        mock_entry_success = Mock()
        mock_entry_success.status.status_str = "success"
        mock_entry_success.status.is_success.return_value = True
        mock_entry_success.get_output_filenames.return_value = {}

        mock_history3 = Mock()
        mock_history3.is_empty.return_value = False
        mock_history3.get_entry.return_value = mock_entry_success

        mock_get_history.side_effect = [mock_history1, mock_history2, mock_history3]

        args = ArgsComfyUI(
            host="localhost:8188", lost_job_check_limit=2, queue_check_interval=0.1
        )
        client = ComfyUIClient(args)

        result = asyncio.run(client.wait_for_completion("prompt123"))
        assert result == mock_entry_success
