"""Seed 5 sample clients with realistic wealth-advisor conversations into Lakebase.

Run from the repo root:
    uv run python scripts/seed_sample_data.py
"""

from __future__ import annotations

import uuid

from dotenv import load_dotenv

load_dotenv()

from agent_memory.memory.store import LakebaseMemoryStore  # noqa: E402 (after load_dotenv)

ADVISOR_ID = "advisor_demo_01"

# ---------------------------------------------------------------------------
# Sample data: 5 clients × 2 sessions × realistic multi-turn dialogues
# ---------------------------------------------------------------------------

SEED_DATA: list[dict] = [
    {
        "client_id": "client_0000",
        "display_name": "Alex Santos",
        "sessions": [],  # already seeded elsewhere; just register the name
    },
    {
        "client_id": "client_0001",
        "display_name": "Sophia Hartmann",
        "sessions": [
            {
                "session_id": "client_0001_session_00",
                "turns": [
                    ("user", "Hi, I'm approaching 58 and thinking seriously about retirement. I have about $2.1M in a mix of 401(k) and brokerage accounts. Where should I start?"),
                    ("assistant", "Sophia, great timing to start this conversation. At 58 with $2.1M, your primary tasks are (1) estimating your retirement income needs, (2) reviewing your asset allocation for sequence-of-returns risk, and (3) deciding when to claim Social Security. Can you tell me roughly what annual spend you're targeting in retirement, and whether you have any pension or other guaranteed income sources?"),
                    ("user", "We spend about $120k a year now. My husband has a small pension of about $18k/year. No other guaranteed income besides Social Security."),
                    ("assistant", "With a $120k target spend and an $18k pension, you need roughly $102k/year from your portfolio plus Social Security. At full retirement age (67) you'd likely get around $30–35k, which means portfolio drawdown of ~$67–72k/year — about a 3.2% withdrawal rate on $2.1M. That's comfortably within the 4% guideline. Your main risk is the 7-year gap if you retire now at 58, so we should look at the allocation in your taxable brokerage first as a near-term spending buffer. What does the current allocation look like?"),
                    ("user", "The 401(k) is mostly target-date funds — 2030 vintage. The brokerage is individual stocks, heavy in tech. Probably 60% in tech names."),
                    ("assistant", "The tech concentration in your taxable account is the priority concern. Heavy single-sector exposure at this stage introduces both sequence risk and tax complexity — if you need to sell in a down market to fund expenses, concentrated losses can be painful. I'd recommend a systematic tax-loss harvesting and rebalancing plan over the next 2–3 years to diversify without triggering a single large capital gains event. We should also assess whether the 2030 target-date fund's glide path is conservative enough for your actual timeline. Would you like me to model a phased diversification plan?"),
                    ("user", "Yes, that would be really helpful. Also — is there anything we should be doing on the Roth conversion front before I retire?"),
                    ("assistant", "Absolutely — Roth conversions are a high-value lever right now. You're likely in the 22–24% bracket today. Once you retire and before RMDs start at 73, you'll have a low-income window where you can convert at 12–22% depending on amount. Strategically filling the 22% bracket with conversions between retirement and age 73 could save significantly on RMD taxes later. I'll put together a Roth conversion ladder projection alongside the diversification plan. Let's schedule a follow-up to review both."),
                ],
            },
            {
                "session_id": "client_0001_session_01",
                "turns": [
                    ("user", "We looked at the diversification plan you sent. I'm on board with the phased approach. One new thing: my mother passed away last month and I'm inheriting roughly $400k in an IRA. How does that change things?"),
                    ("assistant", "Sophia, I'm sorry for your loss. An inherited IRA adds a meaningful dimension to your plan. As a non-spouse beneficiary under current rules, you're subject to the 10-year rule — you must fully distribute the account by the end of the 10th year after the original owner's death. You don't have to take distributions each year, but the full balance must be out by year 10. The question is how to sequence withdrawals to minimize your combined tax bill, especially given the Roth conversion strategy we discussed."),
                    ("user", "So should I take it out slowly or all at once?"),
                    ("assistant", "Spreading distributions across the 10 years is almost always better than bunching them — it avoids bracket spikes. The optimal strategy depends on your income each year. During your early retirement years with low income (before Social Security and RMDs), taking larger inherited IRA distributions while you're in a low bracket could be very efficient. I'd coordinate those distributions with the Roth conversion amounts so you don't stack them on top of each other and inadvertently push into a higher bracket. I'll model 3 scenarios: (1) even $40k/yr distributions, (2) front-loaded in low-income retirement years, (3) back-loaded. Give me a week to run the numbers."),
                    ("user", "That makes sense. On a different note, we also want to update our estate plan. Do you work with estate attorneys?"),
                    ("assistant", "We partner with two estate planning attorneys in the area — I'll connect you with both for an initial consultation. Given the inherited IRA, the Roth conversions, and your overall asset level, the priorities for the estate plan are: (1) confirming beneficiary designations across all accounts post-inheritance, (2) reviewing whether a credit shelter trust or a simpler pour-over will structure fits your situation, and (3) possibly an ILIT if your estate is approaching federal exemption thresholds. At $2.5M combined (post-inheritance), you're under current federal limits, but state estate taxes may apply depending on where you live."),
                ],
            },
        ],
    },
    {
        "client_id": "client_0002",
        "display_name": "Marcus Delacroix",
        "sessions": [
            {
                "session_id": "client_0002_session_00",
                "turns": [
                    ("user", "I just got a job offer that includes $800k in RSUs vesting over 4 years. I have no idea how RSUs are taxed or what to do when they vest."),
                    ("assistant", "Marcus, RSUs are taxed as ordinary income at vest — not at grant. On each vest date, the fair market value of the shares that vest is added to your W-2 income. So if 200 shares vest when the stock is $100, you have $20k of taxable income that year. Your employer will typically withhold at the 22% supplemental rate, which is often insufficient if you're in the 37% bracket. You'll want to model your total income each vest year to estimate the true tax liability and plan for underpayment."),
                    ("user", "That underpayment issue sounds like a problem. I was already surprised by a large tax bill last year."),
                    ("assistant", "Given last year's surprise, let's set up quarterly estimated payments tied to your vest schedule. I can help you calculate safe harbor amounts — either 100% of prior year tax liability (110% if AGI > $150k) or 90% of current year. Since your RSU income will be uneven across the year, we should look at the annualized income installment method, which lets you match estimated payments to when income actually hits rather than paying evenly. This prevents overpaying early quarters when income is low. What's your base salary?"),
                    ("user", "Base is $280k. Total comp will be roughly $480k in a full vest year."),
                    ("assistant", "At $480k total comp, you're solidly in the 37% bracket for federal plus your state rate. Here's the issue: employer withholding on the RSUs at 22% leaves a ~15% gap on each vest — that's potentially $30–45k underpaid per vest year depending on tranche size. Quarterly estimates will close that gap. On the investment side, the question is how long to hold RSUs after vest. From a concentration risk perspective, I generally recommend selling a meaningful portion at vest to diversify, unless there's a strong fundamental case for hold. What are your thoughts on concentration in company stock?"),
                    ("user", "I've been burned before — I held a lot of my last company's stock through a bad earnings miss. I'd rather diversify."),
                    ("assistant", "That's a prudent instinct. A simple rule: sell at least 50–75% of each vest tranche to cap concentration, keep remainder if you have high conviction. We can do this via a Rule 10b5-1 plan if you're classified as an insider, which allows pre-scheduled sales without insider trading concerns. For the proceeds, we'll build a diversified portfolio alongside your existing accounts. Let's also look at maximizing your 401(k) and any mega-backdoor Roth option your new employer offers — at your income, every pre-tax dollar counts."),
                ],
            },
            {
                "session_id": "client_0002_session_01",
                "turns": [
                    ("user", "First vesting cliff just happened — 25% of the grant vested. I sold 60% like we discussed. The remaining shares have already appreciated 15% since vest. Should I sell more?"),
                    ("assistant", "Great execution on the 60% sale. For the remaining 40%: the 15% gain since vest means you now have short-term capital gains territory if you sell before the 1-year holding period from vest date. If you can hold those shares another ~9 months, you convert to long-term capital gains, which at your income is 20% federal versus 37% ordinary. That's roughly a 17% tax rate difference, which on a $50k holding could be $8,500 in tax savings — worth waiting for if your concentration comfort allows."),
                    ("user", "I can stomach holding them. New question: I want to buy a house in the next 18 months, roughly $1.8M purchase. How should I think about the down payment?"),
                    ("assistant", "An $1.8M purchase typically requires 20% ($360k) to avoid jumbo PMI. With your income and assets, you could put 20–30% down. The key trade-off is opportunity cost: dollars in the down payment aren't invested. At your income level, a jumbo mortgage rate is likely 6.5–7%, while a diversified equity portfolio has a historical expected return of 7–10% — the spread is thin, so a 20% down payment rather than a larger one is defensible. I'd recommend reserving the down payment in a money market or short-duration bond ladder now given the 18-month timeline — equity risk is too high for a fixed near-term goal. What's your current liquid savings outside of retirement accounts?"),
                    ("user", "About $220k in a brokerage, plus the RSU proceeds from the cliff vest — roughly $180k after tax."),
                    ("assistant", "You're at ~$400k liquid, which covers a 20–22% down payment with a small buffer. I'd sweep the $400k into a tiered liquidity stack: 6-month emergency fund in HYSA, then 6-month bucket in 3–6 month T-bills, then the remaining home purchase reserve in a 12–18 month CD ladder or short-duration bond ETF. This way you're earning 4.5–5% while you wait, rather than sitting in cash. We should also pre-qualify for the mortgage now — lenders will want to see 2 years of W-2s plus documentation of the RSU vesting schedule, and the pre-qual process can surface any issues early."),
                ],
            },
        ],
    },
    {
        "client_id": "client_0003",
        "display_name": "Elena Vasquez",
        "sessions": [
            {
                "session_id": "client_0003_session_00",
                "turns": [
                    ("user", "My husband and I are recently divorced. I received the house ($850k, paid off) and $310k in a brokerage account in the settlement. I've never managed finances on my own before. Where do I start?"),
                    ("assistant", "Elena, navigating finances solo for the first time after a major life transition is challenging, and I want to make sure we build this properly from the ground up. First priority: change all beneficiary designations on every account — brokerage, retirement accounts, life insurance policies — today. These override your will and the settlement agreement. Second: establish a household cash flow budget. Third: we'll review the brokerage account allocation, which may have been structured around joint goals that no longer apply. Can you tell me about your income situation and any existing retirement accounts?"),
                    ("user", "I work as a nurse practitioner, about $135k/year. I have a 403(b) with roughly $180k in it. My ex-husband has the 401(k); I received a QDRO for half of it, which should add another $95k when it transfers."),
                    ("assistant", "Good — the QDRO transfer is important to follow up on. Once it arrives, you'll have the option to roll it into your own IRA or into your 403(b) if your plan allows rollovers in. An IRA rollover gives you more investment flexibility. Total retirement assets will be roughly $275k, plus $310k brokerage and $850k in home equity — a solid foundation. At $135k income, your emergency fund target is 6 months of expenses. Do you know roughly what your monthly expenses are now that you're running the household solo?"),
                    ("user", "The mortgage is paid off, which helps a lot. I'm estimating around $5,500/month including property taxes and utilities. My son is 14, so college is coming up in 4 years."),
                    ("assistant", "With $5,500/month, a 6-month emergency fund is $33k — that should be your first cash target from the brokerage account, sitting in a HYSA. On college: 4 years is a short timeline for a 529, but even partial funding helps. You won't be eligible for financial aid at your income for most schools. I'd suggest opening a 529 and contributing $500–1,000/month, which at current rates could grow to $25–30k by college start — meaningful but not full coverage. Does your son have any sense of what kind of schools he's targeting?"),
                    ("user", "He wants to study engineering. We're looking at state schools primarily, maybe $30–35k/year all-in."),
                    ("assistant", "State school at $30–35k with 4 years of growth, you're looking at ~$130–140k total. The 529 won't cover it all, but I'd still aim to fund a third to half via 529 and plan to supplement from cash flow and the brokerage. On the brokerage account — what is currently in it? I want to assess whether the allocation fits your new risk profile as a single-income household."),
                ],
            },
            {
                "session_id": "client_0003_session_01",
                "turns": [
                    ("user", "I've been thinking about the house. It feels too big now — it's a 4-bedroom. Should I sell and downsize? What are the tax implications?"),
                    ("assistant", "A great question and a very common post-divorce consideration. The primary residence capital gains exclusion for a single filer is $250k — you can exclude up to $250k of gain from the sale. You need to have lived in the home as your primary residence for 2 of the last 5 years. What did you and your ex-husband pay for the home originally, and how long have you lived there?"),
                    ("user", "We bought it 12 years ago for $420k. So the gain is about $430k. I think I'll owe tax on $180k of that?"),
                    ("assistant", "Exactly right — $430k gain minus $250k exclusion leaves $180k taxable as long-term capital gains. At your income, that's the 15% federal LTCG rate, so roughly $27k in federal capital gains tax, plus your state rate. Before you decide, let's model the sell-vs-stay economics: if you sell and net roughly $820k after tax and transaction costs, you could buy a $500k condo free and clear and invest the $320k difference. That invested $320k at historical returns could generate meaningful portfolio growth while eliminating maintenance costs on a large house. Would you like me to run that comparison with a 10- and 15-year projection?"),
                    ("user", "Yes please. Also — I realized I never set up a will or healthcare directive. My ex handled all of that."),
                    ("assistant", "Estate documents are essential to update right away, especially with a minor child. You need at minimum: (1) a will that names a guardian for your son and specifies who receives your assets, (2) a durable power of attorney for finances, (3) a healthcare directive or living will, and (4) a healthcare proxy designating who makes medical decisions if you're incapacitated. Given your son's age, you should also create a testamentary trust in your will that holds his inheritance in trust until he reaches 25 or so — rather than having assets pass outright to a minor. I'll connect you with our estate planning partner. This should take 2–3 sessions with her to complete."),
                ],
            },
        ],
    },
    {
        "client_id": "client_0004",
        "display_name": "James Okafor",
        "sessions": [
            {
                "session_id": "client_0004_session_00",
                "turns": [
                    ("user", "I'm 34, just started earning serious money — $210k base plus bonus. I feel behind on saving and investing. How do I prioritize?"),
                    ("assistant", "James, you're not behind — starting to optimize at 34 with a strong income is an excellent position. The standard prioritization framework: first, capture the full employer 401(k) match (free money, do this before everything else). Second, build a 3–6 month emergency fund if you don't have one. Third, max the HSA if you have a high-deductible health plan — it's the only triple-tax-advantaged account. Fourth, max the 401(k) ($23,500 limit in 2025). Fifth, consider a backdoor Roth IRA ($7,000 limit). Sixth, taxable brokerage. Does this order generally match what you're doing today?"),
                    ("user", "I'm contributing 6% to the 401(k) to get the match, but that's it. No HSA. I have about $40k in savings."),
                    ("assistant", "You're leaving significant tax-advantaged space on the table. At $210k, maxing your 401(k) to $23,500 saves roughly $8,225 in federal taxes alone (at 35% marginal rate) versus contributing only the match amount. I'd recommend increasing your 401(k) contribution to the maximum — your take-home will drop but by less than the contribution amount because of the tax savings. On the HSA: if your employer offers an HDHP option, compare the premium savings versus the higher deductible risk. For a healthy 34-year-old, the HDHP plus HSA is almost always the better deal. What are your current monthly expenses and debts?"),
                    ("user", "Rent is $2,200. No debt except a car payment of $450/month, 2 years left. Monthly expenses are around $5,500 total."),
                    ("assistant", "At $5,500/month, your $40k savings is a solid 7-month emergency fund — that's the right level. The car loan at $450/month with 2 years left at presumably 4–6% rate doesn't need to be rushed; I'd channel excess cash to the 401(k) rather than paying the car off early. Once the car is paid off in 2 years, redirect that $450 to the taxable brokerage. Let's talk about the brokerage account — do you have one, and if so what's in it? And what's your risk tolerance? Are you comfortable with full equity exposure given your long time horizon?"),
                    ("user", "I have $15k in a Robinhood account, mostly individual stocks — a few tech names and some Reddit-popular stocks I bought a couple years ago. Nothing huge."),
                    ("assistant", "The Robinhood account with individual stocks is common for someone building interest in investing, but at your stage, individual stock picking is less effective than index funds — primarily because of concentration, behavioral risk, and the difficulty of beating the market. I'd suggest a migration plan: evaluate each position for unrealized gains or losses. Positions with losses can be sold for tax-loss harvesting to offset future gains. Positions with large gains you might hold temporarily or sell over a year or two. The proceeds go into low-cost index ETFs — total market, international, bonds proportional to your risk tolerance. Over 30 years, expense ratios matter enormously."),
                ],
            },
            {
                "session_id": "client_0004_session_01",
                "turns": [
                    ("user", "Quick update: I maxed the 401(k) like you suggested and switched to the HDHP for the HSA. Feels good. New question: I'm thinking about buying my first home in the next 2–3 years. How do I plan for that?"),
                    ("assistant", "Excellent execution, James. For the home purchase in 2–3 years: the core planning task is building and protecting the down payment. First, decide your target price range and down payment percentage. In most markets, 20% avoids PMI on conventional loans, but there are first-time buyer programs that allow 3–5% down with other benefits. What city/market are you targeting, and do you have a rough price point in mind?"),
                    ("user", "Probably stay in Austin. Hoping to spend $550–650k. I'd want to put 20% down."),
                    ("assistant", "Austin at $600k mid-range means a $120k down payment target. Plus closing costs of roughly 2–3% ($12–18k) and a 3–6 month post-closing cash reserve. All-in you want ~$150–160k liquid and accessible within 2–3 years. Your current trajectory — maxing 401(k) at $23.5k plus HSA at $4.3k — frees about $25–30k/year for the taxable brokerage and home savings. At that rate you can hit $150k in about 2 years if you keep living costs flat. Key principle: money earmarked for a 2–3 year home purchase should not be in equities. Target high-yield savings, I-bonds, or a 2-year CD ladder. The last thing you want is a 20% market drop 6 months before closing."),
                    ("user", "That makes sense. Separately — I got a bonus of $35k this year. Any guidance on deploying that?"),
                    ("assistant", "Perfect timing on the bonus question. Here's how I'd allocate it: First, check if you've maxed your HSA — if not, fill it ($4,300 for individual coverage). Second, contribute $7,000 to a backdoor Roth IRA for the year if you haven't. Those two moves shelter ~$11k. The remaining $24k I'd split: half to your home down payment reserve (in a HYSA or T-bills), half to taxable brokerage in a total market index fund. You're already saving aggressively in the 401(k), so this bonus allocation gets you to your home goal faster while keeping equity exposure going. How does that feel relative to other priorities?"),
                ],
            },
        ],
    },
    {
        "client_id": "client_0005",
        "display_name": "Patricia Chen",
        "sessions": [
            {
                "session_id": "client_0005_session_00",
                "turns": [
                    ("user", "My father passed away last year and I inherited a $1.2M portfolio. I'm 52, still working, income around $175k. I feel overwhelmed and haven't done anything with the inherited assets."),
                    ("assistant", "Patricia, I'm sorry for the loss of your father. Taking time before making major decisions with inherited assets is actually wise — emotional decisions made in grief often look different a year later. The most urgent items are procedural: confirm all accounts have been re-titled into your name or an inherited account structure, and check whether any of the assets were in IRAs (requiring specific inherited IRA treatment) versus taxable accounts (which receive a stepped-up cost basis). Do you know the breakdown between retirement accounts and taxable accounts in the portfolio?"),
                    ("user", "About $400k is in a traditional IRA — his. The rest, $800k, is in a taxable brokerage that his advisor managed. I'm not sure of the cost basis."),
                    ("assistant", "The cost basis question on the $800k taxable account is actually good news: inherited taxable accounts receive a stepped-up cost basis to the fair market value on the date of death. This means if your father bought a stock for $50 that's now worth $200, your cost basis is $200 — the $150 gain evaporates from a tax perspective. This is a powerful planning tool: you can rebalance or diversify the $800k portfolio with minimal capital gains tax if done soon. The $400k inherited IRA is subject to the 10-year distribution rule — you must empty it by end of year 10 after his death. With your income at $175k, thoughtful distribution planning is essential. What year did he pass?"),
                    ("user", "He passed in August 2024. So I have until 2034. How should I think about the IRA distributions?"),
                    ("assistant", "You have a 10-year window from 2024 to 2034. Your income at $175k puts you in the 32% bracket. If we assume your income stays relatively flat or grows modestly, you'll want to spread distributions across years where your total income — including the IRA distribution — stays below the 35% threshold ($243k for single, $487k married). If you're single, taking $60–70k/year from the inherited IRA would keep you in the 32% bracket. If income drops in early retirement years, you can take larger distributions at lower rates. The worst outcome is bunching large distributions into high-income years or leaving it all to year 10 when mandatory full withdrawal could create a massive tax spike. I'll build a distribution projection."),
                    ("user", "I'm married, filing jointly. My husband earns about $80k. So combined income is $255k before any IRA distributions."),
                    ("assistant", "With combined income of $255k MFJ, you're already in the 32% bracket (threshold is $243k for 2025). Adding any inherited IRA distribution pushes further into 32% or into 35%. The strategy shifts slightly: take conservative distributions each year — perhaps $40–60k — to avoid the 35% bracket ($487k MFJ threshold). This smooths out the tax over 10 years rather than hitting a large rate in any single year. Additionally, I'd check if you and your husband have room to maximize pre-tax contributions to reduce your current AGI: 401(k)s, HSA, possible SEP-IRA if either of you has self-employment income."),
                ],
            },
            {
                "session_id": "client_0005_session_01",
                "turns": [
                    ("user", "We've started the inherited IRA distributions — taking $50k/year like you suggested. New question: my daughter is starting college next year, and we haven't saved as much as I wish. She's been accepted to a private school that costs $72k/year."),
                    ("assistant", "Patricia, $72k/year is at the high end of private school costs — total 4-year cost around $288k. What's your current college savings situation? Do you have a 529 or other dedicated college savings?"),
                    ("user", "We have $85k in a 529. That covers about a year. We're planning to pay from cash flow and the inherited assets for the rest."),
                    ("assistant", "With $85k in the 529 and $255k combined income plus the inherited portfolio, you have the resources to handle this — it's a matter of structuring it tax-efficiently. Options: (1) Use the 529 first, exhaust it over 1–1.5 years. (2) Then pay from after-tax cash flow — at $255k combined, you may not qualify for much aid, so you're likely paying full freight. (3) Use the stepped-up basis in the inherited taxable portfolio to fund the remaining years — since basis is stepped up, selling appreciated shares generates minimal gains tax. The $800k taxable portfolio is actually an ideal college funding vehicle for exactly this reason. I'd avoid withdrawing more from the inherited IRA than the $50k/year plan because of the tax cost."),
                    ("user", "That makes sense. I want to make sure the assets last. I'm also starting to think about my own retirement — my target is 62, so roughly 10 years. Is $1.2M plus our own savings enough?"),
                    ("assistant", "Let's build that picture. You have the $1.2M inherited portfolio, plus your own retirement savings — what do those look like? And roughly what annual spending are you targeting in retirement?"),
                    ("user", "We have about $480k combined in our 401(k)s. Plus we own our home outright, worth about $900k. Target spend is around $150k/year."),
                    ("assistant", "Total picture: $480k retirement accounts + $1.2M inherited (less college costs of ~$200k over 4 years, so ~$1M net) = roughly $1.5M portfolio going into retirement, plus $900k illiquid home equity. At $150k/year spend, you'd likely see $45–50k from Social Security at 62 (reduced for early claiming) or $65–75k if you wait to 67. Taking Social Security at 62 means a permanent 30% reduction. With $1.5M, funding the $150k gap before Social Security at a 5–6% withdrawal rate is feasible but tight. I'd strongly recommend running the numbers on delaying Social Security to 65 or 67 — every year of delay increases the benefit 6–8%, and by 85 the breakeven math heavily favors waiting. I'll model 3 claiming ages for both you and your husband."),
                ],
            },
        ],
    },
]


def seed():
    store = LakebaseMemoryStore()
    total_turns = 0

    for client in SEED_DATA:
        client_id = client["client_id"]
        display_name = client["display_name"]
        print(f"\nRegistering {display_name} ({client_id})...")
        store.upsert_client(client_id, display_name)

        for session_data in client.get("sessions", []):
            session_id = session_data["session_id"]
            print(f"  Session {session_id}: ", end="", flush=True)

            for idx, (role, content) in enumerate(session_data["turns"]):
                store.append_turn(
                    client_id=client_id,
                    advisor_id=ADVISOR_ID,
                    session_id=session_id,
                    turn_index=idx,
                    role=role,
                    content=content,
                    source="agent",
                    embed=True,
                )
                print(".", end="", flush=True)
                total_turns += 1

            print(f" {len(session_data['turns'])} turns")

    print(f"\nDone. Inserted {total_turns} turns across {len(SEED_DATA)} clients.")


if __name__ == "__main__":
    seed()
