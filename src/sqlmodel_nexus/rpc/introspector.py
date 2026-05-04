"""ServiceIntrospector — method scanning and SDL type generation.

Extracts method metadata from RpcService subclasses, generating
SDL-style type descriptions for compact, AI-friendly output.
"""

from __future__ import annotations

import inspect
import typing
from typing import Any, get_args, get_origin

from pydantic import BaseModel

from sqlmodel_nexus.rpc.business import (
    RPC_METHODS_ATTR,  # noqa: F401
    RpcService,
)
from sqlmodel_nexus.subset import get_subset_source

# ──────────────────────────────────────────────────
# SDL type name conversion
# ──────────────────────────────────────────────────


def _type_to_sdl_name(anno: Any) -> str:
    """Convert a type annotation to an SDL type name string.

    Examples::

        int         → "Int"
        str         → "String"
        list[int]   → "[Int!]!"
        int | None  → "Int"
        UserDTO     → "UserDTO"
        list[UserDTO] | None → "[UserDTO!]!"
    """
    if anno is inspect.Parameter.empty or anno is None:
        return "String"

    if isinstance(anno, str):
        return "String"

    origin = get_origin(anno)

    # Handle list[X]
    if origin is list:
        args = get_args(anno)
        if args:
            inner = _type_to_sdl_name(args[0])
            return f"[{inner}!]!"
        return "[String!]!"

    # Handle Optional[X] / Union[X, None]
    import types as _types

    if origin is typing.Union or isinstance(anno, _types.UnionType):
        args = get_args(anno)
        non_none = [a for a in args if a is not type(None)]
        has_none = any(a is type(None) for a in args)

        if has_none and len(non_none) == 1:
            # Optional[X] — nullable (no trailing !)
            return _type_to_sdl_name(non_none[0])
        # General Union — use first non-None type
        if non_none:
            return _type_to_sdl_name(non_none[0])
        return "String"

    # Handle Annotated[X, ...]
    if origin is typing.Annotated:
        args = get_args(anno)
        if args:
            return _type_to_sdl_name(args[0])
        return "String"

    # Handle Pydantic BaseModel subclasses (DTOs) → use class name
    if isinstance(anno, type) and issubclass(anno, BaseModel):
        return anno.__name__

    # Handle basic Python types
    _SCALAR_MAP = {int: "Int", float: "Float", str: "String", bool: "Boolean"}
    if anno in _SCALAR_MAP:
        return _SCALAR_MAP[anno]

    # Handle dict
    if anno is dict:
        return "JSON"

    # Fallback
    if isinstance(anno, type):
        return anno.__name__

    return "String"


def _type_to_legacy_name(anno: Any) -> str:
    """Convert a type annotation to a lenient, non-SDL type name.

    This is used for backwards-compatible method signatures in
    ``describe_service`` responses.
    """
    if anno is inspect.Parameter.empty or anno is None:
        return "any"

    if isinstance(anno, str):
        return "string"

    origin = get_origin(anno)

    if origin is list:
        args = get_args(anno)
        inner = _type_to_legacy_name(args[0]) if args else "any"
        return f"list[{inner}]"

    import types as _types

    if origin is typing.Union or isinstance(anno, _types.UnionType):
        args = get_args(anno)
        non_none = [a for a in args if a is not type(None)]
        has_none = any(a is type(None) for a in args)
        if has_none and len(non_none) == 1:
            return _type_to_legacy_name(non_none[0])
        if non_none:
            return _type_to_legacy_name(non_none[0])
        return "any"

    if origin is typing.Annotated:
        args = get_args(anno)
        return _type_to_legacy_name(args[0]) if args else "any"

    if isinstance(anno, type) and issubclass(anno, BaseModel):
        return anno.__name__

    _SCALAR_MAP = {int: "int", float: "float", str: "string", bool: "bool"}
    if anno in _SCALAR_MAP:
        return _SCALAR_MAP[anno]

    if anno is dict:
        return "dict"

    if isinstance(anno, type):
        return anno.__name__

    return "any"


