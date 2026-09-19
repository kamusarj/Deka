#!/usr/bin/env python3
"""Scan regular files from every saved runtime image layer; never extract links or devices."""
import argparse
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--image', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()
output = Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='audit-184-image-secrets-') as temporary:
    root = Path(temporary);archive = root / 'image.tar';files = root / 'files';files.mkdir()
    subprocess.run(['docker','image','save','-o',str(archive),args.image],check=True)
    count = 0
    with tarfile.open(archive) as saved:
        manifest = json.load(saved.extractfile('manifest.json'))
        layers = sorted({name for item in manifest for name in item['Layers']})
        configs = sorted({item['Config'] for item in manifest})
        for number,name in enumerate(configs):
            (files / f'config-{number}.json').write_bytes(saved.extractfile(name).read())
        for number,name in enumerate(layers):
            stream = saved.extractfile(name)
            with tarfile.open(fileobj=stream,mode='r|*') as layer:
                for member in layer:
                    path = PurePosixPath(member.name)
                    if not member.isfile() or path.is_absolute() or '..' in path.parts:
                        continue
                    target = files / f'layer-{number}' / path
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with layer.extractfile(member) as source, target.open('wb') as destination:
                        import shutil
                        shutil.copyfileobj(source,destination)
                    count += 1
    with (output / 'scanner.log').open('w') as log:
        result = subprocess.run(['docker','run','--rm','--network','none','-v',f'{files}:/scan:ro',
            '-v',f'{output}:/evidence','-v',f'{Path("deploy/gitleaks-image.toml").resolve()}:/config.toml:ro',
            'zricethezav/gitleaks:v8.24.3','dir','/scan','--config','/config.toml','--redact','--no-banner',
            '--max-decode-depth','2','--report-format','json','--report-path','/evidence/findings.json'],stdout=log,stderr=log)
    findings = json.loads((output / 'findings.json').read_text()) if (output / 'findings.json').exists() else None
    identity = subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',args.image],text=True).strip()
    summary = {'image_id':identity,'runtime_layers':len(layers),'regular_files':count,'findings':len(findings) if findings is not None else None,
               'scanner_exit':result.returncode,'scope':'All regular files including deleted files in saved runtime layers and image config; no intermediate build stages'}
    (output / 'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))
    raise SystemExit(result.returncode)
