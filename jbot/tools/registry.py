import inspect

TOOLS = {}


def tool(func):
    TOOLS[func.__name__] = func
    return func


def _json_type(annotation):
    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())
    if origin is not None and args:
        annotation = args[0]
    mapping = {str: "string", int: "integer", float: "number", bool: "boolean"}
    return mapping.get(annotation, "string")


def get_tool_definitions():
    definitions = []
    for name, func in TOOLS.items():
        sig = inspect.signature(func)
        properties = {}
        required = []
        for param_name, param in sig.parameters.items():
            properties[param_name] = {"type": _json_type(param.annotation)}
            if param.default is inspect.Parameter.empty:
                required.append(param_name)
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": inspect.getdoc(func) or "",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return definitions


def _coerce(func, arguments):
    sig = inspect.signature(func)
    coerced = {}
    for key, value in arguments.items():
        param = sig.parameters.get(key)
        if param is None:
            continue
        annotation = param.annotation
        origin = getattr(annotation, "__origin__", None)
        args = getattr(annotation, "__args__", ())
        target = args[0] if origin is not None and args else annotation
        try:
            if target is bool and isinstance(value, str):
                coerced[key] = value.strip().lower() in {"1", "true", "yes", "y"}
            elif target in (int, float) and not isinstance(value, target):
                coerced[key] = target(value)
            else:
                coerced[key] = value
        except (TypeError, ValueError):
            coerced[key] = value
    return coerced


def execute_tool(name, arguments):
    if name not in TOOLS:
        return f"Error: unknown tool '{name}'"
    func = TOOLS[name]
    try:
        result = func(**_coerce(func, arguments or {}))
        return result if isinstance(result, str) else _to_text(result)
    except Exception as exc:
        return f"Tool error ({name}): {exc}"


def _to_text(value):
    import json

    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        return str(value)


def list_tool_names():
    return sorted(TOOLS.keys())