# ──────────────────────────────────────────────────
# SDL type definition generation
# ──────────────────────────────────────────────────


def _is_optional_type(anno: Any) -> bool:
    """Check if a type annotation is Optional (X | None)."""
    if anno is None:
        return True

    origin = get_origin(anno)

    import types as _types

    if origin is typing.Union or isinstance(anno, _types.UnionType):
        args = get_args(anno)
        return any(a is type(None) for a in args)

    return False


def _is_fk_field(field_name: str, dto_class: type[BaseModel]) -> bool:
    """Check if a field is a foreign key that should be hidden from SDL output."""
    source = get_subset_source(dto_class)
    if source is None:
        return False

    # Check if this field is from the source entity (not a relationship field)
    subset_fields = getattr(dto_class, "__subset_fields__", None)
    if subset_fields and field_name in subset_fields:
        # Check source entity's model_fields for FK metadata
        source_field = source.model_fields.get(field_name)
        if source_field:
            if hasattr(source_field, "foreign_key") and isinstance(
                source_field.foreign_key, str
            ):
                return True
            for meta in getattr(source_field, "metadata", []):
                if hasattr(meta, "foreign_key") and isinstance(meta.foreign_key, str):
                    return True
    return False


def _generate_dto_sdl(dto_class: type[BaseModel], visited: set[str] | None = None) -> str:
    """Generate SDL type definition for a DTO class.

    Returns a ``type Xxx { ... }`` string with all fields.
    FK fields from DefineSubset are excluded.
    """
    if visited is None:
        visited = set()

    type_name = dto_class.__name__
    if type_name in visited:
        return ""
    visited.add(type_name)

    lines: list[str] = []
    # Add type description if present
    if dto_class.__doc__:
        lines.append(f'  """{dto_class.__doc__.strip()}"""')

    for field_name, field_info in dto_class.model_fields.items():
        # Skip FK fields
        if _is_fk_field(field_name, dto_class):
            continue

        anno = field_info.annotation
        sdl_type = _type_to_sdl_name(anno)

        # Add ! for required (non-Optional) fields, unless already ends with !
        if not _is_optional_type(anno) and not sdl_type.endswith("!"):
            sdl_type += "!"

        # Add field description if present
        desc = getattr(field_info, "description", None)
        if desc:
            lines.append(f'  """{desc}"""')
        lines.append(f"  {field_name}: {sdl_type}")

    return f"type {type_name} {{\n{chr(10).join(lines)}\n}}"


def _collect_dto_types(
    anno: Any, visited: set[str] | None = None
) -> list[type[BaseModel]]:
    """Recursively collect all DTO types referenced in a type annotation."""
    if visited is None:
        visited = set()

    if anno is None or anno is inspect.Parameter.empty or isinstance(anno, str):
        return []

    origin = get_origin(anno)

    # Handle list[X]
    if origin is list:
        args = get_args(anno)
        if args:
            return _collect_dto_types(args[0], visited)
        return []

    # Handle Optional[X] / Union
    import types as _types

    if origin is typing.Union or isinstance(anno, _types.UnionType):
        args = get_args(anno)
        results: list[type[BaseModel]] = []
        for a in args:
            if a is not type(None):
                results.extend(_collect_dto_types(a, visited))
        return results

    # Handle Annotated[X, ...]
    if origin is typing.Annotated:
        args = get_args(anno)
        if args:
            return _collect_dto_types(args[0], visited)
        return []

    # Handle BaseModel subclasses
    if isinstance(anno, type) and issubclass(anno, BaseModel):
        name = anno.__name__
        if name in visited:
            return []
        visited.add(name)

        result = [anno]
        # Recurse into fields to find nested DTOs
        for _fn, fi in anno.model_fields.items():
            if fi.annotation:
                result.extend(_collect_dto_types(fi.annotation, visited))
        return result

    return []


# ──────────────────────────────────────────────────
# Simple type description for parameters (JSON Schema lite)
# ──────────────────────────────────────────────────


