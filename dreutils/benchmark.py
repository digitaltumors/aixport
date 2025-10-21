
import sys
import dreutils
from dreutils.basecmdtool import BaseCommandLineTool
from dreutils.exceptions import DreutilsError
import cellmaps_utils.constants


class BenchmarkTool(BaseCommandLineTool):
    """
    Runs benchmark pipeline
    """
    COMMAND = 'benchmark'

    def __init__(self, theargs):
        """

        :param theargs:
        """
        super().__init__(theargs)

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

            # TODO: add code to evaluate/benchmark
            #       predictions found in self._theargs['input']
            #       RO-Crate aka folder

            # The line below registers the computation
            # performed by this tool into the RO-Crate
            # metadata
            self._finalize_rocrate()
            return exitcode
        finally:
            # write a task finish file
            self._write_task_finish_json(exitcode)
        return 0

    def add_subparser(subparsers):
        """

        :return:
        """
        desc = """

        Version {version}

        {cmd} prints Hello world and exits
        """.format(version=dreutils.__version__,
                   cmd=BenchmarkTool.COMMAND)

        parser = subparsers.add_parser(BenchmarkTool.COMMAND,
                                       help='Benchmarks predictions on trained DRE models',
                                       description=desc,
                                       formatter_class=cellmaps_utils.constants.ArgParseFormatter)
        parser.add_argument('outdir',
                            help='Output directory. This directory should not already exist')
        parser.add_argument('--input',
                            help='Directory path to predict output RO-Crate')
        return parser
