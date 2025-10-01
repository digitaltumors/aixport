
import sys
import dreutils
from dreutils.basecmdtool import BaseCommandLineTool
from dreutils.exceptions import DreutilsError
import cellmaps_utils.constants


class TrainTool(BaseCommandLineTool):
    """
    Runs benchmark pipeline
    """
    COMMAND = 'train'

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
                   cmd=TrainTool.COMMAND)

        parser = subparsers.add_parser(TrainTool.COMMAND,
                                       help='Trains DRE models',
                                       description=desc,
                                       formatter_class=cellmaps_utils.constants.ArgParseFormatter)

        return parser
