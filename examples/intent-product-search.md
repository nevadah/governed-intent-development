---
unit: catalog/product-search
version: 0.2.0
status: approved
author: nevada.hamaker
reviewers:
  - nevada.hamaker
exposes:
  - GET /catalog/products
depends_on:
  - catalog/product-index
  - catalog/category-taxonomy
must_not_know:
  - orders/cart
  - user/purchase-history
  - pricing/personalized-pricing
tags:
  - read-only
  - public-api
  - performance-critical
---

# Intent: Product Search

## Summary

Allow a visitor or authenticated user to search the product catalog by keyword and filter by category, returning a paginated list of matching products. This unit is read-only and has no side effects. It does not personalize results based on user history or pricing.

---

## Domain Semantics

**Search query** — A freetext string submitted by the user. Interpreted as a bag-of-words match against product name, description, and tags. Phrase matching and boolean operators are not supported in this version. An empty query string returns all products subject to filters and pagination.

**Filter** — A set of constraints narrowing results to a specific category, availability status, or price range. Filters are conjunctive (AND): a product must satisfy all applied filters to appear in results. A result set satisfying no products is valid — it is not an error.

**Pagination** — Results are returned in fixed-size pages. The caller specifies a page number and page size. Page size is bounded; requests exceeding the maximum are silently clamped to the maximum. There is no cursor-based pagination in this version.

**Relevance** — The ordering of results within a page. Ordering is by relevance score when a non-empty query is present, and by a stable default sort (product name ascending) when the query is empty. The relevance algorithm is an implementation detail owned by `catalog/product-index` and is not specified here.

**Stale results** — The search index may lag behind the product database by up to the defined index refresh interval. A product added or updated within that window may not appear in results. This is expected behavior, not an error.

---

## Behavioral Contract

### Preconditions

- The caller has supplied a valid request: `query` is a string (may be empty), `page` is a positive integer, `page_size` is a positive integer.
- `catalog/product-index` is reachable.
- `catalog/category-taxonomy` is reachable (required only when a category filter is applied).

### Postconditions

**On successful search:**
- A response is returned containing: a list of matching products (may be empty), the total count of matching products across all pages, the current page number, and the effective page size used.
- Products in the response are ordered by relevance (non-empty query) or by default sort (empty query).
- No state is mutated. The request has no side effects.

**On empty results:**
- A successful response is returned with an empty product list and a total count of zero. This is not an error condition.

**On invalid filter value (e.g., unrecognized category ID):**
- A 400 response is returned with a description of the invalid parameter. No search is performed.

**On page number exceeding total pages:**
- A successful response is returned with an empty product list. The total count and page metadata reflect the actual result set.

### Invariants

- `page_size` in the response always reflects the effective value used, which may be less than the requested value if the request exceeded the maximum.
- The maximum `page_size` is 100. This is not configurable per-request.
- The index refresh interval (maximum staleness) is 60 seconds. Results may be up to 60 seconds stale; they will not be older than that.
- This endpoint never mutates catalog data. It is safe to call repeatedly with identical parameters and expect identical or more-recent results.
- Authentication is not required. The same results are returned for authenticated and unauthenticated callers. (Personalized results are explicitly out of scope — see `must_not_know`.)

### Scenarios

