"""Merges the handlers of every handlers_*.py module (commands not handled in command.py)."""
from handlers_buildings import HANDLERS as _buildings
from handlers_economy import HANDLERS as _economy
from handlers_battle import HANDLERS as _battle

EXTRA_HANDLERS = {}
for _group in (_buildings, _economy, _battle):
    for _cmd, _fn in _group.items():
        assert _cmd not in EXTRA_HANDLERS, f"command '{_cmd}' handled twice"
        EXTRA_HANDLERS[_cmd] = _fn
