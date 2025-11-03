from copy import deepcopy

from comfyui_utils.comfy import Callbacks, ComfyAPI  # type: ignore[import-untyped]

from comfyui_mcp.argument_parser import ArgsComfyUI
from comfyui_mcp.base_types import (
    InputTypes,
    WorkflowParamType,
    WorkflowType,
)


async def call_workflow(argscomfyui: ArgsComfyUI, workflow: WorkflowType) -> list[str]:
    images = []

    class ComfyCallbacks(Callbacks):
        async def queue_position(self, position):
            pass

        async def in_progress(self, node_id, progress, total):
            pass

        # cached required for funct contract
        async def completed(self, output, cached):  # noqa: ARG002
            if output and output["images"]:
                for image in output["images"]:
                    # List comprehension doesnt assign to the global
                    images.append(image["filename"])  # noqa: PERF401

    comfyapi = ComfyAPI(argscomfyui.host)
    await comfyapi.submit(workflow, ComfyCallbacks())
    return [f"http://{argscomfyui.host}/api/view?filename={image}" for image in images]


def get_params_from_workflow(workflow: WorkflowType) -> WorkflowParamType:
    result: WorkflowParamType = {}
    for value in workflow.values():
        class_type: str = value["class_type"]
        _meta: dict[str, str] = value["_meta"]
        inputs: dict[str, InputTypes] = value["inputs"]
        _meta_title: str = _meta["title"]
        inputs_image: str | None = inputs.get("image")
        inputs_value: InputTypes | None = inputs.get("value")
        if class_type == "PrimitiveFloat" and inputs_value is not None:
            result[_meta_title] = float(inputs_value)
        elif class_type.startswith("Primitive") and inputs_value is not None:
            result[_meta_title] = inputs_value
        elif class_type == "LoadImageOutput" and inputs_image is not None:
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
