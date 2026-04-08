===============================================================
Artificial Intelligence Predictive Oncology Research Toolkit
===============================================================


AIxPORT is provides standards and tools train, evaluate, and run
predictions with AI models for predicting drug response.

.. image:: https://app.travis-ci.com/digitaltumors/aixport.svg?branch=main
        :target: https://app.travis-ci.com/digitaltumors/aixport

.. image:: https://readthedocs.org/projects/aixport/badge/?version=latest
        :target: https://aixport.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

* Documentation: https://aixport.readthedocs.io.
* Source code: https://github.com/digitaltumors/aixport

Dependencies
------------

* `cellmaps_utils <https://pypi.org/project/cellmaps-utils>`__

Compatibility
-------------

* Python 3.8+

Installation
------------

.. code-block::

   git clone https://github.com/digitaltumors/aixport
   cd aixport
   pip install -r requirements_dev.txt
   make install


Run **make** command with no arguments to see other build/deploy options including creation of Docker image

.. code-block::

   make

Output:

.. code-block::

   clean                remove all build, test, coverage and Python artifacts
   clean-build          remove build artifacts
   clean-pyc            remove Python file artifacts
   clean-test           remove test and coverage artifacts
   lint                 check style with flake8
   test                 run tests quickly with the default Python
   test-all             run tests on every Python version with tox
   coverage             check code coverage quickly with the default Python
   docs                 generate Sphinx HTML documentation, including API docs
   servedocs            compile the docs watching for changes
   testrelease          package and upload a TEST release
   release              package and upload a release
   dist                 builds source and wheel package
   install              install the package to the active Python's site-packages
   dockerbuild          build docker image and store in local repository
   dockerpush           push image to dockerhub

Usage
-----

For a summary of available commands run :code:`aixportcmd.py -h`. Each sub-command
also exposes its own help via :code:`aixportcmd.py <command> -h`.

The baseline model configs in ``aixport/configs/aixport_models.json`` now support
feature-set and task selection for the 3 classical models:

* ``feature_types``: explicit combinations such as ``["mutations", "cnd", "cna", "expression"]``
* ``task_type``: ``regression`` or ``classification``
* ``label_threshold``: AUC cutoff used when ``task_type`` is ``classification``
* ``loss_function``: optional classification loss/objective hint (``bce`` is supported
  for ElasticNet and XGBoost)

``aixportcmd.py optimize-train`` also supports ``feature_set_search`` in the train
config, which lets the optimizer compare multiple feature combinations for the same model.

For a fuller parameter guide with condition-specific examples, see
``README_MODEL_CONFIG.md`` in this directory.

For end-to-end reproduction of the 3-model optimized runs, see
``scripts/run_optimized_scenarios.sh``. The script runs:

* ``optimize-train``
* ``train``
* ``predict``
* ``benchmark``

across the selected RO-Crate scenarios using the ElasticNet, RandomForest, and
XGBoost baselines.

Example:

.. code-block:: console

   bash scripts/run_optimized_scenarios.sh \
       --outdir /path/to/optimized_run \
       --ccle-v2-dir /path/to/rocrates/ccle_v2 \
       --ccle-to-msk-dir /path/to/rocrates/ccle_to_msk_393 \
       --msk-dir /path/to/rocrates/msk_chord \
       --msk-to-ccle-dir /path/to/rocrates/msk_to_ccle_393

The script assumes the four repos are cloned side-by-side by default, but that
can be overridden with environment variables documented in the script header.

Run On Your Own Dataset
~~~~~~~~~~~~~~~~~~~~~~~

For a single-command workflow on a new dataset, use
``scripts/run_custom_dataset.sh``. It will:

* build per-drug ``*_train_rocrate`` and ``*_test_rocrate`` folders from a
  response table
* optionally run ``optimize-train``
* run ``train``
* run ``predict``
* run ``benchmark`` unless ``--skip-benchmark`` is set

Example:

.. code-block:: console

   bash scripts/run_custom_dataset.sh \
       --response-table /path/to/responses.tsv \
       --shared-features-dir /path/to/shared_features \
       --output-dir /path/to/custom_run \
       --model-config /path/to/custom_dataset_models.json

The response table is expected to contain at least:

* a drug column
* a cell/sample column
* a label column

Optional columns can also be mapped for:

* SMILES strings
* source dataset tags
* split groups (to avoid leakage across related samples)

The shared features directory must contain AIxPORT-compatible feature tables such as:

* ``cell2ind.txt``
* ``gene2ind.txt``
* ``cell2mutation.txt``
* ``cell2cndeletion.txt``
* ``cell2cnamplification.txt``

