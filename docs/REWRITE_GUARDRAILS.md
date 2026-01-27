# Rewrite Guardrails Document

## Overview

This document consolidates critical constraints for rewriting or refactoring four backend modules:
- `table_aware_parser.py` - Invoice table parsing
- `hybrid_search.py` - Hybrid vector + keyword search
- `llm_auditor.py` - LLM-powered invoice auditing
- `faiss_indexer.py` - FAISS index management

---

## 1. Edge Cases Found (By Module)

### `table_aware_parser.py`

| Edge Case | Function | Input Example | Expected Behavior |
|-----------|----------|---------------|-------------------|
| Multi-line descriptions | `_merge_orphan_lines()` | `"PUMP\n  Model: XYZ\n  Size: 10mm"` | Merge into single item |
| Arabic + English mixed | `_detect_language()` | `"مضخة PUMP 10 inch"` | Detect as bilingual, handle RTL |
| Variable column order | `_detect_column_positions()` | Headers: `[QTY, DESC, PRICE]` vs `[DESC, QTY, PRICE]` | Adapt parsing dynamically |
| Missing HS code column | `parse_table()` | Invoice without HS codes | Return `hs_code: None`, don't fail |
| Decimal comma format | `_parse_number()` | `"1.234,56"` (European) | Parse as `1234.56` |
| Quantity in description | `_extract_embedded_quantity()` | `"Pump (qty: 5)"` | Extract `quantity=5` |
| Empty rows between items | `_filter_noise_rows()` | `["Item1", "", "", "Item2"]` | Skip empty, preserve items |
| Header row in middle of table | `_is_header_row()` | Repeated headers on page 2 | Detect and skip |

### `hybrid_search.py`

| Edge Case | Function | Input Example | Expected Behavior |
|-----------|----------|---------------|-------------------|
| Query with no FTS matches | `search()` | `"xyzzy123"` (gibberish) | Return FAISS-only results |
| Query with no FAISS matches | `search()` | Very short query `"a"` | Return FTS-only results |
| Duplicate doc in both indexes | `_merge_results()` | Same doc from FAISS + FTS | Deduplicate, combine scores via RRF |
| Empty query string | `search()` | `""` | Return empty list, no error |
| Special characters in query | `_tokenize()` | `"pump (10\") model"` | Escape/handle quotes |
| Arabic-only query | `search()` | `"مضخة مياه"` | Tokenize correctly, search both indexes |
| top_k > total results | `search()` | `top_k=100`, only 5 docs exist | Return 5 results, no padding |

### `llm_auditor.py`

| Edge Case | Function | Input Example | Expected Behavior |
|-----------|----------|---------------|-------------------|
| LLM returns non-JSON | `_parse_response()` | `"I cannot process this invoice..."` | Trigger fallback |
| LLM returns JSON in markdown | `_parse_response()` | `` ```json {...}``` `` | Extract and parse |
| LLM times out | `_call_ollama()` | Response > 120s | Return `status="ERROR"` |
| Ollama not running | `check_available()` | Connection refused | Return error, suggest start command |
| Model not pulled | `_call_ollama()` | HTTP 404 | Error: "Run `ollama pull llama3.1:8b`" |
| Empty items_table + no invoice_no | `evaluate_report_sanity()` | `{"items_table": [], "proforma_summary": {}}` | `sanity_ok=False`, trigger fallback |
| Fallback also fails | `run_llm_audit()` | Exception in `InvoiceAuditor` | Return original LLM error |
| Price trend with single history | `enrich_items_with_usage_history()` | Only 1 previous price | `price_trend: None` (need ≥2) |

### `faiss_indexer.py`

| Edge Case | Function | Input Example | Expected Behavior |
|-----------|----------|---------------|-------------------|
| FAISS not installed | `build_index_a()` | Missing faiss-cpu | Raise `ImportError` with install command |
| Index file missing | `search_chunks()` | No `.bin` file | Raise `RuntimeError` with guidance |
| Mapping table out of sync | `search_items()` | `mapping_count != index.ntotal` | Log warning, partial results |
| FAISS ID not in mapping | `search_items()` | Stale index after DB change | Skip result, increment `mapping_misses` |
| Bank info in item name | `is_bank_info()` | `"IBAN: GB29NWBK..."` | Filter out (return `True`) |
| Item text < 3 chars | `is_bank_info()` | `"AB"` | Filter out |
| Zero results from search | `search_items()` | No matching vectors | Log warning with diagnostics |
| Reranker disabled | `search_chunks()` | `RERANKER_ENABLED=False` | Return FAISS scores directly |

