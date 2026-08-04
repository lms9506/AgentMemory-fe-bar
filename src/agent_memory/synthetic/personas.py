"""Hand-authored demo personas — refined client dossiers for the seed (ADR-0015).

Three distinct clients, each with a continuous storyline told across 6-7 dossier
artifacts in mixed input formats (handwritten note, printed PDF statement, scanned
form, typed text) spread over ~8 months. ``days_ago`` backdates each artifact at
seed time so the dossier timeline reads as a real longitudinal history.

Binary artifacts (handwritten/pdf/scan) are rendered to committed fixtures by
``scripts/render_fixtures.py``; text artifacts are ingested from ``content`` directly.
The ``content`` here is the ground truth — for binary artifacts it is what gets
rendered onto the page, so ai_parse_document should recover it on ingest.

Absolute dates are intentionally kept out of the content (the timeline carries the
date); content uses relative phrasing so it never contradicts the backdated stamp.

Realism uplift (2026-07): every printed / scanned document carries a Meridian
Wealth Partners, LLC header, an advisor of record (J. Reyes, CFP®), an internal
account identifier, and a compliance / retention footer. Statements include
share counts and % of portfolio columns.
"""

from __future__ import annotations

from dataclasses import dataclass

ArtifactFormat = ["text", "handwritten", "pdf", "scan"]

# format → ingest ArtifactKind (handwritten + scan are both image OCR paths).
_FORMAT_KIND = {"text": "text", "handwritten": "image", "pdf": "pdf", "scan": "image"}
_FORMAT_EXT = {"text": "txt", "handwritten": "png", "pdf": "pdf", "scan": "jpg"}

_ADVISOR_ID = "advisor_demo_01"


@dataclass(frozen=True)
class SeedArtifact:
    """One artifact in a persona dossier."""

    category: str            # 'note' | 'statement' | 'doc'
    fmt: str                 # 'text' | 'handwritten' | 'pdf' | 'scan'
    slug: str                # stable basename (no extension), unique within a client
    content: str             # ground-truth text (rendered for binary fmts)
    days_ago: int            # backdate offset from seed time

    @property
    def kind(self) -> str:
        return _FORMAT_KIND[self.fmt]

    def filename(self, client_id: str) -> str:
        return f"{client_id}_{self.slug}.{_FORMAT_EXT[self.fmt]}"


@dataclass(frozen=True)
class Persona:
    client_id: str
    display_name: str
    artifacts: tuple[SeedArtifact, ...]


