"""Data provider plugins.

Every module here that defines a `@register`-decorated `BaseProvider` subclass
is auto-discovered by `numint.core.registry.discover()`. To add a new source,
drop one file in this package - no other wiring needed.
"""