---

## 2. Performance Hotspots and Why

### `table_aware_parser.py`

| Hotspot | Function | Why | Impact |
|---------|----------|-----|--------|
| **Regex compilation in loop** | `_detect_column_positions()` | Recompiles patterns per row | O(rows × patterns) |
| **Nearest-neighbor cell matching** | `_match_cells_to_columns()` | O(cells × columns) per row | Slow on wide tables |
| **Multi-pass row iteration** | `parse_table()` | 3-4 passes over same rows | Memory pressure on large docs |

**Mitigation**: Pre-compile all regexes at module level; consider single-pass state machine.

### `hybrid_search.py`

| Hotspot | Function | Why | Impact |
|---------|----------|-----|--------|
| **Double embedding** | `search()` | FAISS + reranker both need vectors | 2× embedding cost |
| **FTS5 tokenization** | `_fts_search()` | Re-tokenizes on every query | CPU-bound |
| **RRF merge sort** | `_merge_results()` | Sorting all candidates | O(n log n) |

**Mitigation**: Cache embeddings; consider async parallel search.

### `llm_auditor.py`

| Hotspot | Function | Why | Impact |
|---------|----------|-----|--------|
| **LLM inference** | `_call_ollama()` | 60-80s per audit | Blocking, single-threaded |
| **Sync requests in async** | `_call_ollama()` | `run_in_executor` overhead | Thread pool contention |
| **JSON repair attempts** | `_parse_response()` | 3 regex searches on failure | Negligible vs LLM time |

**Mitigation**: Consider streaming responses; batch multiple audits; pre-warm model.

### `faiss_indexer.py`

| Hotspot | Function | Why | Impact |
|---------|----------|-----|--------|
| **Full index rebuild** | `build_index_b()` | No incremental update | Minutes for large datasets |
| **Bulk SQL with placeholders** | `search_items()` | Dynamic SQL generation | Safe but string-heavy |
| **Embedding generation** | `build_index_*()` | O(n × embed_time) | Dominates build time |
| **Two-stage filtering** | `build_index_b()` | Iterates items twice | 2× memory for item list |

**Mitigation**: Implement incremental index updates; use IVF index for >100k vectors.

---

## 3. Behavior That Must Remain Identical

### Critical Invariants

#### `table_aware_parser.py`

```python
# INVARIANT 1: Line item structure
# Output items MUST have these fields (can be None)
{
    "item_name": str,      # Required, non-empty
    "quantity": float,     # Required, >= 0
    "unit_price": float,   # Required, >= 0
    "total_price": float,  # Required, >= 0
    "unit": str | None,
    "hs_code": str | None,
}

# INVARIANT 2: Multi-line merge
# Input:  ["PUMP MODEL X", "  Size: 10 inch", "  Material: Steel"]
# Output: Single item with item_name = "PUMP MODEL X Size: 10 inch Material: Steel"

# INVARIANT 3: Calculation tolerance
# abs(quantity * unit_price - total_price) < 0.01 OR trust stated total
```

#### `hybrid_search.py`

```python
# INVARIANT 1: RRF formula MUST be exactly:
score = sum(1.0 / (k + rank + 1) for each source)
# where k = 60 (hardcoded constant)

# INVARIANT 2: Deduplication key
# Documents are deduplicated by `doc_id` (not by content hash)

# INVARIANT 3: Score range
# Final scores MUST be in [0.0, 1.0] after normalization

# INVARIANT 4: Empty query handling
search("", top_k=10)  # Returns: []  (not error)
```

#### `llm_auditor.py`

```python
# INVARIANT 1: 9-section report structure (all sections present)
{
    "document_intake": {},
    "proforma_summary": {},
    "items_table": [],
    "arithmetic_check": {},
    "amount_words_check": {},
    "bank_details_check": {},
    "commercial_terms_suggestions": [],
    "contract_summary": {},
    "final_verdict": {}
}

# INVARIANT 2: Sanity rule (triggers fallback)
sanity_ok = not (not has_items and not has_invoice_no)
# False ONLY when BOTH items_table empty AND invoice_no missing

# INVARIANT 3: Status values
status in {"PASS", "HOLD", "FAIL", "ERROR"}

# INVARIANT 4: Fallback preserves processing_time from LLM attempt
result.processing_time  # Includes failed LLM time, not just fallback time

# INVARIANT 5: Arithmetic tolerance
line_check: abs(stated - expected) < 0.01  # PASS
grand_total: abs(stated - calculated) < stated * 0.10  # PASS (10%)
```

