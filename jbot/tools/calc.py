import ast
import math

from jbot.tools.registry import tool

ALLOWED_NAMES = {
    name: getattr(math, name)
    for name in dir(math)
    if not name.startswith("_")
}
ALLOWED_NAMES.update({"abs": abs, "round": round, "min": min, "max": max, "pow": pow})


@tool
def calculate(expression: str):
    """
    Safely evaluate a mathematical expression and return the result.

    Supports +, -, *, /, //, %, **, parentheses, and common math functions
    such as sqrt, sin, cos, tan, log, log10, floor, ceil, pow, and constants
    like pi and e.

    Args:
        expression: The mathematical expression to evaluate as a string.
                    Example: "(3 + 5) * 2" or "sqrt(16) + pi"
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        return {"error": f"Invalid expression: {exc}"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in ALLOWED_NAMES:
            return {"error": f"Disallowed name: {node.id}"}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id not in ALLOWED_NAMES:
                return {"error": f"Disallowed function: {node.func.id}"}
        if isinstance(node, (ast.Attribute, ast.Subscript, ast.Lambda, ast.Await)):
            return {"error": "Disallowed syntax in expression."}

    try:
        result = eval(compile(tree, "<calculate>", "eval"), {"__builtins__": {}}, ALLOWED_NAMES)
        return {"result": result}
    except Exception as exc:
        return {"error": f"Calculation failed: {exc}"}
