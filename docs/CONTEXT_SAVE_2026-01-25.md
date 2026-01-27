# Context Save: SRG Invoice Processing System Backend Analysis

**Captured**: 2026-01-25
**Context Type**: Comprehensive
**Project**: SRG Invoice Processing System

---

## Session Summary

Performed deep code analysis and documentation of four critical backend modules:
1. `table_aware_parser.py` - Invoice table parsing
2. `hybrid_search.py` - Hybrid FAISS + FTS5 search
3. `llm_auditor.py` - LLM-powered invoice auditing
4. `faiss_indexer.py` - FAISS vector index management

Produced a comprehensive **Rewrite Guardrails Document** with edge cases, invariants, and test specifications.

---

## Modules Analyzed

### 1. table_aware_parser.py (1304 lines)
**Location**: `C:\SrGonaH\clean\srgonahB-clean\backend\table_aware_parser.py`

**Purpose**: Multi-strategy invoice table parser with bilingual support (Arabic + English)

**Key Algorithms**:
- Reciprocal Position Clustering for column detection
- Weighted Keyword Scoring for header identification
- Greedy Nearest-Neighbor Cell Matching
- State Machine Parser for row processing

**Critical Invariants**:
- Output items MUST have: `item_name`, `quantity`, `unit_price`, `total_price`
- Multi-line descriptions merge into single items
- Calculation tolerance: `abs(qty * price - total) < 0.01`

---

### 2. hybrid_search.py (280 lines)
**Location**: `C:\SrGonaH\clean\srgonahB-clean\backend\hybrid_search.py`

**Purpose**: Combines FAISS vector search + FTS5 keyword search with Reciprocal Rank Fusion

**Key Algorithm - RRF Formula**:
```
score(d) = Σ 1/(k + rank + 1)  where k = 60
```

**Critical Invariants**:
- RRF constant k=60 MUST NOT change
- Documents deduplicated by `doc_id`
- Final scores normalized to [0.0, 1.0]
- Empty query returns `[]` (not error)

**Tunables**:
| Parameter | Default | Purpose |
|-----------|---------|---------|
| `k` | 60 | RRF smoothing constant |
| `faiss_weight` | 0.6 | Vector search weight |
| `fts_weight` | 0.4 | Keyword search weight |
| `top_k` | 10 | Results to return |

---

### 3. llm_auditor.py (1050 lines)
**Location**: `C:\SrGonaH\clean\srgonahB-clean\backend\llm_auditor.py`

**Purpose**: LLM-powered invoice auditing via Ollama with rule-based fallback

**9-Section Report Structure**:
1. `document_intake` - File metadata
2. `proforma_summary` - Invoice header info
3. `items_table` - Line items
4. `arithmetic_check` - Math verification
5. `amount_words_check` - Written amount validation
6. `bank_details_check` - Bank info completeness
7. `commercial_terms_suggestions` - Improvements
8. `contract_summary` - Contract consistency
9. `final_verdict` - Decision + reasons

**Critical Invariants**:
- Status values: `{"PASS", "HOLD", "FAIL", "ERROR"}`
- Sanity rule: `sanity_ok = not (!has_items AND !has_invoice_no)`
- Arithmetic: line check < 0.01, grand total < 10%
- Fallback triggers when: `(!success OR !sanity_ok) AND fallback_to_rules AND invoice_data`

**Tunables**:
| Constant | Value | Purpose |
|----------|-------|---------|
| `OLLAMA_TEXT_MODEL` | `"llama3.1:8b"` | Model selection |
| `LLM_AUDIT_TIMEOUT` | 120s | Request timeout |
| `LLM_AUDIT_MAX_TOKENS` | 4096 | Max response |
| `LLM_AUDIT_TEMPERATURE` | 0.1 | Low for JSON |
| Price trend threshold | ±5% | stable vs changing |

---

### 4. faiss_indexer.py (623 lines)
**Location**: `C:\SrGonaH\clean\srgonahB-clean\backend\faiss_indexer.py`

**Purpose**: Dual FAISS index manager for document chunks (Index A) and line items (Index B)

**Index Specifications**:
| Property | Value |
|----------|-------|
| Index Type | `faiss.IndexFlatIP` |
| Similarity | Cosine (via normalized vectors) |
| Dimension | Dynamic (from embedding client) |
| Data Type | `float32` |
| Persistence | `.bin` files + SQLite mapping |

**Two-Stage Filtering (Index B)**:
1. Bank Info Filter - 30+ keywords (EN + Arabic) + IBAN/SWIFT regex
2. Adaptive Noise Filter - Score-based validity check

