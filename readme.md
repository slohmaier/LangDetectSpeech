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

This addon bundles a compiled native extension (`fasttext_pybind*.pyd`) from the
[fasttext-predict](https://pypi.org/project/fasttext-predict/) package, which provides
Python bindings for [Facebook's fastText](https://github.com/facebookresearch/fastText) library.
Native code is required because fastText's language detection relies on a C++ implementation;
no pure-Python equivalent exists with comparable speed and accuracy.

The `.pyd` files are **not built by this project** — they are taken unmodified from the official
`fasttext-predict` wheel on PyPI.

## Included builds

| File | Python | Architecture | NVDA version |
|------|--------|--------------|--------------|
| `fasttext_pybind.cp311-win32.pyd` | 3.11 | 32-bit | up to 2025.x |
| `fasttext_pybind.cp311-win_amd64.pyd` | 3.11 | 64-bit | IDE / stubs |
| `fasttext_pybind.cp313-win_amd64.pyd` | 3.13 | 64-bit | 2026.x |

## Rebuilding for a new Python version

If a future NVDA release upgrades Python, download the matching wheel and copy the `.pyd`:

```
pip download --no-deps --dest _deps \
    --python-version <X.Y> \
    --platform <win32|win_amd64> \
    --only-binary=:all: \
    fasttext-predict
# Extract the wheel (it is a zip archive) and copy the .pyd:
unzip _deps/fasttext_predict-*.whl -d _deps/extracted
copy _deps\extracted\fasttext_pybind.cpXY-<platform>.pyd addon\globalPlugins\fast_langdetect\
```

The source code of `fasttext-predict` is available at
https://github.com/facebookresearch/fastText under the MIT licence.
