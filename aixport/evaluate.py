
import sys
import aixport
from aixport.basecmdtool import BaseCommandLineTool
from aixport.exceptions import AIxPORTError
import cellmaps_utils.constants


class EvaluateTool(BaseCommandLineTool):
    """
    Runs benchmark pipeline
    """
    COMMAND = 'evaluate'

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
                   cmd=EvaluateTool.COMMAND)

        parser = subparsers.add_parser(EvaluateTool.COMMAND,
                                       help='Evaluates predictions on trained models (run on single patient/cell line)',
                                       description=desc,
                                       formatter_class=cellmaps_utils.constants.ArgParseFormatter)

        return parser
