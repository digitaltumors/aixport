
import json
import os
import sys
import re
import hashlib
import aixport
from aixport.basecmdtool import BaseCommandLineTool
from aixport.exceptions import AIxPORTError
import aixport.constants
import cellmaps_utils.constants
from typing import Iterator
import time


class DRETrainRunner(object):
    """
    Defines runner for invoking various Drug Recommender engines in
    Training mode
    """
    def __init__(self, outdir=None, input_rocrates=None, algorithms=None,
                 algorithm_configs=None,
                 algorithm_rocrate_configs=None):
        """
        Constructor
        """
        self._outdir = outdir
        self._algorithms = algorithms
        self._input_rocrates = input_rocrates
        if algorithm_configs is None:
            algorithm_configs = {}
        if algorithm_rocrate_configs is None:
            algorithm_rocrate_configs = {}
        self._algorithm_configs = algorithm_configs
        self._algorithm_rocrate_configs = algorithm_rocrate_configs
        self._config_path_cache = {}

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
            raise AIxPORTError('No input RO-Crates')

        for ro_crate in self._input_rocrates:
            out.write(ro_crate + '\n')

    def _write_algorithm_configs(self, out=None):
        """

        """
        if out is None:
            return
        for algo in self._algorithms:
            config_value = self._algorithm_configs.get(algo, '')
            config_path = self._resolve_algorithm_config(algo=algo,
                                                         rocrate_path='')
            out.write(str(config_path) + '\n')

    def _materialize_algorithm_config(self, algo=None, config_value=None,
                                      config_key='default'):
        """
        Returns config path/string ready to pass to an algorithm command.
        """
        if config_value is None or config_value == '':
            return ''
        if not isinstance(config_value, dict):
            return str(config_value)

        cache_key = (str(algo), str(config_key))
        if cache_key in self._config_path_cache:
            return self._config_path_cache[cache_key]

        config_dir = os.path.join(self._outdir, 'algorithm_configs')
        os.makedirs(config_dir, exist_ok=True)

        algo_base = os.path.basename(str(algo))
        safe_algo = re.sub(r'[^A-Za-z0-9._-]+', '_', algo_base)
        digest = hashlib.md5(str(config_key).encode('utf-8')).hexdigest()[:12]
        config_path = os.path.join(config_dir, f'{safe_algo}_{digest}.json')
        with open(config_path, 'w') as cfg:
            json.dump(config_value, cfg, indent=2, sort_keys=True)
        self._config_path_cache[cache_key] = config_path
        return config_path

    def _resolve_algorithm_config(self, algo=None, rocrate_path=None):
        """
        Resolve algorithm config for a specific RO-Crate with fallback to default.
        """
        default_config = self._algorithm_configs.get(algo, '')
        per_rocrate = self._algorithm_rocrate_configs.get(algo, {})

        override_value = None
        if isinstance(per_rocrate, dict) and rocrate_path:
            abs_path = os.path.abspath(rocrate_path)
            real_path = os.path.realpath(abs_path)
            base_name = os.path.basename(abs_path)
            for key in (abs_path, real_path, base_name):
                if key in per_rocrate:
                    override_value = per_rocrate.get(key)
                    break

        if override_value is None:
            config_value = default_config
            config_key = 'default'
        else:
            config_value = override_value
            config_key = os.path.basename(rocrate_path) if rocrate_path else 'override'

        return self._materialize_algorithm_config(algo=algo,
                                                  config_value=config_value,
                                                  config_key=config_key)

