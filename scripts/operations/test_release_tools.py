"""Negative release gates use synthetic evidence; no Docker mutation or secrets."""
import importlib.util
from pathlib import Path
import unittest
from datetime import date


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class SecurityGateTests(unittest.TestCase):
    def setUp(self):
        self.gate = module('security-gate')
        self.scan = {'Metadata': {'ImageID': 'sha256:fixture'}, 'Results': [{'Vulnerabilities': [
            {'Severity': 'CRITICAL', 'VulnerabilityID': 'CVE-test', 'PkgName': 'test', 'InstalledVersion': '1'}]}]}
        self.profile = {'image_id': 'sha256:fixture', 'facts': {'nonroot': True}}
        self.reviews = {'reviews': [{'cve': 'CVE-test', 'packages': {'test': '1'},
            'status': 'not_affected_in_release_profile', 'reviewed_on': '2026-09-01', 'expires': '2026-09-30',
            'rationale': 'Synthetic condition', 'source': 'https://example.com', 'requires': ['nonroot']}]}

    def check(self):
        return self.gate.evaluate(self.scan, self.reviews, self.profile, today=date(2026, 9, 14))['passed']

    def test_known_version_requires_all_runtime_conditions(self):
        self.assertTrue(self.check())
        self.profile['facts']['nonroot'] = False
        self.assertFalse(self.check())

    def test_new_cve_and_package_version_are_not_waived(self):
        self.scan['Results'][0]['Vulnerabilities'][0]['InstalledVersion'] = '2'
        self.assertFalse(self.check())

    def test_expiry_missing_scan_and_wrong_image_fail(self):
        self.reviews['reviews'][0]['expires'] = '2026-09-13'
        self.assertFalse(self.check())
        self.scan['Results'] = []
        self.assertFalse(self.check())
        self.profile['image_id'] = 'sha256:other'
        self.assertFalse(self.check())

if __name__ == '__main__':
    unittest.main()

class PreflightTests(unittest.TestCase):
    def test_missing_external_acceptance_cannot_pass(self):
        preflight = module('preflight')
        self.assertGreaterEqual(len(preflight.acceptance_errors({}, {'backend': 'fixture'})), 7)

    def test_unsafe_profile_and_malformed_pricing_fail_without_echoing_values(self):
        preflight = module('preflight')
        config = {'services': {'backend': {'environment': {'AI_MODEL_PRICING': 'private-invalid-json'},
                  'command': ['uvicorn', '--workers', '2'], 'ports': [{'target': 8000}]}}}
        errors = preflight.check(config)
        self.assertTrue(any('one worker' in error for error in errors))
        self.assertTrue(any('AI_MODEL_PRICING' in error for error in errors))
        self.assertNotIn('private-invalid-json', str(errors))
