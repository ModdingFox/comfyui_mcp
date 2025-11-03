from functools import wraps
from inspect import Parameter, Signature
from logging import getLogger

from comfyui_mcp.argument_parser import ArgsComfyUI, ArgsGenerate
from comfyui_mcp.base_types import (
    GenerateFunctionType,
    WorkflowParamType,
    WorkflowType,
    WrappedFunctionType,
)
from comfyui_mcp.workflow_utils import get_params_from_workflow

logger = getLogger(__name__)


def wrap_fn(
    argscomfyui: ArgsComfyUI,
    argsgenerate: ArgsGenerate,
    name: str,
    workflow: WorkflowType,
    wrapped_fn: GenerateFunctionType,
) -> WrappedFunctionType:
    annotations: dict[str, type] = {}
    parameters: list[Parameter] = []

    found_parameters: WorkflowParamType = get_params_from_workflow(workflow)

    for key, value in found_parameters.items():
        default_value = value
        annotations[key] = type(value)
        parameters.append(
            Parameter(
                name=key, kind=Parameter.POSITIONAL_OR_KEYWORD, default=default_value, annotation=annotations[key]
            )
        )

    annotations["submit_batch"] = int
    parameters.append(
        Parameter(
            name="submit_batch", kind=Parameter.POSITIONAL_OR_KEYWORD, default=1, annotation=annotations["submit_batch"]
        )
    )

    annotations["batch_by_time"] = bool
    parameters.append(
        Parameter(
            name="batch_by_time",
            kind=Parameter.POSITIONAL_OR_KEYWORD,
            default=False,
            annotation=annotations["batch_by_time"],
        )
    )

    signature: Signature = Signature(parameters)
    logger.info(f"{name}: {signature}")

    @wraps(wrapped_fn)
    def wrapper(**kwargs):
        signature_args = signature.bind(**kwargs)
        signature_args.apply_defaults()
        return wrapped_fn(argscomfyui, argsgenerate, workflow, signature_args.arguments)

    wrapper.__annotations__ = annotations
    wrapper.__doc__ = (
        f"Dynamically generated wrapper for {wrapped_fn.__name__} with parameters: {list(found_parameters)}"
    )
    wrapper.__name__ = name
    # Required voodoo to set the funct function signature. My pygets quite angry about this
    wrapper.__signature__ = signature  # type: ignore[attr-defined]
    return wrapper