class BashTrainRunner(DRETrainRunner):
    """
    Runs DREs via Bash script
    """

    def __init__(self, outdir=None, input_rocrates=None, algorithms=None,
                 algorithm_configs=None,
                 algorithm_rocrate_configs=None):
        """
        Constructor
        """
        super().__init__(outdir=outdir, input_rocrates=input_rocrates,
                         algorithms=algorithms,
                         algorithm_configs=algorithm_configs,
                         algorithm_rocrate_configs=algorithm_rocrate_configs)

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
        jobsfile = os.path.join(self._outdir, 'training_jobs.tsv')
        with open(input_rocratefile, 'w') as f:
            self._write_input_ro_crates(f)
        with open(jobsfile, 'w') as f:
            for algo in self._algorithms:
                for rocrate in self._input_rocrates:
                    config_path = self._resolve_algorithm_config(algo=algo,
                                                                 rocrate_path=rocrate)
                    f.write(str(algo) + '\t' + str(config_path) + '\t' + str(rocrate) + '\n')

        with open(bashjobfile, 'w') as f:
            f.write('#! /bin/bash\n\n')
            f.write('progress_bar() {\n')
            f.write('  local current=$1\n')
            f.write('  local total=$2\n')
            f.write('  local label="$3"\n')
            f.write('  local width=30\n')
            f.write('  local filled=$((current * width / total))\n')
            f.write('  local empty=$((width - filled))\n')
            f.write('  local bar=""\n')
            f.write('  local space=""\n')
            f.write('  for ((i=0; i<filled; i++)); do bar+="#"; done\n')
            f.write('  for ((i=0; i<empty; i++)); do space+="-"; done\n')
            f.write('  printf "\\r%s [%s%s] %d/%d" "$label" "$bar" "$space" "$current" "$total"\n')
            f.write('}\n\n')
            f.write('BASEDIR=`dirname $0`\n')
            f.write('pushd $BASEDIR\n')
            f.write('OUTDIR="' + str(aixport.constants.TRAINED_MODELS_DIRECTORY) + '"\n')
            total_jobs = len(self._algorithms) * len(self._input_rocrates)
            f.write('\necho "Training ' + str(total_jobs) + ' jobs (' +
                    str(len(self._algorithms)) + ' algorithms x ' +
                    str(len(self._input_rocrates)) + ' datasets)"\n')
            f.write('COUNT=0\n')
            f.write("while IFS=$'\\t' read -r ALGO CONFIG TRAIN_ROCRATE ; do\n")
            f.write('  [ -z "$ALGO" ] && continue\n')
            f.write('  TRAIN_ROCRATE_NAME=`basename "$TRAIN_ROCRATE"`\n')
            f.write('  ALGO_BASE=`basename "$ALGO"`\n')
            f.write('  ALGO_NOSUFFIX="${ALGO_BASE%.*}"\n')
            f.write('  CONFIG="${CONFIG:-}"\n')
            f.write('  if [ -n "$CONFIG" ]; then\n')
            f.write('    "$ALGO" "${OUTDIR}/${TRAIN_ROCRATE_NAME}_${ALGO_NOSUFFIX}" --input_crate "$TRAIN_ROCRATE" --mode train --config "$CONFIG"\n')
            f.write('  else\n')
            f.write('    "$ALGO" "${OUTDIR}/${TRAIN_ROCRATE_NAME}_${ALGO_NOSUFFIX}" --input_crate "$TRAIN_ROCRATE" --mode train\n')
            f.write('  fi\n')
            f.write('  STATUS=$?\n')
            f.write('  if [ $STATUS -ne 0 ]; then\n')
            f.write('    echo "FAILED ($STATUS): $ALGO $TRAIN_ROCRATE"\n')
            f.write('  fi\n')
            f.write('  COUNT=$((COUNT + 1))\n')
            f.write('  progress_bar "$COUNT" "' + str(total_jobs) + '" "train jobs"\n')
            f.write('done < training_jobs.tsv\n')
            f.write('echo ""\n')
            f.write('popd\n')
        os.chmod(bashjobfile, 0o755)
        return 0


