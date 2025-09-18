"""Griffe extension for `@warnings.deprecated` (PEP 702)."""

from __future__ import annotations

import ast
from collections.abc import Sequence
from typing import Any

from griffe import Class, Docstring, DocstringSectionAdmonition, Expr, ExprCall, ExprKeyword, ExprList, Extension, Function, get_logger

logger = get_logger(__name__)
self_namespace = "griffe_warnings_deprecated"
mkdocstrings_namespace = "mkdocstrings"

_decorators = {"warnings.deprecated", "typing_extensions.deprecated", "braian.utils.deprecated"}

def _object_anchestry(obj: Class) -> list[str]:
    import_name = []
    while obj:
        if not obj.name.startswith("_") or obj.parent is None:
            import_name.append(obj.name)
        obj = obj.parent
    return list(reversed(import_name))

def _remove_common_anchestors(package_path: str, other_anchestry: list[str]):
    anchestry = package_path.split(".")
    common = [a1 for a1,a2 in zip(anchestry,other_anchestry) if a1==a2]
    return ".".join(anchestry[len(common):])

def _deprecated_braian(obj: Class | Function, kwargs: Sequence[Expr]) -> str | None:
    message = None
    since = None
    alternatives = None
    for arg in kwargs:
        if not isinstance(arg, ExprKeyword):
            continue
        match arg.name:
            case "message":
                try:
                    message =  ast.literal_eval(arg.value)
                except ValueError:
                    pass
            case "since":
                try:
                    since = ast.literal_eval(arg.value)
                except ValueError:
                    pass
            case "alternatives": # ExprList
                try:
                    alternatives = [ast.literal_eval(e) for e in arg.value.elements]
                except ValueError:
                    pass
    if since is None:
        logger.debug("No static string or 'since=<string>' keyword found")
        return None
    text = f"`{obj.name}` is deprecated since {since} and may be removed in future versions."
    if message is not None:
        text += f"\n\n{message}"
    if alternatives:
        obj_anchestry = _object_anchestry(obj)
        alternatives = [f"[`{_remove_common_anchestors(a, obj_anchestry)}`][{a}]" for a in alternatives]
        text += f"\n\n**Alternative{'s' if len(alternatives) > 1 else ''}**: {', '.join(alternatives)}"
    return text

def _deprecated(obj: Class | Function) -> str | None:
    for decorator in obj.decorators:
        if decorator.callable_path in _decorators and isinstance(decorator.value, ExprCall):
            first_arg = decorator.value.arguments[0]
            try:
                return ast.literal_eval(first_arg)  # type: ignore[arg-type]
            except (ValueError, IndexError):
                pass
            return _deprecated_braian(obj, decorator.value)
    return None


class WarningsDeprecatedExtension(Extension):
    """Griffe extension for `@warnings.deprecated` (PEP 702)."""

    def __init__(
        self,
        kind: str = "danger",
        title: str | None = "Deprecated",
        label: str | None = "deprecated",
    ) -> None:
        """Initialize the extension.

        Parameters:
            kind: Admonitions kind.
            title: Admonitions title.
            label: Label added to deprecated objects.
        """
        super().__init__()
        self.kind = kind
        self.title = title or ""
        self.label = label

    def _insert_message(self, obj: Function | Class, message: str) -> None:
        title = self.title
        if not self.title:
            title, message = message, title
        if not obj.docstring:
            obj.docstring = Docstring("", parent=obj)
        sections = obj.docstring.parsed
        sections.insert(0, DocstringSectionAdmonition(kind=self.kind, text=message, title=title))

    def on_class_instance(self, *, cls: Class, **kwargs: Any) -> None:  # noqa: ARG002
        """Add section to docstrings of deprecated classes."""
        if message := _deprecated(cls):
            cls.deprecated = message
            self._insert_message(cls, message)
            if self.label:
                cls.labels.add(self.label)

    def on_function_instance(self, *, func: Function, **kwargs: Any) -> None:  # noqa: ARG002
        """Add section to docstrings of deprecated functions."""
        if message := _deprecated(func):
            func.deprecated = message
            self._insert_message(func, message)
            if self.label:
                func.labels.add(self.label)
