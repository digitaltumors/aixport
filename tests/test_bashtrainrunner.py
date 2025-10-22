#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Integration Tests for `dreutils` package."""

import os
import shutil
import tempfile
import unittest
from dreutils.train import BashTrainRunner
from dreutils.exceptions import DreutilsError


class TestBashRunner(unittest.TestCase):
    """Tests for `dreutils` package."""

    def setUp(self):
        """Set up test fixtures, if any."""

    def tearDown(self):
        """Tear down test fixtures, if any."""

    def test_constructor(self):
        """Tests parse arguments"""

        runner = BashTrainRunner()
        self.assertEqual(None, runner._outdir)
        self.assertEqual(None, runner._algorithms)

        runner = BashTrainRunner(outdir='hi', algorithms=[])
        self.assertEqual('hi', runner._outdir)
        self.assertEqual([], runner._algorithms)

    def test_run_no_inputrocrates(self):
        temp_dir = tempfile.mkdtemp()
        try:
            runner = BashTrainRunner(outdir=temp_dir,

                                 algorithms=['elastic_drecmd.py'])
            res = runner.run()
            self.fail('Expected exception')
        except DreutilsError as de:
            self.assertEqual('No input RO-Crates', str(de))
        finally:
            shutil.rmtree(temp_dir)

    def test_run(self):
        temp_dir = tempfile.mkdtemp()
        try:
            runner = BashTrainRunner(outdir=temp_dir,
                                 input_rocrates=['crate1'],
                                 algorithms=['elastic_drecmd.py'])
            res = runner.run()
            self.assertEqual(0, res)
        finally:
            shutil.rmtree(temp_dir)
