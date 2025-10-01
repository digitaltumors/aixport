
import sys
import dreutils
from dreutils.basecmdtool import BaseCommandLineTool
from dreutils.exceptions import DreutilsError
import cellmaps_utils.constants


class PredictTool(BaseCommandLineTool):
    """
    Runs benchmark Train step
    """
    COMMAND = 'predict'

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
                   cmd=PredictTool.COMMAND)

        parser = subparsers.add_parser(PredictTool.COMMAND,
                                       help='Runs prediction on trained DRE models',
                                       description=desc,
                                       formatter_class=cellmaps_utils.constants.ArgParseFormatter)

        return parser
