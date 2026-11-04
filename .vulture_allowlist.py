"""
Vulture allowlist — symbols reported as unused that are intentionally kept.

Vulture scans only the application source (`src/spellbot` and `scripts`), not the test
suite, so any source symbol exercised solely by tests looks unused to it. It also can't see
references made through framework conventions, type-only annotations, TypedDict keys, or
Jinja templates. Referencing a name here marks it "used" so vulture stops reporting it.

Check with `uv run vulture`; regenerate candidates with `uv run vulture --make-whitelist`.
Prefer deleting genuinely dead code over adding it here.
"""

from __future__ import annotations

_.color  # unused attribute (src/spellbot/actions/admin_action.py:60)
_.color  # unused attribute (src/spellbot/actions/admin_action.py:104)
_.color  # unused attribute (src/spellbot/actions/admin_action.py:114)
_.color  # unused attribute (src/spellbot/actions/admin_action.py:237)
_.color  # unused attribute (src/spellbot/actions/admin_action.py:332)
_.color  # unused attribute (src/spellbot/actions/lfg_action.py:692)
_.color  # unused attribute (src/spellbot/actions/lfg_action.py:708)
_.color  # unused attribute (src/spellbot/actions/lfg_action.py:860)
_.color  # unused attribute (src/spellbot/actions/record_action.py:36)
_.color  # unused attribute (src/spellbot/actions/record_action.py:51)
_.color  # unused attribute (src/spellbot/actions/record_action.py:83)
_.color  # unused attribute (src/spellbot/actions/watch_action.py:127)
cache_ok  # unused variable (src/spellbot/audit.py:69)
get_col_spec  # unused method (src/spellbot/audit.py:71)
kw  # unused variable (src/spellbot/audit.py:71)
native_transaction_id  # unused variable (src/spellbot/audit.py:89)
client_addr  # unused variable (src/spellbot/audit.py:91)
schema_name  # unused variable (src/spellbot/audit.py:101)
relid  # unused variable (src/spellbot/audit.py:103)
install  # unused function (src/spellbot/audit.py:154)
attach_triggers  # unused function (src/spellbot/audit.py:165)
uninstall  # unused function (src/spellbot/audit.py:182)
_.message_content  # unused attribute (src/spellbot/client.py:87)
_.messages  # unused attribute (src/spellbot/client.py:88)
_.fetch_application_emojis  # unused attribute (src/spellbot/client.py:313)
_.color  # unused attribute (src/spellbot/cogs/about_cog.py:47)
_.color  # unused attribute (src/spellbot/data/game_data.py:234)
_.color  # unused attribute (src/spellbot/data/game_data.py:240)
__class_getitem__  # unused function (src/spellbot/database.py:35)
rollback_transaction  # unused function (src/spellbot/database.py:201)
_._value_  # unused attribute (src/spellbot/enums.py:20)
_._value_  # unused attribute (src/spellbot/enums.py:90)
_._value_  # unused attribute (src/spellbot/enums.py:163)
# Columns retained from the removed user verification feature so that its data isn't lost.
verified_only  # unused variable (src/spellbot/models/award.py:60)
unverified_only  # unused variable (src/spellbot/models/award.py:67)
unverified_only  # unused variable (src/spellbot/models/channel.py:103)
verified_only  # unused variable (src/spellbot/models/channel.py:110)

# `__exit__` overrides must accept the exception details even when they don't read them.
exc_val  # unused variable (tests/test_metrics.py:87)
exc_tb  # unused variable (tests/test_metrics.py:88)
