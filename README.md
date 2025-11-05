# comfyui-mcp

A Model Context Protocol(MCP) server that exposes [ComfyUI](https://github.com/comfyanonymous/ComfyUI) workflows as callable MCP tools. Built using [FastMCP](https://pypi.org/project/fastmcp/) and [comfyui-utils](https://pypi.org/project/comfyui-utils/).

[![PyPI Version](https://img.shields.io/pypi/v/comfyui-mcp.svg)](https://pypi.org/project/comfyui-mcp/)
[![Python Versions](https://img.shields.io/pypi/pyversions/comfyui-mcp.svg)](https://pypi.org/project/comfyui-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE.txt)
[![CI](https://github.com/ModdingFox/comfyui_mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/ModdingFox/comfyui_mcp/actions)

---

## Installation
Contents of this package require Python 3.11 or higher.

```bash
pip install comfyui-mcp
```

---

## Quick Start
```bash
mcpo --port 8000 --api-key "AwesomeKey" -- python3 -m comfyui_mcp.server
````

## Arguments

### ComfyUI Connection (`--comfyui.*`)

- `--comfyui.host` (default: `127.0.0.1:8188`) - ComfyUI host and port
- `--comfyui.request_timeout` (default: `5`) - Timeout in seconds for ComfyUI API requests
- `--comfyui.use_remote_workflow` (default: `True`) - Pull workflows from ComfyUI API (`True`) or load from local directory (`False`)
- `--comfyui.workflow_directory` (default: `workflows`) - Local directory path for workflow JSON files

### Output Formatting (`--generate.*`)

- `--generate.audio_url_template` - Template for audio output URLs (vars: `{index}`, `{url}`)
- `--generate.image_url_template` - Template for image output URLs (vars: `{index}`, `{url}`)
- `--generate.unknown_url_template` - Template for unknown output types (vars: `{index}`, `{url}`)
- `--generate.nothing_generated_message` - Message when workflow executes but produces no output
- `--generate.reply_include_workflow` (default: `True`) - Include executed workflow parameters in response
- `--generate.reply_workflow_format_indent` (default: `2`) - JSON indentation for workflow output
- `--generate.reply_workflow_format_sort_keys` (default: `True`) - Sort JSON keys in workflow output
- `--generate.reply_workflow_template` - Template for workflow parameters section (vars: `{workflow_params}`)
- `--generate.result_generated_message_template` - Overall message template (vars: `{image_list}`)

---

## Architecture Overview
```bare
src/comfyui_mcp/
```
- \_\_about\_\_.py: Version and license metadata
- argument_parser.py: CLI argument definitions using pydantic
- base_types.py: Shared type aliases 
- function_utils.py: Dynamic function wrapper generation
- workflow_loader.py: Load workflows from disk or ComfyUI API
- workflow_utils.py: Workflow preparation and invocation
- server.py: FastMCP server entry point

## How It Works

1. **Workflow Preparation**:
   - **For local workflows**: Export your ComfyUI workflow in API format (use "Save (API Format)" in ComfyUI's menu). Place the JSON file in your configured workflows directory.
   - **For remote workflows**: Build and save your workflow in ComfyUI, then start or restart the MCP server. The server will automatically fetch and register available workflows from the ComfyUI instance.

2. **Tool Registration**: The server parses workflow JSON and automatically detects parameters by scanning for:
   - **Primitive nodes** (`PrimitiveFloat`, `PrimitiveInt`, `PrimitiveString`, etc.) - extracted as typed parameters
   - **LoadImageOutput nodes** - exposed as image input parameters
   - Node titles (from `_meta.title`) become the parameter names in the MCP tool

3. **Workflow Execution**: When a tool is invoked:
   - User-provided parameters are mapped back to their corresponding primitive nodes
   - The workflow is deep-copied and parameter values are injected into `inputs.value` fields
   - The prepared workflow is submitted to ComfyUI's API
   - Results are polled until completion
   - Generated outputs are returned as accessible URLs (format is user-configurable)

4. **Batch Processing**: Supports `submit_batch` parameter for generating multiple variations:
   - Automatically randomizes seeds for each generation
   - Executes workflows sequentially
   - Collects and returns all results together

---

## Development
```bash
pip setup -hatch
hatch test
hatch build
hatch run release
```

---

## Contributing
1. Fork the repo on GitHub.
2. Make changes, add tests, and build
3. Run `hatch test` to ensure all passes
4. Submit a PR
