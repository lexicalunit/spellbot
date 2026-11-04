#!/usr/bin/env python
# Copyright (c) 2026 spellbot@lexicalunit.com

"""
Bring every `<lang>.po` in line with `messages.pot` after editing the English strings.

New keys are added untranslated, so they show in English until translated. Removed keys
are dropped. A key whose English text changed keeps its old translation marked fuzzy,
which SpellBot ignores until a translator confirms or replaces it.
"""

from __future__ import annotations

from babel.messages.pofile import read_po, write_po

from spellbot.i18n import SOURCE_CATALOG, TRANSLATIONS_DIR

with SOURCE_CATALOG.open("rb") as fp:
    template = read_po(fp)

for path in sorted(TRANSLATIONS_DIR.glob("*.po")):
    with path.open("rb") as fp:
        catalog = read_po(fp)
    catalog.update(template, update_header_comment=False, update_creation_date=False)
    with path.open("wb") as fp:
        write_po(fp, catalog, width=0, ignore_obsolete=True, sort_output=False)
