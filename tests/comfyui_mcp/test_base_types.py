import pytest
from pydantic import HttpUrl, ValidationError

from comfyui_mcp.base_types import (
    ComfyResult,
    HistoryEntry,
    HistoryResponse,
    JobStatus,
    MediaType,
    NodeOutput,
    OutputFile,
    PromptSuccessResponse,
    QueueItem,
    QueueResponse,
)

VALID_URL = "https://example.com/file.png"


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        (MediaType.AUDIO, MediaType.AUDIO),
        (MediaType.IMAGES, MediaType.IMAGES),
        (MediaType.UNKNOWN, MediaType.UNKNOWN),
        ("audio", MediaType.AUDIO),
        ("AUDIO", MediaType.AUDIO),
        ("images", MediaType.IMAGES),
        ("unknown", MediaType.UNKNOWN),
        ("nonsense", MediaType.UNKNOWN),
        (123, MediaType.UNKNOWN),
        (None, MediaType.UNKNOWN),
    ],
)
def test_media_type_field_validator(input_value, expected):
    """Ensure validate_media_type handles all supported input types."""
    result = ComfyResult(media_type=input_value, filename=VALID_URL)
    assert result.media_type == expected


def test_media_type_defaults_to_unknown():
    """If media_type not provided, it should default to UNKNOWN."""
    result = ComfyResult(filename=VALID_URL)
    assert result.media_type == MediaType.UNKNOWN


