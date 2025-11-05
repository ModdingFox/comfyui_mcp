from collections.abc import Callable, Coroutine
from enum import Enum
from typing import Any

from pydantic import BaseModel, HttpUrl, field_validator

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
