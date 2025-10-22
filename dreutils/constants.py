

TRAINED_MODELS_DIRECTORY = 'trainedmodels'
"""
Name of directory where trained models reside under the train RO-Crate
"""

PREDICTIONS_DIRECTORY = 'predictions'
"""
Name of directory where prediction results are written
"""

TRAIN_PREDICTIONS = 'train_predictions.txt'
"""
Name of file containing training predictions
"""

MODEL_PREFIX = 'model'
"""
Prefix name of file containing trained model for algorithm
"""

MODEL_PKL = MODEL_PREFIX +'.pkl'
"""
Name of model file using Python Pickle object structure
"""

MODEL_PT = MODEL_PREFIX + '.pt'
"""
Name of model file using PyTorch object structure
"""

SUPPORTED_MODEL_FILES = [MODEL_PT, MODEL_PKL]
"""
All supported model file names
"""

CELL2CNAMPLIFICATION = 'cell2cnamplification.txt'
CELL2CNDELETION = 'cell2cndeletion.txt'
CELL2IND = 'cell2ind.txt'
CELL2MUTATION = 'cell2mutation.txt'
GENE2IND = 'gene2ind.txt'
TRAINING_DATA = 'training_data.txt'
