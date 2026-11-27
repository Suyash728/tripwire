"""R6: the containment path must never import the LLM service."""
import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
CONTAINMENT = ["gateway", "policy", "ledger", "provenance", "rollback"]
FORBIDDEN = ("app.services.llm", "services.llm", "openai", "groq", "google.genai", "google.generativeai")


def _imports(path: pathlib.Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            yield module
            for alias in node.names:
                yield f"{module}.{alias.name}"


def test_containment_modules_do_not_import_llm():
    offenders = []
    for pkg in CONTAINMENT:
        for py in (APP / pkg).rglob("*.py"):
            for name in _imports(py):
                if any(name == f or name.startswith(f + ".") for f in FORBIDDEN):
                    offenders.append(f"{py.relative_to(APP)} imports {name}")
    assert not offenders, "LLM import in containment path:\n" + "\n".join(offenders)
