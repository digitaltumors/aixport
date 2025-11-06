#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
import unittest

from aixport.rocratezipper import ROCrateZipper


class TestROCrateZipper(unittest.TestCase):

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()
        self._crate_dir = os.path.join(self._temp_dir, 'crate')
        os.makedirs(self._crate_dir, exist_ok=True)

        # Create nested structure
        with open(os.path.join(self._crate_dir, 'root.txt'), 'w') as handle:
            handle.write('root-level data')

        nested_dir = os.path.join(self._crate_dir, 'nested')
        os.makedirs(nested_dir, exist_ok=True)
        with open(os.path.join(nested_dir, 'nested.txt'), 'w') as handle:
            handle.write('nested data')

        empty_dir = os.path.join(self._crate_dir, 'emptydir')
        os.makedirs(empty_dir, exist_ok=True)

        self._zip_path = os.path.join(self._temp_dir, 'crate.zip')
        self._zipper = ROCrateZipper(self._crate_dir, self._zip_path)

    def tearDown(self):
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def test_zip_directory_and_list_contents(self):
        self._zipper.zip_directory()
        self.assertTrue(os.path.isfile(self._zip_path))

        contents = sorted(self._zipper.list_contents())
        expected = sorted(['root.txt', 'nested/nested.txt', 'emptydir/'])
        self.assertEqual(expected, contents)

    def test_read_file(self):
        self._zipper.zip_directory()
        data = self._zipper.read_file('nested/nested.txt')
        self.assertEqual(b'nested data', data)

        with self.assertRaises(FileNotFoundError):
            self._zipper.read_file('missing.txt')

    def test_extract_file(self):
        self._zipper.zip_directory()
        destination = os.path.join(self._temp_dir, 'extracted')
        self._zipper.extract_file('root.txt', destination)

        extracted_path = os.path.join(destination, 'root.txt')
        self.assertTrue(os.path.isfile(extracted_path))

        with open(extracted_path, 'r') as handle:
            self.assertEqual('root-level data', handle.read())

        with self.assertRaises(FileNotFoundError):
            self._zipper.extract_file('missing.txt', destination)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
