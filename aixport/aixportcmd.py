#! /usr/bin/env python

import argparse
import sys
import logging
import logging.config
import traceback
import json
import warnings

import aixport
from cellmaps_utils import logutils
import cellmaps_utils.constants
from aixport.train import TrainTool
from aixport.predict import PredictTool
from aixport.evaluate import EvaluateTool
from aixport.benchmark import BenchmarkTool
from aixport.pipeline import BenchmarkPipelineTool
from aixport.pipeline import PredictionPipelineTool

from aixport.exceptions import AIxPORTError


logger = logging.getLogger(__name__)


def _parse_arguments(desc, args):
    """
    Parses command line arguments

    :param desc: description to display on command line
    :type desc: str
    :param args: command line arguments usually :py:func:`sys.argv[1:]`
    :type args: list
    :return: arguments parsed by :py:mod:`argparse`
    :rtype: :py:class:`argparse.Namespace`
    """
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=cellmaps_utils.constants.ArgParseFormatter)

    subparsers = parser.add_subparsers(dest='command',
                                       help='Command to run. '
                                            'Type <command> -h for '
                                            'more help')
    subparsers.required = True

    TrainTool.add_subparser(subparsers)
    PredictTool.add_subparser(subparsers)
    BenchmarkTool.add_subparser(subparsers)
    EvaluateTool.add_subparser(subparsers)
    BenchmarkPipelineTool.add_subparser(subparsers)
    PredictionPipelineTool.add_subparser(subparsers)

    parser.add_argument('--logconf', default=None,
                        help='Path to python logging configuration file in '
                             'this format: https://docs.python.org/3/library/'
                             'logging.config.html#logging-config-fileformat '
                             'Setting this overrides -v parameter which uses '
                             ' default logger. (default None)')
    parser.add_argument('--verbose', '-v', action='count', default=1,
                        help='Increases verbosity of logger to standard '
                             'error for log messages in this module. Messages are '
                             'output at these python logging levels '
                             '-v = WARNING, -vv = INFO, '
                             '-vvv = DEBUG, -vvvv = NOTSET (default ERROR '
                             'logging)')
    parser.add_argument('--skip_logging', action='store_true',
                        help='If set, output.log, error.log '
                             'files will not be created')
    parser.add_argument('--version', action='version',
                        version=('%(prog)s ' +
                                 aixport.__version__))

    return parser.parse_args(args)


def main(args):
    """
    Main entry point for program

    :param args: arguments passed to command line usually :py:func:`sys.argv[1:]`
    :type args: list

    :return: todo
    :rtype: int
    """

    desc = r"""
Version {version}

Artificial Intelligence Predictive Oncology Research Toolkit (AIxPORT) contains a set of commands that provide
the ability to train models, assess their performance, run predictions,
and evaluate those predictions for a given sample.

    """.format(version=aixport.__version__,
               train=TrainTool.COMMAND,
               predict=PredictTool.COMMAND,
               benchmark=BenchmarkTool.COMMAND,
               evaluate=EvaluateTool.COMMAND,
               benchmarkpipeline=BenchmarkPipelineTool.COMMAND,
               predictionpipeline=PredictionPipelineTool.COMMAND)
    theargs = _parse_arguments(desc, args[1:])
    theargs.program = args[0]
    theargs.version = cellmaps_utils.__version__

    try:
        logutils.setup_cmd_logging(theargs)
        logger.debug('Command is: ' + str(theargs.command))
        if theargs.command == TrainTool.COMMAND:
            cmd = TrainTool(vars(theargs))
        elif theargs.command == PredictTool.COMMAND:
            cmd = PredictTool(vars(theargs))
        elif theargs.command == EvaluateTool.COMMAND:
            cmd = EvaluateTool(vars(theargs))
        elif theargs.command == BenchmarkTool.COMMAND:
            cmd = BenchmarkTool(vars(theargs))
        elif theargs.command == BenchmarkPipelineTool.COMMAND:
            cmd = BenchmarkPipelineTool(vars(theargs))
        elif theargs.command == PredictionPipelineTool.COMMAND:
            cmd = PredictionPipelineTool(vars(theargs))
        else:
            raise AIxPORTError('Invalid command: ' + str(theargs.command))
        return cmd.run()

    except Exception as e:
        logger.exception('Caught exception: ' + str(e))
        sys.stderr.write('\n\nCaught Exception ' + str(e))
        traceback.print_exc()
        return 2
    finally:
        logging.shutdown()


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main(sys.argv))
