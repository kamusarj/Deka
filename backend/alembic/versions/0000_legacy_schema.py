"""Adopt the frozen legacy schema before accounting on fresh/unversioned databases."""
from pathlib import Path
import runpy
revision = '0000_legacy_schema'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    runpy.run_path(str(Path(__file__).parents[1] / 'legacy_schema.py'))['upgrade_legacy']()

def downgrade():
    raise RuntimeError('Legacy adoption has no destructive downgrade')
