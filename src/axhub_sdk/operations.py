from __future__ import annotations

import re
from typing import Any, Mapping

OPERATION_METHODS: list[dict[str, str]] = []

class OperationContextClient:
    def __init__(self, client): self._client = client

class AsyncOperationContextClient:
    def __init__(self, client): self._client = client

def _snake(name: str) -> str:
    name = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name)
    return name.lower()

def _sync_method(operation_id: str):
    def method(self, path_params: Mapping[str, str] | None = None, query: Mapping[str, str] | None = None, body: Any = None):
        return self._client.request(operation_id, path_params=path_params, query=query, body=body)
    method.__name__ = operation_id
    return method

def _async_method(operation_id: str):
    async def method(self, path_params: Mapping[str, str] | None = None, query: Mapping[str, str] | None = None, body: Any = None):
        return await self._client.request(operation_id, path_params=path_params, query=query, body=body)
    method.__name__ = operation_id
    return method

def install_operations(ns: dict[str, Any]) -> None:
    client_cls = ns['AxHubClient']; async_client_cls = ns['AsyncAxHubClient']; apps_cls = ns['AppsClient']; async_apps_cls = ns['AsyncAppsClient']
    if getattr(client_cls, '_axhub_operations_installed', False): return
    global OPERATION_METHODS
    OPERATION_METHODS = [
        {'operationId': r['operationId'], 'context': ns['_context_name'](r), 'snake': _snake(r['operationId'])}
        for r in ns['ROUTES']
    ]
    original_init = client_cls.__init__
    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.identity = OperationContextClient(self); self.tenants = OperationContextClient(self); self.authz = OperationContextClient(self); self.audit = OperationContextClient(self); self.gateway = OperationContextClient(self); self.cost = OperationContextClient(self); self.data = OperationContextClient(self); self.deployments = OperationContextClient(self)
    client_cls.__init__ = init
    original_async_init = async_client_cls.__init__
    def async_init(self, *args, **kwargs):
        original_async_init(self, *args, **kwargs)
        self.identity = AsyncOperationContextClient(self); self.tenants = AsyncOperationContextClient(self); self.authz = AsyncOperationContextClient(self); self.audit = AsyncOperationContextClient(self); self.gateway = AsyncOperationContextClient(self); self.cost = AsyncOperationContextClient(self); self.data = AsyncOperationContextClient(self); self.deployments = AsyncOperationContextClient(self)
    async_client_cls.__init__ = async_init
    by_context = {'apps': apps_cls, 'identity': OperationContextClient, 'tenants': OperationContextClient, 'authz': OperationContextClient, 'audit': OperationContextClient, 'gateway': OperationContextClient, 'cost': OperationContextClient, 'data': OperationContextClient, 'deployments': OperationContextClient}
    async_by_context = {'apps': async_apps_cls, 'identity': AsyncOperationContextClient, 'tenants': AsyncOperationContextClient, 'authz': AsyncOperationContextClient, 'audit': AsyncOperationContextClient, 'gateway': AsyncOperationContextClient, 'cost': AsyncOperationContextClient, 'data': AsyncOperationContextClient, 'deployments': AsyncOperationContextClient}
    for item in OPERATION_METHODS:
        for cls, maker in ((by_context[item['context']], _sync_method), (async_by_context[item['context']], _async_method)):
            fn = maker(item['operationId'])
            setattr(cls, item['snake'], fn)
            setattr(cls, item['operationId'], fn)
    client_cls._axhub_operations_installed = True
