# Lakeflow pipeline — governed Delta output

_Generated 2026-08-28 16:00 UTC by `evidence/generate_evidence.py` against the live FEVM workspace._

The Lakeflow declarative pipeline landed raw Volume files into Unity Catalog Delta tables (`bronze_raw_artifacts` → `silver_parsed_artifacts`).

## Row counts
| table | rows |
| --- | --- |
| bronze_raw_artifacts | 58 |
| silver_parsed_artifacts | 58 |

## Extraction method (GenAI: `ai_parse_document` vs plain text)
| extract_method | rows | avg_ocr_confidence |
| --- | --- | --- |
| ai_parse_document | 15 | 0.971 |
| text | 43 |  |

## Parsed OCR samples (`ai_parse_document` model output)
Scanned/handwritten documents, text extracted + summarized in-pipeline:

| client | file | kind | ocr_conf | extracted_text (240c) | summary (320c) |
| --- | --- | --- | --- | --- | --- |
| client_0002 | client_0002_equity_comp_statement.pdf | pdf | 0.997 | Prepared from participant records Participant: Marcus Delacroix Account: MWP-0002 Plan: Restricted Stock Units (RSUs) Document: current cycle Total grant value at grant date $800,000.00 Vesting schedule 25% per year over 4 yrs Vesting cliff | Marcus Delacroix has a Restricted Stock Units (RSUs) plan with a total grant value of $800,000, vesting 25% per year over 4 years. The first 25% tranche has already vested, with the remaining tranches vesting in years 2, 3, and 4. Each vesting event will be taxed as ordinary income, with the employer withholding 22% an |
| client_0000 | client_0000_risk_update_form.jpg | image | 0.997 | MERIDIAN WEALTH PARTNERS, LLC Registered Investment Adviser  RISK TOLERANCE UPDATE FORM · Form MWP-RT-02 Client: Alex Santos Account: MWP-0000 Prepared by: J. Reyes, CFP Document: following market-volatility review  Following recent market  | Alex Santos has updated their risk tolerance from moderate to moderate-conservative due to increased sensitivity to drawdowns as they approach age 60. This change was made following a review of recent market volatility. A suitability review will be conducted by advisor J. Reyes within 30 days to confirm the update. The |
| client_0002 | client_0002_onboarding_questionnaire.pdf | pdf | 0.996 | Registered Investment Adviser · Form ADV Part 2 on request Document: prior-year Q4 onboarding cycle Client: Marcus Delacroix Account: MWP-0002 Advisor of record: J. Reyes, CFP  1. Objectives: diversification of concentrated equity; tax plan | Marcus Delacroix, client of account MWP-0002, has objectives of diversifying concentrated equity and tax planning, with an aggressive risk tolerance tempered by past losses. His compensation consists of a base salary of $280,000 and total compensation of approximately $480,000 with RSUs, including $800,000 in RSUs vest |
| client_0001 | client_0001_retirement_intake.pdf | pdf | 0.996 | Registered Investment Adviser · Form ADV Part 2 on request Document: prior-year Q3 onboarding cycle Client: Sophia Hartmann Account: MWP-0001 Advisor of record: J. Reyes, CFP  1. Objectives: reliable income in retirement; capital preservati | Sophia Hartmann, a 58-year-old client, has a moderate to conservative risk tolerance and aims to achieve reliable income in retirement and capital preservation. She is nearing retirement, targeting ages 60-62, and has a household income goal of $120,000 per year, supplemented by her spouse's pension of $18,000 per year |
