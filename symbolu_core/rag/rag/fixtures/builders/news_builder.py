"""
News & Current Events Corpus Builder
=====================================

Generates 50 documents covering news topics including politics, technology,
climate, economy, health, social issues, and international affairs.
"""

from typing import List
from .base import CorpusBuilder, DocumentSpec


class NewsCorpusBuilder(CorpusBuilder):
    """Builder for News & Current Events corpus."""

    @property
    def corpus_id(self) -> str:
        return "news"

    @property
    def description(self) -> str:
        return "News and Current Events covering politics, technology, and global affairs"

    @property
    def domain(self) -> str:
        return "news"

    def build_documents(self) -> List[DocumentSpec]:
        docs = []

        # US Politics (docs 1-8)
        docs.append(DocumentSpec(
            doc_id="news_001",
            corpus_id=self.corpus_id,
            title="The American Electoral System Explained",
            content="""The United States employs a unique electoral system that combines direct democracy with representative elements. Understanding this system is essential for following American political news and election coverage.

Presidential elections use the Electoral College, established by the Constitution. Each state receives electoral votes equal to its congressional representation (House seats plus two senators). Most states use winner-take-all allocation—the candidate winning the popular vote in a state receives all its electoral votes. Maine and Nebraska use congressional district allocation.

A candidate needs 270 of 538 electoral votes to win the presidency. This system means candidates focus on "swing states" where outcomes are uncertain, while reliably partisan states receive less attention. Critics argue this distorts democratic representation; supporters say it preserves federalism and prevents candidates from ignoring smaller states.

Congressional elections occur every two years. All 435 House seats are contested biennially, with representatives serving two-year terms. Senators serve six-year terms, with roughly one-third of the Senate elected every two years. Midterm elections, occurring between presidential races, often serve as referendums on the sitting president.

Primary elections and caucuses determine party nominees. States choose between open primaries (any voter can participate), closed primaries (only registered party members), or caucuses (local meetings). The primary calendar, starting with Iowa and New Hampshire, significantly influences nomination outcomes.

Redistricting, conducted after each census, redraws congressional districts. Gerrymandering—manipulating district boundaries for partisan advantage—remains controversial. Some states use independent commissions; others leave redistricting to state legislatures.""",
            metadata={"domain": "politics", "tags": ["elections", "electoral-college", "voting", "congress"], "difficulty": "basic", "focus": "us-politics"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_002",
            corpus_id=self.corpus_id,
            title="The Three Branches of US Government",
            content="""The United States Constitution establishes three co-equal branches of government—executive, legislative, and judicial—creating a system of checks and balances designed to prevent any single branch from accumulating excessive power.

The Executive Branch, headed by the President, enforces laws and conducts foreign policy. The President serves as Commander-in-Chief of the armed forces, negotiates treaties (subject to Senate ratification), and appoints federal judges, cabinet members, and ambassadors. Executive orders allow presidents to direct federal agencies without congressional legislation, though courts can strike down orders exceeding presidential authority.

The Legislative Branch—Congress—comprises the Senate (100 members, two per state) and House of Representatives (435 members, apportioned by population). Congress holds exclusive power to declare war, levy taxes, appropriate funds, and regulate interstate commerce. Bills must pass both chambers before reaching the President. The Senate confirms presidential appointments and ratifies treaties.

The Judicial Branch interprets laws and the Constitution. The Supreme Court, with nine justices serving lifetime appointments, is the final arbiter of constitutional questions. Federal courts below include circuit courts of appeals and district courts. Judicial review, established in Marbury v. Madison (1803), allows courts to invalidate laws conflicting with the Constitution.

Checks and balances include presidential veto power (overridable by two-thirds congressional vote), Senate confirmation of appointments, congressional impeachment authority, and judicial review. The filibuster in the Senate requires 60 votes to advance most legislation, though budget reconciliation and judicial nominations can proceed with simple majorities.

Understanding these structures helps interpret news about legislation, executive actions, and court decisions.""",
            metadata={"domain": "politics", "tags": ["government", "constitution", "congress", "supreme-court"], "difficulty": "basic", "focus": "us-politics"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_003",
            corpus_id=self.corpus_id,
            title="Political Polarization in America",
            content="""Political polarization—the growing ideological distance between parties and their supporters—has intensified in the United States over recent decades. This trend shapes policy debates, media coverage, and democratic discourse.

Research documents increasing partisan sorting: voters now align more consistently with party positions across issues. Where mid-20th century parties contained diverse ideological coalitions, today's Democrats are more uniformly liberal and Republicans more uniformly conservative. Geographic sorting concentrates partisans in different communities.

Contributing factors include media fragmentation, primary election dynamics, gerrymandering, and social media algorithms. Cable news and online platforms allow consumers to select ideologically congenial information. Primary elections incentivize candidates to appeal to partisan bases rather than general electorates. Safe districts reduce incentives for moderation.

Affective polarization—negative feelings toward the opposing party—has increased even more than policy disagreement. Surveys show rising percentages viewing the other party as a threat to national well-being. Cross-party social interactions, including marriages and friendships, have declined.

Consequences include legislative gridlock, as compromise becomes politically costly. Government shutdowns and debt ceiling confrontations reflect inability to reach bipartisan agreements. Norms of political conduct have eroded, with increased willingness to use procedural hardball tactics.

Some scholars distinguish between elite and mass polarization, noting that ordinary voters remain more moderate than party activists and elected officials. Others point to asymmetric polarization, arguing one party has moved further from center than the other. These debates continue in academic and journalistic analysis.""",
            metadata={"domain": "politics", "tags": ["polarization", "partisanship", "democracy", "media"], "difficulty": "intermediate", "focus": "us-politics"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_004",
            corpus_id=self.corpus_id,
            title="Campaign Finance and Money in Politics",
            content="""Campaign finance—how political campaigns raise and spend money—remains one of the most contested aspects of American democracy. Legal frameworks, court decisions, and reform efforts continuously reshape this landscape.

The Federal Election Campaign Act (1971, amended 1974) established disclosure requirements, contribution limits, and public financing for presidential campaigns. The Federal Election Commission (FEC) enforces these rules. Individual contributions to candidates are capped (currently $3,300 per election), as are party committee contributions.

The Supreme Court's Citizens United v. FEC (2010) decision transformed campaign finance by ruling that corporations and unions have First Amendment rights to spend unlimited amounts on independent political expenditures. This spawned Super PACs—political action committees that can raise unlimited funds for independent expenditures but cannot coordinate with candidates.

Dark money refers to political spending by nonprofit organizations that don't disclose donors. These 501(c)(4) "social welfare" groups can engage in political activity if it's not their primary purpose. Critics argue this allows wealthy interests to influence elections anonymously; defenders cite privacy rights and free speech.

Small-dollar fundraising has grown dramatically, with digital platforms enabling candidates to raise substantial sums from numerous small contributors. This shift has empowered candidates with passionate grassroots support and reduced dependence on wealthy donors, though large contributions remain significant.

Proposals for reform include public financing systems, disclosure requirements for dark money, constitutional amendments to overturn Citizens United, and contribution limit adjustments. State and local governments experiment with various approaches, from matching funds to democracy vouchers.""",
            metadata={"domain": "politics", "tags": ["campaign-finance", "citizens-united", "elections", "money"], "difficulty": "intermediate", "focus": "us-politics"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_005",
            corpus_id=self.corpus_id,
            title="Immigration Policy Debates",
            content="""Immigration policy encompasses legal frameworks for entry, pathways to citizenship, border enforcement, and treatment of undocumented immigrants. These issues generate intense political debate and frequent news coverage.

The United States admits approximately one million legal permanent residents annually through family sponsorship, employment-based visas, diversity lottery, and refugee/asylum programs. Wait times for family-based green cards can exceed 20 years for applicants from high-demand countries. Employment-based immigration includes H-1B visas for skilled workers, subject to annual caps.

An estimated 10-11 million undocumented immigrants live in the United States, many having resided for decades. Policy debates center on enforcement priorities, deportation policies, and potential pathways to legal status. DACA (Deferred Action for Childhood Arrivals) protects approximately 600,000 individuals brought to the US as children, though the program's legal status has faced court challenges.

Border security involves physical barriers, technology, and personnel. The US-Mexico border sees varying levels of unauthorized crossings, with recent years witnessing increases in asylum seekers from Central America and beyond. Processing capacity, detention conditions, and asylum adjudication timelines are ongoing concerns.

Comprehensive immigration reform—combining enforcement measures with legalization pathways—has repeatedly failed in Congress despite bipartisan negotiations. Political disagreements center on prioritizing enforcement versus legalization, visa allocation systems, and treatment of undocumented residents.

State and local policies vary from "sanctuary" jurisdictions limiting cooperation with federal immigration enforcement to states enacting their own enforcement measures. Courts have addressed which immigration powers belong exclusively to the federal government.""",
            metadata={"domain": "politics", "tags": ["immigration", "border", "daca", "policy"], "difficulty": "intermediate", "focus": "us-politics"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_006",
            corpus_id=self.corpus_id,
            title="Healthcare Policy in America",
            content="""Healthcare policy addresses how Americans access medical care, who pays for it, and how the system is regulated. The United States spends more on healthcare than any other nation while leaving millions uninsured, making this a perennial policy debate.

The Affordable Care Act (ACA, 2010) expanded coverage through Medicaid expansion, insurance marketplaces with subsidies, and regulations requiring coverage of pre-existing conditions. The law reduced the uninsured rate significantly but remains politically contentious. Republican efforts to repeal the ACA have largely failed, though the individual mandate penalty was eliminated.

Medicare, the federal program for seniors (65+) and disabled individuals, covers approximately 65 million Americans. Traditional Medicare (Parts A and B) provides hospital and medical insurance; Medicare Advantage (Part C) offers private plan alternatives; Part D covers prescription drugs. Medicare financing faces long-term challenges as the population ages.

Medicaid, jointly funded by federal and state governments, covers low-income individuals. Eligibility and benefits vary by state. The ACA's Medicaid expansion extended coverage to adults up to 138% of the poverty level, though some states declined expansion.

Policy debates include single-payer "Medicare for All" proposals, public option plans to compete with private insurers, drug pricing reforms, and surprise billing protections. Prescription drug costs, driven by factors including patent protections and limited price negotiations, generate particular concern.

The COVID-19 pandemic exposed healthcare system vulnerabilities and prompted expanded telehealth, vaccine distribution challenges, and debates about public health authority. Long-term pandemic healthcare consequences continue to unfold.""",
            metadata={"domain": "politics", "tags": ["healthcare", "aca", "medicare", "medicaid"], "difficulty": "intermediate", "focus": "us-politics"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_007",
            corpus_id=self.corpus_id,
            title="Voting Rights and Election Administration",
            content="""Voting rights and election administration have become intensely contested, with debates over ballot access, election security, and democratic participation generating significant news coverage and legal battles.

The Voting Rights Act (1965) prohibited discriminatory voting practices, with Section 5 requiring federal preclearance for election changes in jurisdictions with histories of discrimination. The Supreme Court's Shelby County v. Holder (2013) invalidated the preclearance formula, prompting debates about new legislation.

Voter ID laws require various forms of identification to vote. Supporters argue they prevent fraud and ensure election integrity; opponents contend they disproportionately burden minority, elderly, and low-income voters while addressing minimal actual fraud. Courts have upheld some ID requirements while striking down others as discriminatory.

Mail voting expanded dramatically during the COVID-19 pandemic. Some states conduct all elections by mail; others have restrictive absentee requirements. Debates center on accessibility versus security, with evidence suggesting mail voting doesn't systematically advantage either party.

Election administration in America is highly decentralized, with approximately 10,000 local jurisdictions managing elections. This creates variation in equipment, procedures, and ballot access. Election workers have faced unprecedented harassment and threats, prompting turnover and security concerns.

Claims of widespread voter fraud have been repeatedly investigated and debunked, yet significantly influence policy debates and public trust. The 2020 election generated numerous court challenges, all unsuccessful, and culminated in the January 6, 2021 Capitol attack. Rebuilding confidence in election integrity while protecting voting access remains a major challenge.""",
            metadata={"domain": "politics", "tags": ["voting-rights", "elections", "voter-id", "democracy"], "difficulty": "intermediate", "focus": "us-politics"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_008",
            corpus_id=self.corpus_id,
            title="The Federal Budget and National Debt",
            content="""The federal budget—government spending and revenue—shapes policy priorities and generates recurring political confrontations. Understanding budget processes helps interpret news about shutdowns, debt ceilings, and fiscal debates.

The federal government spends approximately $6 trillion annually. Mandatory spending—including Social Security, Medicare, Medicaid, and interest on debt—consumes about two-thirds of the budget and grows automatically based on eligibility and benefit formulas. Discretionary spending, requiring annual appropriations, covers defense (roughly half) and domestic programs (education, transportation, research, etc.).

Federal revenue comes primarily from individual income taxes (about half), payroll taxes (about one-third), and corporate taxes (about one-tenth). The tax code's complexity reflects accumulated policy decisions about rates, deductions, credits, and exemptions.

Budget deficits occur when spending exceeds revenue. The national debt—accumulated deficits over time—exceeds $33 trillion. Debt as a percentage of GDP, a measure of sustainability, has increased significantly, though the United States borrows at favorable rates due to the dollar's reserve currency status.

The budget process involves presidential proposals, congressional budget resolutions, appropriations bills, and potential reconciliation legislation (which can pass the Senate with 51 votes). Deadlines frequently prompt continuing resolutions or government shutdowns when appropriations aren't enacted.

The debt ceiling—a statutory limit on borrowing—requires periodic increases to avoid default. Debt ceiling confrontations have become political leverage points, with potential default carrying severe economic consequences. Debates about long-term fiscal sustainability center on entitlement reform, tax policy, and discretionary spending levels.""",
            metadata={"domain": "politics", "tags": ["budget", "debt", "spending", "taxes"], "difficulty": "intermediate", "focus": "us-politics"}
        ))

        # Technology News (docs 9-18)
        docs.append(DocumentSpec(
            doc_id="news_009",
            corpus_id=self.corpus_id,
            title="Artificial Intelligence: Current State and Debates",
            content="""Artificial intelligence has moved from research laboratories to everyday applications, generating intense interest in its capabilities, limitations, and societal implications. AI developments dominate technology news coverage.

Modern AI primarily uses machine learning, particularly deep learning with neural networks trained on massive datasets. Large language models (LLMs) like GPT-4 and Claude demonstrate remarkable text generation, analysis, and reasoning capabilities. Image generation models create realistic visuals from text descriptions. These systems learn patterns from training data rather than following explicit programming.

Generative AI burst into public consciousness with ChatGPT's 2022 release. Applications now span content creation, coding assistance, customer service, research, education, and creative work. Businesses across sectors are exploring integration, though implementation challenges include accuracy concerns, hallucinations (confident but incorrect outputs), and workflow adaptation.

AI raises significant policy questions. Job displacement concerns span white-collar professions previously considered automation-resistant. Copyright questions arise when AI trains on creative works or generates content resembling training data. Misinformation risks increase as AI enables synthetic media production at scale.

AI safety encompasses near-term issues (bias, misuse, reliability) and longer-term concerns about increasingly capable systems. Researchers debate potential existential risks from advanced AI, with some calling for development pauses and others arguing continued progress is both inevitable and beneficial.

Regulatory responses are emerging. The EU's AI Act establishes risk-based frameworks. The US has issued executive orders on AI safety. International coordination efforts seek common standards. Technology companies have announced voluntary commitments while lobbying on regulatory specifics.""",
            metadata={"domain": "technology", "tags": ["ai", "artificial-intelligence", "machine-learning", "chatgpt"], "difficulty": "intermediate", "focus": "technology"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_010",
            corpus_id=self.corpus_id,
            title="Big Tech Regulation and Antitrust",
            content="""Major technology companies—including Apple, Google, Amazon, Meta, and Microsoft—face increasing regulatory scrutiny worldwide. Antitrust enforcement, content moderation requirements, and data privacy rules reshape the technology landscape.

Antitrust concerns center on market dominance and competitive practices. Google faces cases regarding search dominance and advertising practices. Apple's App Store policies and fees face legal challenges. Amazon's treatment of third-party sellers draws scrutiny. Meta's acquisitions of Instagram and WhatsApp prompted attempted unwinding. Microsoft's Activision acquisition required regulatory approval across jurisdictions.

The antitrust framework debate pits traditional consumer welfare analysis (focusing on prices and output) against broader concerns about innovation, market access, and concentrated economic power. Some advocate updating antitrust law for digital markets; others argue existing frameworks suffice with proper enforcement.

Section 230 of the Communications Decency Act shields platforms from liability for user-generated content while allowing content moderation. Reform proposals range from narrowing protections to increasing them, reflecting conflicting concerns about platform power, free speech, and harmful content.

The EU has enacted comprehensive digital regulation. The Digital Services Act mandates content moderation transparency and illegal content removal. The Digital Markets Act imposes specific obligations on designated "gatekeepers." These regulations carry significant fines and operational requirements.

Data privacy regulations including GDPR (EU), CCPA (California), and proposed federal legislation require transparency about data collection and use, user consent mechanisms, and data protection measures. Compliance costs and operational changes affect advertising-dependent business models.""",
            metadata={"domain": "technology", "tags": ["big-tech", "antitrust", "regulation", "section-230"], "difficulty": "intermediate", "focus": "technology"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_011",
            corpus_id=self.corpus_id,
            title="Social Media's Influence on Society",
            content="""Social media platforms have transformed communication, information consumption, and public discourse. Research and debate continue regarding their effects on democracy, mental health, and social cohesion.

Platform reach is enormous: Facebook has approximately 3 billion monthly users; YouTube, Instagram, TikTok, and X (formerly Twitter) each reach billions. These platforms have become primary news sources for many, particularly younger demographics.

Algorithmic content curation determines what users see, optimizing for engagement metrics. Critics argue this amplifies sensational, divisive, or false content that generates reactions. Research findings on "filter bubbles" and polarization effects remain contested, with some studies finding modest effects and others documenting significant impacts.

Misinformation spreads rapidly on social platforms, from health misinformation during the pandemic to election-related false claims. Platforms have implemented varying content moderation approaches, from labeling and downranking to removal, generating debates about effectiveness and censorship concerns.

Mental health effects, particularly for adolescents, draw increasing attention. Correlational studies link heavy social media use with anxiety, depression, and body image concerns, though establishing causation is methodologically challenging. Some researchers emphasize displacement of other activities; others focus on specific features like social comparison or notification-driven attention fragmentation.

Platform accountability proposals include transparency requirements for algorithms and content moderation, researcher data access, algorithmic audits, and design changes to reduce harmful features. Youth-specific protections have gained bipartisan support, with proposals limiting data collection and manipulative design features for minors.""",
            metadata={"domain": "technology", "tags": ["social-media", "misinformation", "mental-health", "algorithms"], "difficulty": "intermediate", "focus": "technology"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_012",
            corpus_id=self.corpus_id,
            title="Cryptocurrency and Digital Finance",
            content="""Cryptocurrency—digital assets secured by cryptography and typically running on decentralized networks—has evolved from a technological curiosity to a significant financial phenomenon, though volatility and regulatory uncertainty persist.

Bitcoin, launched in 2009, introduced blockchain technology—a distributed ledger recording transactions across many computers. Bitcoin's limited supply and decentralized nature attracted those seeking alternatives to government-controlled currencies. Its price has experienced dramatic cycles, from under $1,000 to nearly $70,000 and back.

Ethereum introduced smart contracts—self-executing code on blockchain—enabling decentralized applications, non-fungible tokens (NFTs), and decentralized finance (DeFi) protocols. Thousands of other cryptocurrencies exist, with varying purposes and adoption levels.

Institutional adoption has increased, with major financial firms offering cryptocurrency services and Bitcoin ETFs approved for trading. However, high-profile failures—including FTX's collapse and various project failures—have caused significant losses and reinforced concerns about the sector.

Regulatory approaches vary globally. The US has applied existing securities laws inconsistently, with the SEC bringing enforcement actions while comprehensive frameworks remain pending. The EU enacted the Markets in Crypto-Assets (MiCA) regulation. Some countries have banned cryptocurrency trading; others have embraced it.

Central bank digital currencies (CBDCs) represent government-issued digital money distinct from decentralized cryptocurrency. China has piloted a digital yuan. The Federal Reserve is studying a digital dollar. CBDCs raise questions about privacy, financial surveillance, and monetary policy tools.

Environmental concerns about cryptocurrency mining's energy consumption have prompted shifts toward less energy-intensive validation methods, though Bitcoin mining remains energy-intensive.""",
            metadata={"domain": "technology", "tags": ["cryptocurrency", "bitcoin", "blockchain", "digital-finance"], "difficulty": "intermediate", "focus": "technology"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_013",
            corpus_id=self.corpus_id,
            title="Cybersecurity Threats and Responses",
            content="""Cybersecurity threats—from ransomware to state-sponsored espionage—pose growing risks to individuals, businesses, and national security. High-profile incidents regularly generate news coverage and policy responses.

Ransomware attacks encrypt victims' data, demanding payment for decryption keys. Attacks on hospitals, schools, local governments, and businesses have disrupted operations and exposed sensitive data. The Colonial Pipeline attack (2021) caused fuel shortages across the Eastern US. Attackers increasingly target critical infrastructure.

Nation-state actors conduct espionage, intellectual property theft, and destructive attacks. The SolarWinds compromise (discovered 2020) infiltrated numerous government agencies and corporations through compromised software updates. Chinese hackers have targeted defense contractors, research institutions, and dissidents. Russian operations have included election interference and infrastructure attacks.

Supply chain attacks compromise widely-used software to reach numerous targets simultaneously. Zero-day vulnerabilities—previously unknown security flaws—enable attacks before patches exist. The expanding Internet of Things (IoT) creates new attack surfaces through often poorly-secured connected devices.

Organizational responses include security awareness training, multi-factor authentication, network segmentation, incident response planning, and cyber insurance. Many organizations struggle with security talent shortages and competing budget priorities.

Government initiatives include the Cybersecurity and Infrastructure Security Agency (CISA), mandatory incident reporting for critical infrastructure, international cooperation on ransomware, and offensive cyber operations against attackers. The Biden administration's National Cybersecurity Strategy emphasizes shifting security burdens toward technology vendors and critical infrastructure operators.

The cybersecurity workforce gap—estimated at hundreds of thousands of unfilled positions—constrains defensive capabilities across sectors.""",
            metadata={"domain": "technology", "tags": ["cybersecurity", "ransomware", "hacking", "national-security"], "difficulty": "intermediate", "focus": "technology"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_014",
            corpus_id=self.corpus_id,
            title="The Electric Vehicle Revolution",
            content="""Electric vehicles have moved from niche products to mainstream automotive offerings, driven by technology improvements, policy support, and changing consumer preferences. This transition reshapes the automotive industry and energy systems.

EV sales have grown rapidly, though from a small base. Global EV sales exceeded 10 million in 2022, representing about 14% of new car sales. China leads in both production and sales, followed by Europe and the United States. Tesla pioneered the premium EV market; legacy automakers are now launching competitive models across segments.

Battery technology determines EV cost, range, and performance. Lithium-ion battery costs have declined approximately 90% since 2010, enabling competitive vehicle pricing. Energy density improvements extend range while reducing weight. Research continues on solid-state batteries, which promise further improvements.

Charging infrastructure remains a key challenge. Home charging works for many EV owners, but apartment dwellers and travelers require public charging. Fast-charging networks are expanding, with federal investment supporting buildout. Charging time—still longer than gasoline refueling—constrains long-distance travel convenience.

Supply chain considerations include lithium, cobalt, nickel, and rare earth elements for batteries and motors. Mining impacts, geographic concentration of resources, and processing capacity create vulnerabilities. Battery recycling and alternative chemistries address some concerns.

Policy support includes purchase incentives, emissions regulations, and infrastructure investment. The US Inflation Reduction Act provides significant EV tax credits with domestic content requirements. California and other jurisdictions mandate EV sales percentages. Some countries have announced future bans on internal combustion vehicle sales.

Grid impacts from EV charging require utility planning for increased electricity demand and peak management. Vehicle-to-grid technology could eventually make EVs distributed energy storage resources.""",
            metadata={"domain": "technology", "tags": ["electric-vehicles", "tesla", "batteries", "transportation"], "difficulty": "intermediate", "focus": "technology"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_015",
            corpus_id=self.corpus_id,
            title="Space Industry Commercialization",
            content="""The space industry is undergoing rapid commercialization, with private companies launching satellites, ferrying astronauts, and planning ambitious ventures from lunar landings to Mars colonization.

SpaceX has transformed the launch industry with reusable rockets, dramatically reducing costs. The company's Falcon 9 is now the world's most-launched rocket, serving commercial, government, and company (Starlink) missions. Starship, under development, aims for full reusability and massive payload capacity for lunar and Mars missions.

Satellite internet has expanded dramatically. SpaceX's Starlink constellation includes thousands of satellites providing broadband globally, including to remote areas and conflict zones like Ukraine. Amazon's Project Kuiper and other ventures are deploying competing constellations. Concerns include space debris, astronomical observation interference, and orbital congestion.

Commercial space stations are being developed as the International Space Station approaches retirement. Companies including Axiom Space and Blue Origin plan orbital facilities for research, manufacturing, and tourism. NASA supports commercial station development while maintaining human spaceflight capabilities.

Lunar ambitions are accelerating. NASA's Artemis program aims to return humans to the Moon, partnering with SpaceX (lunar lander) and other contractors. Private lunar missions have launched, with varying success. Long-term plans envision lunar bases and resource utilization.

Space tourism has begun, with Blue Origin and Virgin Galactic offering suborbital flights and SpaceX flying private orbital missions. Prices remain prohibitive for most, but companies anticipate cost reductions over time.

Space governance questions multiply as commercial activity expands. The Outer Space Treaty (1967) prohibits national appropriation but doesn't clearly address commercial resource extraction. Debris mitigation, spectrum allocation, and traffic management require international coordination.""",
            metadata={"domain": "technology", "tags": ["space", "spacex", "satellites", "commercialization"], "difficulty": "intermediate", "focus": "technology"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_016",
            corpus_id=self.corpus_id,
            title="The Tech Industry Workforce",
            content="""The technology industry workforce has experienced significant turbulence, from pandemic-era hiring booms to widespread layoffs, reshaping employment patterns and worker expectations.

Major tech companies conducted mass layoffs in 2022-2023, cutting hundreds of thousands of jobs. Meta, Amazon, Google, Microsoft, and numerous smaller companies announced significant workforce reductions. Explanations included pandemic over-hiring, economic uncertainty, and efficiency initiatives. Some companies explicitly cited AI's potential to increase productivity with fewer workers.

Remote work, accelerated by the pandemic, remains contested. Many tech workers value flexibility, and remote job postings increased substantially. However, some companies have mandated return-to-office policies, citing collaboration, culture, and productivity concerns. Hybrid arrangements represent a common compromise.

Tech worker organizing has increased, though unionization remains rare in the industry. Activism has addressed issues including contract worker conditions, government contracts (particularly defense and immigration enforcement), workplace harassment, and environmental policies. Alphabet Workers Union and other efforts represent nascent organizing.

Immigration policy significantly affects tech employment. H-1B visa holders constitute a substantial portion of the tech workforce, and green card backlogs leave many in uncertain status for years or decades. Companies lobby for expanded skilled immigration; critics raise concerns about wage competition and program abuses.

Diversity in tech remains limited despite stated commitments. Women, Black, and Hispanic workers remain underrepresented, particularly in technical and leadership roles. Companies have invested in pipeline programs, hiring initiatives, and inclusion efforts with mixed results.

Skills demands continue evolving, with AI and machine learning expertise increasingly valued across roles. Coding bootcamps, online credentials, and non-traditional pathways supplement traditional computer science education.""",
            metadata={"domain": "technology", "tags": ["tech-industry", "layoffs", "remote-work", "employment"], "difficulty": "intermediate", "focus": "technology"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_017",
            corpus_id=self.corpus_id,
            title="Data Privacy in the Digital Age",
            content="""Data privacy—how personal information is collected, used, and protected—has become a major concern as digital services accumulate vast amounts of data about individuals. Privacy regulations and corporate practices continue evolving.

Personal data collection is pervasive. Websites track browsing behavior; apps access location, contacts, and usage patterns; connected devices monitor homes and health. Data brokers aggregate information from numerous sources, creating detailed profiles sold to advertisers, employers, insurers, and others.

The advertising industry relies heavily on personal data for targeting. Third-party cookies, which track users across websites, are being phased out, prompting shifts toward first-party data and alternative targeting methods. Privacy-preserving advertising approaches attempt to maintain targeting effectiveness while limiting data exposure.

The European Union's General Data Protection Regulation (GDPR), implemented in 2018, established comprehensive privacy requirements including consent requirements, data access rights, breach notification, and significant penalties. Companies worldwide adapted practices to comply.

US privacy regulation remains fragmented. California's Consumer Privacy Act (CCPA) and similar state laws provide some protections. Comprehensive federal privacy legislation has stalled despite bipartisan negotiations. Different standards across jurisdictions complicate compliance.

Privacy-enhancing technologies include encrypted messaging, VPNs, privacy-focused browsers, and techniques like differential privacy that enable data analysis while protecting individual information. Apple's App Tracking Transparency feature disrupted mobile advertising by requiring user consent for cross-app tracking.

Facial recognition technology raises particular concerns about surveillance, with some jurisdictions restricting government or commercial use. Biometric data protections vary by state, with Illinois's BIPA generating substantial litigation.""",
            metadata={"domain": "technology", "tags": ["privacy", "data", "gdpr", "surveillance"], "difficulty": "intermediate", "focus": "technology"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_018",
            corpus_id=self.corpus_id,
            title="The Semiconductor Industry and Chip Wars",
            content="""Semiconductors—the chips powering everything from phones to cars to AI systems—have become central to economic competition and national security. Supply chain disruptions and geopolitical tensions have elevated their strategic importance.

The semiconductor supply chain is highly globalized and concentrated. Design occurs primarily in the US (Intel, Nvidia, AMD, Qualcomm). Manufacturing leadership lies with Taiwan's TSMC and South Korea's Samsung, producing the most advanced chips. Equipment comes from ASML (Netherlands), Applied Materials (US), and others. Assembly and testing concentrate in Southeast Asia.

Taiwan's central role creates vulnerability. TSMC produces over 90% of the world's most advanced chips. Cross-strait tensions raise concerns about supply disruption, whether from conflict, natural disaster, or coercion. Diversification efforts aim to reduce geographic concentration.

The US CHIPS Act (2022) provides $52 billion for domestic semiconductor manufacturing and research. Intel, TSMC, Samsung, and others have announced major US fabrication plant investments. However, building fabs requires years, billions of dollars, and scarce skilled workers.

Export controls restrict China's access to advanced chip technology. US restrictions on advanced chips and manufacturing equipment aim to slow China's AI and military capabilities. The Netherlands and Japan have implemented complementary controls. China is investing heavily in domestic capabilities, though it remains years behind at the cutting edge.

The automotive industry's chip shortage during 2021-2022 disrupted vehicle production globally, highlighting dependencies on just-in-time supply chains and the expanding semiconductor content in modern vehicles. Legacy chip production capacity constraints persisted longer than expected.

AI's computational demands drive semiconductor innovation. Nvidia dominates AI training chips; competitors are developing alternatives. Custom AI chips from cloud providers and startups aim at specific workloads. Advanced packaging technologies combine multiple chips for improved performance.""",
            metadata={"domain": "technology", "tags": ["semiconductors", "chips", "tsmc", "manufacturing"], "difficulty": "intermediate", "focus": "technology"}
        ))

        # Climate and Environment (docs 19-26)
        docs.append(DocumentSpec(
            doc_id="news_019",
            corpus_id=self.corpus_id,
            title="Climate Change: Current Science and Projections",
            content="""Climate science has established that human activities are warming the planet, with observed effects already apparent and future projections indicating accelerating impacts absent significant emissions reductions.

Global average temperature has increased approximately 1.1°C above pre-industrial levels. The Intergovernmental Panel on Climate Change (IPCC), synthesizing thousands of studies, concludes with high confidence that human influence is the dominant cause, primarily through greenhouse gas emissions from fossil fuel combustion, deforestation, and agriculture.

Observed impacts include more frequent and intense heat waves, changing precipitation patterns, rising sea levels (about 20 cm since 1900), shrinking ice sheets, ocean acidification, and shifting species ranges. Attribution science increasingly links specific extreme weather events to climate change.

Future projections depend on emission trajectories. Under high-emission scenarios, warming could exceed 4°C by 2100, bringing severe impacts including multi-meter sea level rise (over centuries), widespread ecosystem collapse, and regions becoming uninhabitable due to heat. Lower emission pathways limit warming but still entail significant adaptation needs.

The Paris Agreement aims to limit warming to well below 2°C, preferably 1.5°C. Current national commitments, if fully implemented, would result in approximately 2.4-2.8°C warming. Achieving 1.5°C requires global emissions to fall roughly 45% by 2030 and reach net-zero around 2050.

Climate modeling continues improving, with higher resolution, better representation of physical processes, and reduced uncertainty in key parameters. However, "tipping points"—potentially irreversible changes like ice sheet collapse or permafrost thawing—remain difficult to predict and could accelerate warming.""",
            metadata={"domain": "climate", "tags": ["climate-change", "global-warming", "ipcc", "science"], "difficulty": "intermediate", "focus": "climate"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_020",
            corpus_id=self.corpus_id,
            title="The Energy Transition",
            content="""The global energy system is transforming from fossil fuels toward renewable sources, driven by climate concerns, technology improvements, and economics. This transition's pace and pathway remain contested.

Renewable electricity generation has grown dramatically. Solar and wind costs have declined 90% and 70% respectively over the past decade, making them the cheapest electricity sources in many regions. In 2022, renewables provided roughly 30% of global electricity, with coal, natural gas, and nuclear comprising most of the remainder.

Solar deployment is accelerating globally, with annual installations reaching hundreds of gigawatts. Utility-scale solar farms and rooftop installations both contribute. Manufacturing concentrates in China, which produces approximately 80% of solar panels. Supply chain diversification efforts are underway.

Wind power, both onshore and offshore, continues expanding. Larger turbines improve economics. Offshore wind development accelerated, particularly in Europe, with US projects now advancing. Wind intermittency requires grid integration solutions.

Energy storage addresses renewable variability. Lithium-ion battery costs have declined substantially, enabling both grid-scale storage and electric vehicles. Storage duration remains limited; longer-duration solutions including pumped hydro, compressed air, and hydrogen are developing.

Natural gas has served as a "bridge fuel," displacing coal while emitting less carbon, though methane leakage concerns persist. The Ukraine conflict disrupted European gas supplies, accelerating renewable deployment while also extending some coal operations.

Nuclear power provides carbon-free baseload electricity but faces cost challenges and public concerns. Existing plants are being extended; new large reactors face delays and overruns. Small modular reactors promise improved economics but remain unproven at scale.

Industrial and heating decarbonization presents additional challenges beyond electricity. Electrification, green hydrogen, and carbon capture address various applications.""",
            metadata={"domain": "climate", "tags": ["energy", "renewables", "solar", "wind"], "difficulty": "intermediate", "focus": "climate"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_021",
            corpus_id=self.corpus_id,
            title="Climate Policy: Global and National Approaches",
            content="""Climate policy encompasses international agreements, national strategies, and local initiatives aimed at reducing emissions and adapting to climate impacts. Policy approaches vary widely across jurisdictions.

The Paris Agreement (2015) established a framework for voluntary national commitments (Nationally Determined Contributions or NDCs), five-year review cycles to increase ambition, and climate finance transfers from developed to developing countries. Nearly all countries participate, though commitments vary in stringency.

Carbon pricing puts a cost on emissions through taxes or cap-and-trade systems. The EU Emissions Trading System is the largest carbon market. Carbon prices vary dramatically—from under $10/ton in some jurisdictions to over $100/ton in parts of Europe. Border carbon adjustments aim to prevent "carbon leakage" to unregulated jurisdictions.

Regulatory approaches include efficiency standards for vehicles and appliances, renewable portfolio standards for utilities, building codes, and phase-outs of certain technologies. The US Inflation Reduction Act relies primarily on incentives rather than mandates, providing tax credits for clean energy, EVs, and manufacturing.

Adaptation policies address unavoidable climate impacts through infrastructure resilience, early warning systems, managed retreat from vulnerable areas, and agricultural adjustments. Adaptation funding remains far below assessed needs, particularly in developing countries.

Climate litigation has expanded, with suits targeting governments for inadequate action and fossil fuel companies for damages. Courts have ordered emissions reductions in some cases; others are pending.

Political polarization on climate varies by country. In the US, partisan divides are substantial, though younger voters across parties show greater climate concern. Elsewhere, climate policy enjoys broader consensus.""",
            metadata={"domain": "climate", "tags": ["climate-policy", "paris-agreement", "carbon-pricing", "regulation"], "difficulty": "intermediate", "focus": "climate"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_022",
            corpus_id=self.corpus_id,
            title="Extreme Weather Events",
            content="""Extreme weather events—heat waves, floods, droughts, wildfires, and storms—are increasing in frequency and intensity, causing humanitarian crises and economic damage while highlighting climate adaptation needs.

Heat waves have intensified globally. The 2023 Northern Hemisphere summer brought record temperatures to multiple continents. Phoenix experienced 31 consecutive days above 110°F. Southern Europe saw temperatures exceeding 45°C. Heat-related deaths are rising, particularly affecting elderly, outdoor workers, and those without air conditioning.

Wildfires have grown more destructive. Longer fire seasons, drought, and accumulated fuel loads contribute. California, Australia, Canada, and Mediterranean regions have experienced historic fire seasons. Smoke affects air quality across vast distances. Wildland-urban interface development increases exposure.

Flooding affects more people than any other natural disaster type. Intense rainfall events, sea level rise, and development patterns increase flood risk. Pakistan's 2022 floods displaced millions and caused billions in damages. Flash flooding struck regions including Libya, where thousands died.

Droughts affect agriculture, water supplies, and ecosystems. The American West has experienced prolonged drought affecting the Colorado River basin. European rivers fell to historic lows, affecting shipping and power generation. African droughts contribute to food insecurity.

Hurricanes and typhoons cause massive damage when making landfall. While overall tropical cyclone frequency hasn't clearly increased, the proportion of major storms has grown, and rapid intensification events are more common. Sea level rise amplifies storm surge impacts.

Attribution science increasingly quantifies climate change's contribution to specific events. Studies found climate change made particular heat waves, rainfall events, or fire conditions significantly more likely. This research informs adaptation planning and climate litigation.""",
            metadata={"domain": "climate", "tags": ["extreme-weather", "heat-waves", "floods", "wildfires"], "difficulty": "intermediate", "focus": "climate"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_023",
            corpus_id=self.corpus_id,
            title="Biodiversity Loss and Conservation",
            content="""Biodiversity—the variety of life on Earth—is declining at unprecedented rates, driven by habitat destruction, overexploitation, pollution, invasive species, and climate change. Conservation efforts aim to slow losses and protect remaining ecosystems.

Species extinction rates are estimated at 100-1,000 times background rates. The IUCN Red List documents over 40,000 species threatened with extinction. Iconic species like elephants, rhinos, and great apes face severe pressures. Less charismatic species, including insects and amphibians, are declining dramatically with less attention.

Habitat loss is the primary driver. Deforestation continues, particularly in tropical regions with high biodiversity. Agricultural expansion, urbanization, and infrastructure development convert natural areas. Remaining habitats are increasingly fragmented, isolating populations.

Ocean ecosystems face multiple pressures. Overfishing has depleted many stocks. Plastic pollution accumulates in gyres and marine food chains. Ocean acidification and warming stress coral reefs, with mass bleaching events becoming more frequent. Dead zones from nutrient runoff expand.

The Convention on Biological Diversity's Kunming-Montreal Framework (2022) established targets including protecting 30% of land and ocean by 2030, restoring degraded ecosystems, and mobilizing $200 billion annually for biodiversity. Implementation remains challenging.

Conservation approaches include protected areas, endangered species programs, sustainable use management, and ecosystem restoration. Indigenous-led conservation increasingly receives recognition for effectiveness. Market-based mechanisms include payments for ecosystem services and biodiversity credits.

Connections between biodiversity and human well-being include ecosystem services (pollination, water filtration, carbon storage), disease emergence (habitat destruction increases zoonotic spillover risk), and cultural values. Economic valuation attempts to quantify nature's contributions.""",
            metadata={"domain": "climate", "tags": ["biodiversity", "extinction", "conservation", "ecosystems"], "difficulty": "intermediate", "focus": "climate"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_024",
            corpus_id=self.corpus_id,
            title="Sustainable Agriculture and Food Systems",
            content="""Food systems—how we produce, distribute, and consume food—contribute significantly to environmental problems while facing climate impacts. Sustainable agriculture aims to feed growing populations while reducing ecological footprints.

Agriculture contributes roughly one-quarter of global greenhouse gas emissions through methane from livestock and rice, nitrous oxide from fertilizers, carbon from land use change, and energy use. Livestock alone account for about 14.5% of emissions.

Industrial agriculture has increased yields dramatically but with environmental costs: soil degradation, water pollution from fertilizer runoff, pesticide impacts on pollinators, and biodiversity loss. Monoculture cropping depletes soil health and increases pest vulnerability.

Regenerative agriculture practices aim to rebuild soil health while maintaining productivity. Techniques include cover cropping, reduced tillage, diverse rotations, and integrated livestock. Carbon sequestration in soil could partially offset emissions, though permanence and measurement remain challenges.

Plant-based proteins and alternative proteins have gained market share. Beyond Meat and Impossible Foods offer products competing with conventional meat. Cultivated meat—grown from animal cells—is beginning commercialization. These alternatives aim to reduce livestock's environmental footprint.

Food waste occurs throughout supply chains—roughly one-third of food produced is lost or wasted. Reducing waste addresses both emissions (decomposing food produces methane) and food security.

Climate impacts on agriculture include shifting growing zones, changing precipitation, extreme weather damage, and pest/disease range expansion. Adaptation measures include drought-resistant varieties, irrigation efficiency, and adjusted planting timing.

Global food security concerns persist despite production capacity. Distribution, affordability, and conflict-related disruptions leave hundreds of millions food insecure. Climate impacts threaten to worsen food insecurity in vulnerable regions.""",
            metadata={"domain": "climate", "tags": ["agriculture", "food", "sustainability", "farming"], "difficulty": "intermediate", "focus": "climate"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_025",
            corpus_id=self.corpus_id,
            title="Environmental Justice",
            content="""Environmental justice addresses the disproportionate environmental burdens borne by low-income communities and communities of color. This movement has gained prominence in climate and environmental policy discussions.

Disparities in environmental exposure are well-documented. Polluting facilities—refineries, chemical plants, waste sites—are disproportionately located near minority and low-income communities. Air quality in these areas is often worse, contributing to higher rates of asthma and other health conditions. Lead exposure, water contamination, and other hazards follow similar patterns.

Historical factors including redlining, exclusionary zoning, and discriminatory siting decisions created these disparities. Communities with less political power were less able to oppose unwanted facilities. Property values near pollution sources are lower, creating feedback loops.

The environmental justice movement emerged in the 1980s, combining civil rights and environmental activism. Robert Bullard's research documented discriminatory waste facility siting. The 1991 First National People of Color Environmental Leadership Summit established foundational principles.

Climate justice extends these concerns to climate change. Vulnerable communities face greater climate impacts while having contributed least to emissions. Frontline communities include low-lying coastal areas, regions dependent on climate-sensitive agriculture, and urban heat islands.

Policy responses include environmental justice screening tools (like EPA's EJScreen), requirements to consider cumulative impacts in permitting, targeted investments in overburdened communities, and meaningful community engagement in decision-making. The Justice40 Initiative aims to direct 40% of certain federal investments toward disadvantaged communities.

Internationally, climate justice discussions address historical emissions responsibility, adaptation financing for developing countries, and loss and damage compensation for climate impacts beyond adaptation capacity.""",
            metadata={"domain": "climate", "tags": ["environmental-justice", "equity", "pollution", "communities"], "difficulty": "intermediate", "focus": "climate"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_026",
            corpus_id=self.corpus_id,
            title="Plastic Pollution and Waste",
            content="""Plastic pollution has emerged as a major environmental concern, with plastic accumulating in oceans, landscapes, and organisms. Efforts to address plastic waste span reduction, recycling, and cleanup.

Global plastic production has increased from 2 million tons in 1950 to over 400 million tons annually. Roughly half is single-use. Production continues growing, driven by packaging, construction, and textiles. Fossil fuel companies are investing in plastic production as transportation fuel demand declines.

Ocean plastic pollution is highly visible. An estimated 8-11 million tons enter oceans annually through rivers, coastal areas, and direct dumping. Garbage patches—including the Great Pacific Garbage Patch—concentrate floating debris. Plastic persists for centuries, breaking into smaller pieces (microplastics) but not biodegrading.

Microplastics—particles smaller than 5mm—are ubiquitous. They've been found in drinking water, food, air, and human blood and tissues. Health effects are still being researched, but concerns include potential toxicity, endocrine disruption, and physical impacts.

Recycling addresses only a fraction of plastic waste. Globally, less than 10% of plastics are recycled. Contamination, material diversity, and economics limit recycling viability. Many plastics collected for recycling have historically been exported, often ending up in landfills or the environment.

Policy responses include plastic bag bans (now in numerous countries and localities), extended producer responsibility schemes, single-use plastic restrictions, and bottle deposit systems. The UN is negotiating a global plastics treaty addressing the full lifecycle.

Alternative materials—biodegradable plastics, paper, metal, glass—can substitute for some applications but have their own environmental footprints. Reduction—avoiding unnecessary plastic use—may be most effective but faces convenience and cost barriers.""",
            metadata={"domain": "climate", "tags": ["plastic", "pollution", "waste", "recycling"], "difficulty": "intermediate", "focus": "climate"}
        ))

        # Economy and Business (docs 27-34)
        docs.append(DocumentSpec(
            doc_id="news_027",
            corpus_id=self.corpus_id,
            title="Inflation and Monetary Policy",
            content="""Inflation—rising prices across the economy—emerged as a major concern following the COVID-19 pandemic, prompting aggressive monetary policy responses with significant economic and political implications.

Inflation surged in 2021-2022 to levels not seen in four decades, reaching 9.1% (year-over-year CPI) in the US in June 2022. Contributing factors included pandemic supply chain disruptions, stimulus-boosted demand, labor market tightness, and energy price spikes following Russia's Ukraine invasion.

Central banks responded with rapid interest rate increases. The Federal Reserve raised rates from near-zero to over 5% in about 18 months—the fastest tightening in decades. The European Central Bank and others followed similar paths. These actions aimed to cool demand and reduce inflation.

Higher interest rates affect the economy through multiple channels. Mortgage rates roughly doubled, cooling housing markets. Business borrowing costs increased, affecting investment. Savers earned higher yields while borrowers faced higher costs. Asset prices, particularly growth stocks, declined.

The policy debate centered on how quickly to raise rates and how high to go. "Soft landing" scenarios anticipated reducing inflation without recession. Concerns about over-tightening risked unnecessary economic damage; under-tightening risked entrenched inflation expectations.

By late 2023, inflation had moderated substantially though remained above central bank targets. Core inflation (excluding volatile food and energy) proved stickier. Labor markets remained relatively strong, defying recession predictions.

Inflation affects people differently. Fixed-income earners and those without assets to hedge against inflation suffer most. Wage growth, while elevated, lagged price increases for much of the inflation period. Housing affordability declined dramatically due to higher prices and mortgage rates.""",
            metadata={"domain": "economy", "tags": ["inflation", "federal-reserve", "interest-rates", "monetary-policy"], "difficulty": "intermediate", "focus": "economy"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_028",
            corpus_id=self.corpus_id,
            title="Labor Markets and the Future of Work",
            content="""Labor markets have experienced significant shifts, from pandemic disruptions through tight conditions, raising questions about the future of work including automation, flexibility, and worker power.

The COVID-19 pandemic caused massive labor market disruption. Unemployment spiked to nearly 15% in April 2020—the highest since the Great Depression. Recovery was faster than expected, with unemployment returning below 4% by late 2021 and remaining low despite recession concerns.

The "Great Resignation" described elevated voluntary quit rates as workers reassessed careers, sought better conditions, or left the workforce. Labor force participation, especially among older workers, declined and hasn't fully recovered. Explanations include early retirements, caregiving responsibilities, long COVID, and changed preferences.

Worker bargaining power increased in tight labor markets. Wages rose, particularly for lower-paid workers, narrowing inequality. Workers demanded and often received flexibility, better conditions, and remote work options. The "quiet quitting" discourse reflected changing attitudes about work-life balance.

Unionization interest has grown, particularly among younger workers and in previously non-union sectors like retail and tech. High-profile campaigns at Amazon and Starbucks achieved some victories despite company opposition. Union membership rates remain near historic lows but have stabilized.

Automation concerns persist, with AI potentially affecting white-collar jobs previously considered secure. However, past automation waves created new jobs even while eliminating others. The transition's speed, distribution of impacts, and policy responses remain uncertain.

Gig economy workers—driving for rideshare apps, delivering food, or completing tasks—face classification debates. Some jurisdictions have required reclassification as employees with associated benefits; others have maintained independent contractor status. Portable benefits and new worker categories are proposed alternatives.""",
            metadata={"domain": "economy", "tags": ["labor", "employment", "unions", "workforce"], "difficulty": "intermediate", "focus": "economy"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_029",
            corpus_id=self.corpus_id,
            title="Housing Affordability Crisis",
            content="""Housing affordability has deteriorated in many markets, with prices and rents rising faster than incomes, creating challenges for prospective buyers, renters, and policymakers.

Home prices increased dramatically during the pandemic, driven by low mortgage rates, remote work enabling relocation, and limited supply. The S&P Case-Shiller index rose roughly 40% from early 2020 to mid-2022. Subsequent mortgage rate increases cooled price growth but didn't reverse gains.

First-time homebuyers face particular challenges. Down payment requirements, student debt burdens, and competition from investors and cash buyers create barriers. The median age of first-time buyers has increased. Homeownership rates among younger households have declined.

Rental markets tightened alongside homeownership challenges. Rent increases exceeded wage growth in many markets. Eviction moratoriums during the pandemic delayed but didn't prevent displacement. Rental vacancy rates reached historic lows in some markets.

Housing supply constraints reflect decades of underbuilding. Zoning restrictions—single-family zoning, density limits, parking requirements—prevent construction in many areas. Construction costs, labor shortages, and approval timelines further limit supply. California, in particular, has built far fewer units than population and job growth warrant.

Policy responses span multiple levels. Local zoning reforms aim to allow more housing construction. State policies preempt restrictive local zoning in some cases. Federal proposals include rental assistance expansion, down payment assistance, and construction incentives. Housing vouchers serve only a fraction of eligible households due to funding limits.

Homelessness has increased, visible in encampments in many cities. Causes include housing costs, mental health and substance abuse issues, and inadequate services. Approaches range from enforcement to housing-first programs providing unconditional housing.""",
            metadata={"domain": "economy", "tags": ["housing", "affordability", "real-estate", "rent"], "difficulty": "intermediate", "focus": "economy"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_030",
            corpus_id=self.corpus_id,
            title="Supply Chain Resilience",
            content="""Global supply chains, optimized for efficiency over decades, proved vulnerable during the COVID-19 pandemic. Subsequent disruptions have prompted rethinking of supply chain design and government involvement.

Pandemic disruptions began with Chinese factory closures in early 2020, then port congestion as demand surged while capacity constraints persisted. Semiconductor shortages idled auto plants worldwide. Container shipping rates increased tenfold at peak. Delays and shortages affected products from bicycles to appliances.

Just-in-time inventory practices, minimizing carrying costs by receiving inputs as needed, amplified disruptions. Without buffer stocks, any supply interruption immediately affected production. Companies are reconsidering inventory strategies, accepting higher costs for greater resilience.

Geographic concentration creates vulnerability. Taiwan's dominance in advanced semiconductors, China's role in electronics manufacturing, and single-source dependencies across industries present risks from natural disasters, geopolitical tensions, or pandemics.

"Reshoring" and "friendshoring" describe efforts to move production closer to consumers or to allied nations. The CHIPS Act incentivizes US semiconductor manufacturing. Companies are diversifying supplier bases across countries. However, cost advantages of existing locations and infrastructure requirements limit transition speed.

Supply chain visibility—knowing where inputs originate and current status—has improved through technology. Companies mapped supplier networks more thoroughly after pandemic exposures. Digital tracking and data sharing enable faster disruption response.

Logistics investments accelerated, including port automation, warehouse robotics, and alternative routing capabilities. Labor challenges in trucking and warehousing persist. E-commerce growth permanently increased logistics demands.

Trade policy increasingly considers supply chain security alongside traditional economic objectives. Critical mineral supply chains, pharmaceutical ingredients, and defense-related manufacturing receive particular attention.""",
            metadata={"domain": "economy", "tags": ["supply-chain", "logistics", "manufacturing", "trade"], "difficulty": "intermediate", "focus": "economy"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_031",
            corpus_id=self.corpus_id,
            title="Income Inequality and Wealth Gaps",
            content="""Economic inequality—gaps in income and wealth between different groups—has widened in recent decades, generating debates about causes, consequences, and policy responses.

Income inequality has increased substantially since the 1970s. The top 1% of earners capture a significantly larger share of national income than in mid-century decades. CEO-to-worker pay ratios have grown from roughly 20:1 to over 300:1. Middle-class income growth has lagged productivity gains.

Wealth inequality exceeds income inequality. The top 10% of households own roughly 70% of wealth; the bottom 50% own about 2%. Racial wealth gaps are stark: median white family wealth significantly exceeds that of Black and Hispanic families, reflecting historical discrimination and ongoing disparities.

Explanations for rising inequality include globalization (competition from lower-wage countries), technological change (automation of middle-skill jobs), declining unionization, tax policy changes, education premiums, and changing corporate practices prioritizing shareholder returns.

Consequences of inequality include reduced social mobility (children's outcomes increasingly tied to parents' status), health disparities, differential political influence, and potentially slower economic growth (as consumption is constrained).

Policy debates span taxation (wealth taxes, higher marginal rates, capital gains treatment), labor policy (minimum wage, union support), education (early childhood programs, college affordability), and direct transfers (expanded tax credits, basic income proposals).

The pandemic initially worsened inequality, with low-wage workers facing job losses while higher-income workers maintained employment remotely. Subsequent tight labor markets and elevated wage growth at the bottom narrowed some gaps, though sustainability remains uncertain.""",
            metadata={"domain": "economy", "tags": ["inequality", "wealth", "income", "poverty"], "difficulty": "intermediate", "focus": "economy"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_032",
            corpus_id=self.corpus_id,
            title="The US-China Economic Relationship",
            content="""The economic relationship between the United States and China—the world's two largest economies—has become increasingly contentious, with implications for trade, technology, and global economic architecture.

Trade tensions escalated under the Trump administration with tariffs on hundreds of billions of dollars of Chinese goods, citing unfair trade practices, intellectual property theft, and trade imbalances. China retaliated with counter-tariffs. The Biden administration has largely maintained tariffs while conducting reviews.

Technology competition has intensified. US export controls restrict China's access to advanced semiconductors and manufacturing equipment. Entity list designations prohibit American companies from supplying certain Chinese firms. Restrictions on TikTok, concerns about Huawei, and scrutiny of Chinese investments reflect national security concerns.

Chinese industrial policy—subsidies, technology transfer requirements, state-owned enterprise advantages—raises concerns about competitive fairness. The "Made in China 2025" plan targeted leadership in key industries. US responses include domestic industrial policy through the CHIPS Act and Inflation Reduction Act.

Supply chain "decoupling" or "de-risking" describes efforts to reduce economic dependencies on China. Complete decoupling is economically impractical given integration levels, but diversification of critical supply chains is accelerating. Companies face pressure from both governments regarding technology sharing and investment decisions.

Investment flows face increasing scrutiny. The US has expanded review of Chinese investments in sensitive sectors. Concerns about capital flows to Chinese military-linked companies led to investment restrictions. Chinese firms have delisted from US stock exchanges amid audit access disputes.

Despite tensions, substantial economic ties persist. Bilateral trade, while evolving, remains enormous. Consumer goods, intermediate inputs, and agricultural products continue flowing. Managing competition while avoiding broader conflict remains a central challenge.""",
            metadata={"domain": "economy", "tags": ["china", "trade", "tariffs", "technology"], "difficulty": "intermediate", "focus": "economy"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_033",
            corpus_id=self.corpus_id,
            title="Banking Sector Stress and Financial Regulation",
            content="""The banking sector experienced significant stress in 2023 with several regional bank failures, raising questions about regulation, supervision, and financial system resilience.

Silicon Valley Bank (SVB) failed in March 2023—the second-largest bank failure in US history. SVB's concentrated depositor base (tech startups and VCs), heavy investment in long-duration bonds that lost value as rates rose, and rapid deposit flight created a classic bank run. Signature Bank failed days later; First Republic Bank followed.

Regulatory responses included FDIC guarantees of all deposits at failed banks (beyond the standard $250,000 limit), Federal Reserve emergency lending facilities, and large bank acquisition of failed institution assets. These actions prevented broader contagion but raised concerns about moral hazard and implicit guarantees.

Post-mortems identified supervision failures alongside bank management failures. Examiners had identified risks that weren't adequately addressed. The 2018 rollback of Dodd-Frank requirements for mid-sized banks left SVB with less stringent oversight than the largest institutions.

International reverberations included Credit Suisse's forced sale to UBS after decades of problems and loss of confidence. European regulators coordinated the rescue to prevent broader instability. AT1 bond write-downs in the deal sparked controversy about creditor hierarchy.

Regulatory discussions center on capital requirements, liquidity rules, interest rate risk management, and supervisory effectiveness. Proposals include enhanced requirements for mid-sized banks, adjustments to how unrealized losses on securities affect capital calculations, and improved stress testing scenarios.

Commercial real estate exposure, particularly office buildings affected by remote work, represents ongoing concern for regional banks with concentrated portfolios. Some anticipate further stress as loans mature and require refinancing at higher rates.""",
            metadata={"domain": "economy", "tags": ["banking", "svb", "regulation", "financial-crisis"], "difficulty": "intermediate", "focus": "economy"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_034",
            corpus_id=self.corpus_id,
            title="Student Debt and Higher Education Costs",
            content="""Student debt in the United States has grown to approximately $1.7 trillion, affecting tens of millions of borrowers and generating ongoing policy debates about relief, reform, and higher education financing.

The growth of student debt reflects rising college costs, expanded enrollment, and shifts from grants to loans in financial aid. Average debt for graduates has increased substantially, with many borrowers owing $50,000 or more. Graduate and professional school debt accounts for a disproportionate share of total balances.

Debt burdens affect life decisions. Research links student debt to delayed homeownership, reduced retirement savings, and postponed marriage and children. Racial disparities exist: Black borrowers, on average, owe more than white borrowers and face greater repayment challenges.

The Biden administration attempted broad student debt cancellation ($10,000-$20,000 per borrower), which the Supreme Court blocked. Subsequent efforts have used existing authority for targeted relief—public service loan forgiveness, income-driven repayment forgiveness, and cancellation for borrowers defrauded by institutions.

Income-driven repayment plans cap payments at a percentage of discretionary income, with forgiveness after 20-25 years. The SAVE plan, introduced in 2023, significantly reduced payments for many borrowers. However, long-term forgiveness creates uncertainty about ultimate repayment.

Broader reform proposals include free community college, expanded Pell Grants, tuition-free public university proposals, and restructuring of federal loan programs. College cost drivers—administrative growth, amenities competition, state funding cuts—remain addressable through different interventions.

For-profit colleges, which often leave students with debt but poor employment outcomes, face ongoing scrutiny. Regulations around gainful employment and borrower defense to repayment aim to protect students from predatory institutions.""",
            metadata={"domain": "economy", "tags": ["student-debt", "education", "loans", "college"], "difficulty": "intermediate", "focus": "economy"}
        ))

        # International Affairs (docs 35-42)
        docs.append(DocumentSpec(
            doc_id="news_035",
            corpus_id=self.corpus_id,
            title="The Russia-Ukraine War",
            content="""Russia's full-scale invasion of Ukraine in February 2022 launched the largest land war in Europe since World War II, reshaping geopolitics, energy markets, and international security relationships.

Russia had seized Crimea in 2014 and supported separatists in eastern Ukraine. The 2022 invasion aimed to capture Kyiv within days and install a compliant government. Ukrainian resistance, Western military assistance, and Russian military shortcomings prevented this outcome.

The conflict evolved into attritional warfare along an extensive front. Ukrainian counteroffensives in late 2022 recaptured significant territory. Fighting in 2023 produced limited territorial changes despite intense combat. Both sides sustained heavy casualties; precise figures remain uncertain.

Western support includes billions in military equipment—from Javelin missiles and HIMARS rocket systems to tanks and eventually F-16 fighters. Economic assistance supports Ukrainian government functions. Sanctions target Russian financial institutions, oligarchs, energy exports, and technology access.

Humanitarian consequences include thousands of civilian deaths, millions of refugees (the largest displacement in Europe since WWII), widespread infrastructure destruction, and documented war crimes including civilian massacres and deportation of children.

Energy market effects were immediate and lasting. European countries rapidly reduced Russian gas dependence, though at significant cost. Energy prices spiked, contributing to inflation. Long-term restructuring of European energy systems accelerated.

Geopolitical realignments include NATO expansion (Finland and Sweden), increased European defense spending, and questions about the global order. Russia has deepened ties with China, Iran, and North Korea. The Global South response has been more mixed, with many countries declining to impose sanctions.

Prospects for resolution remain unclear, with neither side achieving military objectives sufficient to force the other's terms.""",
            metadata={"domain": "international", "tags": ["russia", "ukraine", "war", "nato"], "difficulty": "intermediate", "focus": "international"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_036",
            corpus_id=self.corpus_id,
            title="The Israeli-Palestinian Conflict",
            content="""The Israeli-Palestinian conflict, ongoing for over seven decades, involves competing national claims, territorial disputes, and cycles of violence. Recent escalation has brought renewed international attention.

Historical background includes the 1948 establishment of Israel and resulting Palestinian displacement (the Nakba), the 1967 Six-Day War (Israel captured the West Bank, Gaza Strip, and East Jerusalem), and failed peace processes including the Oslo Accords.

The Gaza Strip has been governed by Hamas since 2007, with Israel and Egypt maintaining a blockade. The West Bank remains under Israeli military occupation with expanding settlements and Palestinian Authority governance of population centers.

Hamas's October 7, 2023 attack killed approximately 1,200 Israelis and took over 200 hostages—the deadliest day in Israeli history. Israel's subsequent military campaign in Gaza has killed tens of thousands of Palestinians, displaced most of Gaza's population, and caused a humanitarian catastrophe.

The conflict generates intense debate. Israeli perspectives emphasize security threats, terrorism, and the right of self-defense. Palestinian perspectives emphasize occupation, settlement expansion, and civilian casualties. International humanitarian law and proportionality are contested.

Regional dynamics include normalization agreements (Abraham Accords) between Israel and several Arab states, Iranian support for Hamas and Hezbollah, and complex relationships with Saudi Arabia, Egypt, and Jordan. US support for Israel has remained strong while criticism of military operations has grown.

Two-state solution proposals—independent Israeli and Palestinian states—have been the framework for peace negotiations, though prospects have diminished with settlement expansion and political polarization. One-state outcomes raise different challenges regarding rights and demographics.""",
            metadata={"domain": "international", "tags": ["israel", "palestine", "hamas", "gaza"], "difficulty": "intermediate", "focus": "international"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_037",
            corpus_id=self.corpus_id,
            title="China's Rise and Global Influence",
            content="""China's economic growth and expanding global influence have reshaped international relations, generating debates about great power competition, development models, and the future of the international order.

China's economy has grown to become the world's second-largest (largest by some purchasing power measures). Hundreds of millions have escaped poverty. Manufacturing dominance spans industries from electronics to solar panels. However, growth has slowed, and challenges include property sector stress, demographic decline, and debt levels.

The Belt and Road Initiative (BRI), launched in 2013, has invested hundreds of billions in infrastructure projects across Asia, Africa, Latin America, and Europe. Critics raise concerns about debt sustainability, governance standards, and geopolitical influence. Supporters note development benefits and alternative financing for countries with limited options.

Taiwan remains the most dangerous flashpoint. The US acknowledges Beijing's position that Taiwan is part of China while opposing unilateral changes to the status quo and maintaining unofficial relations with Taiwan. Military tensions have increased with more frequent Chinese exercises near Taiwan.

The South China Sea disputes involve competing territorial claims with multiple Southeast Asian nations. China has built artificial islands with military installations. Freedom of navigation operations by the US and allies challenge Chinese claims.

Chinese domestic developments affecting international relations include the crackdown in Hong Kong, treatment of Uyghurs in Xinjiang (which the US has termed genocide), COVID-19 origins investigations, and technology controls and surveillance expansion.

Western responses include the Quad grouping (US, Japan, Australia, India), AUKUS security partnership, technology restrictions, and "de-risking" strategies. The international order faces questions about whether it can accommodate China's rise or whether systemic conflict is inevitable.""",
            metadata={"domain": "international", "tags": ["china", "taiwan", "belt-and-road", "geopolitics"], "difficulty": "intermediate", "focus": "international"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_038",
            corpus_id=self.corpus_id,
            title="NATO and European Security",
            content="""The North Atlantic Treaty Organization (NATO), founded in 1949, has experienced renewed relevance following Russia's invasion of Ukraine, expanding membership and increasing defense commitments.

NATO's core principle—Article 5 collective defense—states that an attack on one member is an attack on all. This has been invoked once, following September 11, 2001. The alliance includes 32 members following Finland's 2023 accession and Sweden's 2024 accession.

Russian aggression prompted major shifts. European defense spending, which had declined after the Cold War, is increasing toward NATO's 2% of GDP guideline. Germany announced a €100 billion defense fund and policy reversal on weapons exports. Eastern flank countries host enhanced NATO presence.

NATO capabilities include integrated military command structures, interoperability standards, nuclear sharing arrangements, and rapid reaction forces. The alliance maintains technological advantages in many areas, though ammunition stockpiles depleted through Ukraine support have highlighted industrial capacity needs.

US-European relations have experienced tensions over burden-sharing, with American officials long pressing allies to increase defense spending. European strategic autonomy discussions reflect desire for independent capabilities, though practical implementation remains limited.

Expansion debates continue. Ukraine seeks NATO membership; the alliance has affirmed its right to apply while deferring actual accession. Russia cites potential NATO expansion as a casus belli, though NATO frames itself as defensive.

The alliance faces challenges including consensus requirements (Hungary has delayed some decisions), varied threat perceptions (southern members prioritize Mediterranean issues), and potential American political shifts. NATO's 75th anniversary in 2024 occurs during its most challenging period since the Cold War.""",
            metadata={"domain": "international", "tags": ["nato", "europe", "defense", "russia"], "difficulty": "intermediate", "focus": "international"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_039",
            corpus_id=self.corpus_id,
            title="Global Migration Patterns",
            content="""International migration has reached record levels, driven by conflict, climate impacts, economic opportunity, and demographic imbalances. Migration management has become a central political issue across regions.

Global migrants number approximately 280 million—about 3.5% of world population. Refugees and asylum seekers total roughly 35 million, the highest level recorded. Major displacement crises include Syria, Ukraine, Venezuela, Afghanistan, and Myanmar.

The US southern border has seen record apprehension numbers, with migrants from Central America, Venezuela, Cuba, Haiti, and increasingly Africa and Asia. Root causes include violence, economic conditions, and climate impacts. Policy debates center on asylum processing, border security, and addressing push factors.

European migration flows include Mediterranean crossings (primarily to Italy, Greece, and Spain) from Africa and the Middle East. The 2015-2016 crisis prompted policy changes including agreements with Turkey and Libya. Internal EU tensions persist over burden-sharing and asylum reform.

Climate migration is expected to increase substantially. The World Bank projects 216 million internal climate migrants by 2050 absent climate action. Sea level rise, drought, and extreme weather will displace populations, though most movement will be within countries.

Demographic imbalances shape migration incentives. Aging populations in developed countries face labor shortages; young populations in developing regions face limited opportunities. Legal pathways for economic migration often don't match labor needs, contributing to irregular migration.

Integration challenges include language acquisition, credential recognition, social services access, and xenophobic backlash. Second-generation outcomes vary significantly by context. Remittances sent by migrants total over $600 billion annually—exceeding foreign aid flows and constituting major income for many developing countries.""",
            metadata={"domain": "international", "tags": ["migration", "refugees", "immigration", "borders"], "difficulty": "intermediate", "focus": "international"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_040",
            corpus_id=self.corpus_id,
            title="Global Health Security",
            content="""The COVID-19 pandemic exposed vulnerabilities in global health security systems, prompting efforts to improve preparedness for future health emergencies while highlighting persistent inequities.

COVID-19 has caused over 7 million confirmed deaths globally (likely undercounts), massive economic disruption, and lasting health effects for millions with long COVID. Responses varied dramatically across countries in effectiveness of containment, healthcare capacity, and vaccination rollout.

Vaccine development achieved unprecedented speed, with multiple effective vaccines authorized within a year of the virus's identification. However, global distribution remained inequitable: wealthy countries secured most early supplies while much of Africa and Asia waited months longer for meaningful access.

Pandemic preparedness reforms are underway. WHO members are negotiating a pandemic treaty addressing pathogen sharing, response coordination, and financing. The Pandemic Fund provides resources for preparedness investments in developing countries. Surveillance and early warning systems are being strengthened.

Antimicrobial resistance (AMR) represents another major threat. Drug-resistant infections already cause over 1 million deaths annually and could cause 10 million by 2050 without intervention. New antibiotic development has declined as pharmaceutical companies find the economics unappealing. Stewardship programs and alternative approaches are being pursued.

Health systems in many countries remain fragile. The pandemic depleted healthcare workers and revealed capacity limits. Universal health coverage remains distant for much of the world's population. Climate change brings additional health threats including heat deaths, vector-borne disease expansion, and food security impacts.

Global health governance faces legitimacy and effectiveness questions. WHO reform, coordination between health and security institutions, and financing mechanisms remain works in progress.""",
            metadata={"domain": "international", "tags": ["global-health", "pandemic", "covid", "who"], "difficulty": "intermediate", "focus": "international"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_041",
            corpus_id=self.corpus_id,
            title="International Trade and Economic Integration",
            content="""International trade patterns continue evolving, with tensions between globalization's efficiency benefits and concerns about resilience, labor standards, and national security.

Global trade grew substantially from 1990-2008, with supply chains spanning continents and China becoming the world's factory. Growth has been slower and more contested since the financial crisis and particularly following pandemic disruptions and geopolitical tensions.

Trade agreements have proliferated, though large multilateral deals face obstacles. The WTO's Doha Round remains stalled. Regional agreements have proceeded: USMCA replaced NAFTA; RCEP created the world's largest trade bloc in Asia; the African Continental Free Trade Area aims to integrate the continent.

Trade policy increasingly incorporates non-economic objectives. Labor and environmental provisions appear in newer agreements. "Friend-shoring" prioritizes trade with geopolitical allies. Industrial policy to support strategic sectors has returned to prominence.

Services trade and digital trade grow in importance. Data localization requirements, privacy regulations, and content restrictions fragment the digital economy. E-commerce trade rules remain underdeveloped internationally.

Trade's distributional effects remain contested. Aggregate economic gains coexist with concentrated losses in communities affected by import competition. Trade adjustment assistance programs have proven inadequate. Political backlash against trade agreements reflects these concerns.

Sanctions have become a prominent economic statecraft tool. Russia faces unprecedented sanctions; Chinese firms face restrictions; secondary sanctions affect third parties doing business with sanctioned entities. Questions arise about dollar dominance, alternative payment systems, and sanctions effectiveness.""",
            metadata={"domain": "international", "tags": ["trade", "wto", "globalization", "tariffs"], "difficulty": "intermediate", "focus": "international"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_042",
            corpus_id=self.corpus_id,
            title="Nuclear Weapons and Arms Control",
            content="""Nuclear weapons risks have returned to prominence amid deteriorating great power relations, arms control framework erosion, and emerging technology challenges.

Nine countries possess nuclear weapons: the US and Russia (roughly 90% of global stockpiles), UK, France, China, India, Pakistan, Israel (undeclared), and North Korea. Total warheads number approximately 12,500, with roughly 3,800 deployed.

Arms control frameworks have weakened. The INF Treaty collapsed in 2019. New START, limiting US and Russian strategic weapons, was extended but future negotiations face obstacles. The Open Skies Treaty ended. Russia has suspended New START implementation and resumed nuclear testing (at least rhetorically).

Russian nuclear signaling during the Ukraine invasion—warnings against intervention, nuclear weapons deployment to Belarus—has raised concerns about escalation risks. Experts debate whether Russia would actually use nuclear weapons and how the West should respond to threats.

China is expanding its nuclear arsenal significantly, from roughly 300 warheads toward an estimated 1,000+ by 2030. This complicates arms control previously focused on US-Russia bilateral frameworks. China has resisted trilateral negotiations.

North Korea continues developing delivery systems capable of reaching the US mainland. Negotiations have stalled since 2019. Iran remains below nuclear weapons capability but has expanded enrichment, with the JCPOA nuclear deal defunct in practice.

Emerging technologies create new challenges. Hypersonic weapons, AI applications, space-based systems, and cyber vulnerabilities to nuclear command and control complicate strategic stability calculations.

Nuclear risk reduction proposals include no-first-use declarations, launch procedure changes, communication channels, and limiting destabilizing capabilities. Implementation faces political obstacles and verification challenges.""",
            metadata={"domain": "international", "tags": ["nuclear", "arms-control", "weapons", "nonproliferation"], "difficulty": "advanced", "focus": "international"}
        ))

        # Health and Science News (docs 43-46)
        docs.append(DocumentSpec(
            doc_id="news_043",
            corpus_id=self.corpus_id,
            title="Mental Health: Growing Crisis and Responses",
            content="""Mental health has emerged as a major public health concern, with rising prevalence of conditions, increased awareness, and expanded but still inadequate treatment capacity.

Mental health conditions affect a substantial portion of the population. Depression affects roughly 280 million people globally. Anxiety disorders are similarly prevalent. Suicide remains a leading cause of death, particularly among young people. The pandemic worsened many indicators.

Youth mental health has deteriorated notably. Emergency room visits for mental health crises among adolescents increased sharply. Social media's role is debated, with some research linking heavy use to depression and anxiety, particularly among girls. School-based mental health services have expanded but remain insufficient.

Treatment access remains limited. The US faces severe shortages of mental health professionals, particularly psychiatrists. Wait times for appointments can stretch months. Insurance coverage, while improved by parity laws, often inadequately reimburses providers. Rural areas face particular access challenges.

Workplace mental health receives increasing attention. Employers have expanded employee assistance programs, mental health benefits, and wellness initiatives. Open discussion has reduced some stigma, though concerns about career impacts persist. Burnout gained recognition as an occupational phenomenon.

Treatment innovations include expanded telehealth (which improved access during the pandemic), psychedelic-assisted therapy research (psilocybin for depression, MDMA for PTSD), digital therapeutics (apps with clinical evidence), and ketamine treatments. Integration of mental and physical healthcare aims to improve both.

Crisis response systems are evolving. The 988 Suicide and Crisis Lifeline provides a national number for mental health emergencies. Mobile crisis teams offer alternatives to police response. However, psychiatric bed shortages leave many in crisis without appropriate care settings.""",
            metadata={"domain": "health", "tags": ["mental-health", "depression", "anxiety", "treatment"], "difficulty": "intermediate", "focus": "health"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_044",
            corpus_id=self.corpus_id,
            title="Drug Pricing and Pharmaceutical Industry",
            content="""Prescription drug prices in the United States exceed those in other developed countries, generating ongoing debates about innovation incentives, access to medicines, and pharmaceutical industry practices.

US drug spending approaches $400 billion annually. Prices for brand-name drugs are typically 2-3 times higher than in comparable countries. Some specialty medications cost hundreds of thousands of dollars per year. Insulin prices, though recently declining, have been a particular focus given diabetes prevalence and the drug's century of existence.

The pharmaceutical industry justifies high prices as necessary to fund R&D for innovative treatments. Drug development is expensive and high-risk, with many candidates failing in trials. Industry critics note that significant research funding comes from NIH and that marketing budgets often exceed R&D spending.

Patent protections and regulatory exclusivities enable high prices by preventing generic competition. "Evergreening" strategies extend protection through incremental modifications. "Pay for delay" settlements have been challenged as anticompetitive. Biosimilar adoption has been slower than generic drug uptake.

Policy interventions include the Inflation Reduction Act's Medicare drug price negotiation authority—limited initially but potentially expanding. CMS can now negotiate prices for high-cost drugs lacking competition. Insulin price caps in Medicare, inflation rebates, and out-of-pocket caps also address costs.

State-level actions include price transparency requirements, importation programs (from Canada), and Medicaid rebate negotiations. International reference pricing—setting US prices relative to other countries—has been proposed but not implemented federally.

PBMs (pharmacy benefit managers) face scrutiny for their role in the drug supply chain. Their rebate negotiations, spread pricing, and conflicts of interest have drawn bipartisan criticism and reform proposals.""",
            metadata={"domain": "health", "tags": ["drugs", "pharmaceutical", "pricing", "healthcare"], "difficulty": "intermediate", "focus": "health"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_045",
            corpus_id=self.corpus_id,
            title="Reproductive Rights After Dobbs",
            content="""The Supreme Court's Dobbs decision (2022) overturning Roe v. Wade has fragmented abortion access across states, generating significant legal, political, and healthcare implications.

Dobbs held that the Constitution does not confer a right to abortion, returning the issue to states. This reversed nearly 50 years of precedent under Roe v. Wade (1973) and Planned Parenthood v. Casey (1992).

State responses have varied dramatically. Approximately half of states have banned or severely restricted abortion. Some bans took effect immediately through "trigger laws" enacted in anticipation of Roe's reversal. Other states have expanded protections, with some enshrining abortion rights in state constitutions.

Legal complexities include questions about interstate travel for abortion, medication abortion access (mifepristone is FDA-approved but faces state restrictions and ongoing litigation), enforcement against providers, and exceptions for life of the mother or rape/incest.

Access disparities have widened. Patients in ban states must travel to access care, creating burdens based on economic resources, work flexibility, and childcare availability. Wait times have increased in states still providing services. Telemedicine and mail-order medication abortion have expanded but face legal challenges.

Healthcare implications extend beyond abortion. Providers in restrictive states report confusion about permissible care in pregnancy complications. Medical training in restricted states raises concerns about obstetric education. Emergency room policies for miscarriage management vary.

Political salience has increased, with abortion access motivating voter turnout. Ballot initiatives protecting abortion rights have succeeded even in Republican-leaning states. The issue figures prominently in elections at all levels.""",
            metadata={"domain": "health", "tags": ["abortion", "reproductive-rights", "dobbs", "healthcare"], "difficulty": "intermediate", "focus": "health"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_046",
            corpus_id=self.corpus_id,
            title="Advances in Medical Science",
            content="""Medical science continues advancing rapidly, with breakthroughs in gene therapy, cancer treatment, neuroscience, and medical technology offering new treatment possibilities.

Gene therapy has achieved significant milestones. The first CRISPR-based treatment was approved in 2023 for sickle cell disease and beta-thalassemia, offering potential cures for genetic conditions. Gene therapies for inherited blindness, spinal muscular atrophy, and hemophilia have reached patients. High costs (often millions per treatment) raise access questions.

Cancer treatment continues evolving beyond traditional chemotherapy. Immunotherapy harnesses the immune system to fight cancer, with checkpoint inhibitors and CAR-T cell therapy achieving remarkable responses in some cancers. Targeted therapies attack specific molecular features of tumors. Early cancer detection through blood tests (liquid biopsies) shows promise.

Obesity treatments have transformed with GLP-1 agonists like Ozempic and Wegovy demonstrating substantial weight loss. Originally developed for diabetes, these medications address a condition affecting over 40% of American adults. Supply constraints, high costs, and questions about long-term use accompany rapid adoption.

Brain-computer interfaces have advanced from research settings toward clinical applications. Implanted devices have enabled paralyzed patients to control computers and robotic limbs through thought. Neuralink and other companies pursue broader applications.

Artificial intelligence applications in medicine include diagnostic imaging analysis, drug discovery acceleration, and clinical decision support. Regulatory frameworks are adapting to evaluate AI-based medical devices.

Challenges include translating research advances into accessible treatments, managing healthcare costs of expensive new therapies, addressing disparities in access, and ensuring safety and efficacy as technologies develop rapidly.""",
            metadata={"domain": "health", "tags": ["medicine", "gene-therapy", "cancer", "research"], "difficulty": "intermediate", "focus": "health"}
        ))

        # Media and Information (docs 47-50)
        docs.append(DocumentSpec(
            doc_id="news_047",
            corpus_id=self.corpus_id,
            title="The Changing Media Landscape",
            content="""The news media industry continues transforming, with traditional business models under pressure, digital platforms reshaping distribution, and questions about journalism's sustainability and role.

Local news has declined dramatically. Newspaper employment has fallen roughly 70% since 2005. Many communities have become "news deserts" without local coverage. This affects accountability journalism covering local government, courts, schools, and community institutions.

Digital advertising, once expected to replace print advertising revenue, has concentrated at Google and Meta, leaving publishers with smaller shares. Programmatic advertising, privacy changes, and platform algorithm shifts create ongoing uncertainty.

Subscription models have succeeded for some national outlets (New York Times, Washington Post, Wall Street Journal) but remain challenging for smaller publications. News paywalls create access inequities and may contribute to misinformation spread when quality journalism is unavailable.

Alternative models include nonprofit news organizations, foundation support, public media expansion, and community-funded journalism. ProPublica, The Marshall Project, and local nonprofit newsrooms have established themselves, though sustainability questions persist.

Podcasts and newsletters have created new journalism formats and direct audience relationships. Some journalists have built independent practices on Substack and similar platforms. YouTube and TikTok serve as news sources, particularly for younger audiences.

Trust in media has declined and polarized along partisan lines. Conservative audiences distrust mainstream media; liberal audiences trust it more. This asymmetry reflects and reinforces political polarization. Media literacy education aims to help audiences evaluate sources and claims.

AI's impact on journalism is emerging, from automated reporting to deepfake concerns to chatbots potentially replacing search traffic to news sites.""",
            metadata={"domain": "media", "tags": ["journalism", "news", "media", "newspapers"], "difficulty": "intermediate", "focus": "media"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_048",
            corpus_id=self.corpus_id,
            title="Misinformation and Disinformation",
            content="""False and misleading information spreads through digital platforms, affecting public understanding of health, elections, climate, and other critical issues. Responses remain contested and incomplete.

Misinformation is false information spread without intent to deceive; disinformation is deliberately spread to mislead. Both categories encompass a spectrum from fabricated content to misleading framing of true information.

Health misinformation became prominent during the COVID-19 pandemic—false claims about treatments, vaccines, and pandemic origins spread widely. Anti-vaccine sentiment, amplified online, contributed to vaccination hesitancy. Climate misinformation similarly undermines public understanding and policy support.

Election misinformation includes false claims about candidates, voting procedures, and election outcomes. False claims of widespread fraud in the 2020 election persisted despite court rejections and lack of evidence. Such claims affect trust in democratic institutions.

Platform responses have evolved but remain contentious. Content moderation approaches include labeling, reducing distribution, and removal of violating content. Policies vary across platforms and have shifted over time. Critics argue moderation is excessive censorship; others argue it's insufficient.

State actors conduct disinformation campaigns. Russian operations have targeted elections in multiple countries. Chinese campaigns address Taiwan and COVID-19 narratives. Attribution is challenging, and responses risk escalation.

Generative AI introduces new challenges. Synthetic text, images, audio, and video become increasingly convincing and easy to produce. Deepfakes could enable novel disinformation. Detection tools are developing but may lag generation capabilities.

Media literacy efforts aim to help people evaluate sources, recognize manipulation techniques, and resist sharing false content. Structural interventions addressing platform design, algorithmic amplification, and economic incentives may complement individual skills.""",
            metadata={"domain": "media", "tags": ["misinformation", "disinformation", "fake-news", "fact-checking"], "difficulty": "intermediate", "focus": "media"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_049",
            corpus_id=self.corpus_id,
            title="Free Speech and Content Moderation",
            content="""Debates about free speech, platform responsibility, and content moderation have intensified as social media's influence has grown and as events from elections to pandemics have raised stakes around online speech.

First Amendment protections apply to government restrictions on speech, not private platform decisions. However, platforms' scale and centrality to public discourse have led some to argue they should be treated as public utilities or subject to common carrier principles.

Platform moderation policies address categories including violence, harassment, hate speech, misinformation, copyright, and spam. Enforcement relies on automated systems, human reviewers, and user reporting. Consistency, transparency, and appeals processes vary.

Section 230 of the Communications Decency Act provides platforms immunity from liability for user-generated content while allowing content moderation. Reform proposals range from narrowing immunity (to increase platform accountability) to expanding it (to reduce moderation incentives).

Political speech moderation is particularly contentious. Suspensions of former President Trump from major platforms following January 6 generated both support and criticism. Claims of anti-conservative bias are disputed by research but widely believed by conservative users.

International approaches vary. The EU's Digital Services Act mandates transparency and establishes accountability for large platforms. Some countries criminalize certain speech (Holocaust denial in Germany, for example). Others impose restrictive censorship.

Free speech concerns arise from both government and private power. Platform decisions affect whose speech reaches audiences; government mandates about content could violate the First Amendment or impose viewpoint discrimination. Academic debates consider how traditional free speech principles apply in the digital environment.

The Twitter/X acquisition by Elon Musk and subsequent policy changes illustrated how platform governance depends on owner decisions, raising questions about accountability for essential communications infrastructure.""",
            metadata={"domain": "media", "tags": ["free-speech", "moderation", "section-230", "platforms"], "difficulty": "intermediate", "focus": "media"}
        ))

        docs.append(DocumentSpec(
            doc_id="news_050",
            corpus_id=self.corpus_id,
            title="The Attention Economy and Digital Wellness",
            content="""Digital technologies compete for user attention through design features optimized for engagement, raising concerns about impacts on productivity, wellbeing, and society. "Digital wellness" efforts seek healthier technology relationships.

The attention economy describes how online services monetize user engagement. Advertising-supported business models incentivize maximizing time on platform. Features like infinite scroll, autoplay, notifications, and variable reward mechanisms (like slot machines) exploit psychological vulnerabilities.

Screen time has increased substantially, particularly among young people. Debates continue about whether specific harms result from quantity of use, type of use, or displaced activities. Research methodologies and causation versus correlation questions complicate definitive conclusions.

Design ethics movements advocate for technology that respects users. "Time Well Spent" and "Humane Technology" initiatives (led partly by former tech employees) promote design changes and regulatory requirements. Some platforms have introduced screen time tracking and notification controls, though critics question their effectiveness and sincerity.

Proposed interventions span individual, platform, and policy levels. Individual approaches include digital detoxes, app blockers, and intentional technology use practices. Platform changes could include friction against addictive features, chronological rather than engagement-optimized feeds, and removing metrics like likes.

Regulatory proposals include age verification, limits on data collection from children, restrictions on manipulative design, and digital duty of care requirements. The UK's Age Appropriate Design Code and proposed US KOSA legislation address youth protections specifically.

Workplace implications include debates about always-on communication expectations, attention fragmentation affecting deep work, and remote work's blurring of boundaries. Some organizations experiment with communication norms and tools addressing these challenges.

The broader question concerns what relationship with technology serves human flourishing—a question increasingly central to technology policy and design.""",
            metadata={"domain": "media", "tags": ["attention", "digital-wellness", "screen-time", "social-media"], "difficulty": "intermediate", "focus": "media"}
        ))

        return docs
