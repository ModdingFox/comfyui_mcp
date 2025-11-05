from comfyui_mcp.argument_parser import Args, ArgsComfyUI, ArgsGenerate, get_application_args


def test_get_application_args_defaults():
    """Ensure get_application_args returns Args with correct default objects."""
    args = get_application_args(args=[])
    assert isinstance(args, Args)
    assert isinstance(args.comfyui, ArgsComfyUI)
    assert isinstance(args.generate, ArgsGenerate)
    # Confirm expected defaults
    assert args.comfyui.host == "127.0.0.1:8188"
    assert "Result" in args.generate.image_url_template


def test_get_application_args_custom():
    """Ensure custom CLI args override defaults correctly."""
    test_args = [
        "--comfyui.host=127.0.0.1:9000",
        "--comfyui.request_timeout=10",
        "--generate.image_url_template=foo-{index}",
    ]
    args = get_application_args(test_args)
    assert args.comfyui.host == "127.0.0.1:9000"
    assert args.comfyui.request_timeout == 10
    assert args.generate.image_url_template == "foo-{index}"


def test_args_dataclass_structure():
    """Confirm Args dataclass behaves as expected."""
    comfy = ArgsComfyUI()
    gen = ArgsGenerate()
    args = Args(comfy, gen)
    assert args.comfyui is comfy
    assert args.generate is gen
