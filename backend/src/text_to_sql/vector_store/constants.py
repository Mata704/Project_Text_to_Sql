from pathlib import Path

DEFAULT_COLLECTION_NAME = "train_documentation"
DEFAULT_DISTANCE_METRIC = "cosine"
DEFAULT_VECTOR_STORE_BATCH_SIZE = 500
DEFAULT_PERSIST_DIRECTORY = Path(__file__).resolve().parents[3] / "data" / "chroma"
