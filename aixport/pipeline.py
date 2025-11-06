
import sys
import aixport
from aixport.basecmdtool import BaseCommandLineTool
from aixport.exceptions import AIxPORTError
import cellmaps_utils.constants


class BenchmarkPipelineTool(BaseCommandLineTool):
    """
    Runs benchmark Train step
    """
    COMMAND = 'benchmarkpipeline'

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
        """.format(version=aixport.__version__,
                   cmd=BenchmarkPipelineTool.COMMAND)

        parser = subparsers.add_parser(BenchmarkPipelineTool.COMMAND,
                                       help='Runs benchmark pipeline (same as running train => predict => benchmark)',
                                       description=desc,
                                       formatter_class=cellmaps_utils.constants.ArgParseFormatter)

        return parser


class PredictionPipelineTool(BaseCommandLineTool):
    """
    Runs benchmark Train step
    """
    COMMAND = 'predictpipeline'

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
        """.format(version=aixport.__version__,
                   cmd=PredictionPipelineTool.COMMAND)

        parser = subparsers.add_parser(PredictionPipelineTool.COMMAND,
                                       help='Runs prediction pipeline (same as running predict => evaluate)',
                                       description=desc,
                                       formatter_class=cellmaps_utils.constants.ArgParseFormatter)

        return parser
