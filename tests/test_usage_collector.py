import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('collector',Path(__file__).resolve().parents[1]/'collect-usage.py')
collector=importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)

class StorageScanTests(unittest.TestCase):
    def test_tree_totals_and_depth_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'one.bin').write_bytes(b'a'*10)
            (root/'a'/'b').mkdir(parents=True)
            (root/'a'/'two.bin').write_bytes(b'b'*20)
            (root/'a'/'b'/'three.bin').write_bytes(b'c'*30)
            result=collector.scan_tree(root,max_depth=1,seconds=5)
            self.assertEqual(result['bytes'],60)
            self.assertEqual(result['files'],3)
            self.assertEqual(result['directories'],2)
            self.assertEqual(sum(c['bytes'] for c in result['children']),60)
            child=next(c for c in result['children'] if c['name']=='a')
            self.assertTrue(child['truncated'])
            self.assertEqual(child['bytes'],50)
    def test_deadline_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'file.bin').write_bytes(b'a')
            result=collector.scan_tree(directory,seconds=0)
            self.assertTrue(result['partial'])
            self.assertEqual(result['bytes'],0)

if __name__=='__main__':
    unittest.main()
