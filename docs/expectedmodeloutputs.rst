=================================
Expected Model Outputs
=================================

The mode of invocation (``test``/``predict``, ``train``, ``optimizetrain``)
denotes the expected structure of the *output*. For **all** modes the output
MUST be a valid `RO-Crate <https://www.researchobject.org>`_ written under
the directory given as the ``<OUTPUT>`` argument:

.. code-block:: bash

   $ ./<MODEL COMMAND LINE> <OUTPUT> \
       --mode {train,test,predict,optimizetrain} \
       --input_crate </path/to/input_rocrate> \
       --model </path/to/trained_model_rocrate>

The model wrapper is responsible for:

* creating the ``<OUTPUT>`` directory if it does not exist;
* writing a standards-compliant ``ro-crate-metadata.json`` manifest there;
* placing all result files inside the crate (under ``<OUTPUT>``).

The sections below describe the expected layout of the output RO-Crate for
each mode.

Train Mode
----------

In ``train`` mode the model wrapper receives a **training RO-Crate** via
``--input_crate`` and is expected to emit a **trained model RO-Crate**
under ``<OUTPUT>``. The crate produced in this mode is later passed to
``test``/``predict`` via the ``--model`` flag.

High-level behaviour
~~~~~~~~~~~~~~~~~~~~

* Consume the training crate referenced by ``--input_crate``.
* Optionally honour an external configuration file passed with
  ``--config_file``.
* Train the model.
* Write a *trained model RO-Crate* under ``<OUTPUT>``.
* Exit with code ``0`` on success and a non-zero code with a clear error
  message on failure (missing files, malformed crate, etc.).

Required crate contents
~~~~~~~~~~~~~~~~~~~~~~~

The trained model RO-Crate MUST contain at least:

* ``ro-crate-metadata.json``

  * Standard RO-Crate JSON-LD manifest describing the crate.
  * The root dataset SHOULD describe the trained model (name, version,
    algorithm family, training dataset, etc.).

* Model artifact

  * A serialised model object, for example:

    * ``model.pt`` (PyTorch),
    * ``model.pkl`` (scikit-learn),
    * or another well-documented format.

  * The file SHOULD be referenced from the manifest as a
    ``File``/``Dataset`` with an appropriate ``@type`` or
    ``additionalType``.

* ``config.yml``

  * A YAML configuration file capturing the *effective* hyperparameters
    and settings used during training (including defaults that were not
    explicitly passed on the command line).
  * Implementations SHOULD merge user-provided values with defaults so
    that ``config.yml`` is self-contained.

* ``train_predictions.txt``

  * In-sample predictions on the training data, to enable downstream
    benchmarking and diagnostics.
  * Tab-delimited text with at least:

    #. Sample identifier (e.g. cell line or sample ID).
    #. Drug / compound identifier (e.g. SMILES).
    #. Observed response (if available).
    #. Predicted response.

  * Additional columns (e.g. uncertainty, replicate ID, source) are
    allowed but MUST be documented in the crate metadata.

Recommended / optional files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The crate MAY also include:

* ``metrics.json`` or ``metrics.tsv`` with aggregated performance metrics
  (e.g. Pearson/Spearman correlation, RMSE, R\ :sup:`2`\ ).
* Training logs (e.g. ``training.log``) referenced from the manifest.
* Plots (e.g. learning curves, prediction vs. truth scatter plots).

If such files are present, they SHOULD be linked from the RO-Crate graph
so that automated tooling can discover them.

Constraints on configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In ``train`` mode, ``config.yml`` (whether generated or supplied) MUST NOT
encode hyperparameter *ranges*. Range-based search is reserved for
``optimizetrain``. If a range (e.g. a list of learning rates) is detected,
the model SHOULD fail with a clear, actionable error message.

Optimize Train Mode
-------------------

``optimizetrain`` extends ``train`` by performing hyperparameter search
before producing a final trained model. It consumes a **training
RO-Crate** via ``--input_crate`` and produces a **trained model
RO-Crate** under ``<OUTPUT>`` that is structurally compatible with the
``train`` output.

High-level behaviour
~~~~~~~~~~~~~~~~~~~~

* Read the training crate given by ``--input_crate``.
* Read hyperparameter ranges from ``config.yml`` (either supplied via
  ``--config_file`` or discovered from the model crate / defaults).
* Explore the specified hyperparameter space using the implementation’s
  preferred strategy (grid search, random search, Bayesian optimisation,
  etc.).