#### `faiss_indexer.py`

```python
# INVARIANT 1: Index-mapping parity
assert faiss_index.ntotal == len(mapping_table)

# INVARIANT 2: Normalized vectors assumption
# Embeddings MUST be L2-normalized before adding to IndexFlatIP
# (inner product = cosine similarity only when normalized)

# INVARIANT 3: FAISS ID is position-based
faiss_id = 0, 1, 2, ...  # Contiguous, 0-indexed

# INVARIANT 4: Latest-only filtering
# All queries MUST include: WHERE is_latest = 1

# INVARIANT 5: Bank filter rules
is_bank_info("") == True           # Empty -> exclude
is_bank_info("AB") == True         # len < 3 -> exclude
is_bank_info("IBAN: ...") == True  # Keyword match -> exclude
```

### Input/Output Examples

**Parser:**
```python
# Input PDF text:
"""
| Item Description | Qty | Unit Price | Total |
|------------------|-----|------------|-------|
| Water Pump 10HP  | 5   | 1,200.00   | 6,000 |
|   Model: ABC-123 |     |            |       |
| Valve 2 inch     | 10  | 50.00      | 500   |
"""

# Expected output:
[
    {"item_name": "Water Pump 10HP Model: ABC-123", "quantity": 5.0,
     "unit_price": 1200.0, "total_price": 6000.0, "unit": None, "hs_code": None},
    {"item_name": "Valve 2 inch", "quantity": 10.0,
     "unit_price": 50.0, "total_price": 500.0, "unit": None, "hs_code": None}
]
```

**Hybrid Search:**
```python
# Input:
search("water pump 10HP", top_k=3)

# Output format:
[
    {"doc_id": 42, "score": 0.89, "source": "hybrid", "faiss_rank": 1, "fts_rank": 2},
    {"doc_id": 17, "score": 0.72, "source": "faiss_only", "faiss_rank": 3, "fts_rank": None},
    {"doc_id": 99, "score": 0.65, "source": "fts_only", "faiss_rank": None, "fts_rank": 1}
]
```

**LLM Auditor:**
```python
# Input:
await run_llm_audit(pdf_text="...", filename="INV-001.pdf", invoice_data={...})

# Output (success):
LLMAuditResult(
    success=True,
    audit_type="llm",  # or "rule_based_fallback"
    status="PASS",     # or "HOLD", "FAIL", "ERROR"
    items_table=[...],
    final_verdict={"decision": "PASS", "confidence": 0.85, ...},
    processing_time=67.3,
    parse_repair_used=False
)
```

---

## 4. What Can Be Redesigned Safely

### `table_aware_parser.py`

| Safe to Change | Required Tests |
|----------------|----------------|
| Internal regex patterns | Golden file tests with 20+ invoice samples |
| Column detection algorithm | Unit tests for `_detect_column_positions()` |
| Orphan line merge heuristics | Integration tests with multi-line items |
| Number parsing locale handling | Unit tests for `_parse_number()` with formats |

**Cannot change:** Output schema, multi-line merge behavior, calculation tolerance.

### `hybrid_search.py`

| Safe to Change | Required Tests |
|----------------|----------------|
| Internal tokenization | Unit tests for edge cases (Arabic, special chars) |
| Caching strategy | Performance benchmarks |
| Async implementation | Integration tests verifying same results |
| Score normalization method | Unit tests asserting [0,1] range |

**Cannot change:** RRF formula (k=60), deduplication logic, empty query behavior.

### `llm_auditor.py`

| Safe to Change | Required Tests |
|----------------|----------------|
| LLM prompt templates | Golden file tests comparing report quality |
| JSON repair strategies | Unit tests for `_parse_response()` |
| Tracing/logging details | No functional tests needed |
| HTTP client implementation | Mock tests for `_call_ollama()` |

**Cannot change:** 9-section structure, sanity rule, fallback trigger logic, status values.

### `faiss_indexer.py`

