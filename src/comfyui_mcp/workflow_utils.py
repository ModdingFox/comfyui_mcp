from copy import deepcopy

from comfyui_utils.comfy import Callbacks, ComfyAPI  # type: ignore[import-untyped]

from comfyui_mcp.argument_parser import ArgsComfyUI
from comfyui_mcp.base_types import (
    ComfyResult,
    InputTypes,
    WorkflowParamType,
    WorkflowType,
)


async def call_workflow(argscomfyui: ArgsComfyUI, workflow: WorkflowType) -> list[ComfyResult]:
    results = []

    class ComfyCallbacks(Callbacks):
        async def queue_position(self, position):
            pass

        async def in_progress(self, node_id, progress, total):
            pass

        # cached required for funct contract
        async def completed(self, output, cached):  # noqa: ARG002
            if output:
                for media_type in output:
                    for media_result in output[media_type]:
                        if "filename" in media_result:
                            # List comprehension doesnt assign to the global
                            filename = media_result["filename"]
                            file_link = f"http://{argscomfyui.host}/api/view?filename={filename}"
                            results.append(ComfyResult(media_type=media_type, filename=file_link))

    comfyapi = ComfyAPI(argscomfyui.host)
    await comfyapi.submit(workflow, ComfyCallbacks())
    return results


def get_params_from_workflow(workflow: WorkflowType) -> WorkflowParamType:
    result: WorkflowParamType = {}
    for value in workflow.values():
        class_type: str = value["class_type"]
        _meta: dict[str, str] = value["_meta"]
        inputs: dict[str, InputTypes] = value["inputs"]
        _meta_title: str = _meta["title"]
        inputs_value: InputTypes | None = inputs.get("value")
        if class_type == "PrimitiveFloat" and inputs_value is not None:
            result[_meta_title] = float(inputs_value)
        elif class_type.startswith("Primitive") and inputs_value is not None:
            result[_meta_title] = inputs_value
        elif class_type == "LoadImageOutput":
            result[_meta_title] = ""
    return result


def prepare_workflow(workflow: WorkflowType, **kwargs) -> WorkflowType:
    result_workflow = deepcopy(workflow)
    for key, value in result_workflow.items():
        class_type: str = value["class_type"]
        _meta: dict[str, str] = value["_meta"]
        _meta_title: str = _meta["title"]
        if kwargs.get(_meta_title):
            input_value = kwargs[_meta_title]
            if class_type.startswith("Primitive"):
                result_workflow[key]["inputs"]["value"] = input_value
            elif class_type == "LoadImageOutput":
                result_workflow[key]["inputs"]["image"] = f"{input_value} [output]"

    return result_workflow