def _type_to_param_schema(anno: Any) -> dict[str, Any]:
    """Convert a parameter type to a simple JSON Schema description."""
    if anno is inspect.Parameter.empty or anno is None:
        return {}

    if isinstance(anno, str):
        return {"type": "string", "description": f"<unresolved: {anno}>"}

    _BASIC_TYPE_MAP = {
        int: "integer",
        float: "number",
        str: "string",
        bool: "boolean",
    }
    if anno in _BASIC_TYPE_MAP:
        return {"type": _BASIC_TYPE_MAP[anno]}

    if anno is dict:
        return {"type": "object"}

    if isinstance(anno, type) and issubclass(anno, BaseModel):
        return {"type": "object", "title": anno.__name__}

    origin = get_origin(anno)

    if origin is list:
        args = get_args(anno)
        if args:
            return {"type": "array", "items": _type_to_param_schema(args[0])}
        return {"type": "array"}

    import types as _types

    if origin is typing.Union or isinstance(anno, _types.UnionType):
        args = get_args(anno)
        non_none = [a for a in args if a is not type(None)]
        has_none = any(a is type(None) for a in args)

        if has_none and len(non_none) == 1:
            inner = _type_to_param_schema(non_none[0])
            if inner:
                return {"anyOf": [inner, {"type": "null"}]}
            return {}
        schemas = [_type_to_param_schema(a) for a in non_none]
        schemas = [s for s in schemas if s]
        if schemas:
            result: dict[str, Any] = {"anyOf": schemas}
            if has_none:
                result["anyOf"].append({"type": "null"})
            return result
        return {}

    if origin is typing.Annotated:
        args = get_args(anno)
        if args:
            return _type_to_param_schema(args[0])
        return {}

    return {}


# ──────────────────────────────────────────────────
# ServiceIntrospector
# ──────────────────────────────────────────────────


