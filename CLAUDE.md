# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build Commands

```powershell
# Requires gettext (msgfmt) in PATH - install via: winget install GnuWin32.GetText
# Then add to PATH: $env:PATH += ";C:\Program Files (x86)\GnuWin32\bin"

# Build the addon (creates LangDetectSpeech-X.Y.Z.nvda-addon)
scons

# Build with specific version
scons version=0.5.0

# Build development version (adds date stamp)
scons dev=1

# Build and install directly to NVDA addons folder (requires NVDA restart)
scons install

# Generate translation template
scons pot

# Merge translations
scons mergePot

# Run linting
flake8 addon/globalPlugins/LangDetectSpeech.py
```

## Architecture Overview

LangDetectSpeech is a lightweight NVDA addon that automatically detects the language of spoken text and switches to the appropriate synthesizer voice. Uses fast-langdetect (FastText-based) for efficient offline language detection across 176 languages.

### Core Components

**`addon/globalPlugins/LangDetectSpeech.py`** - Main entry point
- `GlobalPlugin.__init__()` - Wraps `speech.speech.speak()` to intercept all speech sequences
- `checkSynth()` - Detects available synthesizer voices and wraps `synth.speak()`
- `fixSpeechSequence()` - Processes speech sequences to inject `LangChangeCommand`
- `predictLang()` - Uses fast-langdetect to predict language and update/create `LangChangeCommand`
- `LanguageIdentificationSettings` - Settings panel with language checkboxes and fallback config

**`addon/globalPlugins/fast_langdetect/`** - Bundled language detection library
- `infer.py` - LangDetector class using FastText model
- `fasttext/` - FastText Python wrapper
- `fasttext_pybind.cp311-win_amd64.pyd` - Compiled FastText binary (Python 3.11, Windows x64)
- `resources/lid.176.ftz` - Bundled lite model (~1MB, 176 languages)

### Data Flow

```
speech.speech.speak() called
    ↓ [wrapped by GlobalPlugin]
fixSpeechSequence(speechSequence)
    ↓
predictLang(text) → fast-langdetect → LangChangeCommand
    ↓
synth.speak() called with modified sequence
    ↓ [wrapped by checkSynth]
Synthesizer speaks with detected language voice
```

### Configuration

Stored in NVDA config under `[LangDetectSpeech]`:
- `whitelist` - Comma-separated list of enabled languages for detection
- `fallback` - Fallback languages when detection fails (default: "en,de")

### Key Global Variables (LangDetectSpeech.py)

- `synthClass` - Cached synthesizer class for optimization
- `synthLangs` - Dict mapping language codes to voice language settings
- `detector` - LangDetector instance (lazy initialized)

## Bundled Dependencies

The addon bundles fast-langdetect with its dependencies:
- `fasttext_pybind.cp311-win_amd64.pyd` - Compiled for Python 3.11 (NVDA's Python version)
- `lid.176.ftz` - FastText lite model for offline language detection

To update the .pyd for a different Python version:
```powershell
# NVDA uses 32-bit Python, so download win32 version
pip download --no-deps --dest _deps --python-version 3.11 --platform win32 --only-binary=:all: fasttext-predict
# Extract wheel and copy fasttext_pybind.cp311-win32.pyd to addon/globalPlugins/fast_langdetect/
unzip _deps/fasttext_predict-*.whl -d _deps/extracted
cp _deps/extracted/fasttext_pybind.cp311-win32.pyd addon/globalPlugins/fast_langdetect/
```

## NVDA API Reference

The NVDA API stubs are in `..\python-nvda\python\Lib\site-packages\` (use for IDE autocomplete and API reference). Key modules:
- `speech/` - Speech synthesis API
- `speech/commands.py` - `LangChangeCommand` and other speech commands
- `synthDriverHandler` - Synthesizer driver handling
- `globalPluginHandler` - Plugin base class
- `config` - NVDA configuration
- `gui/settingsDialogs.py` - Settings panel base class

### Current speak() signature (NVDA 2024+)

```python
def speak(
    speechSequence: SpeechSequence,
    symbolLevel: characterProcessing.SymbolLevel | None = None,
    priority: Spri = Spri.NORMAL,
):
```

## Working with Synthesizers

The plugin queries `synthDriverHandler.getSynth().availableVoices` to discover voice languages. Some synthesizers raise `NotImplementedError` - the code handles this by falling back to config-based language list.

**Tested working:** OneCore (built-in), IBM TTS, Vocalizer NVDA
**Not working:** CodeFactory Eloquence, CodeFactory Vocalizer

## Debugging

Start NVDA with logging to file, then read the log after startup:

```powershell
# Start NVDA with debug logging
& "$env:ProgramFiles (x86)\NVDA\nvda.exe" --debug-logging --log-file="$env:TEMP\nvda.log"

# Read the log file after testing
Get-Content "$env:TEMP\nvda.log" -Tail 100

# Or follow the log in real-time
Get-Content "$env:TEMP\nvda.log" -Wait -Tail 50
```

The addon logs with prefix `LANGPREDICT:` for voice detection and `LangDetectSpeech` for speech processing.

## Code Style

- Tab indentation (see flake8.ini)
- Max line length: 110
- Uses `_()` for translatable strings (requires `addonHandler.initTranslation()`)
