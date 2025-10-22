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

    def test_run_invalid_predict_rocrate(self):
        """Tests parse arguments"""
        temp_dir = tempfile.mkdtemp()
        try:
            output_dir = os.path.join(temp_dir, 'res')
            tool = BenchmarkTool({'outdir': output_dir,
                                  'skip_logging': False,
                                  'predictions_rocrate': temp_dir,
                                  'input_test_rocrates': temp_dir})
            tool.run()
            self.fail('Expected Exception')
        except DreutilsError as de:
            self.assertEqual('predictions_rocrate is NOT a directory', str(de))
        finally:
            shutil.rmtree(temp_dir)

