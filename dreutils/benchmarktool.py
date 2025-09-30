
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
        super().__init__()

    def run(self):
        """

        :return:
        """
        sys.stdout.write('Hello world\n')
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
                                       help='Runs benchmark',
                                       description=desc,
                                       formatter_class=cellmaps_utils.constants.ArgParseFormatter)

        return parser
