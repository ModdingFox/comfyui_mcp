from collections.abc import Callable, Coroutine
from typing import Any

from comfyui_mcp.argument_parser import ArgsComfyUI, ArgsGenerate

InputTypes = int | str
WorkflowType = dict[str, dict[str, Any]]
WorkflowParamType = dict[str, Any]

GenerateFunctionType = Callable[[ArgsComfyUI, ArgsGenerate, WorkflowType, WorkflowParamType], Coroutine[Any, Any, str]]
WrappedFunctionType = Callable[..., Any]
