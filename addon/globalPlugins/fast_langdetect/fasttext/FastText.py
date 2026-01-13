# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import os
import glob as _glob
import importlib.util

# Find the pyd file in parent directory
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_pyd_pattern = os.path.join(_parent_dir, "fasttext_pybind*.pyd")
_pyd_files = _glob.glob(_pyd_pattern)
if not _pyd_files:
    raise ImportError(f"Cannot find fasttext_pybind*.pyd in {_parent_dir}")

# Load the pyd module directly using importlib
_pyd_path = _pyd_files[0]
_spec = importlib.util.spec_from_file_location("fasttext_pybind", _pyd_path)
fasttext = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fasttext)


class _FastText(object):
    """
    This class defines the API to inspect models and should not be used to
    create objects. It will be returned by functions such as load_model or
    train.

    In general this API assumes to be given only unicode for Python2 and the
    Python3 equvalent called str for any string-like arguments. All unicode
    strings are then encoded as UTF-8 and fed to the fastText C++ API.
    """

    def __init__(self, model_path=None, args=None):
        self.f = fasttext.fasttext()
        if model_path is not None:
            self.f.loadModel(model_path)
        if args is not None:
            raise RuntimeError('args argument is not supported')

    def predict(self, text, k=1, threshold=0.0, on_unicode_error='strict'):
        """
        Given a string, get a list of labels and a list of
        corresponding probabilities. k controls the number
        of returned labels. A choice of 5, will return the 5
        most probable labels. By default this returns only
        the most likely label and probability. threshold filters
        the returned labels by a threshold on probability. A
        choice of 0.5 will return labels with at least 0.5
        probability. k and threshold will be applied together to
        determine the returned labels.

        This function assumes to be given
        a single line of text. We split words on whitespace (space,
        newline, tab, vertical tab) and the control characters carriage
        return, formfeed and the null character.

        If the model is not supervised, this function will throw a ValueError.

        If given a list of strings, it will return a list of results as usually
        received for a single line of text.
        """

        def check(entry):
            if entry.find('\n') != -1:
                raise ValueError(
                    "predict processes one line at a time (remove \'\\n\')"
                )
            entry += "\n"
            return entry

        if type(text) == list:
            text = [check(entry) for entry in text]
            all_labels, all_probs = self.f.multilinePredict(
                text, k, threshold, on_unicode_error)

            return all_labels, all_probs
        else:
            text = check(text)
            predictions = self.f.predict(text, k, threshold, on_unicode_error)
            if predictions:
                probs, labels = zip(*predictions)
            else:
                probs, labels = ([], ())
            return (labels, probs)


def load_model(path):
    """Load a model given a filepath and return a model object."""
    return _FastText(model_path=path)