class SLURMTrainRunner(DRETrainRunner):
    """
    Runs DREs via SLURM
    """

    def __init__(self, outdir=None, input_rocrates=None, algorithms=None,
                 algorithm_configs=None,
                 algorithm_rocrate_configs=None):
        """
        Constructor
        """
        super().__init__(outdir=outdir, input_rocrates=input_rocrates,
                         algorithms=algorithms,
                         algorithm_configs=algorithm_configs,
                         algorithm_rocrate_configs=algorithm_rocrate_configs)
        self._slurm_partition = None
        self._slurm_account = None

    def _write_slurm_directives(self, out=None, allocated_time='4:00:00',
                                mem='32G', cpus_per_task='4',
                                job_name='Unknown',
                                input_rocratefile=None,
                                input_configfile=None):
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
        if input_configfile is not None:
            out.write('CONFIG=`head -n $SLURM_ARRAY_TASK_ID ' + input_configfile + ' | tail -n 1`\n')
        else:
            out.write('CONFIG=""\n')

    def _generate_algorithm_command(self, algorithm=None,
                                    input_rocratefile=None,
                                    input_configfile=None):
        """

        """
        job_script = os.path.join(self._outdir, algorithm + '.sh')
        with open(job_script, 'w') as f:
            self._write_slurm_directives(out=f,
                                         job_name=algorithm + '_train',
                                         input_rocratefile=input_rocratefile,
                                         input_configfile=input_configfile)

            if input_configfile is not None:
                f.write('if [ -n "$CONFIG" ]; then\n')
                f.write(algorithm + ' "' + aixport.constants.TRAINED_MODELS_DIRECTORY +
                        '/${OUTPUT_ROCRATENAME}_' + algorithm +
                        '" --input_rocrate "$INPUT_ROCRATE" --mode train --config "$CONFIG"\n')
                f.write('else\n')
                f.write(algorithm + ' "' + aixport.constants.TRAINED_MODELS_DIRECTORY +
                        '/${OUTPUT_ROCRATENAME}_' + algorithm +
                        '" --input_rocrate "$INPUT_ROCRATE" --mode train\n')
                f.write('fi\n')
            else:
                f.write(algorithm + ' "' + aixport.constants.TRAINED_MODELS_DIRECTORY + '/${OUTPUT_ROCRATENAME}_' + algorithm + '" --input_rocrate "$INPUT_ROCRATE" --mode train\n')
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
        algoconfigfile = os.path.join(self._outdir, 'config_files.txt')
        with open(algoconfigfile, 'w') as f:
            self._write_algorithm_configs(out=f)

        with open(slurmjobfile, 'w') as f:
            f.write('#! /bin/bash\n\n')
            for algo_index, algo in enumerate(self._algorithms):
                f.write('# ' + str(algo) + ' no dependencies\n')
                job_name_var = 'job' + str(algo_index)
                config_file = os.path.join(self._outdir, f'config_files_{algo_index}.txt')
                with open(config_file, 'w') as cfg_out:
                    for rocrate in self._input_rocrates:
                        cfg_out.write(self._resolve_algorithm_config(algo=algo,
                                                                     rocrate_path=rocrate) + '\n')
                f.write(job_name_var +'=$(sbatch ' +
                        self._generate_algorithm_command(algorithm=algo,
                                                         input_rocratefile=input_rocratefile,
                                                         input_configfile=config_file) + ' | awk \'{print $4}\')\n\n')

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

    def _parse_algorithms_argument(self):
        """

        """
        algorithms_arg = self._theargs.get('algorithms')
        if algorithms_arg is None:
            return [], {}, {}

        if os.path.isfile(algorithms_arg):
            try:
                with open(algorithms_arg, 'r') as f:
                    algorithms_data = json.load(f)
            except (OSError, json.JSONDecodeError) as ex:
                raise AIxPORTError('Unable to load algorithms configuration file: ' +
                                    str(ex))
            if not isinstance(algorithms_data, dict):
                raise AIxPORTError('Algorithms configuration file must be a JSON object')

            algorithms = []
            algorithm_configs = {}
            algorithm_rocrate_configs = {}
            for algo_name, algo_settings in algorithms_data.items():
                algorithms.append(algo_name)
                if algo_settings is None:
                    algorithm_configs[algo_name] = ''
                    algorithm_rocrate_configs[algo_name] = {}
                    continue
                if not isinstance(algo_settings, dict):
                    raise AIxPORTError('Configuration for algorithm ' + str(algo_name) +
                                        ' must be a JSON object or null')
                config_value = algo_settings.get('config', '')
                if config_value is None:
                    config_value = ''
                algorithm_configs[algo_name] = config_value
                rocrate_cfg = algo_settings.get('config_by_rocrate', {})
                if rocrate_cfg is None:
                    rocrate_cfg = {}
                if not isinstance(rocrate_cfg, dict):
                    raise AIxPORTError('config_by_rocrate for algorithm ' + str(algo_name) +
                                       ' must be a JSON object')
                algorithm_rocrate_configs[algo_name] = rocrate_cfg
            return algorithms, algorithm_configs, algorithm_rocrate_configs

        algorithms = [algo for algo in re.split(r'\s*,\s*', str(algorithms_arg)) if algo]
        algorithm_configs = {algo: '' for algo in algorithms}
        algorithm_rocrate_configs = {algo: {} for algo in algorithms}
        return algorithms, algorithm_configs, algorithm_rocrate_configs

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
                                     aixport.constants.TRAINED_MODELS_DIRECTORY),
                        mode=0o755)

            train_rocrates = []

            if os.path.isfile(self._theargs['input']):
                train_rocrates = list(self._get_training_rocrates(self._theargs['input']))
            elif os.path.isdir(self._theargs['input']):
                raise AIxPORTError('directory path not supported yet')

            algorithms, algorithm_configs, algorithm_rocrate_configs = self._parse_algorithms_argument()
            if len(algorithms) == 0:
                raise AIxPORTError('No algorithms specified')

            if self._theargs['run_mode'].lower() == 'slurm':
                runner = SLURMTrainRunner(outdir=self._theargs['outdir'],
                                          algorithms=algorithms,
                                          algorithm_configs=algorithm_configs,
                                          algorithm_rocrate_configs=algorithm_rocrate_configs,
                                          input_rocrates=train_rocrates)
            elif self._theargs['run_mode'].lower() == 'bash':
                runner = BashTrainRunner(outdir=self._theargs['outdir'],
                                         algorithms=algorithms,
                                         algorithm_configs=algorithm_configs,
                                         algorithm_rocrate_configs=algorithm_rocrate_configs,
                                         input_rocrates=train_rocrates)
            else:
                raise AIxPORTError('Invalid run mode: ' + str(self._theargs['run_mode']))

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
        """.format(version=aixport.__version__,
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
