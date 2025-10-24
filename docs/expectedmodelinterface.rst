============================
Expected Model Interface
============================

The benchmark platform invokes algorithm wrappers through a single command line
interface.  Any model intended for integration MUST implement the arguments and
behaviours described in this document.

Command Line Signature
----------------------

.. code-block:: console

   $ ./model_wrapper.py <OUTPUT> --mode {train,test,predict,optimizetrain} \
        --input_crate </path/to/input_rocrate> \
        --model </path/to/trained_model_rocrate>

``<OUTPUT>``
    Destination directory where the implementation writes the output RO-Crate.
    The folder MUST be created by the model wrapper and contain a valid
    ``ro-crate-metadata.json`` manifest.

``--mode {train,test,predict,optimizetrain}``
    Selects the execution flow. ``train`` is resposible for training the model,
    ``test`` and ``predict`` are synonyms and are responsible for making prediction. 
    ``optimizetrain`` triggers hyperparameter optimization prior to training.

``--input_crate`` ``</path/to/input_rocrate>``
    Absolute or relative path to the input RO-Crate.  For ``train`` and
    ``optimizetrain`` this is a training crate; for ``test``/``predict`` it is
    a testing crate.  The flag name is fixed to ``--input_crate`` so the
    benchmark launcher can invoke all models uniformly.

``--model`` ``</path/to/trained_model_rocrate>``
    Path to a trained model RO-Crate.  The crate MUST contain:

    - a model (``model.pkl``, ``model.pt``, or similar)
    - a ``config.yml`` file capturing the hyperparameters used to produce the
      model

    ``--model`` is mandatory for ``test``/``predict`` and optional for
    ``train``/``optimizetrain`` when training from scratch.

Behavioural Requirements
------------------------

- ``train``:

  * Consume the provided training RO-Crate and configuration (if any) and emit
    a new trained model RO-Crate under ``<OUTPUT>``.
  * The output crate MUST include a ``config.yml`` file describing the exact
    settings used to produce the model.  Implementations should merge supplied
    values with defaults to ensure the file is exhaustive.
  * If the input ``config.yml`` specifies a range (for example,
    ``learning_rate: [0.001, 0.005, 0.01]``), the command MUST fail with a
    clear error message.  Range exploration is reserved for
    ``optimizetrain`` mode.

- ``test``/``predict``:

  * Treat ``test`` and ``predict`` as identical aliases.
  * Require ``--model`` pointing at a trained model RO-Crate.  The command
    should fail if the crate lacks both ``model.*`` and ``config.yml``.
  * Write prediction outputs into ``<OUTPUT>``, including any mode-specific
    result files (for example, ``predictions.txt``) and the usual RO-Crate
    metadata.

- ``optimizetrain``:

  * Use the provided training RO-Crate together with the ``config.yml`` ranges
    to search the hyperparameter space.
  * The resulting output RO-Crate MUST include the optimal hyperparameter set
    (in ``config.yml``).
  * If the supplied configuration lacks ranges, fall back to the single value
    behaviour used in ``train`` mode.

General Expectations
--------------------

- Implementations SHOULD exit with a non-zero code and descriptive error
  message on any validation failure (missing files, malformed RO-Crates, or
  illegal argument combinations).
- All paths passed via the CLI are expected to be absolute or relative to the
  current working directory; tools MUST NOT change directories implicitly.
- Additional optional flags are allowed, but they must not conflict with the
  required contract above.