Optional files like ``cell2expression.txt`` and ``cell2fusion.txt`` are copied
when present and automatically validated against the selected model config.

Model Config JSON
^^^^^^^^^^^^^^^^^

Use ``configs/custom_dataset_models.json`` as the starting point.

Each model entry can include:

* ``enabled``: set to ``false`` to skip that model
* ``optimize``: set to ``true`` or ``false`` for per-model hyperparameter optimization
* ``install_path``: optional repo path for ``pip install -e`` before running
* ``config``: the normal AIxPORT train/test config block

Minimal example:

.. code-block:: json

   {
     "elasticnet_drecmd.py": {
       "enabled": true,
       "optimize": true,
       "config": {
         "train": {
           "feature_types": ["mutations", "cnd", "cna"],
           "task_type": "regression"
         },
         "test": {}
       }
     },
     "mymodel_drecmd.py": {
       "enabled": true,
       "optimize": false,
       "install_path": "/path/to/my_model_repo",
       "config": {
         "train": {},
         "test": {}
       }
     }
   }

Adding your own model is meant to be a one-step config change: add a new entry
to the JSON file, point ``install_path`` to the repo if needed, and rerun
``run_custom_dataset.sh``.

Hyperparameter Optimization Control
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``run_custom_dataset.sh`` supports both global and per-model optimization control:

* ``--run-hpo auto``: respect each model's ``optimize`` field
* ``--run-hpo true``: optimize every enabled model
* ``--run-hpo false``: skip optimization entirely

Benchmark mode
~~~~~~~~~~~~~~

``aixportcmd.py`` can score previously generated prediction RO-Crates against their
matching test RO-Crates. The benchmark command expects:

1. A text file (``--input_test_rocrates``) listing absolute or relative paths to the
   test RO-Crates used to generate the predictions, one path per line.
2. A prediction RO-Crate directory (``--predictions_rocrate``) produced by
   ``aixportcmd.py predict`` or the benchmark pipeline. It must contain the bundled
   ``predictions`` subdirectory created by the CLI.
3. An output directory that does not yet exist. Benchmark mode will create it and
   write the aggregated metrics, plots, and RO-Crate metadata there.

Run the benchmark command as:

.. code-block:: console

   aixportcmd.py benchmark <OUTPUT_DIR> \
       --input_test_rocrates /path/to/test_rocrates.txt \
       --predictions_rocrate /path/to/predictions_crate

The tool reads each prediction RO-Crate, matches it back to the corresponding test
RO-Crate, and computes Pearson/Spearman correlations. Results are saved to
``results.csv`` and plotted to ``results.png``/``results.svg`` in ``<OUTPUT_DIR>``.

Use ``-v`` (repeat up to three times) for more verbose logging, or supply
``--logconf`` with a custom logging configuration if desired.

For developers
-------------------------------------------

.. note::

    Commands below assume ``pip install -r requirements_dev.txt`` has been run

Run tests
~~~~~~~~~~

To run unit tests:

.. code-block::

    make test

To run tests in multiple python environments defined by ``tox.ini``:

.. code-block::

    make test-all

Continuous integration / Continuous development
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A ``.travis.yml`` file is included in this
repo to easily enable continous integration / continuous development
via `Travis <https://travis-ci.com>`__

The configuration leverages `coverage <https://pypi.org/project/coverage/>`__
and `coveralls <https://coveralls.io>`__ to log
code coverage


Make documentation
~~~~~~~~~~~~~~~~~~~~

Documentation for this code is stored under ``docs/`` and can
be easily configured for display on `Read the Docs <https://readthedocs.io>`__
once the repo is linked from within `Read the Docs <https://readthedocs.io>`__
via github account

Command below requires additional packages that can be installed
with this command:

.. code-block::

    pip install -r docs/requirements.txt

Running the command below creates html documentation under
``docs/_build/html`` that is displayed to the user via
"default" browser

.. code-block::

    make docs


To deploy development versions of this package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Below are steps to make changes to this code base, deploy, and then run
against those changes.

#. Make changes

   Modify code in this repo as desired

#. Build and deploy

.. code-block::

    # From base directory of this repo aixport
    pip uninstall aixport -y ; make clean dist; pip install dist/aixport*whl



Needed files
------------

**TODO:** Add description of needed files


Via Docker
~~~~~~~~~~~~~~~~~~~~~~

**Example usage**

**TODO:** Add information about example usage


.. code-block::

   Coming soon ...

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
.. _NDEx: http://www.ndexbio.org
