#!/usr/bin/env python3
"""Create private release configuration without displaying keys or overwriting existing files."""
import argparse
import os
from pathlib import Path
import re
import secrets

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory', required=True)
parser.add_argument('--domain', required=True)
parser.add_argument('--email', required=True)
parser.add_argument('--project', default='deka-production')
args = parser.parse_args()
if not re.fullmatch(r'[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', args.domain) or not re.fullmatch(r'[a-z][a-z0-9-]+', args.project):
    parser.error('Valid domain and lowercase project name required')
if not re.fullmatch(r'[a-zA-Z0-9._+%-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', args.email):
    parser.error('Valid certificate contact email required')
os.umask(0o077)
root = Path(args.directory).resolve()
root.mkdir(mode=0o700, parents=True, exist_ok=False)
backend = root / 'backend.env'
backend.write_text(Path('deploy/backend.staging.env.example').read_text())
values = {'COMPOSE_PROJECT_NAME':args.project,'PUBLIC_DOMAIN':args.domain,'ACME_EMAIL':args.email,
          'POSTGRES_PASSWORD':secrets.token_hex(32),'SECRET_KEY':secrets.token_hex(32),
          'MFA_ENCRYPTION_KEY':secrets.token_hex(32),'BACKEND_ENV_FILE':str(backend),
          'BACKEND_IMAGE':'deka-backend:ready-184','FRONTEND_IMAGE':'deka-frontend:ready-184',
          'PROXY_IMAGE':'deka-proxy:ready-184','POSTGRES_IMAGE':'deka-postgres:ready-184',
          'INTERNAL_SUBNET':'172.30.184.0/24','PROXY_INTERNAL_IP':'172.30.184.10'}
(root / 'deployment.env').write_text(''.join(f'{key}={value}\n' for key,value in values.items()))
(root / 'acceptance.json').write_text(Path('deploy/acceptance.example.json').read_text())
print('Created private configuration. Fill backend provider/SMTP/pricing settings, choose a free subnet, then run preflight. No services started.')
