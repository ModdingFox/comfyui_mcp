from collections.abc import Callable, Coroutine
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator

from comfyui_mcp.argument_parser import ArgsComfyUI, ArgsGenerate

InputTypes = int | str
WorkflowType = dict[str, dict[str, Any]]
WorkflowParamType = dict[str, Any]
GenerateFunctionType = Callable[[ArgsComfyUI, ArgsGenerate, WorkflowType, WorkflowParamType], Coroutine[Any, Any, str]]
WrappedFunctionType = Callable[..., Any]

class MediaType(str, Enum):
    AUDIO = "audio"
    IMAGES = "images"
    UNKNOWN = "unknown"

class ComfyResult(BaseModel):
    media_type: MediaType = MediaType.UNKNOWN
    filename: HttpUrl

    @field_validator("media_type", mode="before")
    @classmethod
    def validate_media_type(cls, input_variable):
        if isinstance(input_variable, MediaType):
            return input_variable
        if isinstance(input_variable, str):
            try:
                return MediaType(input_variable.lower())
            except ValueError:
                return MediaType.UNKNOWN
        return MediaType.UNKNOWN

class QueueItem(BaseModel):
    """Represents a single item in the queue"""
    model_config = {"extra": "ignore"}

    queue_number: int = Field(..., description="Queue position number")
    prompt_id: str = Field(..., description="Unique prompt identifier")

    @classmethod
    def from_tuple(cls, item: list[Any]) -> "QueueItem":
        """Parse queue item from API tuple format"""
        if not isinstance(item, list) or len(item) < 2:
            raise ValueError(f"Invalid queue item format: expected at least 2 elements, got {item}")

        return cls(
            queue_number=item[0],
            prompt_id=item[1]
        )

class QueueResponse(BaseModel):
    """Represents the queue API response"""
    queue_running: list[QueueItem] = Field(default_factory=list, description="Currently running jobs")
    queue_pending: list[QueueItem] = Field(default_factory=list, description="Pending jobs")

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "QueueResponse":
        """Parse raw API response into validated QueueResponse"""
        running_raw = data.get('queue_running', [])
        pending_raw = data.get('queue_pending', [])

        return cls(
            queue_running=[QueueItem.from_tuple(item) for item in running_raw],
            queue_pending=[QueueItem.from_tuple(item) for item in pending_raw]
        )

    def find_prompt_position(self, prompt_id: str) -> tuple[str, int, int] | None:
        """
        Find prompt in queue and return (status, position, total)
        status: 'pending' or 'running'
        position: 1-based position in queue
        total: total items in that queue
        """
        for idx, item in enumerate(self.queue_pending, start=1):
            if item.prompt_id == prompt_id:
                return ('pending', idx, len(self.queue_pending))

        for idx, item in enumerate(self.queue_running, start=1):
            if item.prompt_id == prompt_id:
                return ('running', idx, len(self.queue_running))

        return None

class OutputFile(BaseModel):
    """Represents a single output file"""
    filename: str
    subfolder: str
    type: str

class NodeOutput(BaseModel):
    """Represents outputs from a single node"""
    model_config = {"extra": "allow"}

    def get_all_outputs(self) -> dict[str, list[OutputFile]]:
        """Get all outputs grouped by media type"""
        result = {}
        data = self.model_dump(exclude_none=True)
        for field_name, field_value in data.items():
            if isinstance(field_value, list) and len(field_value) > 0:
                if isinstance(field_value[0], dict):
                    result[field_name] = [OutputFile.model_validate(item) for item in field_value]
                else:
                    result[field_name] = field_value
        return result

class JobStatus(BaseModel):
    """Represents the status of a job"""
    status_str: str
    completed: bool

    def is_success(self) -> bool:
        return self.status_str == 'success' and self.completed

    def is_failed(self) -> bool:
        return self.status_str in ['error', 'failed']

class HistoryEntry(BaseModel):
    """Represents a complete history entry for a single job"""
    model_config = {"extra": "ignore"}

    outputs: dict[str, NodeOutput] = Field(default_factory=dict)
    status: JobStatus

    def get_output_filenames(self) -> dict[str, list[str]]:
        """Get output filenames grouped by node_id"""
        results = {}
        for node_id, node_output in self.outputs.items():
            all_outputs = node_output.get_all_outputs()
            for media_type, output_list in all_outputs.items():
                if node_id not in results:
                    results[node_id] = []
                results[node_id].extend([output.filename for output in output_list])
        return results

class HistoryResponse(BaseModel):
    """Represents the complete history API response"""
    entries: dict[str, HistoryEntry]

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "HistoryResponse":
        """Parse raw API response"""
        entries = {
            prompt_id: HistoryEntry.model_validate(entry_data)
            for prompt_id, entry_data in data.items()
        }
        return cls(entries=entries)

    def get_entry(self, prompt_id: str) -> HistoryEntry | None:
        return self.entries.get(prompt_id)

    def is_empty(self) -> bool:
        return len(self.entries) == 0

class PromptSuccessResponse(BaseModel):
    model_config = {"extra": "ignore"}

    prompt_id: str

    @field_validator('prompt_id')
    @classmethod
    def validate_prompt_id(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("prompt_id cannot be empty")
        return value
