#!/usr/bin/env python3
"""verify_install.py: structure checks, build lookup and the patched-vs-baseline diff.

Builds synthetic trees (a PE header with a known timestamp, two tables, a couple of ROM files),
so it needs no retail data and no venv packages.
"""
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_tool():
    spec = importlib.util.spec_from_file_location('verify_install', ROOT / 'tools' / 'verify_install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_pe(timestamp):
    """A file whose first bytes are a PE header carrying timestamp."""
    data = bytearray(b'MZ' + b'\0' * (0x40 - 2))
    struct.pack_into('<I', data, 0x3c, 0x40)
    data += b'PE\0\0'
    data += struct.pack('<HHI', 0x14c, 1, timestamp)
    data += b'\0' * 0x100
    return bytes(data)


def make_tree(root, timestamp=1545369600, roms=None):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / 'VTABLE.DAT').write_bytes(b'V' * 32)
    (root / 'FTABLE.DAT').write_bytes(b'F' * 32)
    (root / 'FFXiMain.dll').write_bytes(fake_pe(timestamp))
    (root / 'FFXi.dll').write_bytes(fake_pe(timestamp).replace(b'PE', b'PE'))
    roms = roms if roms is not None else {'ROM/0/1.DAT': b'one!', 'ROM/0/2.DAT': b'two!'}
    for rel, payload in roms.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return root


class VerifyInstallTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = load_tool()

    def test_unknown_build_is_exit_3(self):
        with tempfile.TemporaryDirectory() as d:
            game = make_tree(Path(d) / 'game')
            report, code = self.tool.verify(str(game))
        self.assertEqual(code, 3)
        self.assertEqual(report['problems'], [])
        self.assertIsNone(report['known_build'])
        self.assertEqual(report['dat_count'], 2)
        self.assertEqual(report['programs']['FFXiMain.dll']['pe_date'], '2018-12-21')

    def test_missing_table_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            game = make_tree(Path(d) / 'game')
            (game / 'VTABLE.DAT').unlink()
            report, code = self.tool.verify(str(game))
        self.assertEqual(code, 2)
        self.assertIn('missing VTABLE.DAT', report['problems'])

    def test_no_rom_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            game = make_tree(Path(d) / 'game', roms={})
            report, code = self.tool.verify(str(game))
        self.assertEqual(code, 2)
        self.assertTrue(any('no ROM' in p for p in report['problems']))

    def test_short_dat_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            game = make_tree(Path(d) / 'game', roms={'ROM/0/1.DAT': b'ab'})
            report, code = self.tool.verify(str(game))
        self.assertEqual(code, 2)
        self.assertTrue(any('smaller than 4 bytes' in p for p in report['problems']))

    def test_baseline_diff_counts(self):
        with tempfile.TemporaryDirectory() as d:
            base = make_tree(Path(d) / 'base', roms={'ROM/0/1.DAT': b'old!', 'ROM/0/2.DAT': b'same'})
            new = make_tree(Path(d) / 'new', roms={'ROM/0/1.DAT': b'new!', 'ROM/0/2.DAT': b'same',
                                                  'ROM/0/3.DAT': b'added'})
            report, code = self.tool.verify(str(new), baseline=str(base))
        self.assertEqual(code, 3)
        diff = report['diff']
        self.assertEqual((diff['added'], diff['removed'], diff['changed']), (1, 0, 1))
        self.assertEqual(diff['added_examples'], [os.path.join('ROM', '0', '3.DAT')])

    def test_human_output_names_the_next_command(self):
        with tempfile.TemporaryDirectory() as d:
            game = make_tree(Path(d) / 'game')
            report, _ = self.tool.verify(str(game))
            text = self.tool.human(report)
        self.assertIn('not in meta/builds.json', text)
        self.assertIn('tools/newbuild.py identify', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