def test_invalid_url_raises_validation_error():
    """Invalid URL must raise a Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        ComfyResult(media_type="audio", filename="not-a-valid-url")


def test_valid_url_accepts():
    """Valid URLs should pass validation."""
    result = ComfyResult(media_type="images", filename="https://valid-url.com/output.jpg")
    assert result.filename == HttpUrl("https://valid-url.com/output.jpg")


def test_media_type_enum_values():
    """Ensure the MediaType enum members have correct string values."""
    assert MediaType.AUDIO.value == "audio"
    assert MediaType.IMAGES.value == "images"
    assert MediaType.UNKNOWN.value == "unknown"


class TestQueueItem:
    def test_from_tuple_valid(self):
        """Test QueueItem creation from valid tuple."""
        item = QueueItem.from_tuple([42, "prompt-123"])
        assert item.queue_number == 42
        assert item.prompt_id == "prompt-123"

    def test_from_tuple_invalid(self):
        """Test QueueItem raises error on invalid input."""
        with pytest.raises(ValueError, match="Invalid queue item format"):
            QueueItem.from_tuple([])

        with pytest.raises(ValueError, match="Invalid queue item format"):
            QueueItem.from_tuple([42])


class TestQueueResponse:
    def test_from_api_response(self):
        """Test QueueResponse parsing from API data."""
        api_data = {
            'queue_running': [[1, "prompt-1"]],
            'queue_pending': [[2, "prompt-2"], [3, "prompt-3"]]
        }
        response = QueueResponse.from_api_response(api_data)

        assert len(response.queue_running) == 1
        assert len(response.queue_pending) == 2
        assert response.queue_running[0].prompt_id == "prompt-1"
        assert response.queue_pending[1].prompt_id == "prompt-3"

    def test_find_prompt_position_pending(self):
        """Test finding prompt in pending queue."""
        response = QueueResponse.from_api_response({
            'queue_running': [[1, "prompt-1"]],
            'queue_pending': [[2, "prompt-2"], [3, "prompt-3"]]
        })

        result = response.find_prompt_position("prompt-3")
        assert result == ('pending', 2, 2)

    def test_find_prompt_position_pending_first(self):
        """Test finding first prompt in pending queue."""
        response = QueueResponse.from_api_response({
            'queue_running': [],
            'queue_pending': [[2, "prompt-2"], [3, "prompt-3"]]
        })

        result = response.find_prompt_position("prompt-2")
        assert result == ('pending', 1, 2)

    def test_find_prompt_position_running(self):
        """Test finding prompt in running queue."""
        response = QueueResponse.from_api_response({
            'queue_running': [[1, "prompt-1"]],
            'queue_pending': [[2, "prompt-2"]]
        })

        result = response.find_prompt_position("prompt-1")
        assert result == ('running', 1, 1)

    def test_find_prompt_position_not_found(self):
        """Test prompt not found returns None."""
        response = QueueResponse.from_api_response({
            'queue_running': [],
            'queue_pending': [[2, "prompt-2"]]
        })

        result = response.find_prompt_position("prompt-999")
        assert result is None

    def test_find_prompt_position_with_multiple_pending(self):
        """Test finding prompt when there are multiple items in pending queue."""
        response = QueueResponse.from_api_response({
            'queue_running': [],
            'queue_pending': [
                [1, "prompt-1"],
                [2, "prompt-2"],
                [3, "prompt-3"],
                [4, "prompt-4"]
            ]
        })

        # Test finding in middle of queue
        result = response.find_prompt_position("prompt-3")
        assert result == ('pending', 3, 4)

        # Test finding at end of queue
        result = response.find_prompt_position("prompt-4")
        assert result == ('pending', 4, 4)

    def test_find_prompt_position_with_multiple_running(self):
        """Test finding prompt when there are multiple items in running queue."""
        response = QueueResponse.from_api_response({
            'queue_running': [
                [1, "prompt-1"],
                [2, "prompt-2"]
            ],
            'queue_pending': [[3, "prompt-3"]]
        })

        # Test finding second item in running queue
        result = response.find_prompt_position("prompt-2")
        assert result == ('running', 2, 2)


class TestOutputFile:
    def test_output_file_creation(self):
        """Test OutputFile model creation."""
        file = OutputFile(filename="test.png", subfolder="", type="output")
        assert file.filename == "test.png"
        assert file.subfolder == ""
        assert file.type == "output"


class TestNodeOutput:
    def test_get_all_outputs_with_images(self):
        """Test getting outputs with images."""
        output = NodeOutput(images=[
            OutputFile(filename="img1.png", subfolder="", type="output"),
            OutputFile(filename="img2.png", subfolder="", type="output")
        ])

        results = output.get_all_outputs()
        assert "images" in results
        assert len(results["images"]) == 2
        assert results["images"][0].filename == "img1.png"

    def test_get_all_outputs_empty(self):
        """Test getting outputs when none exist."""
        output = NodeOutput()
        results = output.get_all_outputs()
        assert results == {}

    def test_get_all_outputs_with_dict_values(self):
        """Test getting outputs when values are already dicts (edge case)."""
        output = NodeOutput.model_validate({
            "custom_output": [
                {"filename": "custom.png", "subfolder": "", "type": "output"}
            ]
        })

        results = output.get_all_outputs()
        assert "custom_output" in results
        assert len(results["custom_output"]) == 1
        assert isinstance(results["custom_output"][0], OutputFile)
        assert results["custom_output"][0].filename == "custom.png"

    def test_get_all_outputs_with_non_dict_list(self):
        """Test getting outputs when values are non-dict lists (primitive types)."""
        # This tests the else branch at line 105
        output = NodeOutput.model_validate({
            "simple_list": ["value1", "value2", "value3"]
        })

        results = output.get_all_outputs()
        assert "simple_list" in results
        assert results["simple_list"] == ["value1", "value2", "value3"]
        assert not isinstance(results["simple_list"][0], OutputFile)

    def test_get_all_outputs_mixed_types(self):
        """Test getting outputs with both OutputFile objects and primitive lists."""
        output = NodeOutput.model_validate({
            "images": [
                {"filename": "img1.png", "subfolder": "", "type": "output"}
            ],
            "metadata": ["tag1", "tag2"],  # Non-dict list
            "empty_list": []
        })

        results = output.get_all_outputs()
        assert "images" in results
        assert isinstance(results["images"][0], OutputFile)
        assert "metadata" in results
        assert results["metadata"] == ["tag1", "tag2"]
        # empty_list should not be included (length check)
        assert "empty_list" not in results


class TestJobStatus:
    def test_is_success(self):
        """Test success status detection."""
        status = JobStatus(status_str="success", completed=True)
        assert status.is_success() is True

        status = JobStatus(status_str="success", completed=False)
        assert status.is_success() is False

    def test_is_failed(self):
        """Test failed status detection."""
        status = JobStatus(status_str="error", completed=True)
        assert status.is_failed() is True

        status = JobStatus(status_str="failed", completed=True)
        assert status.is_failed() is True

        status = JobStatus(status_str="success", completed=True)
        assert status.is_failed() is False


class TestHistoryEntry:
    def test_get_output_filenames(self):
        """Test extracting output filenames."""
        node_output = NodeOutput(images=[
            OutputFile(filename="test1.png", subfolder="", type="output"),
            OutputFile(filename="test2.png", subfolder="", type="output")
        ])

        entry = HistoryEntry(
            outputs={"101": node_output},
            status=JobStatus(status_str="success", completed=True)
        )

        filenames = entry.get_output_filenames()
        assert "101" in filenames
        assert len(filenames["101"]) == 2
        assert "test1.png" in filenames["101"]

    def test_get_output_filenames_multiple_media_types(self):
        """Test extracting filenames from multiple media types."""
        node_output = NodeOutput.model_validate({
            "images": [
                {"filename": "img.png", "subfolder": "", "type": "output"}
            ],
            "audio": [
                {"filename": "audio.mp3", "subfolder": "", "type": "output"}
            ]
        })

        entry = HistoryEntry(
            outputs={"101": node_output},
            status=JobStatus(status_str="success", completed=True)
        )

        filenames = entry.get_output_filenames()
        assert "101" in filenames
        assert len(filenames["101"]) == 2
        assert "img.png" in filenames["101"]
        assert "audio.mp3" in filenames["101"]

    def test_get_output_filenames_multiple_nodes(self):
        """Test extracting filenames from multiple nodes."""
        node_output_1 = NodeOutput(images=[
            OutputFile(filename="node1.png", subfolder="", type="output")
        ])
        node_output_2 = NodeOutput(images=[
            OutputFile(filename="node2.png", subfolder="", type="output"),
            OutputFile(filename="node2_alt.png", subfolder="", type="output")
        ])

        entry = HistoryEntry(
            outputs={"101": node_output_1, "102": node_output_2},
            status=JobStatus(status_str="success", completed=True)
        )

        filenames = entry.get_output_filenames()
        assert "101" in filenames
        assert "102" in filenames
        assert len(filenames["101"]) == 1
        assert len(filenames["102"]) == 2
        assert "node1.png" in filenames["101"]
        assert "node2.png" in filenames["102"]
        assert "node2_alt.png" in filenames["102"]

    def test_get_output_filenames_empty_outputs(self):
        """Test getting filenames when there are no outputs."""
        entry = HistoryEntry(
            outputs={},
            status=JobStatus(status_str="success", completed=True)
        )

        filenames = entry.get_output_filenames()
        assert filenames == {}


class TestHistoryResponse:
    def test_from_api_response(self):
        """Test parsing history from API response."""
        api_data = {
            "prompt-123": {
                "outputs": {},
                "status": {"status_str": "success", "completed": True}
            }
        }

        response = HistoryResponse.from_api_response(api_data)
        assert not response.is_empty()
        assert response.get_entry("prompt-123") is not None

    def test_is_empty(self):
        """Test empty history detection."""
        response = HistoryResponse(entries={})
        assert response.is_empty() is True

        response = HistoryResponse.from_api_response({
            "prompt-1": {
                "outputs": {},
                "status": {"status_str": "success", "completed": True}
            }
        })
        assert response.is_empty() is False

    def test_get_entry(self):
        """Test getting specific entry."""
        response = HistoryResponse.from_api_response({
            "prompt-1": {
                "outputs": {},
                "status": {"status_str": "success", "completed": True}
            }
        })

        entry = response.get_entry("prompt-1")
        assert entry is not None
        assert entry.status.status_str == "success"

        entry = response.get_entry("nonexistent")
        assert entry is None


class TestPromptSuccessResponse:
    def test_valid_prompt_id(self):
        """Test valid prompt_id."""
        response = PromptSuccessResponse(prompt_id="valid-prompt-123")
        assert response.prompt_id == "valid-prompt-123"

    def test_empty_prompt_id_raises_error(self):
        """Test empty prompt_id raises validation error."""
        with pytest.raises(ValidationError, match="prompt_id cannot be empty"):
            PromptSuccessResponse(prompt_id="")

        with pytest.raises(ValidationError, match="prompt_id cannot be empty"):
            PromptSuccessResponse(prompt_id="   ")
