"""exform — reshape text by example (deterministic, offline, no LLM)."""

from .synth import Program, SynthesisError, synthesize

__version__ = "0.3.1"
__all__ = ["synthesize", "Program", "SynthesisError", "__version__"]
