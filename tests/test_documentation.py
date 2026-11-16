"""Review client instruction packaging and detect omissions or broken routing."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('client_docs',ROOT/'docs/documentation.py');docs=importlib.util.module_from_spec(spec);spec.loader.exec_module(docs)
class DocumentationTests(unittest.TestCase):
 def test_source_inventory_navigation_and_skill_metadata(self):self.assertEqual(docs.check(),[])
 def test_missing_document_link_and_invalid_skill_are_reported(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'docs').mkdir();(root/'README.md').write_text('[missing](guide.md)\n');skill=root/'skills/example/SKILL.md';skill.parent.mkdir(parents=True);skill.write_text('---\nname: wrong\ndescription: example\n---\n')
   (root/'docs/documentation-catalog.json').write_text(json.dumps(docs.inventory(root)))
   errors=docs.check(root);self.assertTrue(any('missing link' in e for e in errors));self.assertTrue(any('invalid Skill name' in e for e in errors))
   (root/'new.md').write_text('# New\n');self.assertIn('Documentation inventory is missing/stale',docs.check(root))
