# -*- coding: utf-8 -*-

import os
import argparse
import logging
import time
import dreutils
from cellmaps_utils import logutils
from cellmaps_utils.provenance import ProvenanceUtil
from dreutils.exceptions import DreutilsError

logger = logging.getLogger(__name__)


class BaseCommandLineTool(object):
    """
    Base class for all command line tools.
    Command line tools MUST subclass this
    """

    COMMAND = 'BaseCommandLineTool'

    def __init__(self, theargs,
                 provenance_utils=None):
        """
        Constructor

        :param theargs: Arguments for tool. This tool expects the following
                        values in the dict:
        :type theargs: dict
        :param provenance_utils: Wrapper for `fairscape-cli <https://pypi.org/project/fairscape-cli>`__
                                 which is used for
                                 `RO-Crate <https://www.researchobject.org/ro-crate>`__ creation and population
        :type provenance_utils: :py:class:`~cellmaps_utils.provenance.ProvenanceUtil`
        """
        self._theargs = theargs
        self._theargs['start_time'] = int(time.time())
        if provenance_utils is None:
            self._provenance_utils = ProvenanceUtil()
        self._software_ids = []

    def _initialize_rocrate(self):
        """

        """
        self._create_output_directory()
        self._register_rocrate()
        self._initialize_logging()
        self._write_task_start_json(data=self._theargs)
        self._software_ids.append(self._register_software())

    def _finalize_rocrate(self):
        """

        """
        pass


    def _create_output_directory(self):
        """
        Creates output directory if it does not already exist

        :raises DreutilsError: If output directory is None or if directory already exists
        """

        if os.path.isdir(self._theargs['outdir']):
            raise DreutilsError(self._theargs['outdir'] + ' already exists')
        self._theargs['outdir'] = os.path.abspath(self._theargs['outdir'])
        os.makedirs(self._theargs['outdir'], mode=0o755)

    def _register_software(self, name=None,
                          description=None,
                          author=None, version=None, file_format=None, url=None,
                          date_modified=None,
                          keywords=None,
                          guid=None,
                          timeout=30):
        if name is None:
            name = dreutils.__computation_name__
        if description is None:
            description = dreutils.__description__
        if author is None:
            author = dreutils.__author__
        if version is None:
            version = dreutils.__version__
        if file_format is None:
            file_format = 'py'
        if url is None:
            url = dreutils.__repo_url__
        if keywords is None:
            keywords = [dreutils.__computation_name__, 'software',
                        'Drug Recommender Engine']
        return self._provenance_utils.register_software(self._theargs['outdir'],
                                                        name=name,
                                                        description=description,
                                                        author=author,
                                                        version=version,
                                                        file_format=file_format,
                                                        url=url,
                                                        date_modified=date_modified,
                                                        keywords=keywords,
                                                        guid=guid,
                                                        timeout=timeout)
    def _register_rocrate(self, name=None,
                          organization_name=None,
                          project_name=None,
                          description=None,
                          keywords=None,
                          guid=None,
                          timeout=30):
        if name is None:
            name = 'Drug Recommender Engine ' + self.COMMAND + ' RO-Crate'
        if description is None:
            description = ('Contains output from Drug Recommender Engine ' +
                           self.COMMAND + ' step')
        if organization_name is None:
            organization_name = 'Unset organization'
        if project_name is None:
            project_name = 'Unset project'
        if keywords is None:
            keywords = ['DRE', 'Drug Recommender Engine', self.COMMAND]

        self._provenance_utils.register_rocrate(self._theargs['outdir'],
                                                name=name,
                                                organization_name=organization_name,
                                                project_name=project_name,
                                                description=description,
                                                keywords=keywords,
                                                guid=guid,
                                                timeout=timeout)

    def _initialize_logging(self, handlerprefix='dreutils'):
        """

        :param handlerprefix:
        :return:
        """
        if self._theargs['skip_logging'] is False:
            logutils.setup_filelogger(outdir=self._theargs['outdir'],
                                      handlerprefix=handlerprefix)

    def _write_task_start_json(self, version='NA',
                               input_data_dict=None,
                               data=None):
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

        logutils.write_task_start_json(outdir=self._theargs['outdir'],
                                       start_time=self._theargs['start_time'],
                                       version=version,
                                       data=data)

    def _write_task_finish_json(self, exitcode):
        """

        :return:
        """
        if not 'end_time' in self._theargs:
            self._theargs['end_time'] = int(time.time())
        # write a task finish file
        logutils.write_task_finish_json(outdir=self._theargs['outdir'],
                                        start_time=self._theargs['start_time'],
                                        end_time=self._theargs['end_time'],
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

