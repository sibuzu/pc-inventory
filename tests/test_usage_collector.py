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
    def test_large_directories_expand_past_old_depth_and_show_large_files(self):
        for module in (collector,linux_collector):
            with self.subTest(module=module.__name__),tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                deep=root.joinpath(*['level'+str(i) for i in range(12)])
                deep.mkdir(parents=True)
                (deep/'large.bin').write_bytes(b'a'*150)
                (deep/'small.bin').write_bytes(b'b'*10)
                (root/'small'/'nested').mkdir(parents=True)
                (root/'small'/'nested'/'tiny.bin').write_bytes(b'c'*20)
                result=module.scan_expanded_tree(str(root),100,5)
                self.assertEqual(result['bytes'],180)
                self.assertEqual(result['files'],3)
                self.assertFalse(result['partial'])
                node=result
                for i in range(12):
                    self.assertEqual(sum(c['bytes'] for c in node['children']),node['bytes'])
                    node=next(c for c in node['children'] if c['name']=='level'+str(i))
                leaf=next(c for c in node['children'] if c['name']=='large.bin')
                self.assertEqual(leaf['kind'],'file')
                self.assertEqual(leaf['bytes'],150)
                small=next(c for c in result['children'] if c['name']=='small')
                self.assertEqual(small['children'][0]['name'],'nested')
                self.assertEqual(small['children'][0]['children'],[])
                self.assertTrue(small['children'][0]['truncated'])

    def test_optional_budget_prioritizes_larger_small_folders(self):
        for module in (collector,linux_collector):
            with self.subTest(module=module.__name__),tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                for name,size in [('small',10),('larger',90),('mandatory',150)]:
                    (root/name).mkdir()
                    (root/name/'file.bin').write_bytes(b'a'*size)
                result=module.scan_expanded_tree(str(root),100,5,max_optional_nodes=1)
                nodes={child['name']:child for child in result['children']}
                self.assertEqual(nodes['small']['children'],[])
                self.assertEqual(nodes['larger']['children'][0]['name'],'file.bin')
                self.assertEqual(nodes['mandatory']['children'][0]['name'],'file.bin')
                self.assertEqual(result['bytes'],250)

    def test_small_siblings_cannot_consume_large_branch_budget(self):
        for module in (collector,linux_collector):
            with self.subTest(module=module.__name__),tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                for i in range(12):
                    (root/('small'+str(i))).mkdir()
                    (root/('small'+str(i))/'file').write_bytes(b'a')
                (root/'large').mkdir()
                (root/'large'/'boundary.bin').write_bytes(b'b'*100)
                result=module.scan_expanded_tree(str(root),100,5,max_children=3)
                self.assertEqual(result['bytes'],112)
                self.assertEqual(sum(c['bytes'] for c in result['children']),112)
                large=next(c for c in result['children'] if c['name']=='large')
                self.assertEqual(large['children'][0]['name'],'boundary.bin')
                self.assertEqual(large['children'][0]['kind'],'file')
                self.assertEqual(len(result['children']),3)

    def test_expansion_skips_mount_aliases_and_honors_deadline(self):
        for module in (collector,linux_collector):
            with self.subTest(module=module.__name__),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);(root/'alias').mkdir()
                (root/'alias'/'file').write_bytes(b'a'*200)
                result=module.scan_expanded_tree(str(root),100,5,skip_mounts={str(root/'alias')})
                self.assertEqual(result['bytes'],0)
                self.assertEqual(result['skipped'],1)
                result=module.scan_expanded_tree(str(root),100,0)
                self.assertTrue(result['partial'])

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
