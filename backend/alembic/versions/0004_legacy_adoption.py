"""Existing accounting deployments adopt versioned legacy application schema."""
from pathlib import Path
import runpy
revision = '0004_legacy_adoption'
down_revision = '0003_subscription_version'
branch_labels = None
depends_on = None

def upgrade():
    runpy.run_path(str(Path(__file__).parents[1] / 'legacy_schema.py'))['upgrade_legacy']()

def downgrade():
    raise RuntimeError('Additive legacy adoption cannot safely be removed')
