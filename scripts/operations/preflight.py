#!/usr/bin/env python3
"""Read-only release gate. Report missing conditions, never secret values."""
import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import stat
import subprocess
from urllib.parse import urlparse


def check(config, *, synthetic=False):
    errors = []
    services = config['services']
    backend = services['backend']
    env = backend['environment']
    for name, service in services.items():
        if name != 'proxy' and service.get('ports'):
            errors.append(f'{name}: unexpected host ports')
    if not backend.get('read_only') or not backend.get('tmpfs') or 'ALL' not in backend.get('cap_drop', []):
        errors.append('backend: read-only root/tmpfs/capability restrictions required')
    command = backend['command']
    if '--workers' not in command or command[command.index('--workers') + 1:command.index('--workers') + 2] != ['1']:
        errors.append('backend: one worker is required')
    for key in ['SECRET_KEY', 'MFA_ENCRYPTION_KEY']:
        value = env.get(key, '')
        if len(value) < 32 or (not synthetic and any(word in value.lower() for word in ['replace', 'audit-only', 'example'])):
            errors.append(f'{key}: strong deployment value required')
    if env.get('SECRET_KEY') == env.get('MFA_ENCRYPTION_KEY'):
        errors.append('MFA_ENCRYPTION_KEY: must differ from signing key')
    origin = urlparse(env.get('FRONTEND_URL', ''))
    if not synthetic and (origin.scheme != 'https' or not origin.hostname or any(word in origin.hostname for word in ['example.', 'localhost', '127.0.0.1'])):
        errors.append('FRONTEND_URL: actual HTTPS deployment domain required')
    if str(env.get('RAG_USE_CHROMA', 'false')).lower() == 'true':
        errors.append('RAG_USE_CHROMA: optional cache image needs separate security acceptance')
    if str(env.get('PUBLIC_REGISTRATION_ENABLED', 'true')).lower() == 'true' and not env.get('SMTP_HOST'):
        errors.append('SMTP_HOST: required before public registration')
    if not synthetic:
        for name in ['OPENAI_API_KEY', 'GEMINI_API_KEY', 'DEEPSEEK_API_KEY']:
            if not env.get(name): errors.append(f'{name}: required by configured generation/review/embedding defaults')
        try:
            pricing = json.loads(env.get('AI_MODEL_PRICING', '{}'))
            valid = isinstance(pricing, dict) and bool(pricing)
            if valid:
                from decimal import Decimal
                for values in pricing.values():
                    for key in ['input', 'output']:
                        value = Decimal(str(values[key]))
                        valid &= value.is_finite() and value >= 0
            if not valid: raise ValueError()
        except (ValueError, TypeError, KeyError, ArithmeticError):
            errors.append('AI_MODEL_PRICING: valid dated official prices for enabled models required')
    return errors


REQUIRED_ACCEPTANCE = ['external_https_oauth_smtp', 'provider_smoke_and_pricing', 'offhost_backup_and_alerts',
                       'teacher_quality_review', 'pilot_owner_and_budget', 'restore_and_rollback']


def acceptance_errors(data, images):
    errors = []
    if data.get('images') != images:
        errors.append('Acceptance must identify the exact deployment images')
    for name in REQUIRED_ACCEPTANCE:
        row = data.get('checks', {}).get(name, {})
        try:
            when = datetime.fromisoformat(row['checked_at'])
            age = (datetime.now(timezone.utc) - when).total_seconds()
            valid = row.get('passed') is True and row.get('operator') and row.get('evidence') and 0 <= age <= 7 * 86400
        except (ValueError, KeyError, TypeError):
            valid = False
        if not valid:
            errors.append(f'{name}: dated operator acceptance with evidence required (within 7 days)')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--manifest')
    parser.add_argument('--security-dir')
    parser.add_argument('--acceptance')
    parser.add_argument('--synthetic', action='store_true', help='Isolated rehearsal only; never production acceptance')
    args = parser.parse_args()
    errors = []
    try:
        environment = Path(args.env_file)
        if not args.synthetic and stat.S_IMODE(environment.stat().st_mode) & 0o077:
            errors.append('Deployment environment must be readable only by its operator (0600)')
        result = subprocess.run(['docker', 'compose', '--env-file', str(environment), '-f', 'docker-compose.production.yml',
                                 'config', '--format', 'json'], capture_output=True, text=True)
        if result.returncode:
            raise ValueError('Invalid Compose configuration')
        config = json.loads(result.stdout)
        if not args.synthetic:
            from os import environ
            names = dict(line.split('=',1) for line in environment.read_text().splitlines() if '=' in line and not line.lstrip().startswith('#'))
            backend_file = Path(environ.get('BACKEND_ENV_FILE') or names.get('BACKEND_ENV_FILE','').strip('\"\''))
            if not backend_file.is_file() or stat.S_IMODE(backend_file.stat().st_mode) & 0o077:
                errors.append('Backend environment must be a restricted operator file (0600)')
        errors += check(config, synthetic=args.synthetic)
        images = {}
        for name in ['backend', 'frontend', 'proxy', 'postgres']:
            image = config['services'][name]['image']
            inspected = subprocess.run(['docker','image','inspect','--format','{{.Id}}',image], capture_output=True,text=True)
            if inspected.returncode:
                errors.append(f'{name}: candidate image unavailable locally')
            else:
                images[name] = inspected.stdout.strip()
        if args.manifest:
            manifest = json.loads(Path(args.manifest).read_text())
            if manifest.get('images') != images:
                errors.append('Deployment images differ from validated manifest')
            if manifest.get('dirty') and not args.synthetic:
                errors.append('Release commit must include reviewed source; manifest still records a dirty checkout')
        elif not args.synthetic:
            errors.append('Validated image manifest required')
        if not args.synthetic:
            if args.acceptance:
                errors += acceptance_errors(json.loads(Path(args.acceptance).read_text()), images)
            else:
                errors.append('External and teacher acceptance evidence required')
            if args.security_dir:
                spec = importlib.util.spec_from_file_location('security_gate', Path(__file__).with_name('security-gate.py'))
                gate = importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
                reviews = json.loads(Path('deploy/security-review.json').read_text())
                for name, image_id in images.items():
                    directory = Path(args.security_dir)
                    scan = json.loads((directory / f'{name}-vulnerabilities.json').read_text())
                    profile = json.loads((directory / f'{name}-profile.json').read_text())
                    created = datetime.fromisoformat(scan['CreatedAt'].replace('Z', '+00:00'))
                    age = (datetime.now(timezone.utc) - created).total_seconds()
                    if not 0 <= age <= 86400 or profile['image_id'] != image_id or not gate.evaluate(scan,reviews,profile)['passed']:
                        errors.append(f'{name}: current matching security scan/profile must pass')
            else:
                errors.append('Current security evidence directory required')
    except (OSError, ValueError, KeyError, TypeError):
        errors.append('Missing or invalid configuration/evidence; inspect locally without publishing values')
    print(json.dumps({'ready': not errors, 'synthetic_only': args.synthetic, 'errors': errors}, indent=2))
    return int(bool(errors))

if __name__ == '__main__':
    raise SystemExit(main())
