#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Integration Tests for `dreutils` package."""

import os
import shutil
import tempfile
import unittest
from dreutils.benchmark import BenchmarkTool
from dreutils.exceptions import DreutilsError


class TestBenchmarkTool(unittest.TestCase):
    """Tests for `dreutils` package."""

    def setUp(self):
        """Set up test fixtures, if any."""

    def tearDown(self):
        """Tear down test fixtures, if any."""

    def test_run(self):
        """Tests parse arguments"""
        temp_dir = tempfile.mkdtemp()
        try:
            output_dir = os.path.join(temp_dir, 'res')
            tool = BenchmarkTool({'outdir': output_dir,
                                  'skip_logging': False})
            self.assertEqual(99, tool.run())
        finally:
            shutil.rmtree(temp_dir)

