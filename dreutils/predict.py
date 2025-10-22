import os
import re
from typing import Dict, Iterator, List

import dreutils
from dreutils.basecmdtool import BaseCommandLineTool
from dreutils.exceptions import DreutilsError
import dreutils.constants
import cellmaps_utils.constants


class DREPredictRunner(object):
    """
    Base runner that materializes prediction jobs.
    """

    def __init__(self, outdir=None, input_rocrates=None,
                 trained_model_dirs=None, algorithms=None):
        """
        Constructor.
        """
        self._outdir = os.path.abspath(outdir) if outdir else None
        self._input_rocrates = input_rocrates or []
        self._trained_model_dirs = trained_model_dirs or []
        self._algorithms = algorithms or []
        self._predictions_dir = (os.path.join(self._outdir,
                               dreutils.constants.PREDICTIONS_DIRECTORY)
                                 if self._outdir else None)

    def run(self):
        """
        Subclasses implement this to emit the concrete execution artifact.
        """
        raise NotImplementedError('subclasses need to implement')

    def _write_input_ro_crates(self, out=None):
        """
        Serializes input RO-Crate paths.
        """
        if not self._input_rocrates:
            raise DreutilsError('No input RO-Crates')
        for ro_crate in self._input_rocrates:
            out.write(ro_crate + '\n')

    def _write_trained_models(self, out=None):
        """
        Serializes trained model directories.
        """
        if not self._trained_model_dirs:
            raise DreutilsError('No trained model directories')
        for model_dir in self._trained_model_dirs:
            out.write(model_dir + '\n')

    def _get_algorithm_lookup(self):
        """
        Maps algorithm identifiers (without suffix) to commands.
        """
        if not self._algorithms:
            raise DreutilsError('No algorithms specified')
        lookup = {}
        for algo in self._algorithms:
            key = os.path.splitext(os.path.basename(algo))[0]
            lookup[key] = algo
        return lookup

    def _ensure_predictions_dir(self):
        """
        Ensures predictions directory exists.
        """
        if self._predictions_dir is None:
            raise DreutilsError('Output directory is not set')
        os.makedirs(self._predictions_dir, mode=0o755, exist_ok=True)

    def _parse_test_rocrate_name(self, path):
        """
        Extracts dataset token and basename from test RO-Crate path.
        """
        base = os.path.basename(os.path.normpath(path))
        suffix = '_test_rocrate'
        if not base.endswith(suffix):
            raise DreutilsError('Invalid test RO-Crate directory name: ' + base)
        return base[:-len(suffix)], base

    def _parse_trained_model_dir(self, path):
        """
        Extracts dataset and algorithm from trained model directory name.
        """
        base = os.path.basename(os.path.normpath(path))
        token = '_train_rocrate_'
        if token not in base:
            raise DreutilsError('Invalid trained model directory name: ' + base)
        dataset, algorithm = base.split(token, 1)
        return dataset, algorithm

    def _get_model_path(self, trained_model_dir):
        """
        Locates supported model file inside trained model directory.
        """
        for filename in dreutils.constants.SUPPORTED_MODEL_FILES:
            candidate = os.path.join(trained_model_dir, filename)
            if os.path.isfile(candidate):
                return candidate
        raise DreutilsError('No supported model found in ' + trained_model_dir)

    def _write_job_manifest(self, manifest_path, jobs):
        """
        Writes prediction job manifest to disk.
        """
        with open(manifest_path, 'w') as f:
            f.write('dataset\talgorithm\ttrained_model_dir\ttest_rocrate\tmodel_path\toutput_dir\n')
            for job in jobs:
                f.write('\t'.join([job['dataset_name'],
                                   job['algorithm_name'],
                                   job['trained_model_dir'],
                                   job['test_rocrate'],
                                   job['model_path'],
                                   job['output_dir']]))
                f.write('\n')

    def _build_prediction_jobs(self):
        """
        Generates mapping between trained models and test RO-Crates.
        """
        self._ensure_predictions_dir()
        algorithm_lookup = self._get_algorithm_lookup()
        test_map = {}
        for rocrate in self._input_rocrates:
            dataset, base_name = self._parse_test_rocrate_name(rocrate)
            if dataset in test_map:
                raise DreutilsError('Duplicate test RO-Crate for dataset ' + dataset)
            test_map[dataset] = {'path': rocrate, 'name': base_name}

        jobs: List[Dict[str, str]] = []
        for trained_model_dir in self._trained_model_dirs:
            dataset, algorithm_name = self._parse_trained_model_dir(trained_model_dir)
            if dataset not in test_map:
                raise DreutilsError('No matching test RO-Crate for ' + dataset)
            if algorithm_name not in algorithm_lookup:
                raise DreutilsError('Algorithm ' + algorithm_name + ' missing from command list')
            model_path = self._get_model_path(trained_model_dir)
            test_entry = test_map[dataset]
            output_subdir = f"{test_entry['name']}_{algorithm_name}"
            output_dir = os.path.join(self._predictions_dir, output_subdir)
            jobs.append({'dataset_name': dataset,
                         'algorithm_name': algorithm_name,
                         'algorithm_command': algorithm_lookup[algorithm_name],
                         'test_rocrate': test_entry['path'],
                         'test_rocrate_name': test_entry['name'],
                         'trained_model_dir': trained_model_dir,
                         'model_path': model_path,
                         'output_dir': output_dir,
                         'output_subdir': output_subdir})
        return jobs


