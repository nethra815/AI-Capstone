"""Central settings. Everything tunable lives here or in env vars. No secrets are stored in code."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")  # real environment variables win over .env values
DOCS_DIR = Path(os.getenv("SPIT_DOCS_DIR", ROOT / "data" / "pdfs"))

# Real models (sentence-transformers downloads them on first run)
EMBED_MODEL = os.getenv("SPIT_EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
RERANK_MODEL = os.getenv("SPIT_RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

# Groq through its OpenAI-compatible API. Key comes from .env or the environment; never hard-coded.
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_MODEL = os.getenv("SPIT_LLM_MODEL", "llama-3.3-70b-versatile")  # confirm the model id in your Groq console

# A page with fewer text-layer words than this is treated as scanned, and its whole PDF is skipped (no OCR).
TEXT_LAYER_MIN_WORDS = 20

# Retrieval
TOP_K_RETRIEVE = 20
TOP_K_CONTEXT = 5
RRF_K = 60
MAX_CHUNK_WORDS = 170

# Evidence control (tune on a dev split, never on LLM self-confidence)
ABSTAIN_MIN_COVERAGE = float(os.getenv("SPIT_ABSTAIN_COVERAGE", "0.55"))
SUPPORT_MIN_RECALL = 0.7
MIN_QUERY_TERMS = 2