class ServiceIntrospector:
    """Extracts method metadata from RpcService subclasses.

    Provides three levels of information matching the MCP progressive
    disclosure pattern:
    - ``list_services()``: lightweight service listing
    - ``describe_service()``: detailed method signatures + SDL types
    - ``get_service()``: direct access to the service class
    """

    def __init__(self, configs: list[dict[str, Any]]):
        """Initialize with a list of RpcServiceConfig dicts.

        Args:
            configs: Each must have ``name`` and ``service`` keys.
        """
        self._services: dict[str, type[RpcService]] = {}
        self._descriptions: dict[str, str | None] = {}

        for config in configs:
            name = config["name"]
            service = config["service"]
            self._services[name] = service
            self._descriptions[name] = config.get("description")

    def list_services(self) -> list[dict[str, Any]]:
        """Return lightweight service listing.

        Returns:
            List of dicts with name, description, methods_count.
        """
        result = []
        for name, service_cls in self._services.items():
            result.append(
                {
                    "name": name,
                    "description": self._descriptions.get(name)
                    or service_cls.__doc__,
                    "methods_count": len(getattr(service_cls, RPC_METHODS_ATTR)),
                }
            )
        return result

    def describe_service(self, name: str) -> dict[str, Any] | None:
        """Return detailed method info and SDL type definitions.

        Args:
            name: Service name (as registered).

        Returns:
            Dict with name, description, methods (each with SDL signature),
            and types (SDL string of all referenced DTO types),
            or None if service not found.
        """
        service_cls = self._services.get(name)
        if service_cls is None:
            return None

        methods: list[dict[str, Any]] = []
        all_dto_types: list[type[BaseModel]] = []
        visited: set[str] = set()

        for method_name in getattr(service_cls, RPC_METHODS_ATTR):
            method_info = self._extract_method_info(service_cls, method_name)
            methods.append(method_info)

            # Collect DTO types from return value
            return_anno = method_info.get("_return_anno")
            if return_anno is not None:
                all_dto_types.extend(_collect_dto_types(return_anno, visited))

        # Generate SDL for all collected DTO types
        type_defs: list[str] = []
        for dto_cls in all_dto_types:
            sdl = _generate_dto_sdl(dto_cls, visited=set())
            if sdl:
                type_defs.append(sdl)

        types_str = "\n\n".join(type_defs)

        # Remove internal _return_anno from method info before returning
        clean_methods = []
        for m in methods:
            clean_methods.append(
                {
                    "name": m["name"],
                    "description": m["description"],
                    "signature": m["signature"],
                    "signature_sdl": m["signature_sdl"],
                    "parameters": m["parameters"],
                }
            )

        return {
            "name": name,
            "description": self._descriptions.get(name) or service_cls.__doc__,
            "methods": clean_methods,
            "types": types_str,
        }

    def get_service(self, name: str) -> type[RpcService] | None:
        """Look up a service class by name.

        Args:
            name: Service name (as registered).

        Returns:
            The RpcService subclass, or None if not found.
        """
        return self._services.get(name)

    def _extract_method_info(
        self, service_cls: type[RpcService], method_name: str
    ) -> dict[str, Any]:
        """Extract full metadata for a single method."""
        method = getattr(service_cls, method_name, None)
        if method is None:
            return {
                "name": method_name,
                "description": None,
                "signature": f"{method_name}()",
                "parameters": {},
                "_return_anno": None,
            }

        # Get underlying function (unwrap classmethod)
        func = method
        if isinstance(method, classmethod):
            func = method.__func__

        # Use typing.get_type_hints to resolve string annotations
        try:
            hints = typing.get_type_hints(func)
        except Exception:
            hints = {}

        description = inspect.getdoc(func)
        parameters = self._extract_parameters(func, hints)
        return_anno = hints.get("return") or self._get_return_anno_from_sig(func)

        # Build SDL signature: method_name(param: Type, ...): ReturnType
        sdl_param_parts = []
        legacy_param_parts = []
        for pname, pschema in parameters.items():
            sdl_type = pschema.get("type", "String")
            # Convert JSON Schema type names to SDL style
            _json_to_sdl = {
                "integer": "Int",
                "number": "Float",
                "string": "String",
                "boolean": "Boolean",
                "object": "JSON",
            }
            sdl_type = _json_to_sdl.get(sdl_type, sdl_type)
            sdl_param_parts.append(f"{pname}: {sdl_type}!")
            legacy_param_parts.append(f"{pname}: {pschema.get('type', 'any')}")

        sdl_param_str = ", ".join(sdl_param_parts)
        legacy_param_str = ", ".join(legacy_param_parts)
        return_sdl = _type_to_sdl_name(return_anno) if return_anno else ""
        return_legacy = _type_to_legacy_name(return_anno) if return_anno else ""
        sdl_suffix = f": {return_sdl}" if return_sdl else ""
        legacy_suffix = f" -> {return_legacy}" if return_legacy else ""

        signature_sdl = f"{method_name}({sdl_param_str}){sdl_suffix}"
        signature = f"{method_name}({legacy_param_str}){legacy_suffix}"

        return {
            "name": method_name,
            "description": description,
            "signature": signature,
            "signature_sdl": signature_sdl,
            "parameters": parameters,
            "_return_anno": return_anno,
        }

    def _extract_parameters(
        self, func: Any, hints: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract parameter names and their type schema from a function."""
        try:
            sig = inspect.signature(func)
        except (ValueError, TypeError):
            return {}

        params = {}
        for param_name, param in sig.parameters.items():
            if param_name == "cls":
                continue

            anno = hints.get(param_name, param.annotation)
            params[param_name] = _type_to_param_schema(anno)

        return params

    def _get_return_anno_from_sig(self, func: Any) -> Any:
        """Fallback: get return annotation from inspect.signature."""
        try:
            sig = inspect.signature(func)
        except (ValueError, TypeError):
            return None

        if sig.return_annotation is inspect.Signature.empty:
            return None
        return sig.return_annotation
