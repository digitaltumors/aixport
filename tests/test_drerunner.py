#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Integration Tests for `dreutils` package."""

import os

import unittest
from dreutils.train import DRERunner


class TestDRERunner(unittest.TestCase):
    """Tests for `dreutils` package."""

    def setUp(self):
        """Set up test fixtures, if any."""

    def tearDown(self):
        """Tear down test fixtures, if any."""

    def test_constructor(self):
        """Tests parse arguments"""

        runner = DRERunner()
        self.assertEqual(None, runner._outdir)
        self.assertEqual(None, runner._algorithms)

        runner = DRERunner(outdir='hi', algorithms=[])
        self.assertEqual('hi', runner._outdir)
        self.assertEqual([], runner._algorithms)

    def test_run(self):
        try:
            runner = DRERunner()
            runner.run()
            self.fail('Expected Exception')
        except NotImplementedError as ne:
            self.assertEqual('subclasses need to implement', str(ne))