* Select a single “best” configuration according to a clearly defined
  objective (e.g. mean cross-validated correlation).
* Train a final model using that configuration.
* Emit a trained model RO-Crate containing **only the chosen
  hyperparameter set** as the effective configuration.

Required crate contents
~~~~~~~~~~~~~~~~~~~~~~~

The ``optimizetrain`` output crate MUST contain at least the same files
required for ``train``:

* ``ro-crate-metadata.json``

* Model artifact (e.g. ``model.pt`` or ``model.pkl``)

* Final ``config.yml`` with *single* hyperparameter values

* **Copy of the input optimisation configuration**:
  ``input_config.yml``
  This MUST be a **verbatim copy** of the configuration file used to
  define the hyperparameter search space, including any parameter ranges.

  *The purpose is to preserve the provenance of the optimisation
  procedure independent of the final chosen configuration.*

* ``predictions.txt`` for the final trained model

The metadata SHOULD clearly indicate that the model was obtained through
hyperparameter optimisation (for example via a dedicated property or
human-readable description).

Recommended / optional files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Implementations are encouraged to expose optimisation details as part of
the crate, for example:

* ``optimization_history.tsv``

  * One row per trial with hyperparameters and resulting score.

* ``best_config.yml``

  * A copy of the chosen configuration (may be identical to
    ``config.yml``).

* Diagnostic plots (e.g. score vs. hyperparameter value).

These files SHOULD be referenced from the manifest so they can be
discovered programmatically.

Missing or incompatible ranges
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If the supplied configuration does **not** contain ranges (only single
values), the model MAY fall back to the behaviour of ``train`` mode:

* treat the configuration as fixed;
* train once;
* still emit a valid trained model RO-Crate.

In that case, implementations SHOULD document in the metadata that no
hyperparameter search was performed.

Test/Predict Mode
-----------------

``test`` and ``predict`` are treated as synonyms and share the same
output structure. In this mode the model receives:

* a **testing RO-Crate** via ``--input_crate``, and
* a **trained model RO-Crate** via ``--model``.

The model must load the model, apply it to the test data, and emit a
**prediction RO-Crate** under ``<OUTPUT>``.

High-level behaviour
~~~~~~~~~~~~~~~~~~~~

* Require a valid trained model RO-Crate path passed with ``--model``.
* Consume the test crate referenced by ``--input_crate``.
* Apply the trained model to all test observations.
* Write a prediction RO-Crate under ``<OUTPUT>``.
* Fail fast (non-zero exit code) when:

  * ``--model`` is missing;
  * the model crate does not contain both a model artifact and
    ``config.yml``;
  * the test crate is malformed or incompatible with the model.

Required crate contents
~~~~~~~~~~~~~~~~~~~~~~~

The prediction RO-Crate MUST contain:

* ``ro-crate-metadata.json``

  * Root dataset describing this particular prediction run (model
    used, input test crate, timestamp, etc.).
  * References to both:

    * the test crate used as input, and
    * the trained model crate provided via ``--model``.

* ``predictions.txt``

  * Tab-delimited table with one row per inference request.
  * Columns SHOULD include at least:

    #. Sample identifier.
    #. Drug / compound identifier.
    #. Predicted response value.

  * If the ground-truth response is available in the test crate, it may
    be repeated here to simplify downstream evaluation.

Implementations MAY choose a different filename for the predictions
table (e.g. ``predictions.tsv`` or ``scores.txt``) but MUST document the
schema in the crate metadata.

Recommended / optional files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Prediction crates may also include:

* ``metrics.json`` / ``metrics.tsv``

  * If ground-truth responses are available, basic evaluation
    metrics (correlations, RMSE, etc.) computed on the test set.

* Algorithm-specific logs (e.g. ``predict.log``).

* Plots (e.g. prediction vs. truth, residual histograms).

As with the other modes, any such artefacts SHOULD be linked from the
RO-Crate graph to make them machine-discoverable.

General Notes on RO-Crate Compliance
------------------------------------

Across all modes:

* ``<OUTPUT>`` MUST be the *root* of an RO-Crate.
* All files produced by the model SHOULD live inside ``<OUTPUT>``.
* The crate MUST remain self-contained:

  * no hard-coded absolute paths inside the metadata;
  * all referenced files present within the crate directory.

* Additional optional CLI flags are allowed, but they must not break the
  contract above or change the overall output structure in a way that
  would prevent automated benchmarking or downstream pipelines from
  consuming the crate.