class BashPredictRunner(DREPredictRunner):
    """
    Emits bash script to run predictions serially.
    """

    def __init__(self, outdir=None, input_rocrates=None,
                 trained_model_dirs=None, algorithms=None):
        super().__init__(outdir=outdir,
                         input_rocrates=input_rocrates,
                         trained_model_dirs=trained_model_dirs,
                         algorithms=algorithms)

    def run(self):
        """
        Creates bash script for predictions.
        """
        jobs = self._build_prediction_jobs()
        if not jobs:
            raise DreutilsError('No prediction jobs to run')

        manifest_path = os.path.join(self._outdir, 'prediction_jobs.tsv')
        self._write_job_manifest(manifest_path, jobs)

        input_rocratefile = os.path.join(self._outdir, 'input_rocrates.txt')
        with open(input_rocratefile, 'w') as f:
            self._write_input_ro_crates(out=f)

        trainedmodelsfile = os.path.join(self._outdir, 'trainedmodels.txt')
        with open(trainedmodelsfile, 'w') as f:
            self._write_trained_models(out=f)

        bashjobfile = os.path.join(self._outdir, 'bash_predict_job.sh')
        with open(bashjobfile, 'w') as f:
            f.write('#! /bin/bash\n\n')
            f.write('BASEDIR=`dirname $0`\n')
            f.write('pushd $BASEDIR\n')
            f.write(f'PREDICTIONS_DIR="{dreutils.constants.PREDICTIONS_DIRECTORY}"\n')
            f.write('mkdir -p "${PREDICTIONS_DIR}"\n\n')
            f.write(f'echo "Preparing to run {len(jobs)} prediction jobs"\n\n')
            for job in jobs:
                f.write(f'# Dataset: {job["dataset_name"]} Algorithm: {job["algorithm_name"]}\n')
                f.write(f'{job["algorithm_command"]} "${{PREDICTIONS_DIR}}/{job["output_subdir"]}" '
                        f'--input_crate "{job["test_rocrate"]}" '
                        f'--mode test '
                        f'--model "{job["model_path"]}"\n')
                f.write('echo "Exit code: $?"\n\n')
            f.write('popd\n')
        os.chmod(bashjobfile, 0o755)
        return 0


