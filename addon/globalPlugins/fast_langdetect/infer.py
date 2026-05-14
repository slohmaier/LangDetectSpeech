# -*- coding: utf-8 -*-
"""
FastText-based language detection.

Vendored and trimmed from fast-langdetect 1.0.x
(https://github.com/LlmKira/fast-langdetect, MIT licence). The upstream package
optionally downloads the full lid.176.bin model at runtime; this addon ships
only the bundled lite model (lid.176.ftz), so the download path and the
robust_downloader dependency have been removed. The public API the addon uses
(LangDetector, LangDetectConfig, detect) is preserved.
"""

import logging
import os
import platform
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from . import fasttext

logger = logging.getLogger(__name__)

_LOCAL_SMALL_MODEL_PATH = Path(__file__).parent / "resources" / "lid.176.ftz"


class FastLangdetectError(Exception):
	"""Base exception for library-specific failures."""
	pass


class ModelLoadError(FastLangdetectError):
	"""Raised when a FastText model fails to load."""
	pass


class ModelLoader:
	"""Model loading and caching handler."""

	def load_local(self, model_path: Path) -> Any:
		"""Load model from local file."""
		if not model_path.exists():
			raise FileNotFoundError(f"Model file not found: {model_path}")

		if platform.system() == "Windows":
			return self._load_windows_compatible(model_path)
		return self._load_unix(model_path)

	def _load_windows_compatible(self, model_path: Path) -> Any:
		"""
		Handle Windows path compatibility issues when loading FastText models.

		Attempts multiple strategies in order:
		1. Direct loading if path contains only safe characters
		2. Loading via relative path if possible
		3. Copying to temporary file as last resort
		"""
		model_path_str = str(model_path.resolve())

		try:
			return fasttext.load_model(model_path_str)
		except Exception as e:
			logger.debug(f"fast-langdetect: Load model failed: {e}")

		try:
			cwd = Path.cwd()
			rel_path = os.path.relpath(model_path, cwd)
			return fasttext.load_model(rel_path)
		except Exception as e:
			logger.debug(f"fast-langdetect: Failed to load model using relative path: {e}")

		logger.debug(f"fast-langdetect: Using temporary file to load model: {model_path}")
		tmp_path = None
		try:
			tmp_fd, tmp_path = tempfile.mkstemp(suffix='.bin')
			os.close(tmp_fd)
			shutil.copy2(model_path, tmp_path)
			return fasttext.load_model(tmp_path)
		except Exception as e:
			raise ModelLoadError(f"Failed to load model using temporary file: {e}") from e
		finally:
			if tmp_path and os.path.exists(tmp_path):
				try:
					os.unlink(tmp_path)
				except (OSError, PermissionError) as e:
					logger.warning(f"fast-langdetect: Failed to delete temporary file {tmp_path}: {e}")
					if platform.system() == "Windows":
						try:
							import _winapi
							_winapi.MoveFileEx(tmp_path, None, _winapi.MOVEFILE_DELAY_UNTIL_REBOOT)
						except (ImportError, AttributeError, OSError) as we:
							logger.warning(f"fast-langdetect: Failed to schedule file deletion: {we}")

	def _load_unix(self, model_path: Path) -> Any:
		"""Load model on Unix-like systems."""
		try:
			return fasttext.load_model(str(model_path))
		except Exception as e:
			raise ModelLoadError(f"fast-langdetect: Failed to load model: {e}") from e


class LangDetectConfig:
	"""
	Configuration for language detection.

	The addon ships only the bundled lite model; ``model`` is kept for API
	compatibility with upstream fast-langdetect but only "lite" is supported.
	"""

	def __init__(
		self,
		custom_model_path: Optional[str] = None,
		normalize_input: bool = True,
		max_input_length: Optional[int] = 80,
		model: Literal["lite"] = "lite",
	):
		self.custom_model_path = custom_model_path
		self.normalize_input = normalize_input
		self.max_input_length = max_input_length
		self.model: Literal["lite"] = "lite"
		if self.custom_model_path and not Path(self.custom_model_path).exists():
			raise FileNotFoundError(f"fast-langdetect: Target model file not found: {self.custom_model_path}")


class LangDetector:
	"""Language detector using the bundled FastText lite model."""

	def __init__(self, config: Optional[LangDetectConfig] = None):
		self._model: Any = None
		self.config = config or LangDetectConfig()
		self._model_loader = ModelLoader()

	def _preprocess_text(self, text: str) -> str:
		"""Replace newlines (FastText errors on them) and truncate if configured."""
		if "\n" in text:
			text = text.replace("\n", " ")
		if self.config.max_input_length is not None and len(text) > self.config.max_input_length:
			logger.info(
				f"fast-langdetect: Truncating input from {len(text)} to "
				f"{self.config.max_input_length} characters; may reduce accuracy."
			)
			text = text[: self.config.max_input_length]
		return text

	@staticmethod
	def _normalize_text(text: str, should_normalize: bool = False) -> str:
		"""Lowercase mostly-uppercase strings to avoid misdetection as Japanese.

		See https://github.com/LlmKira/fast-langdetect/issues/14
		"""
		if not should_normalize:
			return text
		if text.isupper() or (
			len(re.findall(r'[A-Z]', text)) > 0.8 * len(re.findall(r'[A-Za-z]', text))
			and len(text) > 5
		):
			return text.lower()
		return text

	def _get_model(self) -> Any:
		"""Get or load the bundled lite model."""
		if self._model is not None:
			return self._model
		model_path = (
			Path(self.config.custom_model_path)
			if self.config.custom_model_path is not None
			else _LOCAL_SMALL_MODEL_PATH
		)
		self._model = self._model_loader.load_local(model_path)
		return self._model

	def detect(
		self,
		text: str,
		*,
		k: int = 1,
		threshold: float = 0.0,
	) -> List[Dict[str, Any]]:
		"""
		Detect language candidates. Always returns a list of results.

		:raises FastLangdetectError: For library-specific failures
		:raises Exception: Standard Python exceptions propagate (e.g. FileNotFoundError)
		"""
		ft_model = self._get_model()
		text = self._preprocess_text(text)
		normalized_text = self._normalize_text(text, self.config.normalize_input)
		labels, scores = ft_model.predict(normalized_text, k=k, threshold=threshold)
		results = [
			{
				"lang": label.replace("__label__", ""),
				"score": min(float(score), 1.0),
			}
			for label, score in zip(labels, scores)
		]
		return sorted(results, key=lambda x: x["score"], reverse=True)


_default_detector = LangDetector()


def detect(
	text: str,
	*,
	k: int = 1,
	threshold: float = 0.0,
	config: Optional[LangDetectConfig] = None,
) -> List[Dict[str, Union[str, float]]]:
	detector = LangDetector(config) if config is not None else _default_detector
	return detector.detect(text, k=k, threshold=threshold)
