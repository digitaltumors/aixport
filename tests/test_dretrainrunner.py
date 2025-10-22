#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Integration Tests for `dreutils` package."""

import os

import unittest
from dreutils.train import DRETrainRunner


class TestDRERunner(unittest.TestCase):
    """Tests for `dreutils` package."""

    def setUp(self):
        """Set up test fixtures, if any."""

    def tearDown(self):
        """Tear down test fixtures, if any."""

    def test_constructor(self):
        """Tests parse arguments"""

        runner = DRETrainRunner()
        self.assertEqual(None, runner._outdir)
        self.assertEqual(None, runner._algorithms)

        runner = DRETrainRunner(outdir='hi', algorithms=[])
        self.assertEqual('hi', runner._outdir)
        self.assertEqual([], runner._algorithms)

    def test_run(self):
        try:
            runner = DRETrainRunner()
            runner.run()
            self.fail('Expected Exception')
        except NotImplementedError as ne:
            self.assertEqual('subclasses need to implement', str(ne))