# ---------------------------------------------------------------------------
# Persona 1 — Alex Santos: single professional, conservative-leaning, retirement
# + tax-efficient growth, supports a sibling, ESG preference, ~$2.9M.
# ---------------------------------------------------------------------------
_ALEX = Persona(
    client_id="client_0000",
    display_name="Alex Santos",
    artifacts=(
        SeedArtifact(
            category="doc", fmt="pdf", slug="advisory_questionnaire", days_ago=242,
            content=(
                "MERIDIAN WEALTH PARTNERS, LLC\n"
                "Registered Investment Adviser  ·  Form ADV Part 2 on request\n"
                "\n"
                "ADVISORY INTAKE QUESTIONNAIRE\n"
                "Document: prior-year Q4 onboarding cycle\n"
                "Client: Alex Santos            Account: MWP-0000\n"
                "Advisor of record: J. Reyes, CFP\n"
                "\n"
                "1. Primary objectives: retirement funding and tax-efficient growth.\n"
                "2. Risk tolerance: moderate.\n"
                "3. Time horizon: 10+ years to retirement; target retirement age 65.\n"
                "4. Annual income band: $250k - $500k.\n"
                "5. Liquid net worth band: $1M - $5M.\n"
                "6. Family situation: single professional; supports a younger\n"
                "   sibling's education through a 529 plan.\n"
                "7. Prior investment experience: intermediate.\n"
                "8. Ethical / ESG preferences: ESG preferred where returns are\n"
                "   comparable to non-ESG equivalents.\n"
                "\n"
                "Client signature on file.  Advisor: J. Reyes, CFP\n"
                "Suitability review complete per firm policy.\n"
                "\n"
                "Confidential. Not investment advice on its own; see Form ADV\n"
                "Part 2 for firm disclosures and conflicts of interest.\n"
                "Retention: 7 years per firm policy."
            ),
        ),
        SeedArtifact(
            category="statement", fmt="pdf", slug="brokerage_statement_q1", days_ago=210,
            content=(
                "MERIDIAN WEALTH PARTNERS, LLC\n"
                "Custodian: Meridian Securities LLC (member SIPC)\n"
                "\n"
                "BROKERAGE STATEMENT\n"
                "Account holder: Alex Santos    Account: MWP-0000-BROK\n"
                "Statement period: prior quarter (Q1)\n"
                "Prepared for advisor: J. Reyes, CFP\n"
                "\n"
                "Portfolio summary\n"
                "  Beginning value            $2,748,102.30\n"
                "  Realized gain / loss          +$14,830.10\n"
                "  Unrealized gain / loss       +$124,009.10\n"
                "  ----------------------------------------\n"
                "  Ending value               $2,886,941.50\n"
                "  Period change                     +5.05%\n"
                "\n"
                "Holdings summary\n"
                "  Ticker Description            Shares       Value      % Port\n"
                "  VTI    Total Stock Market     4,214   $1,154,776.60   40.00%\n"
                "  VXUS   International Equity   6,981     $432,041.22   14.97%\n"
                "  BND    Total Bond Market      9,522     $721,735.38   25.00%\n"
                "  VNQ    Real Estate            2,545     $230,955.32    8.00%\n"
                "  VMFXX  Cash / Money Market  347,432     $347,432.98   12.03%\n"
                "\n"
                "Risk profile on file: moderate.\n"
                "Investment objectives: retirement, tax-efficient growth.\n"
                "\n"
                "For informational purposes only. Not a solicitation. Past\n"
                "performance is not indicative of future results. Confirm all\n"
                "trades on your custodian statement. Confidential."
            ),
        ),
        SeedArtifact(
            category="note", fmt="handwritten", slug="meeting_note_intro", days_ago=181,
            content=(
                "Meeting note - Alex Santos - annual review\n"
                "First annual review. Comfortable with the moderate allocation\n"
                "but flagged that tech feels heavy across the funds.\n"
                "Wants exposure reviewed before next year.\n"
                "Reminded client recommendations are considerations only,\n"
                "subject to compliance review. Client acknowledged.\n"
                "Next: pull a sector drilldown ahead of Q4 review.\n"
                "J. Reyes, CFP"
            ),
        ),
        SeedArtifact(
            category="doc", fmt="scan", slug="risk_update_form", days_ago=128,
            content=(
                "MERIDIAN WEALTH PARTNERS, LLC\n"
                "Registered Investment Adviser\n"
                "\n"
                "RISK TOLERANCE UPDATE FORM  ·  Form MWP-RT-02\n"
                "Client: Alex Santos             Account: MWP-0000\n"
                "Prepared by: J. Reyes, CFP\n"
                "Document: following market-volatility review\n"
                "\n"
                "Following recent market volatility the client elected to move\n"
                "their stated risk tolerance from moderate to moderate-\n"
                "conservative.\n"
                "\n"
                "Reason given: greater sensitivity to drawdowns approaching\n"
                "age 60.\n"
                "\n"
                "Advisor confirmed suitability review to follow within 30 days.\n"
                "\n"
                "Client signature on file.\n"
                "Compliance retention: 7 years per firm policy."
            ),
        ),
        SeedArtifact(
            category="note", fmt="handwritten", slug="meeting_note_dip", days_ago=74,
            content=(
                "Meeting note - Alex Santos - post drawdown\n"
                "Market dip rattled the client. Now leaning conservative.\n"
                "Wants to bring retirement forward to age 62 (was 65).\n"
                "Asked about shifting ~150k from equities into bonds.\n"
                "Still concerned about tech concentration.\n"
                "Action: prep suitability summary; flag tax-loss harvesting\n"
                "opportunities before year-end.\n"
                "J. Reyes, CFP"
            ),
        ),
        SeedArtifact(
            category="note", fmt="text", slug="typed_memo_529", days_ago=29,
            content=(
                "MEMO  ·  Meridian Wealth Partners, LLC  ·  Confidential (internal)\n"
                "Client: Alex Santos             Advisor: J. Reyes, CFP\n"
                "Re: 529 plan and taxable-account muni review\n"
                "\n"
                "Client wants to revisit the 529 college savings plan next quarter "
                "for their sibling's education, targeting roughly $80k of funding. "
                "Superfunding option (5-year gift-tax election) discussed as a "
                "possibility.\n"
                "\n"
                "Also asked to review muni bonds for the taxable account given the "
                "tax-efficiency objective. Consider a laddered muni portfolio "
                "(state of residence preferred for double tax exemption).\n"
                "\n"
                "No material life changes otherwise. Follow up before quarter-end.\n"
                "\n"
                "— J. Reyes, CFP"
            ),
        ),
    ),
)