```gherkin
Feature: Product Search

  # --- Happy path ---

  Scenario: Keyword search returns matching products
    Given the catalog contains products matching "running shoes"
    When a search is requested with query "running shoes" and default pagination
    Then a 200 response is returned
    And the response contains products matching "running shoes"
    And results are ordered by relevance score
    And the response includes total count and pagination metadata

  Scenario: Empty query returns all products
    Given the catalog contains 250 products
    When a search is requested with an empty query string
    Then a 200 response is returned
    And the response contains products ordered by name ascending
    And pagination metadata reflects 250 total results

  Scenario: Category filter narrows results
    Given the catalog contains products in "footwear" and "apparel" categories
    When a search is requested with category filter "footwear"
    Then only products in the "footwear" category are returned

  # --- Edge cases ---

  Scenario: Page size exceeds maximum is clamped
    Given the maximum page size is 100
    When a search is requested with page_size 500
    Then a 200 response is returned
    And the effective page_size in the response is 100
    And no error is returned for the oversized request

  Scenario: Page number beyond last page returns empty list
    Given a search query that matches 30 products with page_size 10
    When page 5 is requested
    Then a 200 response is returned with an empty product list
    And the total count is 30
    And the page metadata indicates page 5 of 3

  Scenario: Query with no matching products
    Given no products match the query "xkcd-frobulate-9999"
    When a search is requested with that query
    Then a 200 response is returned
    And the product list is empty
    And the total count is zero

  # --- Failure modes ---

  Scenario: Search index unavailable
    Given the catalog/product-index dependency is unreachable
    When any search is requested
    Then a 503 response is returned
    And no partial results are returned

  Scenario: Category taxonomy unavailable with category filter applied
    Given the catalog/category-taxonomy dependency is unreachable
    And the request includes a category filter
    When the search is requested
    Then a 503 response is returned

  Scenario: Category taxonomy unavailable with no filter applied
    Given the catalog/category-taxonomy dependency is unreachable
    And the request has no category filter
    When the search is requested
    Then the search proceeds normally using the index only
    And a 200 response is returned

  # --- Security-relevant paths ---

  Scenario: Authenticated and unauthenticated callers receive identical results
    Given a product catalog with 10 results matching "jacket"
    When an authenticated user searches for "jacket"
    And an unauthenticated visitor searches for "jacket"
    Then both receive identical result sets
    And no user-specific data appears in either response

  Scenario: Invalid category filter value
    Given a category ID that does not exist in the taxonomy
    When a search is requested with that category filter
    Then a 400 response is returned
    And the error identifies the invalid parameter
    And no search is performed against the index
```

---

## Quality Attributes

```yaml
performance:
  endpoint_p99_ms: 200
  endpoint_p50_ms: 50
  cache:
    layer: response_cache
    ttl_seconds: 30
    key: query+filters+page+page_size
    note: >
      Identical requests within the TTL window return cached responses.
      Cache is invalidated on index refresh, not on individual product updates.
  index_refresh_interval_seconds: 60

scalability:
  read_replica: required
  note: >
    This endpoint must never read from the primary database.
    All reads go through catalog/product-index, which owns replica routing.

failure_modes:
  product_index_unavailable: return_503_no_partial_results
  category_taxonomy_unavailable_with_filter: return_503
  category_taxonomy_unavailable_without_filter: proceed_without_taxonomy
  cache_unavailable: proceed_without_cache_no_error
```

---

## Security Model

<!-- A unit with no authentication and no sensitive data still has a security model.
     Its threats are availability and inference, not credential theft. -->

**Threat actors:**
- Unauthenticated external callers, which is every caller — this is a public endpoint and anonymous access is the normal case.
- Automated scrapers extracting the full catalog through systematic pagination.
- Callers attempting to make the search backend do disproportionate work through crafted queries, oversized page sizes, or deep pagination.

**Trust boundaries:**
- Every request parameter is untrusted: `query`, `category_id`, `page`, and `page_size` all arrive from the open internet. `page_size` is clamped rather than rejected, `page` beyond the last page returns an empty list rather than an error, and `category_id` is validated against `catalog/category-taxonomy` rather than passed through to the index.
- The `query` string is passed to `catalog/product-index`. The boundary contract is that the index accepts it as a search term and never as executable query syntax; this unit must not construct index queries by string interpolation.

**Sensitive data handled:**
- None. No credentials, no tokens, no PII, no personalized data. This is stated explicitly rather than omitted, because "no sensitive data" is a security property the Security Agent should verify rather than assume — and because the `must_not_know` boundaries exist to keep it true.

