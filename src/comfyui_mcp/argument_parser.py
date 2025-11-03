from dataclasses import dataclass

from jsonargparse import ArgumentParser, Namespace
from pydantic import BaseModel, Field


class ArgsComfyUI(BaseModel):
    host: str = Field(default="127.0.0.1:8188", description="ComfyUI host:port")
    request_timeout: int = Field(default=5, description="Timeout for requests to ComfyUI")
    use_remote_workflow: bool = Field(
        default=True,
        description="True pulls workflow form comfyui directly. False uses a local directory path containing the json files",
    )
    workflow_directory: str = Field(default="workflows", description="Path to load workflows from")


class ArgsGenerate(BaseModel):
    image_url_template: str = Field(
        default="![Image {index}]({url})\n",
        description="Template to use for generated image list. Template vars: index and url",
    )
    nothing_generated_message: str = Field(
        default="Tool call succeded but nothing was generated",
        description="Message to return when called and nothing generated",
    )
    reply_include_workflow: bool = Field(
        default=True, description="If the reply will contain the executed workflow info"
    )
    reply_workflow_format_indent: int = Field(default=2, description="Json indentation level")
    reply_workflow_format_sort_keys: bool = Field(default=True, description="Json sort keys or leave them as they are")
    reply_workflow_template: str = Field(
        default="<details>\n<summary>payload.json</summary>\n{workflow_params}\n</details>",
        description="Template to use for returning the called params in the reply. Template vars: workflow_params",
    )
    result_generated_message_template: str = Field(
        default="Return the following to the user exactly as is in markdown format Do not provide any imformation before or after this in the output:\n{image_list}",
        description="Message to return when something was generated. Template vars: image_list",
    )


@dataclass
class Args:
    comfyui: ArgsComfyUI
    generate: ArgsGenerate


def get_application_args(args: list[str] | None = None) -> Args:
    _argument_parser: ArgumentParser = ArgumentParser()
    _argument_parser.add_class_arguments(ArgsComfyUI, "comfyui")
    _argument_parser.add_class_arguments(ArgsGenerate, "generate")
    _namespace_args: Namespace = _argument_parser.parse_args(args)
    _args = _argument_parser.instantiate_classes(_namespace_args)
    return Args(_args["comfyui"], _args["generate"])
