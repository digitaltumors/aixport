# -*- coding: utf-8 -*-
import json
import os
import sys
import argparse
import logging
from dreutils.exceptions import DreutilsError

logger = logging.getLogger(__name__)


class BaseCommandLineTool(object):
    """
    Base class for all command line tools.
    Command line tools MUST subclass this
    """

    COMMAND = 'BaseCommandLineTool'

    def __init__(self):
        """
        Constructor
        """
        pass

    def run(self):
        """
        Should contain logic that will be run by command line tool.
        This must be implemented by subclasses and will always raise
        an error

        :raises DreutilsError: will always raise this
        :return:
        """
        raise DreutilsError('Must be implemented by subclass')

    @staticmethod
    def add_subparser(subparsers):
        """
        Should add any argparse commandline arguments to **subparsers** passed in
        This must be implemented by subclasses and will always raise
        an error

        :param subparsers:
        :type subparsers: argparse
        :raises DreutilsError: will always raise this
        :return:
        """
        raise DreutilsError('Must be implemented by subclass')

