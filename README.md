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

---

## Architecture Overview
```bare
src/comfyui_mcp/
```
- \_\_about\_\_.py: # Version and license metadata
- argument_parser.py: CLI argument definitions using pydantic
- base_types.py: Shared type aliases 
- function_utils.py: Dynamic function wrapper generation
- workflow_loader.py: Load workflows from disk or ComfyUI API
- workflow_utils.py: Workflow preparation and invocation
- server.py: FastMCP server entry point

## How It Works
1. Workfllow discovery: fetch remote or local JSON.
2. Tool generation: parameters mapped into callable MCP tools.
3. Execution: runs workflow via ComfyUI API and returns image URLs as Markdown.
4. Batching: repeated invocations, seed randomization.

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