| Safe to Change | Required Tests |
|----------------|----------------|
| Index type (IVF, HNSW) | Recall@k benchmarks vs IndexFlatIP |
| Batch size for embedding | Performance tests |
| Filter implementation | Unit tests for `is_bank_info()` |
| SQL query structure | Integration tests verifying same results |

**Cannot change:** Index-mapping parity, latest-only filter, normalized vector assumption.

---

## 5. Suggested Tests

### Unit Tests

#### `test_table_aware_parser.py`

```python
class TestNumberParsing:
    def test_european_decimal(self):
        assert _parse_number("1.234,56") == 1234.56

    def test_us_decimal(self):
        assert _parse_number("1,234.56") == 1234.56

    def test_arabic_numerals(self):
        assert _parse_number("١٢٣٤") == 1234.0

    def test_with_currency_symbol(self):
        assert _parse_number("$1,200.00") == 1200.0

    def test_negative_number(self):
        assert _parse_number("-500.00") == -500.0

    def test_empty_string(self):
        assert _parse_number("") == 0.0

class TestColumnDetection:
    def test_standard_order(self):
        headers = ["Description", "Qty", "Unit Price", "Total"]
        positions = _detect_column_positions(headers)
        assert positions["description"] == 0
        assert positions["quantity"] == 1

    def test_reversed_order(self):
        headers = ["Total", "Price", "Qty", "Item"]
        positions = _detect_column_positions(headers)
        assert positions["description"] == 3
        assert positions["total"] == 0

class TestOrphanLineMerge:
    def test_merge_continuation(self):
        rows = [
            {"item_name": "PUMP MODEL X", "quantity": 5},
            {"item_name": "  Size: 10 inch", "quantity": None},
        ]
        merged = _merge_orphan_lines(rows)
        assert len(merged) == 1
        assert "Size: 10 inch" in merged[0]["item_name"]

    def test_no_merge_when_quantity_present(self):
        rows = [
            {"item_name": "PUMP", "quantity": 5},
            {"item_name": "VALVE", "quantity": 10},
        ]
        merged = _merge_orphan_lines(rows)
        assert len(merged) == 2
```

#### `test_hybrid_search.py`

```python
class TestRRFScoring:
    def test_rrf_formula(self):
        # RRF with k=60
        # rank=0 -> 1/(60+0+1) = 0.0164
        # rank=1 -> 1/(60+1+1) = 0.0161
        score = _calculate_rrf_score(ranks=[0, 1], k=60)
        expected = 1/61 + 1/62
        assert abs(score - expected) < 1e-6

    def test_single_source(self):
        score = _calculate_rrf_score(ranks=[0], k=60)
        assert abs(score - 1/61) < 1e-6

class TestDeduplication:
    def test_same_doc_both_sources(self):
        faiss_results = [{"doc_id": 1, "score": 0.9}]
        fts_results = [{"doc_id": 1, "score": 0.8}]
        merged = _merge_results(faiss_results, fts_results)
        assert len(merged) == 1
        assert merged[0]["source"] == "hybrid"

    def test_different_docs(self):
        faiss_results = [{"doc_id": 1, "score": 0.9}]
        fts_results = [{"doc_id": 2, "score": 0.8}]
        merged = _merge_results(faiss_results, fts_results)
        assert len(merged) == 2

class TestEmptyQuery:
    def test_empty_string_returns_empty(self):
        results = search("", top_k=10)
        assert results == []

    def test_whitespace_only_returns_empty(self):
        results = search("   ", top_k=10)
        assert results == []
```

#### `test_llm_auditor.py`

