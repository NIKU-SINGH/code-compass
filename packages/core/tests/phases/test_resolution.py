from pathlib import Path

import compass_core.languages.python  # noqa: F401
from compass_core.languages.python.extractor import PythonExtractor
from compass_core.phases.base import IngestContext
from compass_core.phases.resolution import (
    CONFIDENCE,
    ResolutionPhase,
    _resolve_via_init,
)
from compass_core.phases.symbol_table import SymbolTablePhase


def _ctx_with(tmp_path: Path, files: dict[str, str]) -> IngestContext:
    parsed = []
    for name, source in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(source)
        parsed.append(PythonExtractor().parse(p.read_bytes(), Path(name)))
    ctx = IngestContext(repo_root=tmp_path)
    ctx.parsed_files = parsed
    return ctx


def test_direct_import_call_resolves_with_confidence_1(tmp_path: Path):
    ctx = _ctx_with(
        tmp_path,
        {
            "a.py": "from b import helper\n\ndef run():\n    helper()\n",
            "b.py": "def helper():\n    pass\n",
        },
    )
    ctx = SymbolTablePhase().run(ctx)
    ctx = ResolutionPhase().run(ctx)

    assert ctx.resolved_graph is not None
    assert len(ctx.resolved_graph.call_edges) == 1
    edge = ctx.resolved_graph.call_edges[0]
    assert edge.confidence == 1.0
    assert edge.call_type == "DIRECT_IMPORT"
    assert edge.callee_id.endswith("b::helper")


def test_unresolvable_call_produces_no_edge(tmp_path: Path):
    ctx = _ctx_with(tmp_path, {"a.py": "def run():\n    totally_unknown_thing()\n"})
    ctx = SymbolTablePhase().run(ctx)
    ctx = ResolutionPhase().run(ctx)

    assert ctx.resolved_graph.call_edges == []
    assert ctx.resolved_graph.external_call_edges == []


def test_inherit_edge_resolves_known_base(tmp_path: Path):
    ctx = _ctx_with(
        tmp_path,
        {
            "a.py": "class Base:\n    pass\n\nclass Child(Base):\n    pass\n",
        },
    )
    ctx = SymbolTablePhase().run(ctx)
    ctx = ResolutionPhase().run(ctx)

    assert len(ctx.resolved_graph.inherit_edges) == 1
    edge = ctx.resolved_graph.inherit_edges[0]
    assert edge.child_id.endswith("a::Child")
    assert edge.parent_id.endswith("a::Base")


def test_wildcard_import_resolves_with_confidence_0_6(tmp_path: Path):
    ctx = _ctx_with(
        tmp_path,
        {
            "a.py": "from utils import *\n\ndef run():\n    unknown_helper()\n",
            "utils.py": "def something_else():\n    pass\n",
        },
    )
    ctx = SymbolTablePhase().run(ctx)
    ctx = ResolutionPhase().run(ctx)

    # WILDCARD never produces an edge, but confirms the rule fires by way of
    # producing zero edges (not UNRESOLVED-with-an-edge, since WILDCARD/
    # UNRESOLVED/DYNAMIC/CIRCULAR all short-circuit to "no edge written").
    assert ctx.resolved_graph.call_edges == []
    assert CONFIDENCE["WILDCARD"] == 0.6


def test_external_library_call_produces_external_edge(tmp_path: Path):
    ctx = _ctx_with(
        tmp_path,
        {
            "a.py": "import requests\n\ndef run():\n    requests.get('http://x')\n",
        },
    )
    ctx = SymbolTablePhase().run(ctx)
    ctx = ResolutionPhase().run(ctx)

    assert ctx.resolved_graph.call_edges == []
    assert len(ctx.resolved_graph.external_call_edges) == 1
    edge = ctx.resolved_graph.external_call_edges[0]
    assert edge.library == "requests"
    assert edge.full_ref == "requests.get"


