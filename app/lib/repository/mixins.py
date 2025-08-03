"""
Reusable mixins for repository / service layers
===============================================

Combine these mixins with your concrete repository classes to add
high‑level helpers such as:

* *get‑or‑create* and *update‑or‑create*
* full‑text search, date‑range filtering, “last N days”
* audit‑trail shortcuts (created_by / updated_by / deleted_by)
* basic aggregation statistics
* in‑process query caching

All mixins assume the hosting class exposes at least:

* ``model_class`` – the SQLAlchemy model being managed
* ``session``      – the active SQLAlchemy session
* ``create``       – a method that inserts a new entity
* ``get_by_id``    – a method that fetches by primary key

If you are building on top of the generic ``BaseRepository`` I sent earlier,
everything will work out of the box.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Generic, List, Optional, Tuple, TypeVar

from flask_sqlalchemy.model import Model as _Model
from sqlalchemy import func, or_

# --------------------------------------------------------------------------- #
# Generic typing helpers                                                      #
# --------------------------------------------------------------------------- #
M = TypeVar("M", bound=_Model)


# --------------------------------------------------------------------------- #
# CRUD convenience                                                            #
# --------------------------------------------------------------------------- #
class RepositoryMixin(Generic[M]):
    """Add *get_or_create* and *update_or_create* helpers."""

    def get_or_create(
        self,
        defaults: Optional[Dict[str, Any]] = None,
        **lookup: Any,
    ) -> Tuple[M, bool]:
        """
        Fetch an entity matching *lookup* or create it with *defaults*.

        Returns
        -------
        (entity, created)
            ``created`` is *True* if a new row was inserted.
        """
        entity: Optional[M] = self.model_class.query.filter_by(**lookup).first()

        if entity is not None:
            return entity, False

        create_kwargs = {**lookup, **(defaults or {})}
        entity = self.create(**create_kwargs)  # type: ignore[arg-type]
        return entity, True

    def update_or_create(
        self,
        defaults: Optional[Dict[str, Any]] = None,
        **lookup: Any,
    ) -> Tuple[M, bool]:
        """
        Update an existing entity or create a new one.

        *defaults* are applied to the update or to the insert.
        """
        entity: Optional[M] = self.model_class.query.filter_by(**lookup).first()

        if entity is not None:
            if defaults:
                for k, v in defaults.items():
                    if hasattr(entity, k):
                        setattr(entity, k, v)
                self.session.commit()  # type: ignore[attr-defined]
            return entity, False

        create_kwargs = {**lookup, **(defaults or {})}
        entity = self.create(**create_kwargs)  # type: ignore[arg-type]
        return entity, True


# --------------------------------------------------------------------------- #
# Search helpers                                                              #
# --------------------------------------------------------------------------- #
class SearchMixin(Generic[M]):
    """Full‑text search and date‑range shortcuts."""

    def search(self, phrase: str, fields: List[str]) -> List[M]:
        """
        Case‑insensitive LIKE search across *fields*.

        If *phrase* is empty or no valid fields are given, returns ``[]``.
        """
        if not phrase or not fields:
            return []

        conditions = [
            getattr(self.model_class, f).ilike(f"%{phrase}%")
            for f in fields
            if hasattr(self.model_class, f)
        ]

        if not conditions:
            return []

        return self.model_class.query.filter(or_(*conditions)).all()

    def filter_by_date_range(
        self,
        date_field: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[M]:
        """Return rows where *date_field* is between *start* and *end*."""
        if not hasattr(self.model_class, date_field):
            return []

        query = self.model_class.query
        column = getattr(self.model_class, date_field)

        if start:
            query = query.filter(column >= start)
        if end:
            query = query.filter(column <= end)

        return query.all()

    def get_recent(
        self,
        date_field: str = "created_at",
        days: int = 7,
    ) -> List[M]:
        """Shorthand for “created in the last *N* days”."""
        if not hasattr(self.model_class, date_field):
            return []

        cutoff = datetime.utcnow() - timedelta(days=days)
        column = getattr(self.model_class, date_field)
        return self.model_class.query.filter(column >= cutoff).all()


# --------------------------------------------------------------------------- #
# Audit helpers                                                               #
# --------------------------------------------------------------------------- #
class AuditMixin(Generic[M]):
    """Quick accessors for *created_by*, *updated_by*, *deleted_by* columns."""

    def _filter_by_user(self, field: str, user_id: int) -> List[M]:
        if not hasattr(self.model_class, field):
            return []
        return self.model_class.query.filter_by(**{field: user_id}).all()

    def get_created_by_user(self, user_id: int) -> List[M]:
        return self._filter_by_user("created_by", user_id)

    def get_updated_by_user(self, user_id: int) -> List[M]:
        return self._filter_by_user("updated_by", user_id)

    # soft‑delete aware
    def get_deleted_by_user(self, user_id: int) -> List[M]:
        return self._filter_by_user("deleted_by", user_id)

    # full audit dump
    def get_audit_trail(self, entity_id: int) -> Dict[str, Any]:
        entity: Optional[M] = self.get_by_id(entity_id)  # type: ignore[attr-defined]
        if entity is None:
            return {}

        trail: Dict[str, Any] = {
            "entity_id": entity_id,
            "entity_type": self.model_class.__name__,
        }

        for attr in (
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "deleted_at",
            "deleted_by",
        ):
            if hasattr(entity, attr):
                trail[attr] = getattr(entity, attr)

        return trail


# --------------------------------------------------------------------------- #
# Basic aggregations                                                          #
# --------------------------------------------------------------------------- #
class StatsMixin(Generic[M]):
    """Aggregate counts by arbitrary field or by calendar period."""

    def get_count_by_field(self, field: str) -> Dict[Any, int]:
        if not hasattr(self.model_class, field):
            return {}

        column = getattr(self.model_class, field)
        rows = (
            self.session.query(column, func.count())  # type: ignore[attr-defined]
            .group_by(column)
            .all()
        )
        return {value: count for value, count in rows}

    def get_stats_by_date(
        self,
        date_field: str = "created_at",
        group_by: str = "day",
    ) -> Dict[str, int]:
        """
        Group by *day*, *week*, *month*, or *year*.

        Returns ``{"2025‑07‑15": 12, ...}`` for day grouping,
        ``{"2025‑W29": 34}`` for week, etc.
        """
        if not hasattr(self.model_class, date_field):
            return {}

        column = getattr(self.model_class, date_field)

        match group_by:
            case "day":
                period = func.date(column)
            case "week":
                period = func.strftime("%Y‑W%W", column)
            case "month":
                period = func.strftime("%Y‑%m", column)
            case "year":
                period = func.strftime("%Y", column)
            case _:
                period = func.date(column)

        rows = (
            self.session.query(period.label("p"), func.count().label("c"))  # type: ignore[attr-defined]
            .group_by("p")
            .order_by("p")
            .all()
        )
        return {str(p): c for p, c in rows}


# --------------------------------------------------------------------------- #
# Simple in‑memory cache                                                      #
# --------------------------------------------------------------------------- #
class CacheMixin:
    """
    A very lightweight cache for expensive queries.

    *Not* thread‑safe and resets when the process restarts.
    Plug a proper cache (Redis, Flask‑Caching) for production workloads.
    """

    _cache_timeout: int = 300  # seconds

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # type: ignore[misc]
        self._cache: Dict[str, Dict[str, Any]] = {}

    # ───────────────────────── internal helpers ───────────────────────── #
    def _cache_key(self, method: str, *args, **kwargs) -> str:
        parts = [self.model_class.__name__, method]
        parts += [str(a) for a in args]
        parts += [f"{k}={v}" for k, v in sorted(kwargs.items())]
        return ":".join(parts)

    def _cache_valid(self, entry: Dict[str, Any]) -> bool:
        if not entry:
            return False
        return (datetime.utcnow().timestamp() - entry["ts"]) < self._cache_timeout

    # ───────────────────────── public api ─────────────────────────────── #
    def cached_query(self, method: str, func, *args, **kwargs):
        """
        Execute *func* and cache its result under a composite key.

        Use like:

        ```python
        def list_active(self):
            return self.cached_query("list_active", lambda: self.get_active())
        ```
        """
        key = self._cache_key(method, *args, **kwargs)
        entry = self._cache.get(key)

        if self._cache_valid(entry):
            return entry["data"]

        data = func(*args, **kwargs)
        self._cache[key] = {"data": data, "ts": datetime.utcnow().timestamp()}
        return data

    def clear_cache(self, pattern: str | None = None):
        """Clear the whole cache or only keys containing *pattern*."""
        if pattern is None:
            self._cache.clear()
        else:
            for k in list(self._cache):
                if pattern in k:
                    self._cache.pop(k, None)