**Critical Invariants**:
- `faiss_index.ntotal == len(mapping_table)` (asserted)
- Embeddings MUST be L2-normalized
- All queries filter `WHERE is_latest = 1`
- No incremental updates - full rebuild only

---

## Edge Cases Catalog

### Parser Edge Cases
- Multi-line descriptions
- Arabic + English mixed text
- Variable column order
- Missing HS code column
- European decimal format (`1.234,56`)
- Quantity embedded in description
- Empty rows between items
- Header row repeated mid-table

### Search Edge Cases
- Query with no FTS matches
- Query with no FAISS matches
- Same doc in both indexes (dedup)
- Empty query string
- Special characters in query
- Arabic-only query
- `top_k > total_results`

### Auditor Edge Cases
- LLM returns non-JSON text
- LLM returns JSON in markdown fence
- LLM timeout (>120s)
- Ollama not running
- Model not pulled (404)
- Empty items + no invoice_no (sanity fail)
- Fallback also fails
- Single price history point

### Indexer Edge Cases
- FAISS not installed
- Index file missing
- Mapping table out of sync
- FAISS ID not in mapping
- Bank info in item name
- Item text < 3 chars
- Zero search results
- Reranker disabled

---

## Performance Hotspots

| Module | Hotspot | Why | Mitigation |
|--------|---------|-----|------------|
| Parser | Regex in loop | Recompiles per row | Pre-compile at module level |
| Parser | Cell matching | O(cells × columns) | Single-pass state machine |
| Search | Double embedding | FAISS + reranker | Cache embeddings |
| Search | FTS tokenization | Per-query CPU | Consider async parallel |
| Auditor | LLM inference | 60-80s blocking | Streaming, batching |
| Auditor | Sync in async | Thread pool contention | True async HTTP |
| Indexer | Full rebuild | No incremental | Implement add/remove |
| Indexer | Embedding gen | O(n × embed_time) | Batch, cache |

---

## Test Requirements

### Unit Tests Required
- `_parse_number()` - All number formats
- `_detect_column_positions()` - Variable orders
- `_merge_orphan_lines()` - Merge logic
- `_calculate_rrf_score()` - RRF formula
- `_merge_results()` - Deduplication
- `_parse_response()` - JSON repair strategies
- `evaluate_report_sanity()` - Sanity matrix
- `_build_arithmetic_check()` - Tolerances
- `is_bank_info()` - All patterns

### Integration Tests Required
- Full parsing pipeline with real PDFs
- Search with real FAISS + FTS indexes
- Audit pipeline with mock Ollama
- Index build + search round-trip

### Golden Files Required
- 8+ parser invoice samples (EN, AR, mixed)
- 4+ auditor scenarios (pass, fail, hold, fallback)
- 4+ search query scenarios

---

## Architectural Decisions

1. **Dual Index Architecture**: Separate indexes for chunks vs items enables specialized retrieval
2. **RRF over Linear Combination**: More robust to score scale differences
3. **Rule-Based Fallback**: Ensures graceful degradation when LLM fails
4. **IndexFlatIP over IVF**: Exact search acceptable at current scale (<1M vectors)
5. **Singleton Pattern**: Single FAISS manager instance across app lifecycle

---

## Files Modified This Session

### SRG Project (`C:\SrGonaH\SRG\`)
- `src/application/use_cases/chat_with_context.py` - Fixed SessionResponse.id type mismatch
- `src/api/main.py` - Removed unused variable
- `src/api/middleware/error_handler.py` - Renamed ambiguous variable
- `src/api/routes/health.py` - Fixed unused variables
- `src/srg/api/v1/endpoints/health.py` - Fixed unused variable

### Git Status
- Repository initialized: `C:\SrGonaH\SRG`
- Initial commit: 119 files, 16534 insertions
- Author: srgonah <srakrema@gmail.com>

---

## CI/CD Status (End of Session)

| Check | Status |
|-------|--------|
| Format (ruff) | PASS - 106 files |
| Lint (ruff) | PASS - all clean |
| Tests (pytest) | PASS - 18/18 |
| Build (uv) | PASS - srg-1.0.0 |

---

## Next Steps (Recommended)

1. **Add Tests**: Implement unit tests from the guardrails document
2. **Golden Files**: Create golden file test fixtures for parser/auditor/search
3. **Performance**: Profile embedding generation, consider caching
4. **Index Updates**: Implement incremental FAISS updates
5. **Async HTTP**: Replace `requests` with `httpx` in LLM auditor

---

## Context Fingerprint

```
SHA256: Modules analyzed on 2026-01-25
- table_aware_parser.py: 1304 lines
- hybrid_search.py: 280 lines
- llm_auditor.py: 1050 lines
- faiss_indexer.py: 623 lines
Total: ~3257 lines of backend code documented
```