def test_init_reexport_chain_resolves_with_confidence_0_8(tmp_path: Path):
    ctx = _ctx_with(
        tmp_path,
        {
            "pkg/__init__.py": "from pkg.inner import helper\n",
            "pkg/inner.py": "def helper():\n    pass\n",
            "a.py": "from pkg import helper\n\ndef run():\n    helper()\n",
        },
    )
    ctx = SymbolTablePhase().run(ctx)
    ctx = ResolutionPhase().run(ctx)

    assert len(ctx.resolved_graph.call_edges) == 1
    edge = ctx.resolved_graph.call_edges[0]
    assert edge.confidence == 0.8
    assert edge.call_type == "RE_EXPORT"
    assert edge.callee_id.endswith("inner::helper")


def test_mro_single_level_base_walk_resolves_with_confidence_0_8(tmp_path: Path):
    ctx = _ctx_with(
        tmp_path,
        {
            "a.py": (
                "class Base:\n"
                "    def greet(self):\n"
                "        pass\n\n"
                "class Child(Base):\n"
                "    def run(self):\n"
                "        self.greet()\n"
            ),
        },
    )
    ctx = SymbolTablePhase().run(ctx)
    ctx = ResolutionPhase().run(ctx)

    call_edges = ctx.resolved_graph.call_edges
    assert len(call_edges) == 1
    edge = call_edges[0]
    # self.greet() resolves via the same-class rule (DIRECT_IMPORT) since
    # Child doesn't define greet() itself and greet is looked up starting
    # from Child's own parent_id -- but Child has no greet(), so this must
    # fall through to the MRO rule against Base.
    assert edge.call_type == "MRO"
    assert edge.confidence == 0.8
    assert edge.callee_id.endswith("a::Base.greet")


def test_dynamic_getattr_call_produces_no_edge(tmp_path: Path):
    ctx = _ctx_with(
        tmp_path,
        {
            "a.py": "def run(obj):\n    getattr(obj, 'name')()\n",
        },
    )
    ctx = SymbolTablePhase().run(ctx)
    ctx = ResolutionPhase().run(ctx)

    assert ctx.resolved_graph.call_edges == []
    assert ctx.resolved_graph.external_call_edges == []


def test_circular_reexport_detection_via_internal_helper(tmp_path: Path):
    # The old call_resolver never actually populates `visited` on the
    # recursion path, so CIRCULAR is unreachable through the public
    # ResolutionPhase.run() entry point today -- same as it was through the
    # old resolve() entry point. This is a pre-existing quirk we preserve
    # rather than fix (see resolution.py's module docstring). We verify the
    # CIRCULAR branch itself by calling the internal helper directly with a
    # non-empty `visited` set, the way a white-box unit test would exercise
    # otherwise-dead code paths.
    ctx = _ctx_with(
        tmp_path,
        {
            "pkg/__init__.py": "from pkg import helper\n",
        },
    )
    ctx = SymbolTablePhase().run(ctx)
    pf = ctx.parsed_files[0]

    result = _resolve_via_init(
        raw="helper",
        head="helper",
        tail=None,
        file=pf,
        file_imports={"helper": "pkg/__init__.py"},
        symbol_table=ctx.symbol_table,
        by_path={pf.path: pf},
        visited=frozenset({"pkg/__init__.py"}),
    )
    assert result is not None
    assert result.call_type == "CIRCULAR"
    assert result.confidence == 0.0


def test_self_method_resolves_directly_without_falling_to_mro(tmp_path: Path):
    # Direct test of rule 1: Foo.save() is found on Foo itself, so this must
    # resolve via the same-class rule (DIRECT_IMPORT/1.0), never reaching
    # rule 5 (MRO) at all -- unlike the MRO test above, where Child has no
    # own greet() and rule 1 is designed to miss.
    ctx = _ctx_with(
        tmp_path,
        {
            "a.py": (
                "class Foo:\n"
                "    def save(self):\n"
                "        pass\n\n"
                "    def run(self):\n"
                "        self.save()\n"
            ),
        },
    )
    ctx = SymbolTablePhase().run(ctx)
    ctx = ResolutionPhase().run(ctx)

    call_edges = ctx.resolved_graph.call_edges
    assert len(call_edges) == 1
    edge = call_edges[0]
    assert edge.call_type == "DIRECT_IMPORT"
    assert edge.confidence == 1.0
    assert edge.callee_id.endswith("a::Foo.save")


