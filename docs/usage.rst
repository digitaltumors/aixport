=====
Usage
=====

This page should provide information on how to use aixport

In a project
--------------

To use Artificial Intelligence Predictive Oncology Research Toolkit in a project::

    import aixport

On the command line
---------------------

For information invoke :code:`aixportcmd.py -h`

**Example usage**

**Training**

.. code-block:: console

   $ aixportcmd.py train trainout --input input_train.txt --algorithms elasticnet_drecmd.py --run_mode bash

``input_train.txt`` should contain absolute paths to ``*_train_rocrate`` directories,
one per line. The command will populate ``trainout`` with bash script that populates ``trainout/trainedmodels`` with per-algorithm
trained model directories. Then run the bash script:

.. Code-block::

   ./trainout/bash_train_job.sh

**Prediction**

.. code-block:: console

   $ aixportcmd.py predict predictout --input input_test.txt --trainedmodels trainout/trainedmodels --algorithms elasticnet_drecmd.py --run_mode bash

``input_test.txt`` should list the ``*_test_rocrate`` directories with test data, and
``trainout/trainedmodels`` should contain subdirectories named
``<drugname>_train_rocrate_<algorithm>`` produced by the training step. Then run the bash script:

.. Code-block::

   ./predictout/bash_predict_job.sh

**Benchmark**

.. code-block:: console

   $ aixportcmd.py benchmark benchmarkout \
       --input_test_rocrates input_test.txt \
       --predictions_rocrate predictout

``input_test.txt`` should match the file used during prediction and list the test
RO-Crates, one per line. ``predictout`` should be the prediction RO-Crate folder produced
by ``aixportcmd.py predict`` (or the pipeline), containing the ``predictions`` subdirectory.
The benchmark command creates ``benchmarkout`` (must not already exist), computes
Pearson/Spearman correlations between predictions and ground truth, writes ``results.csv``,
and generates ``results.png``/``results.svg`` for quick inspection.

**Custom RO-Crate pipeline**

.. code-block:: console

   $ bash scripts/run_custom_dataset.sh \
       --rocrates-dir /path/to/rocrates \
       --output-dir /path/to/custom_run \
       --model-config configs/custom_dataset_models.json

The ``--rocrates-dir`` input must already contain per-drug
``*_train_rocrate`` and ``*_test_rocrate`` folders.

By default, the script installs ``aixport`` and the enabled model packages
with their declared Python dependencies before running. Use ``--skip-install``
only when the environment is already prepared.

The model config JSON supports:

* ``enabled`` to turn a model on or off
* ``optimize`` to control per-model hyperparameter optimization
* ``install_path`` to install a custom model repo before running

Via Docker
---------------

**Example usage**

**TODO:** Add information about example usage


.. code-block::

   Coming soon ...

RO-Crate Zipping Utility
------------------------

The `ROCrateZipper` helper can bundle an entire RO-Crate directory into a ZIP
archive and inspect or extract its contents. This is useful for publishing or
sharing generated RO-Crates.

**Example usage**

.. code-block:: python

   from aixport import ROCrateZipper

   zipper = ROCrateZipper("/path/to/folder", "/path/to/output.zip")
   zipper.zip_directory()
   print(zipper.list_contents())  # View all files in the zip
   data = zipper.read_file("subfolder/data.txt")  # Access a specific file
   zipper.extract_file("subfolder/data.txt", "/tmp/extracted/")  # Extract one file
