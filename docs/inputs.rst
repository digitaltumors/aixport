=========
Inputs
=========

The Artificial Intelligence Predictive Oncology Research Toolkit (AIxPORT) utilities exchange datasets via
`RO-Crate <https://www.researchobject.org/ro-crate>`_ bundles.  Each bundle is
a directory that carries a ``ro-crate-metadata.json`` file.  This page
documents the expected layout for the ``*_train_rocrate`` and
``*_test_rocrate`` folders consumed by ``aixportcmd.py train`` and
``aixportcmd.py predict``.

.. note::

   To streamline downstream matching, DRE expects directory names to end with
   ``_train_rocrate`` or ``_test_rocrate``.  The prediction tooling will raise
   an error if those suffixes are missing.

Feature Tables
----------------

Every training and testing crate must include the genomic feature panel used by
the algorithms.  The files below are placed at the top-level of the crate directory.

- ``gene2ind.txt``:
    Tab-delimited mapping from zero-based gene indices to gene symbols.

    .. code-block::

        0	ABCB1
        1	ABCC3
        2	ABL1

- ``cell2ind.txt``:
    Tab-delimited mapping from cell (genotype) indices to cell line names.

    .. code-block::

        0	201T_LUNG
        1	22RV1_PROSTATE
        2	2313287_STOMACH

- ``cell2mutation.txt``:
    Comma-delimited matrix whose rows correspond to ``cell2ind.txt`` entries
    and whose columns follow ``gene2ind.txt`` ordering.  Values are ``1`` when
    a gene carries a non-synonymous mutation and ``0`` otherwise.

    .. code-block::

        0,0,1,0,0,0..
        0,0,0,0,1,0..
        0,0,0,0,0,0..

- ``cell2cndeletion.txt``:
    Comma-delimited matrix with the same shape as ``cell2mutation.txt``.  A
    value of ``1`` denotes a copy-number deletion event; ``0`` means no
    deletion.

    .. code-block::

        0,0,0,0,0,0..
        0,1,0,0,0,0..
        0,0,0,0,1,0..

- ``cell2cnamplification.txt``:
    Comma-delimited matrix indicating copy-number amplification events.

    .. code-block::

        0,0,0,0,0,0..
        0,0,0,1,0,0..
        0,1,0,0,0,0..

References:

1. Park, S., Silva, E., Singhal, A. et al. A deep learning model of tumor cell
   architecture elucidates response and resistance to CDK4/6 inhibitors. Nat
   Cancer (2024). https://doi.org/10.1038/s43018-024-00740-1

Training RO-Crates
------------------

Additionally to the feature tables, training crates include the training data:

- ``training_data.txt``:
    Tab-delimited table with one row per training observation.  Columns are:

    #. Cell identifier matching ``cell2ind.txt`` (column 1)
    #. Drug SMILES string (column 2)
    #. Observed response value (floating point, column 3)
    #. Optional data source label (column 4)

    .. code-block::

        HS633T_SOFT_TISSUE	CC1=C(C(=O)N(C2=NC(=NC=C12)NC3=NC=C(C=C3)N4CCNCC4)C5CCCC5)C(=O)C	0.6695136077442607	GDSC2
        KINGS1_CENTRAL_NERVOUS_SYSTEM	CC1=C(C(=O)N(C2=NC(=NC=C12)NC3=NC=C(C=C3)N4CCNCC4)C5CCCC5)C(=O)C	0.6444092636032414	GDSC1

Running ``aixportcmd.py train`` writes algorithm-specific output RO-Crates
under ``<output>/trainedmodels``.  Each subdirectory includes the fitted model (for example,
``model.pt`` or ``model.pkl``), and a ``train_predictions.txt`` file that
captures in-sample predictions.

Testing RO-Crates
-----------------

Testing crates use the same feature tables as the training crates and includes a file with test data on which predictions are to be made:

- ``test_data.txt``:
    Tab-delimited table with one row per inference request.  Columns mirror
    ``training_data.txt`` (cell identifier, SMILES string, numeric response if
    available, and optional source label).

    .. code-block::

        EW24_BONE	CC1=C(C(=O)N(C2=NC(=NC=C12)NC3=NC=C(C=C3)N4CCNCC4)C5CCCC5)C(=O)C	0.98852067122827	GDSC1
        OCILY7_HAEMATOPOIETIC_AND_LYMPHOID_TISSUE	CC1=C(C(=O)N(C2=NC(=NC=C12)NC3=NC=C(C=C3)N4CCNCC4)C5CCCC5)C(=O)C	0.2728634745574858	GDSC1

``aixportcmd.py predict`` pairs each ``*_test_rocrate`` with the corresponding
trained model directory (``<dataset>_train_rocrate_<algorithm>``).  The command
generates per-algorithm output directories beneath
``<output>/predictions`` that contain RO-Crate metadata, prediction scores, and
any algorithm-specific logs.

