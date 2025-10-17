
import os
import sys
import dreutils
from dreutils.basecmdtool import BaseCommandLineTool
from dreutils.exceptions import DreutilsError
import cellmaps_utils.constants
import time


class DRERunner(object):
    """
    Defines runner for invoking various Drug Recommender engines in
    Training mode
    """
    def __init__(self, outdir=None, algorithms=None):
        """
        Constructor
        """
        self._outdir = outdir
        self._algorithms = algorithms

    def run(self):
        """
        Abstract method to run the pipeline. This method should be implemented by subclasses.

        :raises NotImplementedError: If the subclass does not implement this method.
        """
        raise NotImplementedError('subclasses need to implement')


class SLURMRunner(DRERunner):
    """
    Runs DREs via SLURM
    """

    def __init__(self, outdir, algorithms=None):
        """
        Constructor
        """
        super().__init__(outdir=outdir)
        self._slurm_partition = None
        self._slurm_account = None

    def _write_slurm_directives(self, out=None, allocated_time='4:00:00',
                                mem='32G', cpus_per_task='4',
                                job_name='Unknown'):
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

        out.write('echo $SLURM_JOB_ID\n')
        out.write('echo $HOSTNAME\n')

    def _generate_algorithm_command(self, algorithm=None):
        """

        """
        return algorithm

    def _generate_final_command(self):
        """

        """
        return ''


    def run(self):
        """

        """
        slurmjobfile = os.path.join(self._outdir, 'slurm_dretrain_job.sh')
        job_names = []
        with open(slurmjobfile, 'w') as f:
            f.write('#! /bin/bash\n\n')
            for algo_index, algo in enumerate(self._algorithms):
                f.write('# ' + str(algo) + ' no dependencies\n')
                job_name_var = 'job' + str(algo_index)
                f.write(job_name_var +'=$(sbatch ' +
                        self._generate_algorithm_command(algorithm=algo) + ' | awk \'{print $4}\')\n\n')

                job_names.append(job_name_var)
            dependency_str = ':'.join(job_names)
            f.write('# final clean up job\n')
            f.write(
                'final_job=$(sbatch --dependency=afterok:' + dependency_str + ' ' + self._generate_final_command() + ' | awk \'{print $4}\')\n\n')
            f.write('echo "job submitted; here is ID of final job: $final_job"\n')
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

            # put code here
            if self._theargs['run_mode'] == 'slurm':
                runner = SLURMRunner(outdir=self._theargs['outdir'])
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
                                 'RO-Crates')
        parser.add_argument('--inputregex',
                            help='If set, only allow directories set in --input flag that match '
                                 'the regex set here')
        parser.add_argument('--algorithms', default='elasticnet_drecmd.py',
                            help='Comma delimited list of algorithms to use')
        parser.add_argument('--run_mode', choices=['slurm'],
                            help='Denotes how to run. If slurm, code generates a slurm script, '
                                 'if serial, code runs algorithms one at a time')
        return parser
