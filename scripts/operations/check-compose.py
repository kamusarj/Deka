#!/usr/bin/env python3
"""Validate rendered JSON from docker compose config --format json, without logging secrets."""
import json, sys
config = json.load(sys.stdin)
for name, service in config['services'].items():
    if name != 'proxy' and service.get('ports'):
        raise SystemExit(f'Unexpected published port: {name}')
assert config['services']['backend']['command'].count('1') >= 1
assert config['services']['backend']['environment']['ENV'] == 'production'
print('Compose isolation: only proxy publishes host ports; production backend configured.')
