"""Run inside the candidate with --read-only --cap-drop ALL --security-opt no-new-privileges."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from io import BytesIO
from PIL import Image
from lxml import etree
from app.extractors.document_processor import image_for_ocr
from app.extractors.document_extractors import InvalidDocumentError
from app.core.config import settings
from app.extractors.ocr import TesseractOCRProvider

status=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
models=Path('/usr/share/tesseract-ocr/5/tessdata')
tiff=BytesIO();Image.new('RGB',(2,2)).save(tiff,format='TIFF')
try:
    image_for_ocr(tiff.getvalue());tiff_denied=False
except InvalidDocumentError:
    tiff_denied=True
source=Path('/app/app/extractors/ocr.py').read_text()
xml_guard=Path('/app/app/extractors/document_extractors.py').read_text()
facts={
 'nonroot':os.getuid()==10001,
 'no_capabilities':int(status['CapEff'].strip(),16)==0,
 'no_new_privileges':status['NoNewPrivs'].strip()=='1',
 'readonly_root':any(row.split()[1]=='/' and 'ro' in row.split()[3].split(',') for row in Path('/proc/mounts').read_text().splitlines()),
 'trusted_ocr_models':all((models/f'{name}.traineddata').is_file() and not os.access(models/f'{name}.traineddata',os.W_OK) for name in ['vie','eng']) and "child_env['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr/5/tessdata'" in source,
 'ocr_no_urls':"'stdin', 'stdout'" in source and 'env=child_env' in source and importlib.util.find_spec('pycurl') is None,
 'tiff_rejected':tiff_denied and not Path('/usr/bin/tiffcrop').exists(),
 'xml_guard': 'forbid_dtd=True, forbid_entities=True, forbid_external=True' in xml_guard,
 'random_hash_seed':os.environ.get('PYTHONHASHSEED','random')=='random',
 'no_system_libxml_bindings':importlib.util.find_spec('libxml2') is None,
 'lxml_separate':etree.LIBXML_VERSION >= (2,14,5),
 'no_homed':not Path('/usr/lib/systemd/systemd-homed').exists(),
 'no_perl_tar':not any(Path('/usr/share/perl').glob('*/Archive/Tar.pm')),
 'no_tic':not Path('/usr/bin/tic').exists(),
 'no_chroma':importlib.util.find_spec('chromadb') is None,
 'no_ecdsa':importlib.util.find_spec('ecdsa') is None,
}
print(json.dumps({'facts':facts,'libxml_version':etree.LIBXML_VERSION,
 'source_hashes':{name:hashlib.sha256(Path('/app/app',name).read_bytes()).hexdigest() for name in ['extractors/ocr.py','extractors/document_processor.py','extractors/document_extractors.py']}},indent=2))
