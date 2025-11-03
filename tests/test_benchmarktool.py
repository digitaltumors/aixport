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

    def test_evaluate_predictions(self):
        """
        Test if len(results_df) is equal to number of lines in input_test_rocrates. Using /cellar/users/abishai/digitaltumors/predictout as prediction_rocrate and /cellar/users/abishai/test_v1_43_drugs.txt as input_test_rocrates    
        """
        temp_dir = tempfile.mkdtemp()
        try:
            output_dir = os.path.join(temp_dir, 'res')
            tool = BenchmarkTool({'outdir': output_dir,
                                  'skip_logging': False,
                                  'predictions_rocrate': '/cellar/users/abishai/digitaltumors/predictout',
                                  'input_test_rocrates': '/cellar/users/abishai/test_v1_43_drugs.txt'})
            tool.run()
            self.assertEqual(len(tool._evaluate_predictions(tool._get_predictions_rocrates(), tool._get_test_rocrates_map())), 43)
            self.assertTrue(os.path.exists(os.path.join(output_dir, 'results.png')))
        finally:
            shutil.rmtree(temp_dir)