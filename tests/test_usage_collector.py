import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('collector',Path(__file__).resolve().parents[1]/'collect-usage.py')
collector=importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)
linux_spec=importlib.util.spec_from_file_location('linux_collector',Path(__file__).resolve().parents[1]/'scripts'/'collect-linux.py')
linux_collector=importlib.util.module_from_spec(linux_spec)
linux_spec.loader.exec_module(linux_collector)

class StorageScanTests(unittest.TestCase):
    def test_linux_self_bind_backing_store_is_not_omitted(self):
        mounts='1 0 8:1 / / rw - ext4 /dev/root rw\n2 1 8:1 /var/lib/docker/aufs /var/lib/docker/aufs rw - ext4 /dev/root rw\n3 1 8:1 /home/user/git /dvol/git rw - ext4 /dev/root rw\n4 1 0:1 / /proc rw - proc proc rw\n'
        skipped=linux_collector.storage_mounts(mounts)
        self.assertNotIn('/var/lib/docker/aufs',skipped)
        self.assertIn('/dvol/git',skipped)
        self.assertIn('/proc',skipped)
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
    def test_deep_node_limit_does_not_hide_later_root_folders(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'first'/'a'/'b').mkdir(parents=True)
            (root/'first'/'a'/'b'/'small.bin').write_bytes(b'a')
            (root/'large').mkdir()
            (root/'large'/'payload.bin').write_bytes(b'b'*100)
            result=collector.scan_tree(root,max_depth=4,seconds=5,max_nodes=1)
            self.assertEqual(result['bytes'],101)
            self.assertEqual(next(c for c in result['children'] if c['name']=='large')['bytes'],100)

if __name__=='__main__':
    unittest.main()
