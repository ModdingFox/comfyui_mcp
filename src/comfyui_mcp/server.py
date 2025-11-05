from importlib.metadata import version
from json import dumps
from logging import INFO, basicConfig
from random import SystemRandom
from sys import maxsize
from time import time

from fastmcp import FastMCP

from comfyui_mcp.argument_parser import ArgsComfyUI, ArgsGenerate, get_application_args
from comfyui_mcp.base_types import (
    ComfyResult,
    MediaType,
    WorkflowParamType,
    WorkflowType,
)
from comfyui_mcp.workflow_loader import load_workflows_from_comfyui, load_workflows_from_path
from comfyui_mcp.workflow_utils import call_workflow, prepare_workflow

basicConfig(level=INFO, format="%(asctime)s - %(levelname)s - %(message)s")


system_random = SystemRandom()


def format_comfy_result(argsgenerate: ArgsGenerate, comfy_result: ComfyResult, index: int) -> str:
    templates: dict[MediaType, str] = {
        MediaType.AUDIO: argsgenerate.audio_url_template,
        MediaType.IMAGES: argsgenerate.image_url_template,
        MediaType.UNKNOWN: argsgenerate.unknown_url_template,
    }
    return templates[comfy_result.media_type].format(index=index, url=str(comfy_result.filename))


async def generate(
    argscomfyui: ArgsComfyUI, argsgenerate: ArgsGenerate, workflow: WorkflowType, workflow_params: WorkflowParamType
) -> str:
    workflow_results: list[ComfyResult] = []
    seeds: list[int] = []

    batch_by_time = workflow_params["batch_by_time"]
    submit_batch = workflow_params["submit_batch"]
    if batch_by_time:
        end_time = time() + (submit_batch * 60)
        i = 0
        while time() < end_time:
            if workflow_params.get("seed"):
                if i > 0:
                    workflow_params["seed"] = system_random.randint(0, maxsize)
                seeds.append(workflow_params["seed"])
            workflow = prepare_workflow(workflow, **workflow_params)
            workflow_results.extend(await call_workflow(argscomfyui, workflow))
            i += 1
    else:
        for i in range(submit_batch):
            if workflow_params.get("seed"):
                if i > 0:
                    workflow_params["seed"] = system_random.randint(0, maxsize)
                seeds.append(workflow_params["seed"])
            workflow = prepare_workflow(workflow, **workflow_params)
            workflow_results.extend(await call_workflow(argscomfyui, workflow))

    result: str = argsgenerate.nothing_generated_message
    if len(workflow_results) > 0:
        image_results: list[str] = []
        for index, workflow_result in enumerate(workflow_results):
            formatted_result = format_comfy_result(argsgenerate=argsgenerate, comfy_result=workflow_result, index=index)
            image_results.append(formatted_result)
        result = argsgenerate.result_generated_message_template.format(image_list="".join(image_results))
        if argsgenerate.reply_include_workflow:
            if len(seeds) > 1:
                del workflow_params["seed"]
                workflow_params["seeds"] = seeds
            workflow_params_string = dumps(
                workflow_params,
                indent=argsgenerate.reply_workflow_format_indent,
                sort_keys=argsgenerate.reply_workflow_format_sort_keys,
            )
            result += argsgenerate.reply_workflow_template.format(workflow_params=workflow_params_string)
    return result


if __name__ == "__main__":
    _args = get_application_args()
    fast_mcp: FastMCP = FastMCP(name="ComfyUI MCP Server", version=str(version))

    if _args.comfyui.use_remote_workflow:
        load_workflows_from_comfyui(_args.comfyui, _args.generate, generate, fast_mcp)
    else:
        load_workflows_from_path(_args.comfyui, _args.generate, generate, fast_mcp)

    fast_mcp.run()
