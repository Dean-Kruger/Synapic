# Daminion API Feedback & Enhancement Suggestions

## Introduction

First, I want to express my sincere appreciation for the Daminion API. It has been instrumental in building integrations that leverage Daminion's powerful digital asset management capabilities. The authentication system, structured query support, and media item endpoints have provided a solid foundation for our application development.

The purpose of this document is to share some observations from our integration work and suggest potential enhancements that could benefit the broader developer community building on top of Daminion.

---

## Current API Strengths

The Daminion API excels in several areas:

- **Structured Query System** – The `queryLine` and `operators` parameters work exceptionally well for filtering by tags, saved searches, and collections. This approach is both powerful and reliable.
- **Authentication** – OAuth 2.0 implementation is straightforward and secure.
- **Tag Management** – The ability to retrieve tag values and update item metadata is well-designed.
- **Saved Search & Collection Support** – Querying items via saved search IDs or collection IDs returns accurate counts and supports full pagination.

---

## Observed Limitations

During integration testing, we encountered some behaviors that appear to be API-level constraints. We wanted to document these in case they represent opportunities for enhancement.

### 1. Text-Based Search Pagination Limit

**Observation:**  
When performing text-based searches (using the `search` parameter with syntax like `Keywords:none` or free-text queries), the API appears to return a maximum of approximately 500 items total, regardless of pagination parameters.

**Behavior:**
- First request with `index=0, size=500` returns 500 items
- Subsequent request with `index=500, size=500` returns 0 items
- This occurs even when the `totalCount` indicates more matching items exist

**Contrast with Structured Queries:**  
Structured queries using `queryLine` and operators (e.g., for Saved Searches) do not exhibit this limitation and paginate correctly through the full result set.

### 2. GetCount Accuracy for Text-Based Filters

**Observation:**  
The `/api/MediaItems/GetCount` endpoint sometimes returns the total catalog count rather than the filtered count when using text-based search parameters like `Keywords:none Categories:none`.

**Current Behavior:**
- Query: `search=Keywords:none Categories:none`
- Expected: Count of items matching the filter
- Actual: Returns total catalog count (e.g., 12,605 instead of the filtered subset)

**Workaround Attempted:**  
Using the `/api/MediaItems/Get` endpoint with `page_size=1` and extracting `totalCount` from the response. This returns a count of 200, which appears to be a capped maximum rather than the actual count.

---

## Suggested Enhancements

### 1. Increase or Remove Text Search Pagination Ceiling

**Benefit:**  
Enabling full pagination for text-based searches would allow integrations to process large batches of items matching complex filter criteria. This is particularly valuable for:
- Bulk metadata enrichment workflows
- AI-assisted tagging of "untagged" items
- Export and migration tools

**Suggestion:**  
Consider extending text-based search to support the same unlimited pagination that structured queries currently enjoy, or provide a parameter (e.g., `maxItemsCount`) to explicitly request larger result sets.

### 2. Accurate Counts for Text-Based Filters

**Benefit:**  
Accurate item counts enable integrations to:
- Display reliable progress indicators to users
- Implement efficient batching strategies
- Make informed decisions about processing scope

**Suggestion:**  
Ensure that `GetCount` returns the filtered count when text-based search parameters are provided, matching the behavior for structured queries.

### 3. Optional `maxItemsCount` Parameter

**Benefit:**  
An explicit parameter to control the maximum result set size would give developers flexibility while maintaining server performance controls.

**Suggestion:**  
Add an optional `maxItemsCount` parameter to the `/api/MediaItems/Get` endpoint that overrides default limits when specified.

---

## Summary

The Daminion API provides an excellent foundation for building integrations. The structured query system is particularly well-designed and reliable. The suggestions above are offered in the spirit of expanding the API's capabilities to support more advanced use cases.

We would be happy to provide additional technical details, logs, or test cases to assist in evaluating these suggestions. Thank you for your continued development of Daminion and its API.

---

**Document Prepared By:** Synapic Integration Team  
**Date:** January 2026
