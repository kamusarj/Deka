#!/usr/bin/env python3
"""Capture candidate identities and build-input hashes without environment values."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--backend-image', required=True)
parser.add_argument('--frontend-image', required=True)
parser.add_argument('--proxy-image', default='deka-proxy:ready-184')
parser.add_argument('--postgres-image', default='deka-postgres:ready-184')
args = parser.parse_args()
def run(*command): return subprocess.check_output(command,text=True).strip()
def hashes(paths): return {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(set(paths)) if path.is_file()}
inputs = []
for directory in ['backend/app','backend/alembic','frontend/src','frontend/public','deploy/proxy']:
    inputs.extend(path for path in Path(directory).rglob('*') if path.is_file()
                  and '__pycache__' not in path.parts and 'uploads' not in path.parts
                  and path.suffix not in {'.pyc','.sqlite','.db'} and '.env' not in path.name)
inputs.extend(Path(name) for name in ['backend/Dockerfile','backend/pyproject.toml','backend/uv.lock',
    'frontend/Dockerfile','frontend/package.json','frontend/package-lock.json','frontend/nginx.conf',
    'docker-compose.production.yml','deploy/Caddyfile','deploy/Dockerfile.proxy','deploy/Dockerfile.postgres'])
print(json.dumps({'created_at':datetime.now(timezone.utc).isoformat(),'commit':run('git','rev-parse','HEAD'),
    'dirty':bool(run('git','status','--porcelain')),'migration_head':'0007_admin_mfa',
    'images':{name:run('docker','image','inspect','--format','{{.Id}}',value) for name,value in
              [('backend',args.backend_image),('frontend',args.frontend_image),('proxy',args.proxy_image),('postgres',args.postgres_image)]},
    'build_inputs_sha256':hashes(inputs),
    'dependencies':hashes([Path('backend/uv.lock'),Path('frontend/package-lock.json'),Path('deploy/proxy/go.sum')]),
    'migration_files':hashes(Path('backend/alembic/versions').glob('*.py'))},indent=2))
