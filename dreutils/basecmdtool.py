# -*- coding: utf-8 -*-

import os
import argparse
import logging
import time
from cellmaps_utils import logutils
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

    def _create_output_directory(self, outdir):
        """
        Creates output directory if it does not already exist

        :raises DreutilsError: If output directory is None or if directory already exists
        """
        if os.path.isdir(outdir):
            raise DreutilsError(outdir + ' already exists')

        os.makedirs(outdir, mode=0o755)

    def _initialize_logging(self, handlerprefix='dreutils', outdir='.'):
        """

        :param handlerprefix:
        :return:
        """
        if self._skip_logging is False:
            logutils.setup_filelogger(outdir=outdir,
                                      handlerprefix=handlerprefix)

    def _write_task_start_json(self, version='NA',
                               outdir=None,
                               input_data_dict=None,
                               data=None,
                               start_time=time.time()):
        """
        Writes task_start.json file with information about
        what is to be run

        :param version: Version of tool
                        (should be __version__ from __init__.py of tool)
        :type version: str
        :param input_data_dict:
        :type input_data_dict: dict
        :param data:
        :type data: dict
        :return:
        """
        if input_data_dict is not None:
            data.update({'commandlineargs': input_data_dict})

        logutils.write_task_start_json(outdir=outdir,
                                       start_time=start_time,
                                       version=version,
                                       data=data)

    def _write_task_finish_json(self, exitcode, outdir=None,
                                start_time=time.time()):
        """

        :return:
        """
        # write a task finish file
        logutils.write_task_finish_json(outdir=outdir,
                                        start_time=start_time,
                                        end_time=time.time(),
                                        status=exitcode)

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

