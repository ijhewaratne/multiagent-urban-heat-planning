"""
Street / cluster resolution for the Branitz orchestrator.

Maps raw street mentions (display names, partial matches, cluster IDs)
to valid cluster IDs (``ST###_...``).  Extracted from ``orchestrator.py``.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def get_available_streets() -> List[str]:
    """Load available cluster IDs from cluster index."""
    try:
        from branitz_heat_decision.ui.services import ClusterService

        svc = ClusterService()
        idx = svc.get_cluster_index()
        if not idx.empty:
            col = "cluster_id" if "cluster_id" in idx.columns else idx.columns[0]
            return idx[col].astype(str).tolist()
    except Exception:
        pass
    try:
        from branitz_heat_decision.config import DATA_PROCESSED

        sc = DATA_PROCESSED / "street_clusters.parquet"
        if sc.exists():
            import pandas as pd

            df = pd.read_parquet(sc)
            if not df.empty and "street_id" in df.columns:
                return df["street_id"].astype(str).tolist()
    except Exception:
        pass
    return []


def extract_street_from_query(user_query: str, context: Dict[str, Any]) -> Optional[str]:
    """Extract street/cluster from query using NLU and available streets."""
    from branitz_heat_decision.nlu import extract_street_entities

    available = context.get("available_streets") or get_available_streets()
    return extract_street_entities(user_query, available)


def resolve_cluster(
    raw_street_hint: Optional[str],
    user_query: str,
    cluster_id: Optional[str],
    memory_street: Optional[str],
    context: Dict[str, Any],
) -> "tuple[Optional[str], str]":
    """
    Map a raw street mention to a valid cluster_id (ST###_...).

    Priority order:
      1. If NLU extracted an explicit street -> resolve it (overrides everything)
      2. If cluster_id is a valid ST### from the UI/API -> keep it
      3. If conversation memory has a street -> use it for an implicit follow-up
      4. Otherwise extract from query text

    Returns:
        (cluster_id, resolver_method)
    """
    if raw_street_hint:
        # User explicitly mentioned a street — resolve it even if we already have a cluster_id
        if re.match(r"^ST\d{3}", raw_street_hint):
            return raw_street_hint, "NLU returned valid cluster_id"
        resolved = extract_street_from_query(raw_street_hint, context)
        if resolved:
            return resolved, "resolved from NLU entity"
        resolved = extract_street_from_query(user_query, context)
        if resolved:
            return resolved, "resolved from query (NLU hint failed)"
        return cluster_id, "failed — NLU hint did not match any cluster"

    if cluster_id and re.match(r"^ST\d{3}", cluster_id):
        return cluster_id, "pre-validated (UI/API selection)"

    if memory_street and re.match(r"^ST\d{3}", memory_street):
        # No explicit selection or query mention — preserve conversational continuity.
        return memory_street, "conversation memory (street continuity)"

    resolved = extract_street_from_query(user_query, context)
    if resolved:
        return resolved, "resolved from query"
    return cluster_id, "none (not found)"
