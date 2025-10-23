=====
Usage
=====

This page should provide information on how to use dreutils

In a project
--------------

To use Drug Recommender Engine Utilities in a project::

    import dreutils

On the command line
---------------------

For information invoke :code:`dreutilscmd.py -h`

**Example usage**

**Training**

.. code-block:: console

   $ ./dreutilscmd.py train trainout --input input_train.txt --algorithms elasticnet_drecmd.py --run_mode bash

``input_train.txt`` should contain absolute paths to ``*_train_rocrate`` directories,
one per line. The command will populate ``trainout/trainedmodels`` with per-algorithm
trained model directories.

**Prediction**

.. code-block:: console

   $ ./dreutilscmd.py predict predictout --input input_test.txt --trainedmodels trainout/trainedmodels --algorithms elasticnet_drecmd.py --run_mode bash

``input_test.txt`` should list the ``*_test_rocrate`` directories to evaluate, and
``trainout/trainedmodels`` should contain subdirectories named
``<drugname>_train_rocrate_<algorithm>`` produced by the training step.

.. code-block::

   dreutilscmd.py # TODO Add other needed arguments here

Via Docker
---------------

**Example usage**

**TODO:** Add information about example usage


.. code-block::

   Coming soon ...

