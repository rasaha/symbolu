"""
Finance & Economics Corpus Builder
===================================

Generates 50 documents covering finance topics including stocks, bonds, real estate,
cryptocurrencies, personal finance, banking, investment strategies, and economics.
"""

from typing import List
from .base import CorpusBuilder, DocumentSpec


class FinanceCorpusBuilder(CorpusBuilder):
    """Builder for Finance & Economics corpus."""

    @property
    def corpus_id(self) -> str:
        return "finance"

    @property
    def description(self) -> str:
        return "Finance and Economics covering markets, investments, personal finance, and economic policy"

    @property
    def domain(self) -> str:
        return "finance"

    def build_documents(self) -> List[DocumentSpec]:
        docs = []

        # Stock Markets (docs 1-5)
        docs.append(DocumentSpec(
            doc_id="fin_001",
            corpus_id=self.corpus_id,
            title="Understanding the Stock Market Fundamentals",
            content="""The stock market is a system where shares of publicly-held companies are issued and traded, allowing investors to own pieces of businesses and companies to raise capital. Understanding stock market fundamentals is essential for any investor.

A share of stock represents fractional ownership in a company. When you buy stock, you become a shareholder with a claim on the company's assets and earnings. Stock prices fluctuate based on supply and demand, company performance, economic conditions, and market sentiment.

The primary stock exchanges in the United States are the New York Stock Exchange (NYSE) and NASDAQ. The NYSE is older and primarily lists large-cap stocks, while NASDAQ specializes in technology and growth companies. Other major exchanges exist worldwide, including the London Stock Exchange, Tokyo Stock Exchange, and Hong Kong Stock Exchange.

Market indices track overall performance. The S&P 500 includes 500 large-cap US companies, the Dow Jones Industrial Average tracks 30 blue-chip stocks, and the NASDAQ-100 focuses on technology. These indices serve as benchmarks for portfolio performance and broader economic health.

Stock trading occurs through brokers who execute buy and sell orders. Modern brokers offer online platforms with real-time quotes, research tools, and commission-free trading for many securities. Order types include market orders (immediate execution at current price), limit orders (execute at specified price or better), and stop-loss orders (protective sells at predetermined levels).

The Securities and Exchange Commission (SEC) regulates stock markets and enforces securities laws. Rules including insider trading restrictions, disclosure requirements, and market manipulation prohibitions protect investors. Trading halts occur when price movements exceed certain thresholds, preventing panic selling.""",
            metadata={"domain": "markets", "tags": ["stocks", "exchanges", "trading", "indices"], "difficulty": "basic", "focus": "stock-markets"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_002",
            corpus_id=self.corpus_id,
            title="Stock Valuation Methods and Price-to-Earnings Ratios",
            content="""Stock valuation determines whether a stock is undervalued, fairly valued, or overvalued. Multiple methods exist for assessing stock value, each providing different perspectives on investment opportunity.

The Price-to-Earnings (P/E) ratio divides stock price by annual earnings per share. A lower P/E might suggest undervaluation, while higher P/E could indicate growth expectations or market enthusiasm. The P/E ratio varies by industry; technology companies typically have higher P/E ratios than utility companies due to different growth profiles.

The Price-to-Book (P/B) ratio compares market price to book value (assets minus liabilities). This metric is useful for value-heavy industries like banking and manufacturing but less meaningful for service companies with few tangible assets. A low P/B ratio sometimes indicates undervaluation or suggests market skepticism about future performance.

Discounted Cash Flow (DCF) analysis projects future cash flows and discounts them to present value using a required rate of return. This intrinsic value approach appeals to fundamental investors but depends heavily on accurate assumptions about growth rates and discount rates. Small changes in assumptions significantly affect valuations.

Enterprise Value (EV) equals market capitalization plus debt minus cash. The EV-to-EBITDA ratio (enterprise value divided by earnings before interest, taxes, depreciation, and amortization) enables comparison across companies with different capital structures. This metric is popular for analyzing mature companies.

Free Cash Flow represents cash generated after capital expenditures. The Price-to-Free-Cash-Flow ratio shows how much investors pay for each dollar of available cash. Growing free cash flow often signals strong business fundamentals and shareholder-friendly management.

Different valuation methods sometimes conflict, reflecting uncertainty in stock pricing. Professional analysts use multiple approaches simultaneously, recognizing that no single method perfectly predicts stock performance.""",
            metadata={"domain": "markets", "tags": ["valuation", "p-e-ratio", "analysis", "fundamentals"], "difficulty": "intermediate", "focus": "stock-valuation"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_003",
            corpus_id=self.corpus_id,
            title="Diversification and Portfolio Theory",
            content="""Portfolio diversification reduces risk by spreading investments across multiple assets with different characteristics. Modern Portfolio Theory, developed by Harry Markowitz, provides mathematical framework for optimal diversification.

Diversification works because assets respond differently to market conditions. When one investment declines, another may stay stable or rise, reducing overall portfolio volatility. Correlation measures how investments move together; negative correlation provides better diversification benefits than positive correlation.

Asset classes include stocks, bonds, real estate, commodities, and cash equivalents. Each has different risk-return profiles and responds to economic conditions uniquely. A balanced portfolio typically combines multiple asset classes to achieve desired risk levels.

Geographic diversification reduces country-specific risks. International stocks, bonds, and real estate provide exposure to different economies and currencies. Emerging market investments offer growth potential but with higher volatility and political risks compared to developed markets.

Sector diversification spreads stock holdings across industries—technology, healthcare, finance, consumer goods, energy, and others. Different sectors perform well in different economic environments. Tech stocks often lead in growth periods, while consumer staples and utilities provide stability during downturns.

The efficient frontier represents combinations of assets providing maximum return for each risk level. Investors select portfolios along this frontier matching their risk tolerance. However, markets constantly change, requiring periodic rebalancing to maintain target allocations.

Over-diversification into too many holdings can dilute returns and complicate management. Research suggests 20-30 individual stocks provide adequate diversification within a stock portfolio. Many investors achieve better results with diversified mutual funds or exchange-traded funds (ETFs) rather than picking individual securities.

Time horizon affects optimal diversification. Longer investment periods tolerate more volatility and equity exposure, while shorter horizons require more conservative, stable allocations.""",
            metadata={"domain": "investing", "tags": ["diversification", "portfolio", "risk-management", "asset-allocation"], "difficulty": "intermediate", "focus": "portfolio-theory"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_004",
            corpus_id=self.corpus_id,
            title="Bull and Bear Markets: Understanding Market Cycles",
            content="""Financial markets move in cycles driven by economic conditions, investor sentiment, and business performance. Bull markets feature rising prices and investor optimism, while bear markets experience declining prices and pessimism.

A bull market typically begins during economic recovery, characterized by GDP growth, employment gains, and rising corporate profits. Investors become optimistic about future prospects, increasing demand for stocks and driving prices higher. Bull markets often last several years, with the average bull market lasting roughly 4-5 years.

Bull market characteristics include rising stock indices, widening profit margins, increasing consumer spending, and improving business confidence. During bull markets, stocks typically outperform bonds, and cyclical stocks (autos, construction) outperform defensive stocks (utilities, consumer staples).

A bear market officially occurs when stock indices decline 20 percent from recent highs. Bear markets often accompany recessions, rising unemployment, and declining corporate profits. Investor pessimism causes selling pressure, further depressing prices. Bear markets typically last 1-3 years, though some extend longer.

Bear market characteristics include declining stock indices, compressed profit margins, rising unemployment, and business uncertainty. During bear markets, bonds often provide better returns than stocks, and defensive sectors outperform cyclical ones. Volatility increases, with larger daily price swings.

Market corrections refer to temporary price declines of 10-20 percent within overall bull markets. These normal market fluctuations provide buying opportunities for disciplined investors while testing the resolve of those with weak conviction.

Recognizing market cycle stages helps investors maintain perspective during dramatic price moves. Buying heavily during severe bear market pessimism and maintaining discipline during exuberant bull markets improves long-term results. However, consistently timing market cycles accurately is notoriously difficult even for professional investors.""",
            metadata={"domain": "markets", "tags": ["bull-market", "bear-market", "cycles", "sentiment"], "difficulty": "basic", "focus": "market-cycles"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_005",
            corpus_id=self.corpus_id,
            title="Initial Public Offerings (IPOs) and Going Public",
            content="""An Initial Public Offering (IPO) marks a company's transition from private to public ownership, allowing the general public to purchase shares for the first time. IPOs represent major events for growing companies seeking capital and shareholders seeking investment opportunities.

Companies pursue IPOs to raise capital for expansion, pay down debt, or reward early investors. The IPO process involves selecting underwriters (investment banks), regulatory filings with the SEC, and marketing to institutional and retail investors. The underwriting process typically takes 3-6 months.

The Securities and Exchange Commission requires companies to file detailed disclosure documents including business descriptions, financial statements, risk factors, and management biographies. These documents, called registration statements or prospectuses, provide investors with information necessary to make informed decisions.

Underwriters conduct due diligence, assess market demand, and determine share prices before public trading begins. Often IPOs are "oversubscribed," with demand exceeding available shares. Underwriters typically allocate shares to favored institutional clients rather than general public investors.

IPO pricing aims to provide good value to investors while maximizing capital raised for the company. Underpricing is common; many IPOs rise significantly on their first trading day as buying demand exceeds available shares. This "first-day pop" benefits early institutional buyers but suggests the company left money on the table.

Restrictions limit insider and employee trading after IPOs. These lock-up periods, typically lasting 180 days, prevent massive stock sales by company founders and employees immediately after the IPO. When lock-up periods expire, selling pressure sometimes depresses share prices.

Post-IPO companies face new requirements including quarterly earnings reports, annual audits, and governance standards. Public company status brings scrutiny from analysts, short-sellers, and activist investors. While IPOs provide liquidity and visibility, companies lose privacy and face pressure to meet quarterly earnings targets.""",
            metadata={"domain": "markets", "tags": ["ipo", "public-offerings", "underwriting", "capital-raising"], "difficulty": "intermediate", "focus": "ipo"}
        ))

        # Bonds and Fixed Income (docs 6-10)
        docs.append(DocumentSpec(
            doc_id="fin_006",
            corpus_id=self.corpus_id,
            title="Bond Basics: Understanding Fixed Income Securities",
            content="""Bonds are debt securities representing loans to governments or corporations. Bond investors become creditors, receiving periodic interest payments and principal repayment at maturity. Bonds provide stable income and lower volatility than stocks, making them essential portfolio components.

A bond's coupon rate determines annual interest payments. A $1,000 bond with 5 percent coupon pays $50 annually. Coupon rates depend on credit quality, maturity length, and market conditions. Higher-risk borrowers pay higher coupon rates to attract investors.

Bond prices move inversely to interest rates. When rates rise, existing bond prices fall because new bonds offer higher coupons. When rates decline, existing bonds increase in value. This inverse relationship is fundamental to bond investing and interest rate risk.

Duration measures bond price sensitivity to interest rate changes. Longer-duration bonds experience larger price swings with rate changes. Short-duration bonds provide more stability but lower yields. Investors match duration to their interest rate outlook and time horizon.

Credit ratings from agencies like Moody's, S&P, and Fitch assess default risk. Investment-grade bonds (rated BBB and above) have lower default risk, while high-yield or "junk" bonds offer higher coupons but greater default risk. Bond ratings change as issuer financial conditions evolve.

Yield to maturity (YTM) represents the total annual return including coupon payments and price appreciation or depreciation if held to maturity. YTM exceeds coupon rates for discount bonds (bought below par) and falls below coupon rates for premium bonds (bought above par).

Types include US Treasury bonds (backed by federal government), municipal bonds (issued by states and cities, often tax-exempt), corporate bonds, and international bonds. Different bond types appeal to different investors based on tax situations, risk tolerance, and return requirements.""",
            metadata={"domain": "fixed-income", "tags": ["bonds", "debt", "coupons", "yields"], "difficulty": "basic", "focus": "bond-basics"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_007",
            corpus_id=self.corpus_id,
            title="Interest Rate Risk and Bond Duration",
            content="""Interest rate risk—the danger that bond prices fall when interest rates rise—is crucial for bond investors. Understanding duration helps investors manage this risk and align portfolio positioning with interest rate expectations.

Modified duration measures the percentage price change for each 1 percent change in yield. A bond with 5-year modified duration loses approximately 5 percent of value for each 1 percent yield increase. Duration increases with longer maturities and lower coupon rates.

Macaulay duration represents the weighted average time to receive bond cash flows. This mathematical concept helps investors understand how long they must hold bonds to recover investments if rates change. Longer Macaulay duration indicates greater interest rate sensitivity.

A bond's convexity measures how duration changes as yields change. Positive convexity benefits investors, meaning price gains from falling rates exceed losses from rising rates of equal magnitude. Most bonds have positive convexity, though some mortgage-backed securities have negative convexity due to prepayment risks.

Bond portfolios with longer average duration perform better when interest rates decline but suffer when rates rise. Conservative investors seeking stability may hold shorter-duration bonds, accepting lower yields. Investors expecting rate declines may extend duration to capture larger price appreciation.

The yield curve plots bond yields across different maturities. A normal upward-sloping curve reflects additional risk and opportunity costs for longer-term lending. An inverted curve (short rates exceeding long rates) sometimes precedes recessions. Flat curves indicate market uncertainty about future rates.

Bond funds adjust duration through portfolio management. Rising rate environments encourage shorter-duration positioning, while declining-rate expectations suggest extending duration. Professional bond managers monitor economic data and central bank signals to guide duration decisions.

Understanding interest rate risk helps individual investors avoid panic selling during rate-rising environments and make strategic decisions about timing and maturity allocation.""",
            metadata={"domain": "fixed-income", "tags": ["duration", "interest-rates", "bond-prices", "risk"], "difficulty": "intermediate", "focus": "interest-rate-risk"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_008",
            corpus_id=self.corpus_id,
            title="Corporate Bonds: Credit Risk and Analysis",
            content="""Corporate bonds represent loans to companies, offering higher yields than government bonds but carrying credit risk. Analyzing corporate bond creditworthiness requires understanding company finances and industry dynamics.

Credit risk—the danger that companies default on bond obligations—determines credit spreads. Spreads represent additional yield corporations pay above Treasury bonds of similar maturity. Higher-risk companies pay wider spreads; lower-risk companies pay narrow spreads.

Financial metrics guide credit analysis. Debt-to-equity ratios measure leverage; lower ratios indicate healthier balance sheets. Interest coverage ratios (EBIT divided by interest expense) show whether companies generate sufficient earnings to service debt. Companies with coverage ratios below 2.0x face elevated default risk.

Cash flow analysis reveals whether operations generate sufficient cash for debt repayment. Operating cash flow exceeding interest and principal requirements indicates strong credit quality. Free cash flow after capital expenditures provides additional cushion for debt service.

Rating agencies regularly reassess corporate creditworthiness. Credit rating upgrades typically lower borrowing costs and bond prices rise, while downgrades increase yields and depress prices. Watch list designations signal potential downgrades, sometimes depressing prices before official rating changes.

Covenant protections limit company actions that could damage bondholder interests. Restrictions may include limitations on additional debt, dividend payouts, or asset sales. Negative covenants prevent actions harming creditors, while affirmative covenants require ongoing compliance with financial metrics.

Subordination ranking determines recovery priority in bankruptcy. Senior secured bonds have first claim on specific assets, while subordinated or junior bonds recover funds only after senior creditors. Conversion features allow some bondholders to exchange bonds for stock, creating hybrid equity-debt characteristics.

Bond analysts monitor industry trends, competitive positioning, management quality, and macroeconomic factors affecting companies' ability to repay. Fundamental analysis combining quantitative metrics with qualitative assessment helps identify credit opportunities and risks.""",
            metadata={"domain": "fixed-income", "tags": ["corporate-bonds", "credit-risk", "spreads", "covenants"], "difficulty": "intermediate", "focus": "credit-analysis"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_009",
            corpus_id=self.corpus_id,
            title="US Treasury Securities and Sovereign Debt",
            content="""US Treasury securities represent the safest bonds available to investors, backed by the full faith and credit of the US government. Understanding Treasury markets is fundamental to fixed income investing.

Treasury debt instruments include bills (less than one-year maturity), notes (1-10 years), and bonds (20-30 years). The government issues Treasury bills through auctions, and investors earn returns through discount pricing; bills issued at $9,800 mature for $10,000 par value.

The Treasury yield curve shows yields across maturities. Normal upward-sloping curves indicate expectations of economic growth and inflation. Inverted curves (short rates exceeding long rates) sometimes precede recessions, making them closely watched recession indicators. Flat curves signal market uncertainty.

Treasury Inflation-Protected Securities (TIPS) adjust principal value based on inflation rates. TIPS principal increases with Consumer Price Index increases and decreases with deflation. They provide inflation protection but typically offer lower real yields than conventional Treasuries.

Treasury bond prices and yields move inversely. When the Federal Reserve raises interest rates, new Treasury securities offer higher yields, causing existing bonds to fall in price. Fed rate decisions dramatically affect Treasury yields across the curve.

The national debt represents accumulated government borrowing. As of recent years, federal debt exceeds $30 trillion, raising concerns among some analysts about sustainability. However, unlike individuals and corporations, governments control currency creation and tax revenues, reducing default risk despite high debt levels.

Treasury markets are the world's most liquid bond markets, with huge daily trading volumes. This liquidity makes Treasuries popular for portfolio management and trading. Many international investors hold Treasuries as foreign exchange reserves.

Agencies including Fannie Mae and Freddie Mac issue mortgage-backed securities (MBS) backed by pools of residential mortgages. While not direct Treasury obligations, agency MBS benefit from implicit government backing, offering yields slightly above comparable Treasuries.""",
            metadata={"domain": "fixed-income", "tags": ["treasury", "government-bonds", "yield-curve", "tips"], "difficulty": "basic", "focus": "sovereign-debt"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_010",
            corpus_id=self.corpus_id,
            title="Municipal Bonds: Tax-Advantaged Investing",
            content="""Municipal bonds, issued by states, cities, and local governments, fund infrastructure projects including roads, bridges, schools, and public utilities. Municipal bonds offer significant tax advantages for many investors.

The primary advantage is federal tax exemption. Interest income from most municipal bonds escapes federal income taxation. Investors in high tax brackets benefit substantially; a 5 percent municipal yield equals roughly 7 percent taxable yield for someone in the 28 percent federal tax bracket.

State and local tax exemption enhances returns further. Most states exempt interest from bonds issued within their borders from state taxation. Residents of high-tax states like California, New York, and Massachusetts receive substantial tax benefits from in-state municipal bonds.

Credit quality varies significantly among municipal issuers. General obligation bonds backed by full taxing power of issuing governments carry lower credit risk. Revenue bonds, backed by specific project revenues, carry higher risks. Careful analysis of issuer finances is essential.

The municipal bond market is less liquid than stock and Treasury bond markets. Bid-ask spreads are wider for municipal bonds, and individual investors sometimes face difficulty trading odd lots (fewer than 100 bonds). Mutual funds and exchange-traded funds improve liquidity access.

Yields on municipal bonds typically run 1-3 percent below comparable Treasury yields, reflecting tax advantages and credit risks. Comparing tax-equivalent yields to taxable bonds helps investors evaluate whether municipal bonds offer value. Tax-equivalent yields adjust for federal tax benefits.

Moody's, S&P, and Fitch rate municipal bonds similarly to corporate bonds. Ratings reflect financial health and ability to service debt. Well-rated municipal bonds from major issuers offer attractive yields with reasonable credit quality.

Callable municipal bonds allow issuers to refinance when interest rates decline, potentially limiting investor gains. Call provisions typically require investors to accept reinvestment risk at lower rates. Understanding call provisions is crucial for municipal bond pricing and total return analysis.""",
            metadata={"domain": "fixed-income", "tags": ["municipal-bonds", "tax-exempt", "revenue-bonds", "credit-quality"], "difficulty": "intermediate", "focus": "municipal-bonds"}
        ))

        # Real Estate and Mortgages (docs 11-15)
        docs.append(DocumentSpec(
            doc_id="fin_011",
            corpus_id=self.corpus_id,
            title="Residential Mortgages: Types and Characteristics",
            content="""Mortgages represent one of the largest debts most people incur, involving complex terms and structures. Understanding mortgage options helps borrowers make informed decisions about home financing.

Fixed-rate mortgages maintain the same interest rate throughout the loan term, typically 15 or 30 years. Monthly payments include principal and interest, with principal repayment accelerating over time. Fixed rates provide stability and predictability; borrowers benefit if interest rates rise.

Adjustable-rate mortgages (ARMs) feature lower initial rates that adjust periodically based on market indices. While initial payments are lower, rate adjustments create payment uncertainty. ARMs typically include rate caps limiting annual increases and lifetime maximum rates.

Loan-to-value (LTV) ratio measures the loan amount relative to property value. Higher LTV ratios indicate greater leverage and risk to lenders. When LTV exceeds 80 percent, lenders typically require private mortgage insurance (PMI), adding cost to borrowers.

Points represent prepaid interest; borrowers can pay upfront fees to reduce the mortgage rate. One point equals 1 percent of the loan amount. Borrowers with longer time horizons benefit more from paying points; those expecting to move soon should avoid them.

Mortgage underwriting assesses borrower creditworthiness and property value. Lenders verify income, credit history, assets, and employment. Appraisals determine property values, protecting lender interests. Debt-to-income ratios (total debt payments divided by income) guide approval decisions.

Amortization schedules show payment breakdowns between principal and interest. Early payments are primarily interest; later payments shift toward principal. This structure means refinancing after many years provides less benefit since most interest has already been paid.

Pre-approval letters indicate borrower qualification amounts and make purchase offers more competitive. Mortgage contingencies protect buyers, allowing contract cancellation if financing cannot be obtained. Lenders provide Loan Estimate disclosures standardizing mortgage terms and costs.""",
            metadata={"domain": "real-estate", "tags": ["mortgages", "financing", "interest-rates", "amortization"], "difficulty": "basic", "focus": "mortgage-types"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_012",
            corpus_id=self.corpus_id,
            title="Real Estate Investment Trusts (REITs)",
            content="""Real Estate Investment Trusts (REITs) allow investors to participate in real estate markets without direct property ownership. REITs provide liquidity, professional management, and diversification benefits.

REITs are companies that own, operate, or finance income-producing real estate. They must comply with specific regulations including distributing at least 90 percent of taxable income to shareholders as dividends, avoiding corporate-level taxation.

Equity REITs own and operate properties including apartments, shopping centers, warehouses, hotels, and office buildings. Income derives from property rents. Equity REIT values depend on property quality, occupancy rates, and rental growth. Geographic and sector diversification affect performance.

Mortgage REITs originate or purchase mortgages and mortgage-backed securities. Income derives from mortgage interest payments. Mortgage REIT returns depend on interest rate spreads and credit performance. Rising rates typically hurt mortgage REIT values.

Commercial Real Estate REITs specialize in properties like office buildings and retail centers. These REITs respond to economic cycles; recessions increase vacancy and reduce rents. Essential services properties including groceries and pharmacies provide more stability.

Residential REITs own apartments and single-family homes. Population growth, employment trends, and supply-demand balances affect residential REIT values. Residential properties typically provide stable cash flows with lower volatility than office or retail.

REIT dividends are often taxed as ordinary income rather than capital gains, creating tax inefficiencies in taxable accounts. Holding REITs in tax-advantaged retirement accounts (401k, IRAs) reduces tax drag. REIT share prices fluctuate based on sentiment, interest rates, and property fundamentals.

Public REITs trade like stocks, providing liquidity. Non-traded REITs offer longer holding periods without daily valuation but provide less flexibility. REITs provide real estate exposure without direct property management responsibilities.""",
            metadata={"domain": "real-estate", "tags": ["reits", "real-estate", "equity-reits", "mortgage-reits"], "difficulty": "intermediate", "focus": "reits"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_013",
            corpus_id=self.corpus_id,
            title="Home Ownership: Costs and Financial Benefits",
            content="""Homeownership offers financial benefits and emotional rewards but involves significant costs and responsibilities. Understanding the full financial picture helps potential buyers make informed decisions.

Monthly mortgage payments represent the largest housing expense but come with tax advantages. Mortgage interest deductions reduce federal taxable income for itemizing taxpayers, providing substantial tax benefits, especially early in mortgage terms when interest payments are highest.

Property taxes vary dramatically by location, sometimes exceeding one percent of property value annually. High-tax areas include California, New Jersey, and Illinois. Some states offer homestead exemptions or senior citizen property tax reductions.

Homeowners insurance protects against fire, theft, and liability. Insurance costs depend on property value, location, claims history, and coverage limits. Mortgage lenders require insurance on mortgaged properties, often requiring impound accounts where borrowers prepay property taxes and insurance.

Maintenance and repairs include routine maintenance like lawn care and painting plus major repairs for roofs, HVAC systems, and plumbing. The 1 percent rule suggests setting aside 1 percent of property value annually for maintenance. Older homes typically require more maintenance than newer ones.

Utilities including electricity, gas, water, and sewer depend on climate, efficiency, and usage. Weatherization improvements including insulation, window upgrades, and HVAC efficiency reduce energy costs. Green homes with solar panels and efficient systems have lower utility bills.

Appreciation potential provides wealth-building benefits. Historically, real estate appreciates roughly 3 percent annually, roughly matching inflation. Leverage amplifies returns; a 20 percent down payment on appreciating property generates 5x return on initial investment before accounting for other costs.

Opportunity costs include opportunity to invest down payments and mortgage payments in stocks or bonds. Comparing ownership costs to rental alternatives helps determine whether buying or renting makes more financial sense in particular markets.""",
            metadata={"domain": "real-estate", "tags": ["homeownership", "mortgages", "property-taxes", "maintenance"], "difficulty": "basic", "focus": "home-costs"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_014",
            corpus_id=self.corpus_id,
            title="Real Estate Market Analysis and Investment",
            content="""Real estate markets vary dramatically by location, with different supply-demand dynamics, economic conditions, and demographic trends affecting prices and returns. Successful real estate investing requires thorough market analysis.

Market cycles affect real estate similarly to stock markets. Expansion phases feature rising prices, new construction, and investor optimism. Peak phases show highest prices but often contain speculative bubbles. Contraction phases feature declining prices, foreclosures, and pessimism. Recovery phases begin building conditions for new expansion.

Price-to-rent ratios compare property purchase prices to annual rental income. High ratios suggest buying is expensive relative to renting; low ratios favor buying. Geographic variation is substantial; coastal areas typically have high price-to-rent ratios while many Midwest markets have lower ratios.

Supply-demand balances dramatically affect prices. Limited housing supply in attractive markets supports prices. Markets with high vacancy rates and overbuilding face price pressures. Population growth areas typically show stronger price appreciation than declining markets.

Jobs and employment growth drive demand for housing. Cities with diverse job markets and low unemployment typically outperform economically weak areas. Industry concentrations also matter; tech hubs like San Francisco face different dynamics than manufacturing-dependent regions.

Schools and education drive residential demand. Properties in well-regarded school districts command price premiums. First-time parents often prioritize school quality, supporting prices in those areas.

Development costs including land, labor, and materials influence new construction and limit price appreciation. In areas with high development costs, existing home prices often rise sharply since new supply cannot be easily expanded.

Interest rates significantly affect housing affordability. Rising rates reduce purchasing power; borrowers can afford less at higher rates. Declining rates increase demand and support prices. Mortgage rate changes have immediate effects on housing demand and prices.""",
            metadata={"domain": "real-estate", "tags": ["real-estate-markets", "price-to-rent", "supply-demand", "investment"], "difficulty": "intermediate", "focus": "market-analysis"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_015",
            corpus_id=self.corpus_id,
            title="Commercial Real Estate and Lease Economics",
            content="""Commercial real estate encompasses office, retail, industrial, and hospitality properties generating income through tenant leases. Understanding lease economics is essential for commercial real estate investors.

Commercial leases typically run 3-10 years with renewal options. Base rent represents guaranteed income independent of property performance. Percentage leases, common in retail, include base rent plus percentage of tenant sales, aligning landlord interests with tenant success.

Triple-net (NNN) leases require tenants to pay base rent plus proportional shares of property taxes, insurance, and maintenance. These leases transfer operating risk to tenants. Tenants dislike NNN leases; landlords prefer them since expenses are covered.

Gross leases include operating costs in rental rates, with landlords bearing expense risk. Landlords must carefully price gross leases, including expense estimates. These leases favor tenants and are less common in modern commercial markets.

Capitalization rates (cap rates) divide net operating income by purchase price. A property generating $100,000 annual income selling for $1,000,000 has a 10 percent cap rate. Higher cap rates indicate better yields but often reflect higher risk or worse locations.

Non-Recourse Financing allows lenders to repossess property but not pursue borrowers personally. Commercial real estate typically features non-recourse debt, limiting borrower risk but potentially increasing interest rates.

Occupancy rates measure percentage of leasable space actually leased and generating income. Higher occupancy rates increase cash flow; vacancy increases landlord cost. High vacancy areas face price pressure and lower cap rates.

Tenant quality matters substantially. Creditworthy tenants like major corporations provide stable income; small businesses default more frequently. Long-term tenants with stable operations reduce vacancy risk. Tenant concentration risk (relying on one major tenant) requires premium yields.""",
            metadata={"domain": "real-estate", "tags": ["commercial-real-estate", "leases", "cap-rates", "tenants"], "difficulty": "intermediate", "focus": "commercial-re"}
        ))

        # Retirement Planning (docs 16-20)
        docs.append(DocumentSpec(
            doc_id="fin_016",
            corpus_id=self.corpus_id,
            title="401(k) Plans: Employer-Sponsored Retirement Savings",
            content="""401(k) plans allow workers to save for retirement with favorable tax treatment and often employer matching. Understanding 401(k) mechanics is crucial for retirement planning.

Participants contribute through payroll deductions; contributions are pre-tax, reducing current taxable income. In 2024, the contribution limit is $23,500 annually ($31,000 for those 50 and older with catch-up contributions). Employer contributions beyond these amounts are not capped at the same limit.

Employers often match contributions up to certain percentages, such as matching 100 percent of the first 3 percent of salary contributed. Employer matching represents free money and should be captured whenever possible. Vesting schedules determine when employer contributions become owned by employees.

Investment options within 401(k) plans typically include mutual funds, target-date funds, and stable value funds. Plan participants select asset allocation; common options include diversified portfolios spanning stocks, bonds, and money market funds. Financial guidance within plans helps participants make appropriate choices.

Pre-tax contributions reduce current taxes but create future tax obligations. All withdrawals in retirement are taxed at ordinary income rates. Roth 401(k) options allow after-tax contributions with tax-free withdrawals, providing tax diversification for retirees.

Early withdrawal penalties apply to funds withdrawn before age 59½; taxes plus 10 percent penalties typically apply. Exceptions include disability, medical expenses, and hardship withdrawals for specific purposes. Loans against 401(k) balances allow access without penalties but carry risks if employment ends.

Required Minimum Distributions (RMDs) force withdrawals beginning at age 73 (recently changed from 72). RMDs based on account balances and life expectancy tables ensure retirement savings are eventually distributed and taxed.

Plan portability allows participants to roll 401(k) balances to IRAs or new employer plans when changing jobs. Direct rollovers to IRAs avoid taxes and penalties, maintaining tax-deferred status and providing broader investment options.""",
            metadata={"domain": "retirement", "tags": ["401k", "employer-plans", "contributions", "vesting"], "difficulty": "basic", "focus": "employer-retirement"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_017",
            corpus_id=self.corpus_id,
            title="Individual Retirement Accounts (IRAs) and Tax-Advantaged Investing",
            content="""Individual Retirement Accounts (IRAs) enable individuals to save for retirement with tax advantages. Multiple IRA types serve different situations and retirement planning strategies.

Traditional IRAs allow tax-deductible contributions for those not covered by employer retirement plans or under certain income limits if covered. In 2024, the annual contribution limit is $7,000 ($8,500 for those 50 and older). Contributions reduce taxable income, and earnings grow tax-deferred.

Roth IRAs allow after-tax contributions with tax-free growth and withdrawals. Roth contributions are not tax-deductible, but qualified distributions are completely tax-free. High-income earners face income limits on direct Roth contributions but can use backdoor Roth conversions to fund Roth IRAs.

Backdoor Roth conversions involve contributing to Traditional IRAs then converting to Roth IRAs. For high-income earners above Roth contribution limits, backdoor conversions provide access to Roth accounts. Pro-rata rule complications arise if other Traditional IRAs exist.

SEP-IRAs (Simplified Employee Pensions) suit self-employed individuals and small business owners. Annual contributions up to 25 percent of net self-employment income (maximum $69,000 in 2024) are tax-deductible. SEP-IRAs simplify retirement planning for business owners.

Solo 401(k)s serve self-employed individuals with no employees. These plans combine employee deferrals and employer profit-sharing, potentially allowing larger contributions than SEP-IRAs. Solo 401(k)s require more administration than SEP-IRAs but offer greater flexibility.

Required Minimum Distributions beginning at age 73 apply to Traditional IRAs and SEP-IRAs but not Roth IRAs. Roth IRA owners can let accounts grow indefinitely, providing estate planning benefits.

IRA custodians hold investment assets and handle administrative requirements. Custodians typically include brokerage firms, mutual fund companies, and banks. Self-directed IRAs with specialized custodians allow alternative investments including real estate and private equity.""",
            metadata={"domain": "retirement", "tags": ["ira", "roth-ira", "tax-deferred", "contributions"], "difficulty": "intermediate", "focus": "ira-planning"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_018",
            corpus_id=self.corpus_id,
            title="Social Security: Benefits and Planning Strategies",
            content="""Social Security provides retirement, disability, and survivor benefits. Understanding Social Security claiming strategies helps maximize lifetime benefits.

Full Retirement Age (FRA), the age at which full benefits are available, has gradually increased to age 67 for those born in 1960 and later. Early claiming at age 62 reduces benefits by approximately 30 percent. Delaying until age 70 increases benefits by approximately 24 percent annually beyond FRA.

Primary Insurance Amount (PIA) determines monthly benefits. Social Security calculates PIA based on highest 35 years of earnings, with earnings indexed for inflation. Career breaks or low-income years reduce benefits. Self-employed individuals contribute both employee and employer portions.

Married couples benefit from Social Security spousal and survivor benefits. Spousal benefits (up to 50 percent of earner's PIA) provide benefits for non-working spouses or those with lower earnings. Survivor benefits support widows, widowers, and dependent children. Divorced spouses can claim on ex-spouse's record after 10-year marriage with higher benefits if ex-spouse is 62.

Break-even analysis compares lifetime benefits from different claiming ages. For average-longevity individuals, delaying improves lifetime benefits; those expecting shorter lives might claim earlier. Market conditions, investment returns, and health status influence optimal claiming decisions.

Coordinated claiming strategies for married couples maximize household benefits. Sophisticated strategies using spousal and survivor benefits, now limited by regulations, previously allowed one spouse to claim spousal benefits while the other delayed. Changes in 2015 limited these strategies for those born after 1954.

Social Security faces long-term solvency challenges as baby boomers retire and life expectancy increases. Trust fund reserves are projected to deplete around 2033, after which benefits would be automatically reduced unless Congress acts. Proposed solutions include raising payroll tax rates, increasing the cap on taxable earnings, or means-testing benefits.""",
            metadata={"domain": "retirement", "tags": ["social-security", "benefits", "claiming-age", "spousal-benefits"], "difficulty": "intermediate", "focus": "social-security"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_019",
            corpus_id=self.corpus_id,
            title="Retirement Savings Rate and FIRE Movement",
            content="""Retirement requires substantial savings to fund decades of spending without employment income. Determining appropriate savings rates and retirement timelines involves complex calculations and personal values.

The 4 percent rule, developed by William Bengen, suggests retirees can safely withdraw 4 percent of initial portfolio value annually, adjusting for inflation. This rule, based on historical analysis, aims to support 30-year retirements with high confidence. Portfolio composition and market conditions affect actual sustainability.

The leanfire movement targets lower expenses and earlier retirement than traditional planning. Adherents seek to reduce spending dramatically and reach financial independence faster. FIRE (Financial Independence, Retire Early) assumes investing differences between spending and income.

Savings rates determine years to retirement. Saving 10 percent of income might require 50+ years of work; saving 50 percent enables retirement in roughly 15-17 years. Higher savings rates create urgency but require significant lifestyle changes.

Geographic arbitrage exploits cost-of-living differences. Some early retirees move to lower-cost countries, stretching savings further. Healthcare, currency risks, and quality-of-life considerations complicate international retirement.

Tax optimization before retirement involves timing income recognition, managing capital gains, and utilizing tax-deferred accounts. Roth conversions during low-income years can reduce future tax burdens. Strategic charitable donations during high-income years provide deductions.

Sequence-of-returns risk describes how early retirement returns affect sustainability. Poor returns shortly after retirement require larger portfolio reductions, potentially depleting funds. Varying withdrawal strategies, such as dynamic withdrawals based on market conditions, can mitigate this risk.

Retirement income sources beyond savings include Social Security, pensions, annuities, and part-time work. Diversified income sources reduce portfolio withdrawal pressure and increase retirement security.""",
            metadata={"domain": "retirement", "tags": ["retirement-savings", "fire", "4-percent-rule", "withdrawal-rates"], "difficulty": "intermediate", "focus": "retirement-planning"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_020",
            corpus_id=self.corpus_id,
            title="Healthcare Costs and Medicare Planning",
            content="""Healthcare represents one of the largest retirement expenses, often underestimated in retirement planning. Understanding Medicare and healthcare costs is essential for successful retirement.

Medicare, the federal healthcare program for those 65 and older, covers hospital insurance (Part A), medical insurance (Part B), prescription drugs (Part D), and additional coverage (Part C/Advantage Plans or Medigap). Eligibility begins at 65 with automatic enrollment for those receiving Social Security.

Part A covers hospitalization, skilled nursing, hospice, and home health care. Part A is free for those with sufficient Social Security work credits. Part B covers doctor visits, outpatient services, and medical equipment; beneficiaries pay premiums based on income.

Prescription drug coverage (Part D) protects against high medication costs. Part D plans have deductibles, coverage gaps (often called "donut holes"), and copayments. Plans vary in covered medications; selecting appropriate plans requires reviewing individual drug needs.

Medigap policies supplement Medicare, covering copayments, coinsurance, and deductibles. Standardized Medigap plans (A through N) allow comparison across insurers. Medigap is expensive but valuable for those preferring traditional Medicare with supplemental coverage.

Medicare Advantage (Part C) combines Parts A, B, and usually D through private insurance companies. Advantage plans often have low or zero premiums but may include network restrictions and higher out-of-pocket costs. Annual open enrollment allows plan switching for those dissatisfied.

Long-term care costs for nursing homes, assisted living, or home health aides can exceed $100,000 annually. Medicare covers only limited long-term care; Medicaid covers long-term care for those with minimal assets. Long-term care insurance provides coverage but is expensive and uncertain regarding future availability.

Delayed retirement benefits increase Medicare costs for those working past 65. Continuing employer health insurance is often preferable to Medicare alone if available. Coordinating Medicare with employer coverage requires understanding creditable coverage rules.""",
            metadata={"domain": "retirement", "tags": ["medicare", "healthcare-costs", "long-term-care", "planning"], "difficulty": "intermediate", "focus": "healthcare-retirement"}
        ))

        # Cryptocurrencies and Digital Assets (docs 21-25)
        docs.append(DocumentSpec(
            doc_id="fin_021",
            corpus_id=self.corpus_id,
            title="Bitcoin and Blockchain Technology Fundamentals",
            content="""Bitcoin, the first cryptocurrency, introduced blockchain technology enabling decentralized transactions without intermediaries. Understanding Bitcoin's mechanics is crucial for evaluating cryptocurrencies.

Bitcoin operates on a distributed ledger called the blockchain, where all transactions are recorded. The blockchain prevents double-spending and ensures transaction validity without requiring trusted intermediaries. Miners compete to validate blocks of transactions by solving complex mathematical problems.

Proof-of-Work consensus requires miners to verify transactions and create new blocks. Mining requires computational power and consumes electricity. Miners receive block rewards (newly created Bitcoin plus transaction fees) for successful blocks. This system incentivizes honest behavior; attacking the network would be more expensive than mining honestly.

Bitcoin's supply is fixed at 21 million coins, with a release schedule halving every four years. This scarcity contrasts with fiat currencies that central banks can expand at will. Limited supply supports Bitcoin's narrative as digital gold, though it also creates deflation risks and volatility.

Private keys control Bitcoin wallets. Users with private keys can move their Bitcoin; losing keys results in permanent loss. Secure key storage using hardware wallets, cold storage, or multi-signature arrangements protects against theft.

Transaction confirmations increase security. Most exchanges require 6+ confirmations before finalizing transactions. Bitcoin transactions are permanent once confirmed; unlike credit card transactions, they cannot be reversed, limiting buyer protection.

Scalability challenges affect Bitcoin's utility. The blockchain processes transactions slowly (roughly 10 minutes per block) and expiratively (limited to roughly 7 transactions per second). Layer 2 solutions including the Lightning Network provide faster transactions building on Bitcoin's security.

Bitcoin volatility reflects limited adoption, speculation, regulatory uncertainty, and macroeconomic factors. Volatility limits Bitcoin's utility as payments or stores of value, though some view this as temporary as adoption increases.""",
            metadata={"domain": "crypto", "tags": ["bitcoin", "blockchain", "mining", "cryptocurrency"], "difficulty": "basic", "focus": "blockchain-basics"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_022",
            corpus_id=self.corpus_id,
            title="Ethereum and Smart Contracts",
            content="""Ethereum extended blockchain technology beyond payments to support programmable smart contracts. Understanding Ethereum's capabilities and risks helps investors evaluate this technology.

Smart contracts are self-executing code stored on the blockchain. Contracts automatically execute when predetermined conditions are met, eliminating intermediaries and automating complex transactions. Once deployed, contracts cannot be altered or canceled.

Ethereum's Turing-complete programming language allows sophisticated applications beyond simple transactions. Decentralized Finance (DeFi) applications including lending platforms, exchanges, and derivatives use smart contracts. Non-Fungible Tokens (NFTs) representing digital art and collectibles run on Ethereum.

Ether, Ethereum's native cryptocurrency, pays for computational resources. Users pay "gas fees" in Ether to execute transactions and smart contracts. Fees vary with network congestion; high demand drives fees up, making transactions expensive.

Ethereum 2.0 (The Merge, completed in 2022) transitioned from Proof-of-Work to Proof-of-Stake consensus. Validators stake Ether to secure the network and earn rewards. Proof-of-Stake uses less energy than Proof-of-Work and allows faster transactions.

Risks in DeFi include smart contract bugs allowing funds theft, impermanent loss in liquidity pools, and liquidation cascades. Poorly audited protocols and anonymous developers increase risks. High yields often reflect commensurate risks.

Regulatory uncertainty affects Ethereum's future. Securities law applicability to tokens, tax treatment of cryptocurrency transactions, and institutional adoption uncertainty create volatility. Clear regulations might increase adoption or might restrict functionality.

Layer 2 solutions including Polygon and Arbitrum process transactions off-chain, reducing fees and increasing speed. Cross-chain bridges allow Ethereum interactions with other blockchains, though bridges introduce additional risks.""",
            metadata={"domain": "crypto", "tags": ["ethereum", "smart-contracts", "defi", "proof-of-stake"], "difficulty": "intermediate", "focus": "ethereum"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_023",
            corpus_id=self.corpus_id,
            title="Cryptocurrency Valuation and Price Drivers",
            content="""Cryptocurrency valuations lack the fundamentals (earnings, cash flows, dividends) that guide traditional asset valuation. Understanding price drivers helps investors evaluate cryptocurrency investments.

Adoption and network effects drive cryptocurrency value. Cryptocurrencies become more valuable as more people use them, creating positive feedback loops. Bitcoin's first-mover advantage established it as the most recognized cryptocurrency. Ethereum's smart contract ecosystem created substantial network effects.

Institutional adoption affects cryptocurrency legitimacy and price. MicroStrategy, Block Inc., and Tesla investing in Bitcoin signaled institutional interest. Grayscale's Bitcoin Trust and ETF approvals increased accessibility for traditional investors, expanding the investor base.

Regulations significantly affect prices. Positive regulatory clarity from major economies increases adoption and confidence. Regulatory restrictions including China's cryptocurrency ban or El Salvador's Bitcoin adoption significantly affect prices.

Monetary policy and macroeconomic conditions affect cryptocurrency prices. Cryptocurrencies sometimes serve as inflation hedges, rising when traditional currencies weaken or inflation concerns rise. Risk-off sentiment during financial stress reduces speculative asset demand including cryptocurrencies.

Technological developments affect valuations. Ethereum's transition to Proof-of-Stake reduced energy consumption concerns. Bitcoin's Lightning Network development increases transaction speed. Competing blockchain developments affecting relative attractiveness impact prices.

Cryptocurrency correlations with traditional assets have increased. Cryptocurrencies sometimes move with growth stocks rather than uncorrelated assets; this reduces diversification benefits. Flight-to-quality movements during financial stress often reduce all speculative assets including cryptocurrencies.

Sentiment and speculation significantly drive prices. Retail participation waves create momentum-driven price surges. Influencers and social media communities affect trading patterns. Unlike stocks with fundamental anchors, cryptocurrencies sometimes move primarily on sentiment.""",
            metadata={"domain": "crypto", "tags": ["cryptocurrency-valuation", "adoption", "regulation", "price-drivers"], "difficulty": "intermediate", "focus": "crypto-valuation"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_024",
            corpus_id=self.corpus_id,
            title="Cryptocurrency Risks and Security",
            content="""Cryptocurrency investments involve substantial risks including security threats, market volatility, regulatory uncertainty, and technological risks. Understanding these risks is essential for prudent cryptocurrency investing.

Exchange risks represent a major danger. Cryptocurrency exchanges sometimes collapse, losing customer funds. Mt. Gox's collapse in 2014 resulted in substantial losses. Even established exchanges face hacking risks; the FTX collapse in 2022 resulted from apparent fraud. Using regulated, well-capitalized exchanges reduces but doesn't eliminate exchange risk.

Private key security is paramount. Keys stored online on exchange computers face hacking risks. Hardware wallets provide cold storage reducing online exposure but introduce risks of physical loss or theft. Multi-signature wallets requiring multiple keys increase security but complicate fund access.

Smart contract bugs can result in lost or stolen funds. DeFi platform hacks occur regularly, sometimes resulting in millions in losses. Audits reduce but don't eliminate risks. Using established protocols with long histories and audits is safer than new protocols.

Regulatory risks are substantial. Governments might restrict cryptocurrency use, tax transactions heavily, or require AML/KYC compliance. Changes in tax treatment could affect returns; classification as securities would restrict trading. Regulatory clarity in some countries and restrictions in others create uncertainty.

Market risks include extreme volatility. Cryptocurrencies frequently experience 20-30 percent price swings; 50+ percent declines occur regularly. High leverage in derivatives trading can result in liquidations. Portfolio allocations to cryptocurrencies should match risk tolerance.

Technical risks exist. Blockchain forks (protocol changes) can split communities and coins. 51% attacks, where miners controlling majority hash rate could reverse transactions, remain theoretical risks for Bitcoin but real concerns for smaller cryptocurrencies.

Environmental concerns affect valuations and regulation. Bitcoin's energy consumption and carbon footprint draw criticism. Proof-of-Work consensus skeptics favor Proof-of-Stake alternatives. Environmental consciousness might drive regulatory restrictions.""",
            metadata={"domain": "crypto", "tags": ["cryptocurrency-risks", "security", "regulation", "technical-risks"], "difficulty": "intermediate", "focus": "crypto-security"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_025",
            corpus_id=self.corpus_id,
            title="Tax Treatment of Cryptocurrency Transactions",
            content="""Cryptocurrency transactions create complex tax obligations that many investors underestimate. Proper tax accounting is essential for compliance and minimizing tax burdens.

Capital gains apply when cryptocurrencies are sold or exchanged. Short-term capital gains (held less than one year) are taxed as ordinary income at federal rates up to 37 percent. Long-term capital gains (held more than one year) receive preferential treatment with rates up to 20 percent.

Staking rewards and mining income are ordinary income tax events. Cryptocurrency received from staking or mining is taxable when received at fair market value, regardless of whether it's sold. Staking rewards create continuous tax obligations even if holdings aren't sold.

DeFi transactions including swaps, liquidity pool participation, and lending create tax events. Swapping one cryptocurrency for another is a taxable exchange, even if no fiat currency is involved. Tax-loss harvesting in cryptocurrency involves selling at losses to offset gains.

Wash sale rules have been debated for cryptocurrency. Current IRS guidance suggests wash sale rules, which prevent loss deductions for securities repurchased within 30 days, may not apply to cryptocurrency. This creates planning opportunities unavailable in stocks.

Record-keeping requires detailed transaction histories. Tracking cost basis, holding periods, and transaction values is essential for accurate tax reporting. Tax software designed for cryptocurrency helps compile reports, but manual tracking is sometimes necessary.

Form 8949 and Schedule D report capital gains and losses. Substantial cryptocurrency trading requires extensive Form 8949 filings. The IRS has pursued cryptocurrency tax evaders; voluntary disclosure of unreported income might reduce penalties.

International considerations apply for those abroad. Tax treaties might provide benefits for US expats. Reporting foreign financial accounts exceeding $10,000 is required; FBAR and FATCA reporting obligations apply.""",
            metadata={"domain": "crypto", "tags": ["cryptocurrency-taxes", "capital-gains", "staking", "tax-reporting"], "difficulty": "intermediate", "focus": "crypto-taxes"}
        ))

        # Personal Finance (docs 26-30)
        docs.append(DocumentSpec(
            doc_id="fin_026",
            corpus_id=self.corpus_id,
            title="Budgeting and Expense Tracking",
            content="""Budgeting provides the foundation for financial success by aligning spending with values and goals. Effective budgeting requires understanding spending patterns and making intentional choices.

The 50/30/20 budget allocates 50 percent of after-tax income to needs, 30 percent to wants, and 20 percent to savings and debt repayment. This simple framework works well for many people but may require adjustment based on individual circumstances. High earners often need lower savings percentages; others need more.

Zero-based budgeting allocates every dollar of income to specific purposes. Budgeted categories sum to zero income, requiring intentional decisions about all spending. Zero-based budgeting eliminates unaccounted spending and provides tight control.

Expense tracking reveals actual spending patterns. Many people are surprised by discretionary spending when tracked systematically. Apps and spreadsheets automate tracking; reviewing spending monthly identifies adjustment opportunities.

Fixed expenses including housing, insurance, and utilities don't change monthly and provide budget stability. Variable expenses including groceries, utilities, and entertainment fluctuate. Discretionary expenses like entertainment and dining out are easiest to reduce when spending adjustment is needed.

Emergency funds should equal 3-6 months of living expenses, reducing reliance on debt when unexpected expenses occur. Emergency funds prevent forced asset sales and high-interest borrowing. Keeping emergency funds in accessible accounts (savings accounts or money markets) provides availability while separating them from investment portfolios.

Debt elimination through budgeting accelerates financial progress. Minimum payments indefinitely extend debt; higher payments and lower spending reduce payoff times. Behavioral budgeting approaches like the debt snowball (paying smallest debts first) provide psychological wins building momentum.

Spending reduction through budgeting has limits. Eliminating meaningful expenses harms quality of life; sustainable budgeting includes spending on priorities. Reducing wasteful spending while maintaining valued activities improves both finances and wellbeing.""",
            metadata={"domain": "personal-finance", "tags": ["budgeting", "expenses", "tracking", "spending-control"], "difficulty": "basic", "focus": "budgeting"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_027",
            corpus_id=self.corpus_id,
            title="Credit Scores and Credit Management",
            content="""Credit scores quantify creditworthiness, affecting borrowing costs and availability. Understanding credit score components and management strategies helps optimize financial conditions.

FICO scores, the most widely used credit scores, range from 300 to 850. Scores below 580 are considered very poor, 580-669 are fair, 670-739 are good, 740-799 are very good, and 800+ are excellent. Most lenders require 620+ scores for loans; better rates require 740+ scores.

Credit score components include payment history (35 percent weight), amounts owed (30 percent), length of credit history (15 percent), new credit (10 percent), and credit mix (10 percent). Payment history is most important; late payments significantly damage scores.

Credit utilization, the percentage of available credit being used, affects scores. High utilization (over 30 percent) reduces scores even with on-time payments. Keeping utilization below 10 percent maximizes score. Increasing credit limits without additional spending reduces utilization.

Hard inquiries occur when applying for credit; multiple inquiries within 30-45 days count as single inquiry for rate-shopping purposes. Soft inquiries from checking credit or existing creditor reviews don't affect scores. Hard inquiries reduce scores by 5-10 points but impact fades over time.

Negative items including late payments, charge-offs, and collections severely damage scores. Late payments remain on credit reports for seven years but decline in impact over time. Disputes of inaccurate negative items can result in removal.

Building credit from scratch requires starting with credit-builder loans or secured credit cards. Secured cards require cash deposits providing collateral. Responsible use (paying full balances monthly) builds positive history within six months.

Credit monitoring services track credit reports and scores, alerting to changes. Freezing credit reports prevents unauthorized account opening. Disputing inaccurate information on credit reports can improve scores and reduce identity theft risks.""",
            metadata={"domain": "personal-finance", "tags": ["credit-scores", "credit-reports", "utilization", "borrowing"], "difficulty": "basic", "focus": "credit-management"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_028",
            corpus_id=self.corpus_id,
            title="Consumer Debt: Types and Management Strategies",
            content="""Consumer debt including credit cards, auto loans, and student loans serves various purposes but can become problematic if not carefully managed. Understanding debt types and repayment strategies helps optimize finances.

Credit card debt carries the highest interest rates among consumer debt, typically 15-25 percent APR. Revolving balance debt is particularly expensive; interest compounds daily on unpaid balances. Minimum payments often cover mostly interest, leaving balances nearly unchanged.

Auto loans typically carry 4-8 percent interest rates depending on credit scores and terms. Most auto loans run 60-72 months; longer terms reduce monthly payments but increase total interest. Negative equity (owing more than car value) creates risk if accidents result in insurance payout insufficient to repay loans.

Student loans come in federal and private varieties. Federal student loans offer protections including income-driven repayment plans, forgiveness programs, and deferment options. Private student loans lack these protections but might have lower rates for excellent credit scores.

The debt-to-income ratio, comparing monthly debt payments to gross income, affects mortgage approval and borrowing capacity. Ratios below 43 percent are generally acceptable; higher ratios restrict borrowing. Paying down debt improves ratios and borrowing capacity.

The debt snowball method pays minimum payments on all debts, throwing extra payments toward the smallest balance until paid. Psychological wins from eliminating debts build motivation. This method ignores interest rates; mathematically inefficient compared to targeting highest-rate debt first.

The debt avalanche method prioritizes highest-interest debt, minimizing total interest paid. Mathematically optimal, this method requires discipline since the psychological victories come later. Many people prefer debt snowball despite higher total interest.

Balance transfers move credit card debt to zero or low-percent introductory-rate cards, reducing interest during the promotional period. Introductory rates typically last 6-18 months; rates increase substantially after. Transfer fees of 3-5 percent apply.""",
            metadata={"domain": "personal-finance", "tags": ["consumer-debt", "credit-cards", "loans", "repayment"], "difficulty": "basic", "focus": "debt-management"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_029",
            corpus_id=self.corpus_id,
            title="Insurance Fundamentals and Risk Management",
            content="""Insurance transfers specific risks to insurers in exchange for premiums. Appropriate insurance coverage protects against catastrophic losses while avoiding overinsurance.

Health insurance protects against medical expenses. Deductibles (amounts paid before insurance) range from $500-$7,050 for individual plans (2024 limits). Copays for office visits and prescriptions incentivize prudent use. Coinsurance (percentage of costs paid after deductible) applies to larger expenses.

Homeowners insurance protects against fire, theft, and liability. Most mortgages require coverage up to property value. Adequate liability coverage ($300,000-$500,000) protects against lawsuit risks from injuries on the property. Deductibles typically range from $500-$2,500.

Auto insurance covers liability (damage to others), collision (damage to your vehicle), and comprehensive (theft, weather, vandalism). Most states require liability insurance; collision and comprehensive are typically only required if financing. Liability coverage of $100,000/$300,000 is standard, though higher limits are advisable.

Life insurance replaces lost income if breadwinners die. Term life insurance provides pure protection for specified periods (20-30 years); rates are low and coverage is straightforward. Permanent life insurance (whole, universal, variable) combines insurance with savings components, costing 10-15x more than term.

Disability insurance replaces income if unable to work from illness or injury. Many employers provide coverage; individual policies are available for those without coverage. Long-term disability covering extended disabilities is more important than short-term coverage.

Umbrella insurance provides excess liability coverage beyond homeowners and auto coverage. $1 million umbrellas cost $150-$300 annually, providing valuable protection against major lawsuit risks. Umbrellas require underlying liability limits on base policies.

Insurance shopping every few years often finds better rates. Quotes from multiple insurers reveal competitive differences. Bundling multiple policies with insurers often provides discounts.""",
            metadata={"domain": "personal-finance", "tags": ["insurance", "risk-management", "health-insurance", "liability"], "difficulty": "basic", "focus": "insurance"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_030",
            corpus_id=self.corpus_id,
            title="Tax Planning and Minimization Strategies",
            content="""Tax planning proactively reduces lifetime taxes through strategic timing and structure decisions. Effective tax planning considers current and future tax situations across multiple years.

Tax-loss harvesting offsets capital gains with losses from other investments. Selling underwater investments generates losses that offset gains. Wash sale rules prevent immediate repurchasing of similar securities; waiting 31 days allows loss deductions while regaining market exposure with different securities.

Income timing involves deferring income into lower-tax-bracket years and accelerating deductions when beneficial. Contributing to 401(k)s and Traditional IRAs defers income to retirement when tax rates might be lower. This becomes more complex in high-income years.

Charitable donations during high-income years provide deductions. Bunching donations into single years (instead of spreading across years) sometimes makes itemization worthwhile compared to standard deductions. Donor-advised funds allow charitable deductions in high-income years while distributing grants across multiple lower-income years.

Tax-efficient fund placement uses tax-inefficient investments (bonds, actively managed funds generating capital gains) in tax-deferred accounts and tax-efficient investments (index funds, stocks) in taxable accounts. This straightforward strategy significantly improves after-tax returns.

Roth conversions move Traditional IRA balances to Roth IRAs, paying taxes currently to receive tax-free growth. This makes sense when current tax rates are low or expected future rates are higher. Early retirement years with minimal income often provide ideal conversion opportunities.

Qualified Dividend Income and long-term capital gains receive preferential tax treatment (0-20 percent federal rates) compared to ordinary income (up to 37 percent). Holding investments more than one year qualifies for this treatment; short-term gains are taxed as ordinary income.

Municipal bond interest is typically federal tax-free and state-tax-free if issued within the taxpayer's state. High-income earners in high-tax states benefit substantially from tax-exempt muni yields. Tax-equivalent yield comparisons determine whether muni bonds outperform taxable bonds.""",
            metadata={"domain": "personal-finance", "tags": ["tax-planning", "tax-loss-harvesting", "deductions", "tax-efficiency"], "difficulty": "intermediate", "focus": "tax-strategy"}
        ))

        # Investment Strategy and Economics (docs 31-50)
        docs.append(DocumentSpec(
            doc_id="fin_031",
            corpus_id=self.corpus_id,
            title="Value Investing and Fundamental Analysis",
            content="""Value investing seeks to purchase securities trading below intrinsic values. Fundamental analysis evaluates businesses through financial statements and qualitative factors to identify undervalued opportunities.

Benjamin Graham pioneered value investing, buying stocks when prices fell substantially below calculated intrinsic values. Graham's margin of safety required prices at least 25-30 percent below calculated values, providing protection against estimation errors.

Intrinsic value calculations use discounted cash flow (DCF), comparing future cash flows to current prices. Conservative growth assumptions reduce overvaluation risks. Terminal value assumptions, representing value after explicit forecast periods, significantly impact DCF results.

Financial ratio analysis examines profitability, efficiency, leverage, and valuation metrics. Return on Equity (ROE) measures profit generation on shareholder capital; higher ROE indicates stronger business performance. Debt-to-Equity ratios reveal leverage; higher ratios indicate greater financial risk.

Competitive advantages or "moats" provide value investing appeal. Companies with strong brands, proprietary technology, or network effects maintain pricing power and generate superior returns. Understanding moats helps identify quality businesses worth paying premiums for.

Quality at a reasonable price (GARP) seeks good businesses at fair prices. GARP balances quality characteristics with valuation concerns, avoiding both overpriced quality and value traps (cheap for good reasons).

Value traps appear cheap but are actually declining businesses. No amount of discount makes poor businesses good investments. Distinguishing genuine value opportunities from value traps requires careful analysis of competitive position and sustainability.

Value investing requires patience. Contrarian positions mean buying when others are selling and holding while the market eventually recognizes value. Psychological discipline to maintain positions during volatility is essential.""",
            metadata={"domain": "investing", "tags": ["value-investing", "fundamental-analysis", "dcf", "margin-of-safety"], "difficulty": "intermediate", "focus": "value-strategy"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_032",
            corpus_id=self.corpus_id,
            title="Growth Investing and Momentum Strategies",
            content="""Growth investing seeks companies with above-average earnings growth rates regardless of valuation multiples. Growth investors accept higher valuations in exchange for strong growth prospects.

Growth stocks typically reinvest earnings rather than paying dividends, allowing accelerated compound growth. Amazon, Tesla, and other high-growth companies exemplify this approach, achieving dramatic shareholder value growth despite traditional valuation metrics appearing stretched.

Earnings growth rates and growth sustainability drive valuations. Price-to-Growth (PEG) ratios divide P/E ratios by growth rates, comparing valuations across growth levels. A company growing 30 percent annually might justifiably have higher P/E multiples than a stable mature company.

Momentum investing buys securities trending upward, assuming trends continue. Technical analysis uses price charts and indicators to identify momentum. Momentum strategies often have shorter time horizons than fundamental approaches.

Growth and momentum sometimes diverge. Growth stocks can fall significantly from peaks; momentum traders might sell while growth investors hold. This creates challenges managing portfolios combining both approaches.

Sector rotation cycles emphasize shifting between sectors expecting different performance. Tech growth stocks often lead during expansion; value stocks outperform during late-cycle economic periods. Predicting cycle timing is notoriously difficult.

Concentration risks arise in growth portfolios. Many growth investors hold concentrated positions in few high-conviction ideas. Concentrated portfolios can generate spectacular returns or devastating losses depending on outcomes.

Growth stock volatility exceeds broad market volatility. Growth investors must tolerate 20-30 percent+ drawdowns. Those with low risk tolerance should limit growth allocation proportions.""",
            metadata={"domain": "investing", "tags": ["growth-investing", "momentum", "earnings-growth", "sector-rotation"], "difficulty": "intermediate", "focus": "growth-strategy"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_033",
            corpus_id=self.corpus_id,
            title="Passive Index Investing and ETFs",
            content="""Passive index investing buys diversified portfolios replicating market indices, minimizing costs and complexity. Index investing has attracted trillions of assets as investors recognize challenges beating markets after fees.

Index funds track specific indices including the S&P 500, total stock market, bond indices, and international indices. Vanguard, Fidelity, and iShares offer low-cost index funds and ETFs. Expense ratios of 0.03-0.20 percent make index investing extremely affordable.

Exchange-Traded Funds (ETFs) trade like stocks but hold diversified portfolios like mutual funds. ETF flexibility allows buying partial positions through brokers. Tax efficiency of ETFs often exceeds mutual funds due to unique creation/redemption mechanisms reducing taxable distributions.

Asset allocation using index funds creates globally diversified portfolios. A simple three-fund portfolio combining US stocks, international stocks, and bonds provides complete diversification. Asset allocation between stocks and bonds determines risk and return profiles.

Rebalancing maintains target asset allocations. Rebalancing annually or when allocations drift more than 5 percent maintains discipline. Rebalancing forces buying depressed asset classes and selling appreciated ones, implementing "buy low, sell high" mechanically.

Behavioral advantages of passive investing include reduced monitoring, less trading, and fewer emotionally-driven decisions. Simple passive portfolios often outperform active investors' complex strategies due to costs and behavioral errors.

Dollar-cost averaging, investing fixed amounts at regular intervals, reduces timing risk and sequence-of-returns effects. Automatic regular investing through payroll deductions or automatic transfers removes decision-making and promotes discipline.

Passive investing's growth has created concerns about index concentration and market efficiency. As more assets follow indices, markets may become less efficient, creating opportunities for active managers. Whether this creates meaningful opportunities for investors remains debated.""",
            metadata={"domain": "investing", "tags": ["index-funds", "etf", "passive-investing", "asset-allocation"], "difficulty": "basic", "focus": "passive-investing"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_034",
            corpus_id=self.corpus_id,
            title="Modern Portfolio Theory and Efficient Frontier",
            content="""Modern Portfolio Theory, developed by Harry Markowitz, provides mathematical framework for portfolio optimization. Understanding efficient portfolios helps investors construct well-diversified portfolios.

The efficient frontier represents combinations of assets providing maximum expected return for each risk level. Portfolios below the frontier are dominated; portfolios above don't exist. Rational investors choose portfolios along the efficient frontier.

Expected returns equal weighted averages of component security returns. A portfolio of 60 percent stocks (10 percent expected return) and 40 percent bonds (4 percent expected return) has 7.6 percent expected return. Higher stock allocations increase expected returns but also risk.

Volatility combines individual security risks and correlations. Diversifying into uncorrelated assets reduces total volatility more than individual asset volatility might suggest. Perfect negative correlation (moving oppositely) provides ideal diversification; perfect positive correlation (moving together) provides no diversification benefit.

The Capital Allocation Line (CAL) represents combinations of risky portfolios and risk-free assets (like Treasury bills). Borrowing or lending at risk-free rates extends portfolio possibilities beyond the efficient frontier. The optimal tangency portfolio touches both the efficient frontier and CAL.

Risk and return tradeoffs are fundamental; no portfolio provides both maximum return and minimum risk. Investors select portfolios matching risk tolerance. Higher-risk individuals should allocate more to stocks; conservative individuals should emphasize bonds.

Correlation changes during market stress. Assets with low correlations in normal times sometimes move together during crises, reducing diversification benefits when most needed. Portfolio stress testing reveals behavior during extreme scenarios.

Behavioral finance challenges Modern Portfolio Theory assumptions. Investors don't behave rationally; emotions and heuristics drive decisions. Behavioral approaches including prospect theory better describe actual investor behavior.""",
            metadata={"domain": "investing", "tags": ["modern-portfolio-theory", "efficient-frontier", "correlations", "diversification"], "difficulty": "intermediate", "focus": "portfolio-theory"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_035",
            corpus_id=self.corpus_id,
            title="Macroeconomics and Business Cycles",
            content="""Macroeconomic conditions significantly influence investment returns. Understanding business cycles and economic indicators helps investors anticipate changing conditions.

The business cycle includes expansion, peak, contraction, and trough phases. Expansion features rising GDP, employment, and corporate profits. Peaks mark maximum economic activity before downturns. Contractions feature declining activity; troughs mark bottoms before recovery begins.

Leading economic indicators predict future conditions. Housing starts, consumer confidence, and stock prices typically lead turning points by several months. Following indicators including unemployment lag turning points. Coincident indicators move with the economy.

GDP growth measures economic output growth. Recessions officially involve two consecutive quarters of negative growth. Productivity growth determines long-term economic growth potential; faster productivity growth supports higher wage growth and living standards.

Inflation, the rate at which prices rise, affects purchasing power and real returns. Deflation (falling prices) sometimes accompanies severe recessions. Central banks target 2 percent inflation, balancing avoiding deflation while preventing excessive inflation eroding purchasing power.

Unemployment measures jobless percentages. Full employment typically occurs around 3.5-4 percent unemployment; lower rates indicate unsustainable economic activity. Unemployment lags; it continues rising after recessions officially end.

The Federal Reserve controls monetary policy through interest rates and money supply. Lowering rates stimulates borrowing and spending during weakness; raising rates controls inflation. Quantitative easing (purchasing securities) provides stimulus when rates approach zero.

Fiscal policy through government spending and taxes affects economies directly. Government spending during recessions provides stimulus; spending cuts during expansions cool overheating. Political gridlock sometimes prevents timely fiscal responses.""",
            metadata={"domain": "economics", "tags": ["business-cycles", "gdp", "inflation", "unemployment"], "difficulty": "intermediate", "focus": "macroeconomics"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_036",
            corpus_id=self.corpus_id,
            title="Inflation: Causes, Effects, and Hedges",
            content="""Inflation erodes purchasing power, reducing real returns on cash and fixed-income investments. Understanding inflation mechanics and hedging strategies protects wealth.

Demand-pull inflation occurs when demand exceeds supply, bidding up prices. Cost-push inflation results from input cost increases. Both types reduce real purchasing power and affect investment strategies.

Moderate inflation is expected and priced into markets. 2-3 percent annual inflation means $100 declines to $97-98 in purchasing power over one year. Real returns subtract inflation from nominal returns; 5 percent stock returns with 3 percent inflation provide only 2 percent real returns.

High inflation dramatically affects asset values. Stocks can perform well if companies increase prices faster than costs; however, uncertainty from high inflation increases discount rates, sometimes depressing valuations. Bonds suffer severely from unexpected inflation since fixed coupons lose purchasing power.

Gold traditionally serves as inflation hedge, maintaining value as currencies weaken. Commodities including oil, metals, and agricultural products also appreciate during inflationary periods. REITs often provide inflation hedges since they raise rents with inflation.

TIPS (Treasury Inflation-Protected Securities) adjust principal for inflation, providing explicit inflation protection. TIPS yields typically run 1-2 percent below nominal Treasury yields, reflecting inflation expectations.

Wage growth potentially matches or exceeds inflation. Workers with negotiating power can demand raises matching inflation. Workers without negotiating power suffer real income declines during inflation.

Unexpected inflation is most dangerous. Inflation anticipated and priced into markets creates fewer shocks. Unexpected surges in inflation surprise investors, depressing asset values.""",
            metadata={"domain": "economics", "tags": ["inflation", "purchasing-power", "hedges", "real-returns"], "difficulty": "intermediate", "focus": "inflation"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_037",
            corpus_id=self.corpus_id,
            title="Interest Rates and Federal Reserve Policy",
            content="""The Federal Reserve controls short-term interest rates, fundamentally affecting economic activity and asset valuations. Understanding Fed policy and interest rate mechanics is crucial for investors.

The Federal Funds Rate, the rate banks charge each other for overnight loans, is the Fed's primary policy tool. Fed policy meetings establish target rate ranges; the Fed uses open market operations to maintain actual rates near targets.

Quantitative Easing (QE) involves purchasing longer-term securities when policy rates near zero. QE increases money supply and lowers longer-term rates. The Fed's balance sheet expanded to over $8 trillion during crises including the 2008 financial crisis and 2020 pandemic.

Quantitative Tightening (QT) reverses QE by allowing securities to mature without replacement. QT reduces money supply and raises longer-term rates. The Fed utilized QT after raising rates in 2022-2023.

Interest rate transmission affects economies through multiple channels. Lower rates reduce borrowing costs, increasing business investment and consumer spending. Lower returns on savings reduce saving incentives. Asset price appreciation from lower discount rates increases wealth.

The Taylor Rule predicts Fed policy based on inflation and employment gaps. When inflation exceeds 2 percent or unemployment falls below natural rates, the rule suggests raising rates. When inflation is below target or unemployment exceeds natural rates, rates should be cut.

Forward guidance helps markets understand future policy. The Fed communicates likely future rate changes, managing expectations. Surprisingly hawkish or dovish guidance creates market volatility as investors adjust portfolios.

Independence is crucial for Fed credibility. Political pressure to keep rates low compromises inflation control. Maintaining credibility requires resisting short-term political pressure for long-term price stability.""",
            metadata={"domain": "economics", "tags": ["federal-reserve", "interest-rates", "quantitative-easing", "monetary-policy"], "difficulty": "intermediate", "focus": "fed-policy"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_038",
            corpus_id=self.corpus_id,
            title="Yield Curve and Recession Signals",
            content="""The yield curve, plotting bond yields across maturities, provides valuable information about economic expectations and recession risk. Interpreting yield curve dynamics helps investors anticipate turning points.

Normal yield curves slope upward, with longer-term yields exceeding short-term yields. This reflects compensation for duration risk and inflation expectations. Normal curves suggest economic growth expectations.

Flat yield curves occur when short-term and long-term yields converge. Flat curves often precede inverted curves and sometimes suggest market uncertainty about future directions. Flat curves provide less term premium, reducing bond yields.

Inverted yield curves, when short-term yields exceed long-term yields, have historically preceded recessions. Inversions suggest markets expect economic weakness and Fed rate cuts. The 2019 inversion preceded the 2020 pandemic recession; the 2022-2023 inversion preceded the expected 2024 recession.

Recession prediction accuracy varies. Not all inversions precede recessions within one year, though most recessions are preceded by inversions. The 1998 inversion and 2011-2012 flatness didn't produce recessions; false signals occur.

Yield curve shape changes affect portfolio performance. Steepening curves often accompany economic recovery, benefiting longer-duration bonds and cyclical stocks. Flattening curves sometimes signal weakening, benefiting longer-duration bonds.

Fed policy attempts to steepen curves when inverted. After inversions, Feds typically cut rates aggressively. Rate cuts reduce short-term yields more than long-term yields, steepening curves.

Institutional investors monitor yield curve slopes closely. Pension funds and insurance companies shift asset allocations based on yield curve signals. The amount of institutional money responding to yield curve changes amplifies its predictive power.""",
            metadata={"domain": "economics", "tags": ["yield-curve", "recession-signals", "interest-rates", "economic-indicators"], "difficulty": "intermediate", "focus": "yield-curve"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_039",
            corpus_id=self.corpus_id,
            title="Currency Exchange and International Finance",
            content="""Currency exchange rates significantly affect international investing returns and trade flows. Understanding currency mechanics and risks helps investors evaluate international investments.

Exchange rates reflect supply and demand for currencies. When foreign investors demand dollars, dollar values increase. Large current account deficits (more imports than exports) increase foreign currency supplies, potentially weakening domestic currencies.

Purchasing power parity (PPP) suggests exchange rates equilibrate to make goods equally priced across countries. If American goods become cheaper than foreign goods, foreign demand increases, raising dollar values. PPP predicts long-run exchange rate behavior but deviates substantially in shorter terms.

Interest rate differentials affect currency values. Higher interest rates attract foreign investment, increasing currency demand and value. Currency carry trades involve borrowing in low-interest currencies and investing in high-interest currencies, capturing interest differentials.

Political and economic stability affects currency values. Strong rule of law, transparent institutions, and stable democracies attract investment, supporting currency values. Political instability and economic dysfunction reduce currency values.

Central banks intervene in currency markets to support values. Rapid depreciation harms import prices and inflation; appreciation harms export competitiveness. Intervention effectiveness varies; large interventions sometimes succeed while market forces often overwhelm central bank resistance.

Currency hedging eliminates exchange rate risks for international investments. Forward contracts lock in future exchange rates; currency options provide downside protection while maintaining upside. Hedging costs reduce returns; unhedged investing provides diversification benefits if currencies don't move together with stocks.

Emerging market currencies are often volatile. Capital flows in and out of emerging markets dramatically affect currencies. Strong dollar periods often coincide with emerging market currency weakness.""",
            metadata={"domain": "economics", "tags": ["currency-exchange", "international-finance", "ppp", "currency-risk"], "difficulty": "intermediate", "focus": "forex"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_040",
            corpus_id=self.corpus_id,
            title="Behavioral Finance and Investor Psychology",
            content="""Behavioral finance explains how psychological biases drive investment decisions, often leading to suboptimal outcomes. Understanding biases helps investors recognize and correct them.

Loss aversion describes the tendency to weigh losses more heavily than gains. Losing $100 causes greater pain than gaining $100 provides pleasure. This causes investors to hold losers too long hoping to break even and sell winners too early to lock in gains.

Confirmation bias causes investors to seek information confirming existing beliefs while dismissing contrary information. Stock investors look for reasons stocks will rise; bond investors focus on recession risks. Confirmation bias reduces openness to changing views.

Overconfidence causes investors to overestimate skill and believe they know more than actually true. Professional investors often exhibit overconfidence; research shows active managers underperform after fees despite high confidence in their abilities.

Recency bias overweights recent events when predicting futures. After bull markets, investors believe stocks will perpetually rise; after bear markets, they expect continued declines. Recent events influence forecasts more than statistical analysis warrants.

Anchoring causes investors to anchor to reference points when estimating values. Buying prices become anchors; investors hold at original prices rather than evaluating current values objectively. Resistance levels at round numbers reflect anchoring behavior.

Herding describes tendency to follow crowds. When others buy stocks, investors join in; when others sell, they panic sell. Herding amplifies price movements and creates bubbles.

Sunk cost fallacy causes investors to hold losing positions because of previous investments. Sunk costs are irrelevant to future decisions; investors should focus on forward-looking factors. Recognizing sunk costs helps optimize future decisions.""",
            metadata={"domain": "investing", "tags": ["behavioral-finance", "psychology", "biases", "decision-making"], "difficulty": "intermediate", "focus": "behavioral-finance"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_041",
            corpus_id=self.corpus_id,
            title="Derivatives: Options, Futures, and Hedging",
            content="""Derivatives including options and futures allow investors to hedge risks or speculate on price movements. Understanding derivatives is essential for sophisticated risk management.

Call options give buyers the right to purchase securities at strike prices before expiration. Buying calls provides leverage; $5,000 in options might provide exposure to $50,000 in stocks. Calls appreciate when stock prices rise; lose value when stocks fall.

Put options give buyers the right to sell securities at strike prices. Puts appreciate when stock prices fall and protect portfolios against declines. Protective puts provide downside protection like insurance.

Option values depend on stock prices, volatility, time to expiration, and interest rates. Implied volatility measures volatility the option market expects. High volatility increases option values; low volatility decreases them.

Futures contracts obligate buyers to purchase or sellers to deliver commodities or financial instruments at future dates. Futures provide leverage; small margin deposits control large contract values. Futures magnify gains and losses.

Options and futures allow hedging. Portfolio managers purchase put options protecting against stock market declines. Commodity producers sell futures locking in prices for expected production. Hedging reduces risk but also limits upside.

Leverage in derivatives amplifies returns and risks. A 5 percent stock decline in a fully leveraged options position might decline 50+ percent. Leverage requires strict risk management and sufficient capital to maintain positions.

Complexity of derivatives requires careful analysis. Derivatives pricing involves advanced mathematics; misunderstandings lead to unexpected outcomes. Simple strategies using derivatives are preferable to complex positions most investors don't fully understand.""",
            metadata={"domain": "investing", "tags": ["derivatives", "options", "futures", "hedging"], "difficulty": "intermediate", "focus": "derivatives"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_042",
            corpus_id=self.corpus_id,
            title="Private Equity and Venture Capital",
            content="""Private equity and venture capital investment provide growth capital to companies not yet public. Returns can be substantial but involve high risks and illiquidity.

Venture capital funds invest in early-stage startups offering potentially high growth. Most startups fail; venture capitalists accept failure rates of 50+ percent seeking few spectacular successes. Successful exits through acquisitions or IPOs generate returns compensating for failures.

Private equity buys established companies, improves operations, and sells at premiums. Buy-and-build strategies acquire multiple companies within industries, combining them into larger entities. Financial engineering using leverage increases returns if value creation exceeds borrowed costs.

Leverage substantially amplifies returns. An equity investment of $100 million in a $500 million acquisition (80% debt) generates 25 percent equity returns if the business value doesn't increase; actual value increases amplify returns further. If values decline, losses exceed equity investments (the equity cushion is eliminated first).

Fund structures typically involve management companies creating multiple funds. Limited partners (investors) provide capital; general partners (managers) manage investments and receive management fees (typically 2 percent annually) plus carried interest (typically 20 percent of profits).

Illiquidity represents major risks. Private investments lock up capital for 7-10 years. Emergency capital needs might require selling positions at unfavorable prices. Liquidity constraints make private investments unsuitable for those needing near-term capital.

Returns on successful ventures can be spectacular. Early Facebook investors achieved 100,000x+ returns. Tesla early investors also achieved dramatic returns. However, most ventures fail or achieve modest returns.

Fundraising is challenging. Limited partners increasingly scrutinize track records. Managers without successful exits struggle raising capital. Institutional investors increasingly dominate fund investments; individual investors face barriers accessing quality deals.""",
            metadata={"domain": "investing", "tags": ["venture-capital", "private-equity", "startups", "leverage"], "difficulty": "intermediate", "focus": "private-equity"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_043",
            corpus_id=self.corpus_id,
            title="Accounting Fundamentals and Financial Statement Analysis",
            content="""Understanding financial statements enables investors to evaluate company quality and identify investment opportunities. Accounting provides the foundation for fundamental analysis.

The Income Statement shows revenues, expenses, and profits. Revenue growth indicates business expansion. Gross margins (gross profit divided by revenue) reveal pricing power and production efficiency. Operating margins show profitability after operating expenses.

The Balance Sheet shows assets, liabilities, and equity at specific points in time. Assets include cash, accounts receivable, inventory, and long-term assets like property and equipment. Liabilities include debt and accounts payable. Equity represents assets minus liabilities.

The Cash Flow Statement explains changes in cash. Operating cash flow shows cash generated by business operations. Investing cash flow shows capital expenditures and acquisitions. Financing cash flow shows debt/equity changes and dividends. Positive operating cash flow indicates healthy business fundamentals.

Return on Assets (ROA) divides net income by total assets, measuring profit generation on assets employed. Return on Equity (ROE) divides net income by shareholder equity. High ROA and ROE indicate efficient capital use.

Debt-to-Equity ratios measure financial leverage. High leverage increases financial risk; lenders provide less credit during downturns. Industry norms provide context; technology companies typically have low leverage while utilities carry high leverage.

Earnings quality matters as much as earnings numbers. Cash earnings are higher quality than accounting earnings from accruals. Decreasing receivables and inventory relative to sales indicates quality; increasing suggests potential problems.

Financial statement manipulation is possible but risky. Auditors attempt to prevent fraud; auditor changes or qualified opinions suggest potential problems. Comparing financial metrics to competitors reveals outliers requiring investigation.""",
            metadata={"domain": "investing", "tags": ["financial-statements", "accounting", "analysis", "ratios"], "difficulty": "intermediate", "focus": "accounting"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_044",
            corpus_id=self.corpus_id,
            title="Corporate Governance and Shareholder Rights",
            content="""Corporate governance structures determine how companies are managed and to whom managers are accountable. Strong governance protects shareholder interests.

Boards of directors oversee management on behalf of shareholders. Boards approve strategies, set executive compensation, and monitor risk management. Board independence, with directors lacking personal relationships with management, improves oversight.

Executive compensation aligns management incentives with shareholder interests. Stock options incentivize long-term value creation; excessive compensation unrelated to performance creates agency problems. Disclosure of executive compensation allows shareholder scrutiny.

Shareholder meetings allow voting on board elections, executive compensation, and major decisions. Most investors vote by proxy without attending meetings. Activist investors increasingly use shareholder votes to challenge management.

Proxy fights occur when activists accumulate significant stakes and challenge board elections. Activists attempt to install directors supporting their agenda including dividend initiation, management replacement, or strategic changes. Proxy contests create expense and disruption but sometimes achieve needed changes.

Anti-takeover provisions including poison pills and staggered boards provide management protection. While limiting outside acquisition pressure, they also entrench management insulated from accountability. Excessive anti-takeover provisions reduce shareholder rights.

Related-party transactions where directors or executives transact with companies create conflicts of interest. Disclosure requirements increase transparency. Audit committees review related-party transactions seeking to prevent self-dealing.

International governance varies. Some countries separate chairman and CEO roles, improving independence. Others allow concentrated ownership giving controlling shareholders disproportionate power. US governance provides stronger minority shareholder protections than some countries.""",
            metadata={"domain": "investing", "tags": ["governance", "boards", "shareholder-rights", "proxy-voting"], "difficulty": "intermediate", "focus": "governance"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_045",
            corpus_id=self.corpus_id,
            title="Risk Management and Systemic Financial Risks",
            content="""Risk management protects against potential losses through diversification, hedging, and prudent operations. Systemic risks threatening overall financial stability require regulatory attention.

Operational risks from poor processes, fraud, or system failures threaten all businesses. Strong internal controls reduce operational risk. Key person dependencies expose organizations to risks if critical employees leave.

Market risks from price movements affect valuations. Diversification reduces individual security risk but not market risk. Hedging using derivatives can reduce specific market exposures but introduces counterparty risks.

Credit risk from borrower defaults threatens lenders and investors. Credit analysis and diversification reduce credit risk. Subordination rankings determine recovery in default; senior creditors recover before subordinated ones.

Liquidity risk emerges when selling assets becomes difficult without large price concessions. Illiquid assets are riskier; investors require yield premiums for liquidity risk. Liquidity crises where normally liquid assets become difficult to sell create systemic risks.

Counterparty risks arise in derivative and repo transactions. When counterparties default, derivative values and collateral recovery become uncertain. Lehman Brothers' collapse created counterparty risks throughout the financial system during the 2008 crisis.

Systemic risks threaten financial system stability. Large bank failures, credit market freezes, or contagion across institutions affect entire economies. Regulatory stress tests evaluate systemic risks; capital requirements ensure banks can absorb losses.

Central bank liquidity facilities including discount windows, Fed funds, and emergency lending provide financial system resilience. During crises, central banks become "lenders of last resort," preventing liquidity spirals. However, too-easy liquidity access might encourage excessive risk-taking.""",
            metadata={"domain": "investing", "tags": ["risk-management", "systemic-risk", "credit-risk", "liquidity-risk"], "difficulty": "intermediate", "focus": "risk-management"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_046",
            corpus_id=self.corpus_id,
            title="Financial Regulation and Consumer Protection",
            content="""Financial regulation protects consumers and maintains system stability. Understanding regulatory framework helps investors identify compliant financial institutions.

Securities regulation through the SEC requires companies to disclose material information. Insider trading rules prevent unfair advantage trading on non-public information. Broker regulations require suitability standards ensuring recommendations match client needs.

Banking regulation through the Federal Reserve, OCC, and FDIC maintains bank soundness. Capital requirements ensure banks have sufficient cushion absorbing losses. Stress tests evaluate bank resilience to economic shocks.

Consumer protection laws including Truth in Lending Act require clear disclosures of credit terms. Fair Credit Reporting Act protects against inaccurate credit reporting. Dodd-Frank Act after the 2008 crisis increased consumer protections and required derivatives trading through central clearing.

AML/KYC (Anti-Money Laundering/Know Your Customer) rules require financial institutions to verify client identities and report suspicious activity. These rules reduce money laundering and terrorist financing but add compliance costs.

Fiduciary standards require investment advisors and fiduciaries to act in client interests. Fiduciaries must disclose conflicts of interest and avoid excessive compensation. Non-fiduciaries must meet suitability standards; products must suit client profiles.

Regulatory gaps exist despite extensive rules. Cryptocurrency initially lacked clear regulation; regulators increasingly develop frameworks. Fintech disruption creates regulatory challenges; new platforms and business models sometimes outpace regulatory development.

Regulatory changes affect investments. Dodd-Frank's Volcker Rule restricting proprietary trading reduced bank profitability. Environmental, Social, Governance (ESG) regulations increasingly mandate ESG disclosures. Tax regulation changes including capital gains treatment dramatically affect investment returns.""",
            metadata={"domain": "finance", "tags": ["regulation", "consumer-protection", "aml-kyc", "fiduciary"], "difficulty": "intermediate", "focus": "regulation"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_047",
            corpus_id=self.corpus_id,
            title="Financial Crisis and Systemic Collapse",
            content="""Financial crises, from panics to major collapses, highlight systemic risks and underscore importance of risk management. Understanding past crises helps prevent future ones.

The 2008 financial crisis began with mortgage defaults as housing prices declined. Subprime mortgage securities held by major financial institutions suddenly became worthless. Lehman Brothers collapse triggered widespread financial system stress.

Banking system stress during 2008 threatened total collapse. Overnight lending markets froze; banks couldn't obtain short-term funding. Federal Reserve emergency lending and government interventions stabilized the system.

The crisis caused severe recessions with unemployment exceeding 10 percent. Stock market declined 50+ percent from peak. Home values declined 30+ percent in many markets. Millions of families faced foreclosures.

Crisis responses included government bailouts, emergency lending, quantitative easing, and fiscal stimulus. While controversial, these interventions prevented complete financial system collapse. Debates continue regarding whether interventions were appropriately scaled.

Lessons from 2008 included: the importance of sufficient bank capital, the dangers of excessive leverage, the risks of complex securities nobody fully understands, and the need for systemic risk monitoring. Dodd-Frank attempted to address some lessons through increased regulation and transparency.

The 2020 pandemic recession was different. Businesses closed by government order, not financial system failure. Quick policy response prevented financial system stress. Stock markets recovered rapidly.

Cryptocurrency exchange collapses including FTX in 2022 created localized crises affecting retail investors but not systemic financial system. Lack of interconnection with mainstream finance limited contagion.""",
            metadata={"domain": "finance", "tags": ["financial-crisis", "2008", "systemic-risk", "recession"], "difficulty": "intermediate", "focus": "financial-crisis"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_048",
            corpus_id=self.corpus_id,
            title="International Trade and Tariffs",
            content="""International trade benefits all nations through comparative advantage and specialization. Tariffs and trade restrictions reduce these benefits while providing concentrated benefits to protected industries.

Comparative advantage means countries should specialize in products they can produce efficiently relative to other countries. Even if a country produces everything more efficiently in absolute terms, comparative advantage in some products drives trade benefits.

Trade creates winners and losers. Consumers benefit from cheaper imports and broader product selection. Workers in competing domestic industries face job losses and wage pressures. Concentrated costs on workers create political pressure for protection despite overall economic benefits.

Tariffs tax imports, raising prices and protecting domestic producers. Tariffs reduce imports but harm consumers and downstream industries using imports. Retaliatory tariffs from trading partners reduce export demand. Overall, tariffs reduce economic efficiency and total wealth.

Non-tariff barriers including regulations, subsidies, and quotas restrict trade similarly to tariffs. Regulations requiring domestic content or specific standards effectively exclude foreign competitors. Agricultural subsidies depress prices, harming farmers in countries without subsidies.

Trade agreements reduce barriers benefiting both nations. USMCA replaced NAFTA; agreements with South Korea, Australia, and others reduce trade frictions. WTO rules address trade disputes and promote reduced barriers.

Trade deficits reflect capital flows more than losing economics. Trade deficits mean capital inflows from foreign investment in domestic assets. Large deficits sometimes indicate unsustainable foreign borrowing but don't necessarily indicate economic problems.

Domestic industries sometimes need temporary protection during transitions. Infant industry arguments suggest temporary tariffs allow developing industries to reach efficiency before facing competition. However, industries rarely sunset; protection often becomes permanent.""",
            metadata={"domain": "economics", "tags": ["trade", "tariffs", "comparative-advantage", "trade-agreements"], "difficulty": "intermediate", "focus": "international-trade"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_049",
            corpus_id=self.corpus_id,
            title="ESG Investing and Impact Investing",
            content="""Environmental, Social, and Governance (ESG) investing considers non-financial factors in investment decisions. Impact investing intentionally seeks investments generating positive environmental or social returns alongside financial returns.

ESG factors include environmental considerations (carbon emissions, pollution, resource depletion), social factors (labor practices, community relations, product safety), and governance (board composition, executive compensation, shareholder rights).

ESG proponents argue non-financial risks affect long-term returns. Companies with poor environmental practices face regulatory risks and transition costs. Poor labor practices create supply chain risks. Weak governance increases fraud and mismanagement risks.

Skeptics argue ESG funds significantly underperform. ESG restrictions limit investable universe; excluding low-ESG stocks eliminates some value investments. Overweight positions in high-ESG stocks inflate valuations creating subsequent underperformance.

Impact investing explicitly targets positive social or environmental outcomes. Microfinance investments provide capital to unbanked populations. Green energy investments reduce carbon emissions. Social enterprises address poverty. Impact investors may accept lower financial returns for positive impact.

ESG funds vary dramatically in definitions and methodology. Some emphasize environmental factors; others focus on governance. Lack of standardization allows greenwashing where funds claim ESG credentials without substantive commitment.

Corporate sustainability initiatives increasingly matter for ESG scores. Companies investing in renewable energy, reducing waste, and improving labor practices improve ESG ratings. Disclosure of ESG metrics improves compared to prior years but remains inconsistent.

Regulatory attention to ESG grows. Regulators increasingly require ESG disclosures. Mandatory climate risk disclosures become common. However, politically-driven opposition to ESG investing creates uncertainty about future requirements.""",
            metadata={"domain": "investing", "tags": ["esg", "impact-investing", "sustainability", "environmental"], "difficulty": "intermediate", "focus": "esg-investing"}
        ))

        docs.append(DocumentSpec(
            doc_id="fin_050",
            corpus_id=self.corpus_id,
            title="Financial Planning and Wealth Management",
            content="""Comprehensive financial planning aligns investments with life goals, incorporating all financial dimensions. Professional wealth managers coordinate complex financial situations.

Financial planning includes budgeting, debt management, insurance, retirement planning, investment strategy, and tax optimization. Comprehensive plans address how each component supports overall financial wellbeing.

Goal prioritization helps allocate resources efficiently. Highest priority goals might include emergency funds, debt elimination, and retirement funding. Lower priority goals include travel and discretionary spending. Balancing short-term satisfaction with long-term security is challenging.

Investment policy statements establish portfolio guidelines. Policy statements specify asset allocation, acceptable investments, risk tolerance, and rebalancing schedules. Written policies improve discipline during emotional market periods.

Asset allocation determines most return variation, more so than security selection. Appropriate asset allocation matching time horizons and risk tolerance is more important than picking perfect investments.

Rebalancing maintains target allocations. Annual rebalancing forces discipline—buying depreciated assets and selling appreciated ones. Rebalancing improves returns by mechanically implementing "buy low, sell high."

Tax efficiency throughout wealth strategies reduces tax drag. Tax-loss harvesting, municipal bonds for high-income individuals, and asset location strategies improve after-tax returns. Tax-efficient investing is especially important for high-income earners.

Professional advice, when obtained from fee-only fiduciaries, can improve outcomes through behavioral coaching and comprehensive planning. However, costs matter; expensive advisors must provide value exceeding their fees. Passive index approaches with occasional rebalancing serve many investors well.""",
            metadata={"domain": "personal-finance", "tags": ["financial-planning", "wealth-management", "asset-allocation", "goals"], "difficulty": "basic", "focus": "financial-planning"}
        ))

        return docs
