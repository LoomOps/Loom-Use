"""Keep the current verification matrix tied to actual test modules."""
from pathlib import Path
import re
import unittest


class VerificationMatrixTests(unittest.TestCase):
    def test_current_matrix_maps_every_test_module_without_obsolete_entries(self):
        root=Path(__file__).resolve().parents[1]
        text=(root/'docs/verification.md').read_text()
        matrix=text.split('# Verification blocks\n',1)[1].split('\n\nRun ',1)[0]
        documented=set(re.findall(r'`(test_[a-z_]+\.py)`',matrix))
        actual={p.name for p in (root/'tests').glob('test_*.py')}
        self.assertEqual(documented,actual)