# ---------------------------------------------------------------------------
# Persona 2 — Sophia Hartmann: 58, approaching retirement, tech-concentrated
# taxable account, inherited IRA from her mother, Roth-conversion planning, ~$2.5M.
# ---------------------------------------------------------------------------
_SOPHIA = Persona(
    client_id="client_0001",
    display_name="Sophia Hartmann",
    artifacts=(
        SeedArtifact(
            category="doc", fmt="pdf", slug="retirement_intake", days_ago=233,
            content=(
                "MERIDIAN WEALTH PARTNERS, LLC\n"
                "Registered Investment Adviser  ·  Form ADV Part 2 on request\n"
                "\n"
                "RETIREMENT PLANNING INTAKE\n"
                "Document: prior-year Q3 onboarding cycle\n"
                "Client: Sophia Hartmann        Account: MWP-0001\n"
                "Advisor of record: J. Reyes, CFP\n"
                "\n"
                "1. Objectives: reliable income in retirement; capital preservation.\n"
                "2. Risk tolerance: moderate, trending conservative.\n"
                "3. Current age: 58. Target retirement: 60 - 62.\n"
                "4. Household: married; spouse has a pension of ~$18k/yr and\n"
                "   Medicare eligibility in 5 years.\n"
                "5. Target annual spend in retirement: ~$120,000.\n"
                "6. Assets: ~$2.1M across 401(k) and a taxable brokerage account.\n"
                "7. Notes: taxable account is heavily concentrated in technology\n"
                "   stocks from long-tenure employer stock plan.\n"
                "\n"
                "Client signature on file.  Advisor: J. Reyes, CFP\n"
                "Suitability review scheduled.\n"
                "\n"
                "Confidential. Not investment advice on its own; see Form ADV\n"
                "Part 2 for firm disclosures. Retention: 7 years."
            ),
        ),
        SeedArtifact(
            category="statement", fmt="pdf", slug="brokerage_statement", days_ago=205,
            content=(
                "MERIDIAN WEALTH PARTNERS, LLC\n"
                "Custodian: Meridian Securities LLC (member SIPC)\n"
                "\n"
                "BROKERAGE STATEMENT (TAXABLE)\n"
                "Account holder: Sophia Hartmann  Account: MWP-0001-BROK\n"
                "Statement period: prior quarter\n"
                "Prepared for advisor: J. Reyes, CFP\n"
                "\n"
                "Portfolio summary\n"
                "  Beginning value           $2,014,109.60\n"
                "  Realized gain / loss          +$4,220.00\n"
                "  Unrealized gain / loss       +$86,490.40\n"
                "  ----------------------------------------\n"
                "  Ending value              $2,104,820.00\n"
                "  Period change                    +4.50%\n"
                "\n"
                "Holdings summary (taxable)\n"
                "  Ticker Description         Shares       Value      % Port\n"
                "  AAPL   Apple Inc.           2,015     $441,012.20   20.95%\n"
                "  NVDA   NVIDIA Corp.           288     $388,907.40   18.48%\n"
                "  MSFT   Microsoft Corp.        567     $266,540.10   12.66%\n"
                "  VTI    Total Stock Market     768     $210,482.00   10.00%\n"
                "  VMFXX  Cash / Money Market 147,337    $147,337.40    7.00%\n"
                "  Other single-name equity  ---        $650,540.90   30.91%\n"
                "\n"
                "Concentration note: single-name technology exposure totals\n"
                "roughly 60% of the taxable account. Sequence-of-returns risk\n"
                "is elevated for a client within 4 years of retirement.\n"
                "\n"
                "Risk profile on file: moderate.\n"
                "For informational purposes only. Confirm all trades on\n"
                "your custodian statement."
            ),
        ),
        SeedArtifact(
            category="note", fmt="handwritten", slug="meeting_note_concentration", days_ago=176,
            content=(
                "Meeting note - Sophia Hartmann - concentration review\n"
                "Spends ~120k/yr now; spouse pension 18k.\n"
                "Needs ~102k/yr from portfolio plus Social Security.\n"
                "Main worry: tech concentration in the taxable account -\n"
                "sequence risk if she retires at 58.\n"
                "Agreed: phased diversification over 2-3 years using\n"
                "tax-loss harvesting where possible. Will model Roth\n"
                "conversions.\n"
                "Next: three glide-path scenarios (fast / medium / gradual)\n"
                "by Q4.\n"
                "J. Reyes, CFP"
            ),
        ),
        SeedArtifact(
            category="doc", fmt="scan", slug="inherited_ira_letter", days_ago=96,
            content=(
                "MERIDIAN SECURITIES LLC  ·  CUSTODIAN NOTICE\n"
                "Custodian for Meridian Wealth Partners\n"
                "\n"
                "BENEFICIARY NOTIFICATION - INHERITED IRA\n"
                "Beneficiary: Sophia Hartmann   Account: MWP-0001-INH\n"
                "Prior owner: [redacted] (client's mother)\n"
                "Document: month following owner's death\n"
                "\n"
                "Notice of an inherited IRA of approximately $400,000\n"
                "following the death of the original account owner.\n"
                "\n"
                "As a non-spouse beneficiary the account is subject to the\n"
                "10-year distribution rule (SECURE Act). Full distribution\n"
                "is required by December 31 of the tenth year following the\n"
                "year of death. Annual distributions are not required unless\n"
                "the deceased had already begun RMDs.\n"
                "\n"
                "Please designate a rollover destination within 60 days.\n"
                "Compliance retention: 7 years per firm policy."
            ),
        ),
        SeedArtifact(
            category="note", fmt="handwritten", slug="meeting_note_inheritance", days_ago=61,
            content=(
                "Meeting note - Sophia Hartmann - inherited IRA\n"
                "Discussed the inherited IRA (~400k, 10-year rule).\n"
                "Plan: spread distributions across low-income early-\n"
                "retirement years and coordinate with Roth conversions\n"
                "to avoid bracket spikes.\n"
                "Client also wants to update the estate plan - refer to\n"
                "our local ELR partner firm.\n"
                "Combined estate now ~$2.5M.\n"
                "Next: 10-year distribution model with three cadence\n"
                "options (even / front / back-loaded).\n"
                "J. Reyes, CFP"
            ),
        ),
        SeedArtifact(
            category="note", fmt="text", slug="typed_memo_roth", days_ago=24,
            content=(
                "MEMO  ·  Meridian Wealth Partners, LLC  ·  Confidential (internal)\n"
                "Client: Sophia Hartmann         Advisor: J. Reyes, CFP\n"
                "Re: Roth conversion ladder\n"
                "\n"
                "Modeling a Roth conversion ladder for the window between "
                "retirement and age 73 (before required minimum distributions). "
                "Objective: fill the 22% federal bracket each year while keeping "
                "inherited-IRA distributions from stacking on top and pushing the "
                "marginal rate into the 24% or 32% brackets.\n"
                "\n"
                "Next: deliver three distribution scenarios (even / front-loaded / "
                "back-loaded), confirm beneficiary designations post-inheritance, "
                "and model state tax impact for state of residence.\n"
                "\n"
                "— J. Reyes, CFP"
            ),
        ),
    ),
)