class SLURMPredictRunner(DREPredictRunner):
    """
    Emits SLURM scripts to run predictions on a cluster.
    """

    def __init__(self, outdir=None, input_rocrates=None,
                 trained_model_dirs=None, algorithms=None):
        super().__init__(outdir=outdir,
                         input_rocrates=input_rocrates,
                         trained_model_dirs=trained_model_dirs,
                         algorithms=algorithms)
        self._slurm_partition = None
        self._slurm_account = None

    def _write_slurm_directives(self, out=None, allocated_time='4:00:00',
                                mem='32G', cpus_per_task='4',
                                job_name='dre_predict'):
        """
        Writes SLURM directives for a single job script.
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

    def _generate_job_script(self, job, index):
        """
        Generates per-job SLURM script.
        """
        script_name = f'{job["algorithm_name"]}_{index}.sh'
        script_path = os.path.join(self._outdir, script_name)
        with open(script_path, 'w') as f:
            self._write_slurm_directives(out=f,
                                         job_name=f'{job["algorithm_name"]}_{job["dataset_name"]}_predict')
            f.write(f'mkdir -p "{self._predictions_dir}"\n')
            f.write(f'{job["algorithm_command"]} "{job["output_dir"]}" --input_crate '
                    f'"{job["test_rocrate"]}" --mode test --model "{job["model_path"]}"\n')
            f.write('exit $?\n')
        os.chmod(script_path, 0o755)
        return script_name

    def run(self):
        """
        Creates SLURM submission script.
        """
        jobs = self._build_prediction_jobs()
        if not jobs:
            raise DreutilsError('No prediction jobs to run')

        manifest_path = os.path.join(self._outdir, 'prediction_jobs.tsv')
        self._write_job_manifest(manifest_path, jobs)

        input_rocratefile = os.path.join(self._outdir, 'input_rocrates.txt')
        with open(input_rocratefile, 'w') as f:
            self._write_input_ro_crates(out=f)

        trainedmodelsfile = os.path.join(self._outdir, 'trainedmodels.txt')
        with open(trainedmodelsfile, 'w') as f:
            self._write_trained_models(out=f)

        slurmjobfile = os.path.join(self._outdir, 'slurm_predict_job.sh')
        with open(slurmjobfile, 'w') as f:
            f.write('#! /bin/bash\n\n')
            for idx, job in enumerate(jobs):
                job_script = self._generate_job_script(job, idx)
                f.write(f'# Dataset: {job["dataset_name"]} Algorithm: {job["algorithm_name"]}\n')
                f.write(f'job{idx}=$(sbatch {job_script} | awk \'{{print $4}}\')\n\n')
        os.chmod(slurmjobfile, 0o755)
        return 0


class PredictTool(BaseCommandLineTool):
    """
    Runs predictions using trained DRE models.
    """
    COMMAND = 'predict'

    def __init__(self, theargs, provenance_utils=None):
        """

        :param theargs: arguments
        :type theargs: dict
        """
        super().__init__(theargs,
                         provenance_utils=provenance_utils)

    def _get_test_rocrates(self, input_file) -> Iterator[str]:
        """
        Yields absolute paths to test RO-Crate directories.
        """
        with open(input_file, 'r') as f:
            for line in f:
                yield os.path.abspath(line.strip())

    def _get_trained_model_dirs(self, source) -> List[str]:
        """
        Resolves trained model directories from file or directory.
        """
        if source is None:
            raise DreutilsError('--trainedmodels is required')

        abs_source = os.path.abspath(source)
        trained_models = []

        if os.path.isfile(abs_source):
            with open(abs_source, 'r') as f:
                for line in f:
                    candidate = line.strip()
                    if candidate == '':
                        continue
                    abs_path = os.path.abspath(candidate)
                    if not os.path.isdir(abs_path):
                        raise DreutilsError('Trained model directory does not exist: ' + abs_path)
                    trained_models.append(abs_path)
        elif os.path.isdir(abs_source):
            for entry in sorted(os.listdir(abs_source)):
                candidate = os.path.join(abs_source, entry)
                if os.path.isdir(candidate):
                    trained_models.append(os.path.abspath(candidate))
        else:
            raise DreutilsError('trainedmodels path does not exist: ' + abs_source)

        if not trained_models:
            raise DreutilsError('No trained model directories found in ' + abs_source)
        return trained_models

    def run(self):
        """

        :return:
        """
        exitcode = 99
        try:
            self._initialize_rocrate()
            predictions_dir = os.path.join(self._theargs['outdir'],
                                           dreutils.constants.PREDICTIONS_DIRECTORY)
            os.makedirs(predictions_dir, mode=0o755, exist_ok=True)

            if os.path.isfile(self._theargs['input']):
                test_rocrates = list(self._get_test_rocrates(self._theargs['input']))
            else:
                raise DreutilsError('directory path not supported yet')

            trained_model_dirs = self._get_trained_model_dirs(self._theargs['trainedmodels'])

            algorithms = [algo for algo in re.split(r'\s*,\s*', self._theargs['algorithms']) if algo]
            if not algorithms:
                raise DreutilsError('No algorithms specified')

            run_mode = self._theargs['run_mode'].lower()
            if run_mode == 'slurm':
                runner = SLURMPredictRunner(outdir=self._theargs['outdir'],
                                            input_rocrates=test_rocrates,
                                            trained_model_dirs=trained_model_dirs,
                                            algorithms=algorithms)
            elif run_mode == 'bash':
                runner = BashPredictRunner(outdir=self._theargs['outdir'],
                                           input_rocrates=test_rocrates,
                                           trained_model_dirs=trained_model_dirs,
                                           algorithms=algorithms)
            else:
                raise DreutilsError('Invalid run mode: ' + str(self._theargs['run_mode']))

            exitcode = runner.run()
            self._finalize_rocrate()
            return exitcode
        finally:
            self._write_task_finish_json(exitcode)

    def add_subparser(subparsers):
        """

        :return:
        """
        desc = """

        Version {version}

        {cmd} generates bash or SLURM scripts to run predictions
        """.format(version=dreutils.__version__,
                   cmd=PredictTool.COMMAND)

        parser = subparsers.add_parser(PredictTool.COMMAND,
                                       help='Runs prediction on trained DRE models',
                                       description=desc,
                                       formatter_class=cellmaps_utils.constants.ArgParseFormatter)

        parser.add_argument('outdir',
                            help='Output directory. This directory should not already exist')
        parser.add_argument('--input', required=True,
                            help='File containing absolute paths to test RO-Crate directories')
        parser.add_argument('--trainedmodels', required=True,
                            help='File containing trained model directories or directory holding them')
        parser.add_argument('--algorithms', default='elasticnet_drecmd.py',
                            help='Comma delimited list of algorithms to use')
        parser.add_argument('--run_mode', choices=['slurm', 'bash'], default='bash',
                            help='Denotes how to run. If slurm, code generates a SLURM script, '
                                 'if bash, code runs algorithms one at a time')
        return parser