```python
class TestJSONParsing:
    def test_direct_json(self):
        response = '{"final_verdict": {"decision": "PASS"}}'
        parsed, repair_used, error = _parse_response(response)
        assert parsed["final_verdict"]["decision"] == "PASS"
        assert repair_used == False

    def test_markdown_wrapped_json(self):
        response = '```json\n{"final_verdict": {"decision": "PASS"}}\n```'
        parsed, repair_used, error = _parse_response(response)
        assert parsed is not None
        assert repair_used == True

    def test_json_with_preamble(self):
        response = 'Here is the audit:\n{"final_verdict": {"decision": "PASS"}}'
        parsed, repair_used, error = _parse_response(response)
        assert parsed is not None
        assert repair_used == True

    def test_invalid_json(self):
        response = "I cannot process this invoice."
        parsed, repair_used, error = _parse_response(response)
        assert parsed is None
        assert error is not None

class TestSanityCheck:
    def test_both_present_passes(self):
        report = {"items_table": [{"item": "x"}], "proforma_summary": {"invoice_no": "INV-1"}}
        ok, flags, issues = evaluate_report_sanity(report)
        assert ok == True

    def test_items_only_passes(self):
        report = {"items_table": [{"item": "x"}], "proforma_summary": {}}
        ok, flags, issues = evaluate_report_sanity(report)
        assert ok == True

    def test_invoice_no_only_passes(self):
        report = {"items_table": [], "proforma_summary": {"invoice_no": "INV-1"}}
        ok, flags, issues = evaluate_report_sanity(report)
        assert ok == True

    def test_both_missing_fails(self):
        report = {"items_table": [], "proforma_summary": {}}
        ok, flags, issues = evaluate_report_sanity(report)
        assert ok == False

class TestArithmeticCheck:
    def test_line_item_pass(self):
        # qty=5, price=100, stated=500 -> diff=0 -> PASS
        check = _build_arithmetic_check([], [{"quantity": 5, "unit_price": 100, "total_price": 500}], {})
        assert check["line_checks"][0]["status"] == "PASS"

    def test_line_item_fail(self):
        # qty=5, price=100, stated=600 -> diff=100 -> FAIL
        check = _build_arithmetic_check([], [{"quantity": 5, "unit_price": 100, "total_price": 600}], {})
        assert check["line_checks"][0]["status"] == "FAIL"

    def test_grand_total_10_percent_tolerance(self):
        # calculated=1000, stated=1050 -> 5% diff -> PASS
        items = [{"quantity": 10, "unit_price": 100, "total_price": 1000}]
        invoice = {"grand_total": 1050}
        check = _build_arithmetic_check([], items, invoice)
        assert check["grand_total"]["status"] == "PASS"
```

#### `test_faiss_indexer.py`

```python
class TestBankInfoFilter:
    def test_iban_detected(self):
        assert is_bank_info("GB29NWBK60161331926819") == True

    def test_swift_detected(self):
        assert is_bank_info("DEUTDEFF") == True

    def test_keyword_detected(self):
        assert is_bank_info("Beneficiary: ABC Corp") == True

    def test_arabic_keyword(self):
        assert is_bank_info("رقم الايبان") == True

    def test_normal_item_passes(self):
        assert is_bank_info("Water Pump 10HP Model XYZ") == False

    def test_empty_excluded(self):
        assert is_bank_info("") == True

    def test_short_excluded(self):
        assert is_bank_info("AB") == True

class TestIndexStats:
    def test_stats_structure(self):
        manager = FAISSIndexManager()
        stats = manager.get_index_stats()
        assert "index_a_loaded" in stats
        assert "index_b_loaded" in stats
        assert "embedding_dimension" in stats
```

### Integration Tests

```python
class TestParserIntegration:
    """Test full parsing pipeline with real PDF text."""

    def test_parse_standard_invoice(self, sample_invoice_text):
        result = parse_invoice(sample_invoice_text)
        assert len(result["items"]) > 0
        assert all("item_name" in item for item in result["items"])
        assert all("quantity" in item for item in result["items"])

    def test_parse_multipage_invoice(self, multipage_invoice_text):
        result = parse_invoice(multipage_invoice_text)
        # Should handle header repetition
        assert len(result["items"]) > 5

class TestHybridSearchIntegration:
    """Test search with real FAISS + FTS indexes."""

    @pytest.fixture
    def indexed_data(self, tmp_path):
        # Set up test indexes
        manager = FAISSIndexManager()
        manager.build_index_a(force_rebuild=True)
        manager.build_index_b(force_rebuild=True)
        return manager

    def test_search_returns_results(self, indexed_data):
        results = search("water pump", top_k=5)
        assert len(results) <= 5
        assert all("score" in r for r in results)

    def test_search_scores_sorted(self, indexed_data):
        results = search("valve", top_k=10)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

class TestLLMAuditorIntegration:
    """Test audit pipeline with mock Ollama."""

    @pytest.fixture
    def mock_ollama(self, monkeypatch):
        def mock_post(*args, **kwargs):
            return MockResponse({"response": '{"final_verdict": {"decision": "PASS"}}'})
        monkeypatch.setattr(requests, "post", mock_post)

    async def test_audit_success(self, mock_ollama, sample_invoice):
        result = await run_llm_audit(
            pdf_text=sample_invoice["text"],
            filename="test.pdf",
            invoice_data=sample_invoice["data"]
        )
        assert result.success == True
        assert result.status in ["PASS", "HOLD", "FAIL"]

    async def test_fallback_triggers(self, mock_ollama_empty, sample_invoice):
        result = await run_llm_audit(
            pdf_text=sample_invoice["text"],
            filename="test.pdf",
            invoice_data=sample_invoice["data"]
        )
        assert result.audit_type == "rule_based_fallback"
```

