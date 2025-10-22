
import os
import sys
import dreutils
from dreutils.basecmdtool import BaseCommandLineTool
from dreutils.exceptions import DreutilsError
import cellmaps_utils.constants
import dreutils.constants


class BenchmarkTool(BaseCommandLineTool):
    """
    Runs benchmark pipeline
    """
    COMMAND = 'benchmark'

    def __init__(self, theargs):
        """

        :param theargs: command line arguments as a dict
                        should have the following values:
                        {'outdir': <OUTPUT RO-CRATE PATH>,
                         'predictions_rocrate': <PREDICTIONS RO-CRATE PATH>,
                         '
        :type theargs: dict
        """
        super().__init__()

    def _get_test_rocrates_map(self):
        """

        """
        results = {}
        with open(self._theargs['input_test_rocrates'], 'r') as f:
            for line in f:
                fp = os.path.abspath(line.strip())
                results[os.path.basename(fp)] = fp
        return results

    def _get_predictions_rocrates(self):
        """
        Gets predictions rocrates from prediction_rocrate,
        boy that is confusing.
        :return: map of predict rocrate name to path
        :rtype: dict
        """
        if not os.path.isdir(self._theargs['predictions_rocrate']):
            raise DreutilsError('predictions_rocrate is NOT a directory')

        results = {}
        predict_rocrate_path = os.path.abspath(os.path.join(self._theargs['predictions_rocrate'],
                                                            dreutils.constants.PREDICTIONS_DIRECTORY))
        for entry in os.listdir(predict_rocrate_path):
            fp = os.path.join(predict_rocrate_path, entry)
            if not os.path.isdir(fp):
                continue
            results[entry] = fp
        return results

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

            predict_rocrates_map = self._get_predictions_rocrates()
            print(predict_rocrates_map)

            test_rocrates_map = self._get_test_rocrates_map()
            print(test_rocrates_map)

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
        parser.add_argument('--input_test_rocrates',
                            help='File listing directories of test RO-Crates, one per line')
        parser.add_argument('--predictions_rocrate',
                            help='RO-Crate where prediction was run')
        return parser
