"""Restricted Python environment for native CaP's ACT code blocks.

The native generation/regeneration loop is unchanged. Its environment exposes
robot.call plus basic Python computation, not filesystem/network/import tools.
This is an API restriction, not an OS resource-isolation boundary.
"""
import ast

SAFE_BUILTINS = {name: getattr(__import__("builtins"), name) for name in (
    "print", "range", "len", "min", "max", "sum", "abs", "float", "int", "str",
    "bool", "dict", "list", "tuple", "set", "enumerate", "zip", "round", "sorted",
    "all", "any", "reversed")}
METHODS = {"get", "append", "items", "values", "keys", "pop", "update", "sort", "copy", "index", "count"}
FORBIDDEN = (ast.Import, ast.ImportFrom, ast.With, ast.AsyncWith, ast.Try,
             ast.TryStar, ast.ClassDef, ast.Global, ast.Nonlocal, ast.AsyncFunctionDef,
             ast.Await, ast.Yield, ast.YieldFrom, ast.Delete)


def compile_policy(code):
    if not isinstance(code, str) or len(code.encode()) > 64000:
        raise ValueError("generated code exceeds limit")
    tree = ast.parse(code, filename="<cap-act-tools>")
    for node in ast.walk(tree):
        if isinstance(node, FORBIDDEN):
            raise ValueError("only computation and robot.call are supported")
        if isinstance(node, ast.Name):
            if node.id.startswith("_") or (node.id == "robot" and not isinstance(node.ctx, ast.Load)):
                raise ValueError("private names and robot rebinding are prohibited")
        if isinstance(node, (ast.FunctionDef, ast.arg)):
            name = node.name if isinstance(node, ast.FunctionDef) else node.arg
            if name.startswith("_") or name == "robot":
                raise ValueError("reserved function/argument name")
        if isinstance(node, ast.Attribute):
            is_robot_call = node.attr == "call" and isinstance(node.value, ast.Name) and node.value.id == "robot"
            if not isinstance(node.ctx, ast.Load) or not (is_robot_call or node.attr in METHODS):
                raise ValueError("unsupported attribute access")
    return compile(tree, "<cap-act-tools>", "exec")
