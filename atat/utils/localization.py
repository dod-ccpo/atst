from functools import lru_cache

import yaml
from flask import current_app as app

from atat.utils import getattr_path


class LocalizationInvalidKeyError(Exception):
    def __init__(self, key, variables):
        self.key = key
        self.variables = variables

    def __str__(self):
        return "Requested {key} and variables {variables} with but an error occured".format(
            key=self.key, variables=self.variables
        )


@lru_cache(maxsize=None)
def _translations_file():
    file_name = "translations.yaml"

    if app:
        file_name = app.config.get("DEFAULT_TRANSLATIONS_FILE", file_name)

    # Non-ASCII characters such as smart quotes may be used in the translations
    # file and therefore it should be parsed as UTF-8
    with open(file_name, encoding="utf-8") as translations_file:
        return yaml.safe_load(translations_file)


def all_keys():
    translations = _translations_file()
    keys = []

    def _recursive_key_lookup(chain):
        results = getattr_path(translations, chain)
        if isinstance(results, str):
            keys.append(chain)
        else:
            [_recursive_key_lookup(".".join([chain, result])) for result in results]

    [_recursive_key_lookup(key) for key in translations]

    return keys


def translate(key, variables=None):
    translations = _translations_file()
    value = getattr_path(translations, key)

    if variables is None:
        variables = {}

    if value is None:
        raise LocalizationInvalidKeyError(key, variables)

    return value.format(**variables).replace("\n", "")
