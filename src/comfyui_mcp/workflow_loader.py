from json import load
from logging import getLogger
from os import listdir
from os.path import join
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from fastmcp import FastMCP
from fastmcp.tools.tool import FunctionTool, Tool
from requests import get, post

from comfyui_mcp.argument_parser import ArgsComfyUI, ArgsGenerate
from comfyui_mcp.base_types import (
    GenerateFunctionType,
    WorkflowType,
)
from comfyui_mcp.function_utils import wrap_fn

if TYPE_CHECKING:
    from collections.abc import Callable

logger = getLogger(__name__)


def load_workflows_from_path(
    argscomfyui: ArgsComfyUI, argsgenerate: ArgsGenerate, generation_function: GenerateFunctionType, fast_mcp: FastMCP
) -> None:
    file_names: list[str] = listdir(argscomfyui.workflow_directory)
    for file_name in file_names:
        logger.info("Loading %s from %s", file_name, argscomfyui.workflow_directory)
        function_name: str = file_name.replace(".", "_")
        file_path: str = join(argscomfyui.workflow_directory, file_name)
        with open(file_path) as workflow_file:
            workflow: WorkflowType = load(workflow_file)
            call: Callable[..., Any] = wrap_fn(argscomfyui, argsgenerate, function_name, workflow, generation_function)
            function_tool: FunctionTool = Tool.from_function(
                fn=call, name=function_name, description=f"Comfy image generation workflow {file_name}"
            )
            fast_mcp.add_tool(function_tool)


def load_workflows_from_comfyui(
    argscomfyui: ArgsComfyUI, argsgenerate: ArgsGenerate, generation_function: GenerateFunctionType, fast_mcp: FastMCP
) -> None:
    workflow_directory_urlencoded: str = quote(argscomfyui.workflow_directory, safe="")
    workflow_list_response = get(
        f"http://{argscomfyui.host}/api/v2/userdata?path={workflow_directory_urlencoded}",
        timeout=argscomfyui.request_timeout,
    )
    workflow_list_response.raise_for_status()
    workflow_list = workflow_list_response.json()
    for workflow in workflow_list:
        workflow_name = workflow["name"]
        logger.info(
            "Loading workflow %s from %s on %s", workflow_name, argscomfyui.workflow_directory, argscomfyui.host
        )
        function_name: str = workflow_name.replace(".", "_")
        if workflow["type"] == "file":
            workflow_path = quote(workflow["path"], safe="")
            workflow_data_response = get(
                f"http://{argscomfyui.host}/api/userdata/{workflow_path}", timeout=argscomfyui.request_timeout
            )
            workflow_data_response.raise_for_status()
            workflow_data = workflow_data_response.json()
            workflow_convert_response = post(
                f"http://{argscomfyui.host}/workflow/convert",
                json=workflow_data,
                timeout=argscomfyui.request_timeout,
            )
            workflow_convert_response.raise_for_status()
            workflow_api: WorkflowType = workflow_convert_response.json()
            call: Callable[..., Any] = wrap_fn(
                argscomfyui, argsgenerate, function_name, workflow_api, generation_function
            )
            function_tool: FunctionTool = Tool.from_function(
                fn=call, name=function_name, description=f"Comfy image generation workflow {workflow_path}"
            )
            fast_mcp.add_tool(function_tool)