**Security responsibilities of this unit:**
- Response uniformity between authenticated and unauthenticated callers. An authenticated caller must receive byte-identical results for an identical query, so that the response cannot be used to infer anything about the caller's account, cart, or history.
- Bounded work per request: page size clamped to the documented maximum, deep pagination bounded, no unbounded result sets.
- Failing closed on an unavailable category taxonomy when a filter was supplied, rather than silently returning unfiltered results that the caller would read as filtered.

**Explicitly out of scope:**
- Authentication and authorization — there is none to perform; the catalog is public by design.
- Rate limiting and bot mitigation — enforced at the API gateway, not here. This unit assumes it may still be called at high volume and bounds its per-request cost accordingly.
- Query sanitization semantics inside the search index — owned by `catalog/product-index`. This unit's responsibility ends at passing the query as data.
- Price correctness and price personalization — `pricing/personalized-pricing` is an explicit `must_not_know` boundary, and leaking personalized prices through this endpoint would be a boundary violation as well as a privacy one.
---

## Dependencies and Boundaries

**Depends on:**
- `catalog/product-index` — executes the search query and returns ranked results. This unit does not own the index, the relevance algorithm, or replica routing.
- `catalog/category-taxonomy` — validates category filter values and resolves category identifiers. Only required when a category filter is present in the request.

**Exposes:**
<!-- This prose list mirrors the machine-readable `exposes` field in the frontmatter.
     The frontmatter version is for tooling; this version explains what callers can rely on. -->
- `GET /catalog/products` — accepts `query` (string), `category_id` (optional), `page` (integer), `page_size` (integer). Returns paginated product list with total count and pagination metadata.

**Must not know about:**
- `orders/cart` — cart state must not influence search results
- `user/purchase-history` — purchase history must not influence result ordering or availability
- `pricing/personalized-pricing` — prices in search results reflect catalog pricing only; personalization is a separate concern

---

## Rationale

**Read replicas required, not optional**
Search is the highest-traffic read path in most catalog systems. Routing search queries to the primary database risks write latency degradation under load. This is treated as an architectural invariant, not a performance suggestion.

**Category taxonomy as a separate dependency**
Category validation is not inlined into this unit because the taxonomy is a shared domain object — other units (product listing, navigation) also depend on it. Coupling the taxonomy to search would create a hidden dependency chain.

**No personalization in this unit**
Personalized search (reranking by purchase history, personalized pricing overlays) is intentionally excluded and listed in `must_not_know`. Mixing personalization into catalog search conflates two concerns with very different privacy, caching, and compliance implications. Personalization belongs in a separate unit layered over this one.

**Response cache keyed on full request parameters**
Caching by query alone would return stale pagination metadata when the catalog changes between page requests. Including page and page_size in the cache key ensures each unique request is independently cached and invalidated.

**Stale results are acceptable, 503 is not**
A 60-second staleness window is acceptable for a search result. A degraded experience (stale but present results) is preferable to an error when the index is experiencing a slow refresh. However, if the index is entirely unreachable, returning partial or empty results silently would be misleading — 503 is the correct response.

---

## Changelog

```yaml
- version: 0.1.0
  date: 2026-05-08
  classification: initial
  changed_by: nevada.hamaker
  changes: []
  reason: Initial approved version.

- version: 0.2.0
  date: 2026-09-13
  classification: non-breaking
  trigger: elicitation_report
  changed_by: nevada.hamaker
  changes:
    - "[ADDED] Security Model — threat actors, trust boundaries, the explicit absence of sensitive data, and out-of-scope items"
  reason: >
    The Security Model section was added to the intent document template when the
    security audit stage joined the pipeline, and this document predated it. Without
    a declared security scope the Security Agent has nothing to audit against and the
    Elicitation Agent cannot check for missing security scenarios.
```
