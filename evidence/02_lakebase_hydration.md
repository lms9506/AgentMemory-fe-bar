# Lakebase (operational serving) — hydration output

_Generated 2026-08-28 16:00 UTC by `evidence/generate_evidence.py` against the live FEVM workspace._

The `hydrate` job task loaded the silver rows into Lakebase Postgres + pgvector (the tier the advisor app queries for recall).

## Counts
| metric | value |
| --- | --- |
| artifacts | 58 |
| artifact_chunks | 58 |
| distinct clients | 13 |
| job-attributed audit rows (bulk_onboard_artifact) | 58 |

## Artifacts per client
| client_id | artifacts |
| --- | --- |
| client_0000 | 6 |
| client_0001 | 6 |
| client_0002 | 6 |
| client_1000 | 4 |
| client_1001 | 4 |
| client_1002 | 4 |
| client_1003 | 4 |
| client_1004 | 4 |
| client_1005 | 4 |
| client_1006 | 4 |
| client_1007 | 4 |
| client_1008 | 4 |
| client_1009 | 4 |

## Sample embedded chunks (pgvector; embedding dimension shown)
| artifact_id | chunk_index | embedding_dims | content (160c) |
| --- | --- | --- | --- |
| 1 | 0 | 1024 | Brokerage Statement — Riley Patel Account: CLIENT_1002-BROK Period ending: 2026-02-30 Total portfolio value: $893,131.38 Holdings summary: VMFXX $ 126,790.11 VN |
| 2 | 0 | 1024 | Brokerage Statement — Riley Kim Account: CLIENT_1005-BROK Period ending: 2026-03-30 Total portfolio value: $7,620,138.19 Holdings summary: VNQ $ 2,990,717.05 VX |
| 3 | 0 | 1024 | Brokerage Statement — Casey Patel Account: CLIENT_1008-BROK Period ending: 2026-01-30 Total portfolio value: $3,839,494.19 Holdings summary: VNQ $ 395,094.49 VM |
