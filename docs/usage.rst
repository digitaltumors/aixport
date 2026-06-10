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

**VCF conversion**

``aixportcmd.py vcf2inputs`` converts an annotated VCF into genomic feature
matrices. By default it writes the AIxPORT five-file layout:

.. code-block:: console

   $ aixportcmd.py vcf2inputs patient_test_rocrate \
       --vcf patient.annotated.vcf.gz \
       --output-profile aixport \
       --gene-panel nest_vnn_718

The AIxPORT profile writes ``gene2ind.txt``, ``cell2ind.txt``,
``cell2mutation.txt``, ``cell2cnamplification.txt``, and
``cell2cndeletion.txt`` at the output RO-Crate root.

The MutationProjector profile writes tab-delimited ``mut.txt``, ``cna.txt``,
``cnd.txt``, ``covariates.txt``, and ``outcomes.txt``:

.. code-block:: console

   $ aixportcmd.py vcf2inputs mutationprojector_eval_dataset \
       --vcf patient.annotated.vcf.gz \
       --output-profile mutationprojector \
       --gene-panel mutationprojector_mskimpact468 \
       --covariates covariates.txt \
       --outcomes outcomes.txt

VCF records must include gene annotations in ``INFO``. The converter supports
``CSQ``, ``ANN``, and simple gene-symbol fields such as ``SYMBOL``. It writes
``conversion_report.json``, ``variants_used.tsv``, and ``variants_skipped.tsv``
to make skipped and accepted calls auditable.

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