# ---------------------------------------------------------------------------
# Persona 3 — Marcus Delacroix: tech executive, RSU-heavy comp, concentration
# risk, quarterly-tax underpayment history, planning a home purchase, ~$1.8M.
# ---------------------------------------------------------------------------
_MARCUS = Persona(
    client_id="client_0002",
    display_name="Marcus Delacroix",
    artifacts=(
        SeedArtifact(
            category="doc", fmt="pdf", slug="onboarding_questionnaire", days_ago=219,
            content=(
                "MERIDIAN WEALTH PARTNERS, LLC\n"
                "Registered Investment Adviser  ·  Form ADV Part 2 on request\n"
                "\n"
                "NEW CLIENT QUESTIONNAIRE\n"
                "Document: prior-year Q4 onboarding cycle\n"
                "Client: Marcus Delacroix       Account: MWP-0002\n"
                "Advisor of record: J. Reyes, CFP\n"
                "\n"
                "1. Objectives: diversification of concentrated equity; tax planning.\n"
                "2. Risk tolerance: aggressive, tempered by past single-stock losses.\n"
                "3. Compensation: base $280,000; total comp ~$480,000 with RSUs.\n"
                "4. Equity holdings: $800,000 in RSUs vesting over 4 years.\n"
                "5. Time horizon: long; near-term goal is a home purchase in\n"
                "   ~18 months.\n"
                "6. Prior investment experience: experienced; held a prior\n"
                "   employer's stock through a large drawdown before joining\n"
                "   current firm.\n"
                "\n"
                "Client signature on file.  Advisor: J. Reyes, CFP\n"
                "Suitability review complete.\n"
                "\n"
                "Confidential. Not investment advice on its own; see Form ADV\n"
                "Part 2. Retention: 7 years."
            ),
        ),
        SeedArtifact(
            category="statement", fmt="pdf", slug="equity_comp_statement", days_ago=198,
            content=(
                "MERIDIAN WEALTH PARTNERS, LLC\n"
                "Prepared from participant records\n"
                "\n"
                "EQUITY COMPENSATION STATEMENT\n"
                "Participant: Marcus Delacroix  Account: MWP-0002\n"
                "Plan: Restricted Stock Units (RSUs)\n"
                "Document: current cycle\n"
                "\n"
                "Grant summary\n"
                "  Total grant value at grant date       $800,000.00\n"
                "  Vesting schedule                      25% per year over 4 yrs\n"
                "  Vesting cliff completed               First 25% tranche\n"
                "\n"
                "Vesting schedule\n"
                "  Tranche  Vest year  Units      Value at grant     % Grant\n"
                "  1        Year 1      1,000      $200,000.00        25.00%\n"
                "  2        Year 2      1,000      $200,000.00        25.00%\n"
                "  3        Year 3      1,000      $200,000.00        25.00%\n"
                "  4        Year 4      1,000      $200,000.00        25.00%\n"
                "\n"
                "Tax note\n"
                "  RSUs are taxed as ordinary income at vest. Employer withholds\n"
                "  at the 22% supplemental federal rate, which is below the\n"
                "  participant's marginal rate (37%). Expect a ~15 percentage\n"
                "  point underpayment gap on each vesting event. Plan quarterly\n"
                "  estimated payments accordingly.\n"
                "\n"
                "For informational purposes only. Consult your tax adviser\n"
                "before acting. Confidential — for participant use only."
            ),
        ),
        SeedArtifact(
            category="note", fmt="handwritten", slug="meeting_note_rsu", days_ago=170,
            content=(
                "Meeting note - Marcus Delacroix - RSU planning\n"
                "Surprised by a big tax bill last year. RSU withholding at 22%\n"
                "leaves a ~15% gap vs his 37% bracket - 30-45k underpaid per\n"
                "vest year.\n"
                "Action: set up quarterly estimates (annualized-income method).\n"
                "On vesting: wants to diversify - sell 60-75% of each tranche.\n"
                "Consider a 10b5-1 plan for insider-window comfort.\n"
                "Burned holding old employer stock before - sensitive to\n"
                "concentration risk.\n"
                "J. Reyes, CFP"
            ),
        ),
        SeedArtifact(
            category="doc", fmt="scan", slug="estimated_tax_voucher", days_ago=118,
            content=(
                "UNITED STATES INTERNAL REVENUE SERVICE  ·  FORM 1040-ES\n"
                "(Client copy - retained by Meridian Wealth Partners, LLC)\n"
                "\n"
                "ESTIMATED TAX PAYMENT RECORD\n"
                "Taxpayer: Marcus Delacroix     Account: MWP-0002\n"
                "Document: quarterly submission (current period)\n"
                "\n"
                "Quarterly estimated federal payment submitted for the current\n"
                "period. Method: annualized-income installment, tied to the RSU\n"
                "vesting schedule so payments track when withholding shortfalls\n"
                "occur rather than being spread evenly across the year.\n"
                "\n"
                "Purpose: close the supplemental-withholding gap on vested\n"
                "shares and avoid an underpayment penalty under IRC §6654.\n"
                "Safe-harbor target: 110% of prior-year federal liability\n"
                "(AGI over $150,000).\n"
                "\n"
                "Advisor of record: J. Reyes, CFP  ·  Meridian Wealth Partners"
            ),
        ),
        SeedArtifact(
            category="note", fmt="handwritten", slug="meeting_note_house", days_ago=58,
            content=(
                "Meeting note - Marcus Delacroix - home purchase\n"
                "First vest done - sold 60% as agreed. Remaining shares\n"
                "up ~15%; hold to long-term to cut the rate from 37% to\n"
                "20% (LTCG).\n"
                "New goal: buy a ~$1.8M home in ~18 months. Target 20%\n"
                "down (~360k).\n"
                "Park the down-payment reserve in T-bills / short-duration -\n"
                "no equity risk for a fixed near-term goal.\n"
                "~400k liquid available today.\n"
                "Next: build the tiered liquidity plan.\n"
                "J. Reyes, CFP"
            ),
        ),
        SeedArtifact(
            category="note", fmt="text", slug="typed_memo_liquidity", days_ago=21,
            content=(
                "MEMO  ·  Meridian Wealth Partners, LLC  ·  Confidential (internal)\n"
                "Client: Marcus Delacroix       Advisor: J. Reyes, CFP\n"
                "Re: home-purchase liquidity plan\n"
                "\n"
                "Down-payment reserve plan: tier ~$400k into three buckets ---\n"
                "\n"
                "  •  $50k    6-month HYSA emergency bucket (~4.5% APY)\n"
                "  •  $100k   3-6 month T-bill ladder (~5.0% YTM)\n"
                "  •  $250k   12-18 month CD ladder for the home-purchase\n"
                "             reserve (~4.8% avg, staggered maturity)\n"
                "\n"
                "Weighted blended yield ~4.85% while we wait.\n"
                "\n"
                "Also: pre-qualify for the jumbo mortgage now; lender will "
                "want two years of W-2s plus the RSU vest schedule. Keep "
                "diversifying vested proceeds into low-cost index funds; "
                "consolidate old 401(k) to current-employer plan if fees "
                "are favorable.\n"
                "\n"
                "— J. Reyes, CFP"
            ),
        ),
    ),
)

PERSONAS: tuple[Persona, ...] = (_ALEX, _SOPHIA, _MARCUS)
