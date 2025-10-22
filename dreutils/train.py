
import os
import sys
import re
import dreutils
from dreutils.basecmdtool import BaseCommandLineTool
from dreutils.exceptions import DreutilsError
import dreutils.constants
import cellmaps_utils.constants
from typing import Iterator
import time


class DRETrainRunner(object):
    """
    Defines runner for invoking various Drug Recommender engines in
    Training mode
    """
    def __init__(self, outdir=None, input_rocrates=None, algorithms=None):
        """
        Constructor
        """
        self._outdir = outdir
        self._algorithms = algorithms
        self._input_rocrates = input_rocrates

    def run(self):
        """
        Abstract method to run the pipeline. This method should be implemented by subclasses.

        :raises NotImplementedError: If the subclass does not implement this method.
        """
        raise NotImplementedError('subclasses need to implement')

    def _write_input_ro_crates(self, out=None):
        """

        """
        if self._input_rocrates is None or len(self._input_rocrates) == 0:
            raise DreutilsError('No input RO-Crates')

        for ro_crate in self._input_rocrates:
            out.write(ro_crate + '\n')

class BashTrainRunner(DRETrainRunner):
    """
    Runs DREs via Bash script
    """

    def __init__(self, outdir=None, input_rocrates=None, algorithms=None):
        """
        Constructor
        """
        super().__init__(outdir=outdir, input_rocrates=input_rocrates,
                         algorithms=algorithms)

    def _write_algorithms(self, out=None):
        """

        """
        for algo in self._algorithms:
            out.write(algo + '\n')

    def run(self):
        """

        """
        bashjobfile = os.path.join(self._outdir, 'bash_train_job.sh')
        input_rocratefile = os.path.join(self._outdir, 'input_rocrates.txt')
        algosfile = os.path.join(self._outdir, 'algorithms.txt')
        with open(input_rocratefile, 'w') as f:
            self._write_input_ro_crates(f)

        with open(algosfile, 'w') as f:
            self._write_algorithms(out=f)

        with open(bashjobfile, 'w') as f:
            f.write('#! /bin/bash\n\n')
            f.write('BASEDIR=`dirname $0`\n')
            f.write('pushd $BASEDIR\n')
            f.write('OUTDIR="' + str(dreutils.constants.TRAINED_MODELS_DIRECTORY) + '"\n')
            num_algos = len(self._algorithms)
            num_training_datasets = len(self._input_rocrates)
            f.write('\necho "Training ' + str(num_algos) + ' models on ' +
                    str(num_training_datasets) + ' training datasets"\n' )
            f.write('for ALGO in `cat algorithms.txt` ; do\n')
            f.write('  echo "Training $ALGO"\n')
            f.write('  for TRAIN_ROCRATE in `cat input_rocrates.txt` ; do\n')
            f.write('    TRAIN_ROCRATE_NAME=`basename $TRAIN_ROCRATE`\n')
            f.write('    ALGO_NOSUFFIX=`echo "$ALGO" | sed "s/\\..*//"`\n')
            f.write('    $ALGO "${OUTDIR}/${TRAIN_ROCRATE_NAME}_${ALGO_NOSUFFIX}" --input_crate "$TRAIN_ROCRATE" --mode train\n')
            f.write('    echo "Exit code: $?"\n')
            f.write('  done\n')
            f.write('done\n')
            f.write('popd\n')
        os.chmod(bashjobfile, 0o755)
        return 0


