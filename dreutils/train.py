
import sys
import dreutils
from dreutils.basecmdtool import BaseCommandLineTool
from dreutils.exceptions import DreutilsError
import cellmaps_utils.constants
import time


class TrainTool(BaseCommandLineTool):
    """
    Runs benchmark pipeline
    """
    COMMAND = 'train'

    def __init__(self, theargs, provenance_utils=None):
        """

        :param theargs: arguments
        :type theargs: dict
        """
        super().__init__(theargs,
                         provenance_utils=provenance_utils)

    def run(self):
        """

        :return:
        """
        exitcode = 99
        try:
            # The line below creates output RO-Crate
            # The path to this output RO-Crate can be
            # found in self._theargs['outdir']
            self._initialize_rocrate()

            # put code here


            # The line below registers the computation
            # performed by this tool into the RO-Crate
            # metadata
            self._finalize_rocrate()
            return exitcode
        finally:
            # write a task finish file
            self._write_task_finish_json(exitcode)

    def add_subparser(subparsers):
        """

        :return:
        """
        desc = """

        Version {version}

        {cmd} Trains DRE Models
        """.format(version=dreutils.__version__,
                   cmd=TrainTool.COMMAND)

        parser = subparsers.add_parser(TrainTool.COMMAND,
                                       help='Trains DRE models',
                                       description=desc,
                                       formatter_class=cellmaps_utils.constants.ArgParseFormatter)

        parser.add_argument('outdir',
                            help='Output directory. This directory should not already exist')
        parser.add_argument('--input',
                            help='Directory path to a single training data '
                                 'RO-Crate or a directory containing '
                                 'subdirectories that are training '
                                 'RO-Crates')
        return parser
