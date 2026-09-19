"""Run with ENV=test and PYTHONPATH=backend against an isolated database."""
from fastapi.routing import APIRoute
from app.main import app
from app.services.ai.policy import OPERATIONS

def dependencies(node):
    result = set()
    for item in node.dependencies:
        result.add(getattr(item.call, '__name__', type(item.call).__name__))
        result.update(dependencies(item))
    return result

print('# API and operation inventory\n\nGenerated from registered routes; dependencies show entry guards, service scope checks require tests.\n')
print('| Method | Route | Handler | Dependencies |\n| --- | --- | --- | --- |')
def routes(router, prefix="", inherited=()):
    for route in router.routes:
        if isinstance(route, APIRoute):
            yield prefix + route.path, route, inherited
        elif hasattr(route, 'original_router'):
            context = route.include_context
            guards = tuple(getattr(d.dependency, '__name__', 'guard') for d in context.dependencies)
            yield from routes(route.original_router, prefix + context.prefix, inherited + guards)

rows = list(routes(app))
assert len(rows) > 100, 'Route inventory unexpectedly incomplete'
for path, route, inherited in sorted(rows, key=lambda row:row[0]):
    print(f'| {", ".join(sorted(route.methods))} | `{path}` | `{route.endpoint.__name__}` | {", ".join(sorted(dependencies(route.dependant) | set(inherited)))} |')
print('\n| Operation | Credits | Purpose |\n| --- | --- | --- |')
for name, policy in OPERATIONS.items():
    print(f'| {name} | {policy.credits} | {policy.purpose} |')