### Golden File Tests

```python
class TestParserGoldenFiles:
    """Compare parser output against known-good results."""

    GOLDEN_DIR = Path("tests/golden/parser")

    @pytest.mark.parametrize("invoice_name", [
        "standard_invoice_en",
        "standard_invoice_ar",
        "multiline_descriptions",
        "variable_column_order",
        "european_number_format",
        "missing_hs_codes",
        "embedded_quantities",
        "bilingual_mixed",
    ])
    def test_parser_golden(self, invoice_name):
        input_path = self.GOLDEN_DIR / f"{invoice_name}_input.txt"
        expected_path = self.GOLDEN_DIR / f"{invoice_name}_expected.json"

        with open(input_path) as f:
            input_text = f.read()
        with open(expected_path) as f:
            expected = json.load(f)

        result = parse_invoice(input_text)

        # Compare item count
        assert len(result["items"]) == len(expected["items"])

        # Compare each item
        for actual, exp in zip(result["items"], expected["items"]):
            assert actual["item_name"] == exp["item_name"]
            assert abs(actual["quantity"] - exp["quantity"]) < 0.01
            assert abs(actual["unit_price"] - exp["unit_price"]) < 0.01

class TestLLMAuditorGoldenFiles:
    """Compare audit reports against known-good results."""

    GOLDEN_DIR = Path("tests/golden/auditor")

    @pytest.mark.parametrize("invoice_name", [
        "clean_invoice_pass",
        "arithmetic_error_fail",
        "missing_fields_hold",
        "fallback_triggered",
    ])
    async def test_auditor_golden(self, invoice_name, mock_ollama_from_golden):
        input_path = self.GOLDEN_DIR / f"{invoice_name}_input.json"
        expected_path = self.GOLDEN_DIR / f"{invoice_name}_expected.json"

        with open(input_path) as f:
            input_data = json.load(f)
        with open(expected_path) as f:
            expected = json.load(f)

        result = await run_llm_audit(
            pdf_text=input_data["pdf_text"],
            filename=input_data["filename"],
            invoice_data=input_data["invoice_data"]
        )

        # Compare critical fields
        assert result.status == expected["status"]
        assert result.audit_type == expected["audit_type"]
        assert len(result.items_table) == len(expected["items_table"])

        # Compare arithmetic check
        assert result.arithmetic_check["overall_status"] == expected["arithmetic_check"]["overall_status"]

class TestSearchGoldenFiles:
    """Compare search results against known-good rankings."""

    GOLDEN_DIR = Path("tests/golden/search")

    @pytest.mark.parametrize("query_name", [
        "water_pump_query",
        "arabic_query",
        "exact_match_query",
        "no_results_query",
    ])
    def test_search_golden(self, query_name, indexed_test_data):
        input_path = self.GOLDEN_DIR / f"{query_name}_input.json"
        expected_path = self.GOLDEN_DIR / f"{query_name}_expected.json"

        with open(input_path) as f:
            query_data = json.load(f)
        with open(expected_path) as f:
            expected = json.load(f)

        results = search(query_data["query"], top_k=query_data["top_k"])

        # Compare top-k doc_ids (order matters)
        result_ids = [r["doc_id"] for r in results]
        expected_ids = [r["doc_id"] for r in expected["results"]]

        # Allow some flexibility in ranking
        assert set(result_ids[:3]) == set(expected_ids[:3])  # Top 3 must match
```

---

## Summary Checklist

Before merging any rewrite:

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] All golden file tests pass (or differences reviewed and approved)
- [ ] Index-mapping parity assertion passes
- [ ] RRF formula unchanged (k=60)
- [ ] 9-section report structure preserved
- [ ] Sanity rule logic unchanged
- [ ] Arithmetic tolerances unchanged (0.01 line, 10% grand total)
- [ ] Bank filter patterns unchanged
- [ ] Empty query returns empty list (not error)
- [ ] Performance benchmarks within 10% of baseline
