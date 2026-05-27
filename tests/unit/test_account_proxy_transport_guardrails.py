from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCANNED_MODULES = [*_PROJECT_ROOT.glob("app/core/clients/*.py"), _PROJECT_ROOT / "app/core/auth/refresh.py"]

# Any new raw outbound primitive in these modules requires explicit review.
# Account-bound branches in the fallback functions below route through
# account_proxy; OAuth uses a pre-account proxy snapshot; version lookup is
# intentionally system/direct traffic.
_ALLOWED_RAW_CALLS = Counter(
    {
        ("app/core/auth/refresh.py", "refresh_access_token", "client_session.post"): 1,
        ("app/core/clients/codex_version.py", "_fetch_from_github", "session.get"): 1,
        ("app/core/clients/codex_version.py", "_fetch_from_npm", "session.get"): 1,
        ("app/core/clients/files.py", "_post_context", "client_session.post"): 1,
        ("app/core/clients/model_fetcher.py", "fetch_models_for_plan", "session.get"): 1,
        ("app/core/clients/oauth.py", "exchange_authorization_code", "client_session.post"): 1,
        ("app/core/clients/oauth.py", "request_device_code", "client_session.post"): 1,
        ("app/core/clients/oauth.py", "exchange_device_token", "client_session.post"): 1,
        ("app/core/clients/proxy.py", "_open_upstream_websocket", "session.ws_connect"): 1,
        ("app/core/clients/proxy.py", "_fetch_image_data_url", "session.get"): 1,
        ("app/core/clients/proxy.py", "_stream_via_http", "client_session.post"): 1,
        ("app/core/clients/proxy.py", "execute", "self.session.post"): 1,
        ("app/core/clients/proxy.py", "thread_goal_request", "client_session.request"): 1,
        ("app/core/clients/proxy.py", "codex_control_request", "client_session.request"): 1,
        ("app/core/clients/proxy.py", "_transcribe_audio_with_session", "client_session.post"): 1,
        ("app/core/clients/proxy_websocket.py", "connect_responses_websocket", "websocket_connect"): 1,
        ("app/core/clients/usage.py", "_usage_request_context", "retry_client.request"): 1,
    }
)


class _RawOutboundVisitor(ast.NodeVisitor):
    def __init__(self, module_path: str) -> None:
        self._module_path = module_path
        self._function_stack: list[str] = []
        self.calls: Counter[tuple[str, str, str]] = Counter()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_stack.append(node.name)
        self.generic_visit(node)
        self._function_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        label: str | None = None
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"get", "post", "request", "ws_connect"}:
            receiver = ast.unparse(node.func.value)
            if any(fragment in receiver for fragment in ("session", "client", "retry_client")):
                label = f"{receiver}.{node.func.attr}"
        elif isinstance(node.func, ast.Name) and node.func.id == "websocket_connect":
            label = node.func.id

        if label is not None:
            function = self._function_stack[-1] if self._function_stack else "<module>"
            self.calls[(self._module_path, function, label)] += 1
        self.generic_visit(node)


def test_account_bound_raw_outbound_primitives_remain_explicitly_allowlisted() -> None:
    discovered: Counter[tuple[str, str, str]] = Counter()
    for module in _SCANNED_MODULES:
        relative_path = module.relative_to(_PROJECT_ROOT).as_posix()
        if relative_path == "app/core/clients/account_proxy.py":
            continue
        visitor = _RawOutboundVisitor(relative_path)
        visitor.visit(ast.parse(module.read_text(encoding="utf-8"), filename=str(module)))
        discovered.update(visitor.calls)

    assert discovered == _ALLOWED_RAW_CALLS
