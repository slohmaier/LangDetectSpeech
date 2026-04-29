# LangDetectSpeech - NVDA Addon

A lightweight NVDA addon that automatically detects the language of spoken text and switches to the appropriate synthesizer voice. Uses fast-langdetect (FastText-based) for efficient offline language detection across 176 languages.

Features:
- Lightweight and fast language detection using FastText
- Automatic voice switching based on detected language
- Whitelist for considered languages
- Configurable fallback languages

# Tested synthesizers

 - builtin One Core
 - IBM TTS ( https://github.com/davidacm/NVDA-IBMTTS-Driver )
 - Vocalizer NVDA ( https://vocalizer-nvda.com/ )

# Not working

 - CodeFactory Eloquence
 - Codefactory Vocalizer

# Bundled binary dependencies

This addon bundles `fasttext_pybind*.pyd` from the
[fasttext-predict](https://pypi.org/project/fasttext-predict/) package
([source](https://github.com/facebookresearch/fastText), MIT licence).
The `.pyd` files are taken unmodified from the official PyPI wheel.

## Included builds

| File | Python | NVDA version |
|------|--------|--------------|
| `fasttext_pybind.cp311-win32.pyd` | 3.11 32-bit | up to 2025.x |
| `fasttext_pybind.cp313-win_amd64.pyd` | 3.13 64-bit | 2026.x |

## Rebuilding for a new Python version

```powershell
pip download --no-deps --dest _deps `
    --python-version <X.Y> `
    --platform <win32|win_amd64> `
    --only-binary=:all: `
    fasttext-predict
Expand-Archive _deps\fasttext_predict-*.whl -DestinationPath _deps\extracted
Copy-Item _deps\extracted\fasttext_pybind.cpXY-<platform>.pyd addon\globalPlugins\fast_langdetect\
```
