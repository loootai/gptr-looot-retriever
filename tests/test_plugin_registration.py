"""Checks the installed package against the real gpt-researcher loader."""
from importlib.metadata import entry_points

from gpt_researcher.actions.retriever import get_retriever

from gptr_looot_retriever import LoootSearch


def test_entry_point_registered():
    names = {e.name: e.value for e in entry_points(group="gpt_researcher.retrievers")}
    assert names["looot"] == "gptr_looot_retriever:LoootSearch"


def test_gpt_researcher_loader_resolves_looot():
    assert get_retriever("looot") is LoootSearch