class SLURMTrainRunner(DRETrainRunner):
    """
    Runs DREs via SLURM
    """

    def __init__(self, outdir=None, input_rocrates=None, algorithms=None):
        """
        Constructor
        """
        super().__init__(outdir=outdir, input_rocrates=input_rocrates,
                         algorithms=algorithms)
        self._slurm_partition = None
        self._slurm_account = None

    def _write_slurm_directives(self, out=None, allocated_time='4:00:00',
                                mem='32G', cpus_per_task='4',
                                job_name='Unknown',
                                input_rocratefile=None):
        """
        Writes SLURM job directives to a bash script file.

        :param out: File handle to write the SLURM directives.
        :param allocated_time: String specifying the maximum time allowed for the job.
        :param mem: String specifying the memory allocated for the job.
        :param cpus_per_task: String specifying the number of CPUs per task.
        :param job_name: String specifying the name of the SLURM job.
        """
        out.write('#!/bin/bash\n\n')
        out.write('#SBATCH --job-name=' + str(job_name) + '\n')
        out.write('#SBATCH --chdir=' + self._outdir + '\n')

        out.write('#SBATCH --output=%x.%j.out\n')
        if self._slurm_partition is not None:
            out.write('#SBATCH --partition=' + self._slurm_partition + '\n')
        if self._slurm_account is not None:
            out.write('#SBATCH --account=' + self._slurm_account + '\n')
        out.write('#SBATCH --ntasks=1\n')
        out.write('#SBATCH --cpus-per-task=' + str(cpus_per_task) + '\n')
        out.write('#SBATCH --mem=' + str(mem) + '\n')
        out.write('#SBATCH --time=' + str(allocated_time) + '\n\n')
        out.write('#SBATCH --array=1-' + str(len(self._input_rocrates) + 1) + '\n')
        out.write('echo "Job.Array: ${SLURM_JOB_ID}.${SLURM_ARRAY_TASK_ID}"\n')
        out.write('echo $HOSTNAME\n\n')

        out.write('INPUT_ROCRATE=`head -n $SLURM_ARRAY_TASK_ID ' + input_rocratefile + ' | tail -n 1`\n')
        out.write('OUTPUT_ROCRATENAME=`basename $INPUT_ROCRATE`\n')

    def _generate_algorithm_command(self, algorithm=None,
                                    input_rocratefile=None):
        """

        """
        job_script = os.path.join(self._outdir, algorithm + '.sh')
        with open(job_script, 'w') as f:
            self._write_slurm_directives(out=f,
                                         job_name=algorithm + '_train',
                                         input_rocratefile=input_rocratefile)

            f.write(algorithm + ' "' + dreutils.constants.TRAINED_MODELS_DIRECTORY + '/${OUTPUT_ROCRATENAME}_' + algorithm + '" --input_rocrate "$INPUT_ROCRATE" --mode train\n')
            f.write('exit $?\n')
        os.chmod(job_script, 0o755)
        return os.path.basename(job_script)

    def _generate_final_command(self):
        """

        """
        return ''

    def run(self):
        """

        """
        slurmjobfile = os.path.join(self._outdir, 'slurm_train_job.sh')
        job_names = []
        input_rocratefile = os.path.join(self._outdir, 'input_rocrates.txt')
        with open(input_rocratefile, 'w') as f:
            self._write_input_ro_crates(f)

        with open(slurmjobfile, 'w') as f:
            f.write('#! /bin/bash\n\n')
            for algo_index, algo in enumerate(self._algorithms):
                f.write('# ' + str(algo) + ' no dependencies\n')
                job_name_var = 'job' + str(algo_index)
                f.write(job_name_var +'=$(sbatch ' +
                        self._generate_algorithm_command(algorithm=algo,
                                                         input_rocratefile=input_rocratefile) + ' | awk \'{print $4}\')\n\n')

                job_names.append(job_name_var)
            dependency_str = ':'.join(job_names)
            # f.write('# final clean up job\n')
            # f.write(
            #     'final_job=$(sbatch --dependency=afterok:' + dependency_str + ' ' + self._generate_final_command() + ' | awk \'{print $4}\')\n\n')
            # f.write('echo "job submitted; here is ID of final job: $final_job"\n')
        os.chmod(slurmjobfile, 0o755)
        return 0


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

    def _get_training_rocrates(self, input_file):
        """

        """
        with open(input_file, 'r') as f:
            for line in f:
                yield os.path.abspath(line.strip())

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
            runner = None
            os.makedirs(os.path.join(self._theargs['outdir'],
                                     dreutils.constants.TRAINED_MODELS_DIRECTORY),
                        mode=0o755)

            train_rocrates = []

            if os.path.isfile(self._theargs['input']):
                train_rocrates = list(self._get_training_rocrates(self._theargs['input']))
            elif os.path.isdir(self._theargs['input']):
                raise DreutilsError('directory path not supported yet')

            if self._theargs['run_mode'].lower() == 'slurm':
                runner = SLURMTrainRunner(outdir=self._theargs['outdir'],
                                     algorithms=re.split(r'\s*,\s*',
                                                         self._theargs['algorithms']),
                                     input_rocrates=train_rocrates)
            elif self._theargs['run_mode'].lower() == 'bash':
                runner = BashTrainRunner(outdir=self._theargs['outdir'],
                                     algorithms=re.split(r'\s*,\s*',
                                                         self._theargs['algorithms']),
                                     input_rocrates=train_rocrates)
            else:
                raise DreutilsError('Invalid run mode: ' + str(self._theargs['run_mode']))

            exitcode = runner.run()

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
                                 'RO-Crates OR file containing '
                                 'list of directory paths')
        parser.add_argument('--inputregex',
                            help='If set, only allow directories set in --input flag that match '
                                 'the regex set here')
        parser.add_argument('--algorithms', default='elasticnet_drecmd.py',
                            help='Comma delimited list of algorithms to use')
        parser.add_argument('--run_mode', choices=['slurm', 'bash'], default='bash',
                            help='Denotes how to run. If slurm, code generates a slurm script, '
                                 'if serial, code runs algorithms one at a time')
        return parser