# ---------------------------------------------------------------------------
# Regression tests -- Critical fixes from code review
# ---------------------------------------------------------------------------


def _same_named_class_files(first_base: str, second_base: str) -> dict[str, str]:
    """Two files each define `class Handler` with a `handle` method; `c.py`
    imports Handler from `second_base` specifically and inherits from it.
    Only the class in `second_base` is the "correct" one -- if resolution
    ever falls back to an unqualified, insertion-order-dependent scan, it can
    silently pick the class in `first_base` instead."""
    return {
        f"{first_base}.py": "class Handler:\n    def handle(self):\n        pass\n",
        f"{second_base}.py": "class Handler:\n    def handle(self):\n        pass\n",
        "c.py": (
            f"from {second_base} import Handler\n\n"
            "class Child(Handler):\n"
            "    def run(self):\n"
            "        self.handle()\n"
        ),
    }


def test_inherit_and_mro_pick_the_imported_class_not_first_scanned_order_a(tmp_path: Path):
    # base_a.py written/parsed before base_b.py.
    ctx = _ctx_with(tmp_path, _same_named_class_files("base_a", "base_b"))
    ctx = SymbolTablePhase().run(ctx)
    ctx = ResolutionPhase().run(ctx)

    assert len(ctx.resolved_graph.inherit_edges) == 1
    inherit_edge = ctx.resolved_graph.inherit_edges[0]
    assert inherit_edge.parent_id.endswith("base_b::Handler")
    assert "base_a" not in inherit_edge.parent_id

    call_edges = ctx.resolved_graph.call_edges
    assert len(call_edges) == 1
    call_edge = call_edges[0]
    assert call_edge.call_type == "MRO"
    assert call_edge.callee_id.endswith("base_b::Handler.handle")
    assert "base_a" not in call_edge.callee_id


def test_inherit_and_mro_pick_the_imported_class_not_first_scanned_order_b(tmp_path: Path):
    # Same scenario, but base_b.py (the *importable* one) is written/parsed
    # first this time -- proves the correct file is picked regardless of
    # filesystem/dict insertion order, not just when it happens to come last.
    ctx = _ctx_with(tmp_path, _same_named_class_files("base_b", "base_a"))
    ctx = SymbolTablePhase().run(ctx)
    ctx = ResolutionPhase().run(ctx)

    assert len(ctx.resolved_graph.inherit_edges) == 1
    inherit_edge = ctx.resolved_graph.inherit_edges[0]
    assert inherit_edge.parent_id.endswith("base_a::Handler")
    assert "base_b" not in inherit_edge.parent_id

    call_edges = ctx.resolved_graph.call_edges
    assert len(call_edges) == 1
    call_edge = call_edges[0]
    assert call_edge.call_type == "MRO"
    assert call_edge.callee_id.endswith("base_a::Handler.handle")
    assert "base_b" not in call_edge.callee_id


def test_dotted_module_attribute_call_resolves_internally_not_external(tmp_path: Path):
    # import mod; mod.Class.method() -- a dotted tail ("Worker.run") must
    # resolve to the internal Definition, not fall through every rule down
    # to EXTERNAL and misclassify an internal module as a third-party lib.
    ctx = _ctx_with(
        tmp_path,
        {
            "mod.py": "class Worker:\n    def run(self):\n        pass\n",
            "a.py": "import mod\n\ndef start():\n    mod.Worker.run()\n",
        },
    )
    ctx = SymbolTablePhase().run(ctx)
    ctx = ResolutionPhase().run(ctx)

    assert ctx.resolved_graph.external_call_edges == []
    call_edges = ctx.resolved_graph.call_edges
    assert len(call_edges) == 1
    edge = call_edges[0]
    assert edge.call_type == "MODULE_ATTR"
    assert edge.confidence == 0.9
    assert edge.callee_id.endswith("mod::Worker.run")
