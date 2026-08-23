from compass_core.ir.graph import (
    CONFIDENCE,
    CallEdge,
    ExternalCallEdge,
    ImportEdge,
    InheritEdge,
    ResolvedGraph,
)


def test_resolved_graph_defaults_to_empty_lists():
    g = ResolvedGraph()
    assert g.files == []
    assert g.call_edges == []
    assert g.external_call_edges == []
    assert g.import_edges == []
    assert g.inherit_edges == []


def test_edge_dataclasses_hold_expected_fields():
    ce = CallEdge(
        caller_id="py::a::f",
        callee_id="py::b::g",
        call_type="RESOLVED",
        confidence=CONFIDENCE["DIRECT_IMPORT"],
        line=12,
    )
    assert ce.confidence == 1.0
    ext = ExternalCallEdge(
        caller_id="py::a::f", full_ref="requests.get", library="requests", line=3
    )
    assert ext.library == "requests"
    imp = ImportEdge(from_path="a.py", to_path="b.py")
    inh = InheritEdge(child_id="py::a::Foo", parent_id="py::b::Base")
    assert imp.to_path == "b.py"
    assert inh.parent_id == "py::b::Base"


def test_confidence_table_matches_spec_scale():
    assert CONFIDENCE["DIRECT_IMPORT"] == 1.0
    assert CONFIDENCE["RE_EXPORT"] == 0.8
    assert CONFIDENCE["MRO"] == 0.8
    assert CONFIDENCE["WILDCARD"] == 0.6
    assert CONFIDENCE["DYNAMIC"] == 0.0
    assert CONFIDENCE["UNRESOLVED"] == 0.0
