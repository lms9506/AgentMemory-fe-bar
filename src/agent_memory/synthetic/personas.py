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
                "ADVISORY INTAKE QUESTIONNAIRE\n"
                "Client: Alex Santos\n"
                "\n"
                "1. Primary objectives: retirement and tax-efficient growth.\n"
                "2. Risk tolerance: moderate.\n"
                "3. Time horizon: 10+ years to retirement; target retirement age 65.\n"
                "4. Annual income band: 250k-500k.\n"
                "5. Liquid net worth band: 1M-5M.\n"
                "6. Family situation: single professional; supports a younger sibling's"
                " education.\n"
                "7. Prior investment experience: intermediate.\n"
                "8. Ethical / ESG preferences: ESG preferred where returns are comparable.\n"
                "\n"
                "Client signature on file. Advisor review complete."
            ),
        ),
        SeedArtifact(
            category="statement", fmt="pdf", slug="brokerage_statement_q1", days_ago=210,
            content=(
                "BROKERAGE STATEMENT\n"
                "Account: CLIENT_0000-BROK\n"
                "Period: prior quarter\n"
                "\n"
                "Total portfolio value: $2,886,941.50\n"
                "\n"
                "Holdings summary:\n"
                "  VTI    Total Stock Market         $1,154,776.60\n"
                "  VXUS   International Equity          $432,041.22\n"
                "  BND    Total Bond Market             $721,735.38\n"
                "  VNQ    Real Estate                   $230,955.32\n"
                "  VMFXX  Cash / Money Market           $347,432.98\n"
                "\n"
                "Risk profile on file: moderate.\n"
                "Investment objectives: retirement, tax-efficient growth.\n"
                "This statement is provided for informational purposes only."
            ),
        ),
        SeedArtifact(
            category="note", fmt="handwritten", slug="meeting_note_intro", days_ago=181,
            content=(
                "Meeting note - Alex Santos\n"
                "First annual review. Comfortable with the moderate allocation\n"
                "but flagged that tech feels heavy across the funds.\n"
                "Wants exposure reviewed before next year.\n"
                "Reminded client recommendations are considerations only,\n"
                "subject to compliance review. Client acknowledged."
            ),
        ),
        SeedArtifact(
            category="doc", fmt="scan", slug="risk_update_form", days_ago=128,
            content=(
                "RISK TOLERANCE UPDATE FORM\n"
                "Client: Alex Santos\n"
                "\n"
                "Following recent market volatility the client elected to move their\n"
                "stated risk tolerance from moderate to moderate-conservative.\n"
                "Reason given: greater sensitivity to drawdowns approaching age 60.\n"
                "Advisor confirmed suitability review to follow.\n"
                "\n"
                "Client signature on file."
            ),
        ),
        SeedArtifact(
            category="note", fmt="handwritten", slug="meeting_note_dip", days_ago=74,
            content=(
                "Meeting note - Alex Santos\n"
                "Market dip rattled the client. Now leaning conservative.\n"
                "Wants to bring retirement forward to age 62 (was 65).\n"
                "Asked about shifting roughly 150k from equities into bonds.\n"
                "Still concerned about tech concentration.\n"
                "Action: prepare a suitability summary; flag tax-loss harvesting."
            ),
        ),
        SeedArtifact(
            category="note", fmt="text", slug="typed_memo_529", days_ago=29,
            content=(
                "Typed memo - Alex Santos\n"
                "\n"
                "Client wants to revisit the 529 college savings plan next quarter for "
                "their sibling, targeting roughly 80k of funding. Also asked to review "
                "muni bonds for the taxable account given the tax-efficiency objective. "
                "No material life changes otherwise. Follow up before quarter-end."
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
                "RETIREMENT PLANNING INTAKE\n"
                "Client: Sophia Hartmann\n"
                "\n"
                "1. Objectives: income in retirement; capital preservation.\n"
                "2. Risk tolerance: moderate, trending conservative.\n"
                "3. Current age: 58. Target retirement: 60-62.\n"
                "4. Household: married; spouse has a pension of ~$18k/year.\n"
                "5. Target annual spend in retirement: ~$120,000.\n"
                "6. Assets: ~$2.1M across 401(k) and a taxable brokerage account.\n"
                "7. Notes: taxable account is heavily concentrated in technology stocks.\n"
            ),
        ),
        SeedArtifact(
            category="statement", fmt="pdf", slug="brokerage_statement", days_ago=205,
            content=(
                "BROKERAGE STATEMENT\n"
                "Account: CLIENT_0001-BROK\n"
                "Period: prior quarter\n"
                "\n"
                "Total portfolio value: $2,104,820.00\n"
                "\n"
                "Holdings summary (taxable):\n"
                "  AAPL   Apple Inc.                    $441,012.20\n"
                "  NVDA   NVIDIA Corp.                  $388,907.40\n"
                "  MSFT   Microsoft Corp.               $266,540.10\n"
                "  VTI    Total Stock Market            $210,482.00\n"
                "  VMFXX  Cash / Money Market           $147,337.40\n"
                "\n"
                "Concentration note: technology names total roughly 60% of the taxable"
                " account.\n"
                "Risk profile on file: moderate."
            ),
        ),
        SeedArtifact(
            category="note", fmt="handwritten", slug="meeting_note_concentration", days_ago=176,
            content=(
                "Meeting note - Sophia Hartmann\n"
                "Spends ~120k/yr now; spouse pension 18k. Needs ~102k/yr from\n"
                "portfolio plus Social Security. Main worry is the tech\n"
                "concentration in the taxable account - sequence risk if she\n"
                "retires at 58. Agreed to a phased diversification plan over\n"
                "2-3 years using tax-loss harvesting. Will model Roth conversions."
            ),
        ),
        SeedArtifact(
            category="doc", fmt="scan", slug="inherited_ira_letter", days_ago=96,
            content=(
                "BENEFICIARY NOTIFICATION - INHERITED IRA\n"
                "Beneficiary: Sophia Hartmann\n"
                "\n"
                "Notice of an inherited IRA of approximately $400,000 following the\n"
                "death of the original account owner (client's mother).\n"
                "As a non-spouse beneficiary the account is subject to the 10-year\n"
                "distribution rule. Full distribution required by the end of year 10.\n"
                "Annual distributions are not required, but the balance must be zero\n"
                "by the deadline."
            ),
        ),
        SeedArtifact(
            category="note", fmt="handwritten", slug="meeting_note_inheritance", days_ago=61,
            content=(
                "Meeting note - Sophia Hartmann\n"
                "Discussed the inherited IRA (~400k, 10-year rule). Plan to spread\n"
                "distributions across low-income early-retirement years and\n"
                "coordinate with Roth conversions to avoid bracket spikes.\n"
                "Client also wants to update the estate plan - connect her with\n"
                "an estate attorney. Combined estate now ~$2.5M."
            ),
        ),
        SeedArtifact(
            category="note", fmt="text", slug="typed_memo_roth", days_ago=24,
            content=(
                "Typed memo - Sophia Hartmann\n"
                "\n"
                "Modeling a Roth conversion ladder for the window between retirement and "
                "age 73 (before RMDs). Goal: fill the 22% bracket each year while keeping "
                "inherited-IRA distributions from stacking on top. Next: deliver three "
                "distribution scenarios (even / front-loaded / back-loaded) and confirm "
                "beneficiary designations post-inheritance."
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
                "NEW CLIENT QUESTIONNAIRE\n"
                "Client: Marcus Delacroix\n"
                "\n"
                "1. Objectives: diversification of concentrated equity; tax planning.\n"
                "2. Risk tolerance: aggressive, but burned by past single-stock losses.\n"
                "3. Compensation: base $280k; total comp ~$480k with RSUs.\n"
                "4. Equity: $800k in RSUs vesting over 4 years.\n"
                "5. Time horizon: long; near-term goal is a home purchase in ~18 months.\n"
                "6. Prior experience: experienced; held prior employer stock through a"
                " large drawdown.\n"
            ),
        ),
        SeedArtifact(
            category="statement", fmt="pdf", slug="equity_comp_statement", days_ago=198,
            content=(
                "EQUITY COMPENSATION STATEMENT\n"
                "Participant: CLIENT_0002\n"
                "Plan: Restricted Stock Units (RSUs)\n"
                "\n"
                "Total grant value at grant: $800,000.00\n"
                "Vesting schedule: 25% per year over 4 years.\n"
                "\n"
                "Tax note: RSUs are taxed as ordinary income at vest. Employer withholds\n"
                "at the 22% supplemental rate, which is below the participant's marginal\n"
                "rate (37%) - expect an underpayment gap on each vest.\n"
                "Next vesting cliff: first 25% tranche."
            ),
        ),
        SeedArtifact(
            category="note", fmt="handwritten", slug="meeting_note_rsu", days_ago=170,
            content=(
                "Meeting note - Marcus Delacroix\n"
                "Surprised by a big tax bill last year. RSU withholding at 22%\n"
                "leaves a ~15% gap vs his 37% bracket - 30-45k underpaid per\n"
                "vest year. Set up quarterly estimates (annualized method).\n"
                "On vesting: wants to diversify - sell 60-75% of each tranche,\n"
                "consider a 10b5-1 plan. Burned holding old employer stock before."
            ),
        ),
        SeedArtifact(
            category="doc", fmt="scan", slug="estimated_tax_voucher", days_ago=118,
            content=(
                "ESTIMATED TAX PAYMENT RECORD\n"
                "Taxpayer: Marcus Delacroix\n"
                "\n"
                "Quarterly estimated federal payment submitted for the current period.\n"
                "Method: annualized income installment, tied to the RSU vest schedule.\n"
                "Purpose: close the supplemental-withholding gap on vested shares and\n"
                "avoid an underpayment penalty.\n"
                "Safe harbor target: 110% of prior-year liability (AGI over $150k)."
            ),
        ),
        SeedArtifact(
            category="note", fmt="handwritten", slug="meeting_note_house", days_ago=58,
            content=(
                "Meeting note - Marcus Delacroix\n"
                "First vest done - sold 60% as agreed. Remaining shares up ~15%;\n"
                "hold to long-term to cut the rate from 37% to 20%.\n"
                "New goal: buy a ~$1.8M home in ~18 months, 20% down (~360k).\n"
                "Park the down payment in T-bills / short-duration - no equity\n"
                "risk for a fixed near-term goal. ~400k liquid available."
            ),
        ),
        SeedArtifact(
            category="note", fmt="text", slug="typed_memo_liquidity", days_ago=21,
            content=(
                "Typed memo - Marcus Delacroix\n"
                "\n"
                "Down-payment reserve plan: tier ~$400k into a 6-month HYSA emergency "
                "bucket, a 3-6 month T-bill bucket, and a 12-18 month CD ladder for the "
                "home-purchase reserve, earning ~4.5-5% while we wait. Pre-qualify for the "
                "jumbo mortgage now; lender will want two years of W-2s plus the RSU vest "
                "schedule. Keep diversifying vested proceeds into low-cost index funds."
            ),
        ),
    ),
)

PERSONAS: tuple[Persona, ...] = (_ALEX, _SOPHIA, _MARCUS)
