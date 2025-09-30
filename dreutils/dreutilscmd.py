#! /usr/bin/env python

import argparse
import sys
import logging
import logging.config
import traceback
import json
import warnings

import dreutils
from cellmaps_utils import logutils
import cellmaps_utils.constants
from dreutils.basecmdtool import HelloWorldCommand
from dreutils.benchmarktool import BenchmarkTool
from dreutils.exceptions import DreutilsError


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

    HelloWorldCommand.add_subparser(subparsers)
    BenchmarkTool.add_subparser(subparsers)



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
    parser.add_argument('--version', action='version',
                        version=('%(prog)s ' +
                                 dreutils.__version__))

    return parser.parse_args(args)


def main(args):
    """
    Main entry point for program

    :param args: arguments passed to command line usually :py:func:`sys.argv[1:]`
    :type args: list

    :return: todo
    :rtype: int
    """

    desc = """
Version {version}




    """.format(version=dreutils.__version__)
    theargs = _parse_arguments(desc, args[1:])
    theargs.program = args[0]
    theargs.version = cellmaps_utils.__version__

    try:
        logutils.setup_cmd_logging(theargs)
        logger.debug('Command is: ' + str(theargs.command))
        if theargs.command == HelloWorldCommand.COMMAND:
            cmd = HelloWorldCommand(theargs)
        elif theargs.command == BenchmarkTool.COMMAND:
            cmd = BenchmarkTool(theargs)
        else:
            raise DreutilsError('Invalid command: ' + str(theargs.command))
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
