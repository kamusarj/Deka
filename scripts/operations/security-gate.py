#!/usr/bin/env python3
"""Fail closed on unreviewed High/Critical findings; retain the original scanner report."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path


def evaluate(scan, reviews, profile, *, today=None):
    today = today or date.today()
    errors, assessed, total = [], [], 0
    if scan.get('Metadata', {}).get('ImageID') != profile.get('image_id'):
        errors.append('Scanner and runtime profile image identities differ')
    if not scan.get('Results'):
        errors.append('Scanner results missing')
    entries = reviews.get('reviews', [])
    for target in scan.get('Results', []):
        for item in target.get('Vulnerabilities') or []:
            if item['Severity'] not in {'HIGH', 'CRITICAL'}:
                continue
            total += 1
            identity = f"{item['VulnerabilityID']}:{item['PkgName']}:{item['InstalledVersion']}"
            matches = [row for row in entries if row['cve'] == item['VulnerabilityID']
                       and row['packages'].get(item['PkgName']) == item['InstalledVersion']]
            valid = [row for row in matches if row['status'] == 'not_affected_in_release_profile'
                     and date.fromisoformat(row['reviewed_on']) <= today <= date.fromisoformat(row['expires'])
                     and row.get('rationale') and row.get('source') and row.get('requires')
                     and all(profile.get('facts', {}).get(key) is True for key in row['requires'])]
            if valid:
                assessed.append(identity)
            else:
                errors.append(identity + ': unresolved or profile/expiry mismatch')
    return {'passed': not errors, 'high_critical_entries': total,
            'conditionally_not_affected': len(assessed), 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scan', required=True)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--reviews', default='deploy/security-review.json')
    args = parser.parse_args()
    try:
        paths = [Path(args.scan), Path(args.profile), Path(args.reviews)]
        result = evaluate(*(json.loads(path.read_text()) for path in [paths[0], paths[2], paths[1]]))
        result['evidence_sha256'] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    except (ValueError, KeyError, TypeError, OSError):
        result = {'passed': False, 'errors': ['Invalid or missing security evidence']}
    print(json.dumps(result, indent=2))
    return int(not result['passed'])

if __name__ == '__main__':
    raise SystemExit(main())
