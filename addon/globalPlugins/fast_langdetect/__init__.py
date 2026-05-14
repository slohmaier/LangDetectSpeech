# -*- coding: utf-8 -*-
"""
Vendored subset of fast-langdetect 1.0.x (https://github.com/LlmKira/fast-langdetect, MIT).

Only the API used by LangDetectSpeech is re-exported.
"""

from .infer import (  # noqa: F401
	FastLangdetectError,
	LangDetectConfig,
	LangDetector,
	ModelLoadError,
	detect,
)
