# Genie — natural-language query transcript

_Captured 2026-08-28 against the live Genie space on the FEVM `solacc` workspace via the Genie Conversation API (`resources/genie_rooms.py` from the genie-rooms skill)._

**Space:** Wealth Advisor Dossier — Genie · `space_id = 01f1a2f91cbc15d49a0e847bc02bb161`
**Tables:** `serverless_stable_solacc_catalog.wealth_advisor.{bronze_raw_artifacts, client_profile, silver_parsed_artifacts}`

Each entry is a real natural-language question, the SQL Genie generated, and the answer it returned — no hand-editing.

---

### Q1. "How many dossier artifacts do we have per client?"

```sql
SELECT `client_id`, COUNT(*) AS artifact_count
FROM `serverless_stable_solacc_catalog`.`wealth_advisor`.`silver_parsed_artifacts`
WHERE `client_id` IS NOT NULL
GROUP BY `client_id`
ORDER BY artifact_count DESC
```

**Answer:** There are **13 clients** with dossier artifacts. The number per client ranges from **4 to 6**. Clients with the most (**6 each**) are client_0000, client_0001, client_0002 (the hand-authored personas); all others have **4**.

---

### Q2. "Which clients have a conservative risk tolerance?"

```sql
SELECT client_id, risk_tolerance
FROM serverless_stable_solacc_catalog.wealth_advisor.client_profile
WHERE risk_tolerance = 'conservative'
  AND client_id IS NOT NULL
  AND risk_tolerance IS NOT NULL
```

**Answer:** **7 clients** have a **conservative** risk tolerance (e.g. client_1001, client_1003, client_1005, client_1008, client_1009). _(Genie queried the distilled `client_profile` — the long-term memory produced by the distillation task.)_

---

### Q3. "How many documents were extracted by OCR (ai_parse_document) versus plain text?"

```sql
SELECT `extract_method`, COUNT(*) AS document_count
FROM `serverless_stable_solacc_catalog`.`wealth_advisor`.`silver_parsed_artifacts`
WHERE `extract_method` IS NOT NULL
GROUP BY `extract_method`
```

**Answer:** **15 documents** were extracted with OCR (**ai_parse_document**) and **43** as plain **text** — matching the pipeline's own breakdown exactly (the 15 scanned/printed/handwritten persona artifacts vs. the 43 typed notes).

---

Recreate the space from the committed definition with `uv run python scripts/setup_genie.py`, then ask questions with
`python3 <genie-rooms-skill>/resources/genie_rooms.py --room-id <space_id> --profile <profile> ask "<question>"`.
