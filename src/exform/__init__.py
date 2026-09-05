"""exform — reshape text by example (deterministic, offline, no LLM)."""

from .synth import Program, SynthesisError, synthesize

__version__ = "0.5.0"
__all__ = ["synthesize", "Program", "SynthesisError", "__version__"]
