"""
American History Corpus Builder
===============================

Generates 50 documents covering American history from Colonial era to modern times.
"""

from typing import List
from .base import CorpusBuilder, DocumentSpec


class HistoryCorpusBuilder(CorpusBuilder):
    """Builder for American History corpus."""

    @property
    def corpus_id(self) -> str:
        return "history"

    @property
    def description(self) -> str:
        return "American History from Colonial era to modern times"

    @property
    def domain(self) -> str:
        return "history"

    def build_documents(self) -> List[DocumentSpec]:
        docs = []

        # Colonial Era (docs 1-8)
        docs.append(DocumentSpec(
            doc_id="hist_001",
            corpus_id=self.corpus_id,
            title="The Jamestown Settlement (1607)",
            content="""The Jamestown Settlement, established in 1607, was the first permanent English settlement in North America. Located in present-day Virginia, the colony faced tremendous hardships in its early years, including starvation, disease, and conflicts with the Powhatan Confederacy.

Captain John Smith played a crucial role in the colony's survival, implementing strict discipline and establishing trade relationships with Native Americans. The famous story of Pocahontas saving Smith's life has become legendary, though its historical accuracy is debated.

The introduction of tobacco cultivation by John Rolfe in 1612 transformed the colony's economic prospects. Tobacco became Virginia's cash crop and drove the demand for labor, eventually leading to the introduction of enslaved Africans in 1619. That same year saw the establishment of the House of Burgesses, the first representative assembly in the Americas.

The Jamestown experience established patterns that would shape American colonial development: the plantation economy, representative government, and the tragic institution of slavery.""",
            metadata={"domain": "colonial", "tags": ["jamestown", "virginia", "colonization"], "difficulty": "intermediate", "era": "colonial"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_002",
            corpus_id=self.corpus_id,
            title="The Mayflower Compact (1620)",
            content="""The Mayflower Compact, signed on November 11, 1620, stands as one of the foundational documents of American democracy. Drafted aboard the Mayflower before the Pilgrims disembarked at Plymouth, Massachusetts, the compact established a framework for self-governance.

The 41 male passengers who signed agreed to "covenant and combine ourselves together into a civil Body Politick" and to enact "just and equal Laws" for the general good of the colony. This represented a significant departure from the divine right of kings that dominated European governance.

The Pilgrims, separatists from the Church of England, sought religious freedom in the New World. Their journey and the Mayflower Compact reflected Enlightenment ideas about social contracts that would later influence the Declaration of Independence and Constitution.

The harsh first winter killed nearly half the colonists, but with help from the Wampanoag people, particularly Squanto, the survivors learned to cultivate native crops. The first Thanksgiving celebration in 1621 commemorated this survival and cooperation.""",
            metadata={"domain": "colonial", "tags": ["pilgrims", "massachusetts", "democracy"], "difficulty": "intermediate", "era": "colonial"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_003",
            corpus_id=self.corpus_id,
            title="The Salem Witch Trials (1692)",
            content="""The Salem Witch Trials of 1692 represent one of the darkest chapters in colonial American history. Beginning in Salem Village, Massachusetts, a wave of hysteria led to the accusation of over 200 people of practicing witchcraft.

The crisis began when several young girls, including Betty Parris and Abigail Williams, exhibited strange behaviors and accused local women of bewitching them. The accusations spread rapidly through the community, fueled by existing tensions, religious fervor, and fear.

Between February 1692 and May 1693, special courts convicted and executed nineteen people by hanging. One man, Giles Corey, was pressed to death for refusing to enter a plea. Many more died in jail awaiting trial.

The trials eventually ended when Governor William Phips dissolved the special court after his own wife was accused. The Salem Witch Trials serve as a cautionary tale about mass hysteria, the dangers of extremism, and the importance of due process in the justice system.""",
            metadata={"domain": "colonial", "tags": ["salem", "witchcraft", "massachusetts", "hysteria"], "difficulty": "intermediate", "era": "colonial"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_004",
            corpus_id=self.corpus_id,
            title="The French and Indian War (1754-1763)",
            content="""The French and Indian War, the North American theater of the global Seven Years' War, fundamentally altered the balance of power in the continent and set the stage for American independence.

The conflict began over competing French and British claims to the Ohio Valley. A young George Washington led a Virginia militia force that clashed with French troops in 1754, igniting a war that would span nearly a decade.

Major battles included the British defeat at Fort Duquesne (1755), the fall of Quebec (1759), and the eventual surrender of Montreal (1760). The war showcased both British military might and the importance of colonial militias and Native American alliances.

The Treaty of Paris (1763) ended the war, with France ceding Canada and all territory east of the Mississippi to Britain. However, the war's massive costs led Britain to impose new taxes on the colonies, directly contributing to revolutionary sentiments. The war also trained a generation of American military leaders who would later fight for independence.""",
            metadata={"domain": "colonial", "tags": ["french-indian-war", "seven-years-war", "washington"], "difficulty": "advanced", "era": "colonial"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_005",
            corpus_id=self.corpus_id,
            title="The Stamp Act Crisis (1765)",
            content="""The Stamp Act of 1765 marked a turning point in colonial-British relations, igniting widespread resistance and establishing the principle of "no taxation without representation."

Parliament imposed the Stamp Act to help pay debts from the French and Indian War. The law required colonists to pay a tax on printed materials including newspapers, legal documents, and playing cards. Unlike previous trade duties, this was a direct tax on the colonists.

Colonial response was swift and organized. The Sons of Liberty formed in Boston and spread to other colonies. Stamp distributors were intimidated into resigning. The Stamp Act Congress, meeting in New York, issued a declaration of rights and grievances.

Facing economic pressure from colonial boycotts and British merchant complaints, Parliament repealed the Stamp Act in 1766. However, it simultaneously passed the Declaratory Act, asserting its right to legislate for the colonies "in all cases whatsoever." The crisis established patterns of colonial resistance—boycotts, committees of correspondence, and appeals to natural rights—that would intensify over the next decade.""",
            metadata={"domain": "revolutionary", "tags": ["stamp-act", "taxation", "colonial-resistance"], "difficulty": "intermediate", "era": "pre-revolutionary"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_006",
            corpus_id=self.corpus_id,
            title="The Boston Tea Party (1773)",
            content="""The Boston Tea Party on December 16, 1773, was a pivotal act of defiance against British authority that accelerated the path to revolution.

The Tea Act of 1773 gave the British East India Company a monopoly on tea sales in the colonies. While the act actually lowered tea prices, colonists saw it as another attempt to assert Parliamentary authority and undermine colonial merchants.

On the night of December 16, members of the Sons of Liberty, some disguised as Mohawk Indians, boarded three ships in Boston Harbor. Over the course of three hours, they dumped 342 chests of tea—worth approximately £10,000—into the harbor.

Britain's response was swift and punitive. The Coercive Acts (called the Intolerable Acts by colonists) closed Boston Harbor, revoked Massachusetts' charter, and allowed British officials accused of crimes to be tried in England. These acts united the colonies in opposition and led directly to the First Continental Congress in 1774.""",
            metadata={"domain": "revolutionary", "tags": ["boston-tea-party", "taxation", "rebellion"], "difficulty": "basic", "era": "pre-revolutionary"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_007",
            corpus_id=self.corpus_id,
            title="The Declaration of Independence (1776)",
            content="""The Declaration of Independence, adopted on July 4, 1776, announced the thirteen colonies' separation from Great Britain and articulated the philosophical foundations of American democracy.

Thomas Jefferson, with input from Benjamin Franklin and John Adams, drafted the document. Its preamble contains some of the most influential words in political history: "We hold these truths to be self-evident, that all men are created equal, that they are endowed by their Creator with certain unalienable Rights, that among these are Life, Liberty and the pursuit of Happiness."

The Declaration listed grievances against King George III, justifying revolution as a response to tyranny. It drew on Enlightenment philosophy, particularly John Locke's theories of natural rights and social contract.

The document's ideals have inspired freedom movements worldwide, though the contradiction between its principles and the reality of slavery was apparent even then. Jefferson's original draft included a passage condemning the slave trade, which was removed to secure Southern support. The Declaration remains America's founding creed, its promises still being fulfilled.""",
            metadata={"domain": "revolutionary", "tags": ["declaration", "jefferson", "independence"], "difficulty": "basic", "era": "revolutionary"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_008",
            corpus_id=self.corpus_id,
            title="The Battle of Saratoga (1777)",
            content="""The Battle of Saratoga, fought in September and October 1777, proved to be the turning point of the American Revolution.

British General John Burgoyne led an army south from Canada, planning to split the colonies by controlling the Hudson River Valley. His campaign faced supply difficulties, guerrilla attacks, and the loss of expected support from other British forces.

The American forces, commanded by General Horatio Gates with crucial support from Benedict Arnold, engaged Burgoyne's army in two battles near Saratoga, New York. The first battle at Freeman's Farm on September 19 was tactically inconclusive but weakened the British.

The decisive second battle at Bemis Heights on October 7 saw Arnold's aggressive tactics break the British lines despite his lack of official command. Burgoyne surrendered his entire army of nearly 6,000 men on October 17, 1777.

This victory convinced France to formally ally with the United States, providing crucial military and financial support that would prove decisive in winning independence.""",
            metadata={"domain": "revolutionary", "tags": ["saratoga", "revolution", "france-alliance"], "difficulty": "intermediate", "era": "revolutionary"}
        ))

        # Constitution Era (docs 9-14)
        docs.append(DocumentSpec(
            doc_id="hist_009",
            corpus_id=self.corpus_id,
            title="The Constitutional Convention (1787)",
            content="""The Constitutional Convention, meeting in Philadelphia from May to September 1787, produced the United States Constitution, the world's oldest written national constitution still in use.

Delegates from twelve states (Rhode Island abstaining) gathered to address the weaknesses of the Articles of Confederation. George Washington presided over the convention, while James Madison's detailed notes provide our primary record of the proceedings.

Major compromises shaped the document. The Great Compromise established a bicameral legislature with proportional representation in the House and equal state representation in the Senate. The Three-Fifths Compromise addressed how enslaved people would be counted for representation and taxation.

The Constitution created a federal system with separation of powers among executive, legislative, and judicial branches. The delegates debated intensely over the balance between federal and state power, executive authority, and the protection of individual rights.

The Constitution was signed on September 17, 1787, beginning the ratification process that would conclude with New Hampshire's approval in June 1788.""",
            metadata={"domain": "founding", "tags": ["constitution", "philadelphia", "madison"], "difficulty": "intermediate", "era": "founding"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_010",
            corpus_id=self.corpus_id,
            title="The Federalist Papers (1787-1788)",
            content="""The Federalist Papers, a collection of 85 essays written by Alexander Hamilton, James Madison, and John Jay, stand as the most authoritative interpretation of the Constitution and a masterpiece of political philosophy.

Written under the pseudonym "Publius," these essays were published in New York newspapers to advocate for ratification of the Constitution. Hamilton wrote approximately 51 essays, Madison 29, and Jay 5, with some jointly authored.

Key essays include Federalist No. 10, where Madison argues that a large republic can better control the effects of faction than small democracies. Federalist No. 51 explains the system of checks and balances: "Ambition must be made to counteract ambition."

The papers address concerns about federal power, the structure of government, and the protection of liberty. They remain essential reading for understanding the framers' intentions and are frequently cited in Supreme Court decisions.

The Federalist Papers represent the most sophisticated defense of constitutional government ever written, combining practical political analysis with enduring philosophical insights.""",
            metadata={"domain": "founding", "tags": ["federalist", "hamilton", "madison", "jay"], "difficulty": "advanced", "era": "founding"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_011",
            corpus_id=self.corpus_id,
            title="The Bill of Rights (1791)",
            content="""The Bill of Rights, ratified on December 15, 1791, comprises the first ten amendments to the Constitution and guarantees fundamental freedoms that define American liberty.

Anti-Federalists had opposed ratification without explicit protections for individual rights. James Madison, initially skeptical of the need for a bill of rights, became its chief architect in Congress, drawing from state constitutions and declarations.

The First Amendment protects freedom of religion, speech, press, assembly, and petition. The Second Amendment addresses the right to bear arms. The Fourth through Eighth Amendments establish criminal justice protections including prohibitions against unreasonable searches, self-incrimination, and cruel punishment.

The Ninth Amendment reserves unenumerated rights to the people, while the Tenth Amendment reserves powers not delegated to the federal government to the states or the people.

The Bill of Rights initially applied only to the federal government, but the Fourteenth Amendment (1868) eventually led courts to apply most of these protections to state governments as well through the doctrine of incorporation.""",
            metadata={"domain": "founding", "tags": ["bill-of-rights", "amendments", "madison"], "difficulty": "basic", "era": "founding"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_012",
            corpus_id=self.corpus_id,
            title="The Louisiana Purchase (1803)",
            content="""The Louisiana Purchase of 1803 doubled the size of the United States, adding 828,000 square miles of territory west of the Mississippi River for approximately $15 million.

President Thomas Jefferson faced a constitutional dilemma. He believed in strict construction of the Constitution, which contained no explicit provision for acquiring new territory. Yet the opportunity to purchase Louisiana from Napoleon Bonaparte was too significant to refuse.

Napoleon, facing renewed war with Britain and the failure of his Caribbean empire following the Haitian Revolution, decided to sell the entire Louisiana Territory rather than just New Orleans, which the Americans had originally sought.

The purchase included land that would become all or part of 15 states, stretching from the Gulf of Mexico to the Canadian border. Jefferson commissioned the Lewis and Clark Expedition (1804-1806) to explore the new territory and find a route to the Pacific.

The Louisiana Purchase established the precedent for territorial expansion, raised questions about the constitutional basis for such acquisitions, and dramatically accelerated westward expansion.""",
            metadata={"domain": "expansion", "tags": ["louisiana", "jefferson", "expansion"], "difficulty": "basic", "era": "early-republic"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_013",
            corpus_id=self.corpus_id,
            title="The War of 1812",
            content="""The War of 1812, sometimes called America's "Second War of Independence," pitted the young United States against Great Britain from 1812 to 1815.

The war's causes included British impressment of American sailors, trade restrictions during the Napoleonic Wars, British support for Native American resistance to American expansion, and American desires to annex Canada. War Hawks in Congress, including Henry Clay and John C. Calhoun, pushed for war.

The conflict saw mixed results. American invasions of Canada failed. The British captured and burned Washington, D.C. in August 1814. However, American naval victories on the Great Lakes and successful defense of Baltimore (inspiring "The Star-Spangled Banner") boosted morale.

Andrew Jackson's victory at the Battle of New Orleans on January 8, 1815, made him a national hero, though it occurred after the Treaty of Ghent had been signed ending the war. The treaty essentially restored prewar conditions.

The war fostered American nationalism, ended Native American resistance east of the Mississippi, and established that the United States would defend its sovereignty against European powers.""",
            metadata={"domain": "war", "tags": ["war-of-1812", "britain", "nationalism"], "difficulty": "intermediate", "era": "early-republic"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_014",
            corpus_id=self.corpus_id,
            title="The Monroe Doctrine (1823)",
            content="""The Monroe Doctrine, articulated by President James Monroe in his 1823 annual message to Congress, established fundamental principles of American foreign policy that endured for nearly two centuries.

The doctrine declared that the Western Hemisphere was closed to further European colonization and that the United States would view any European intervention in the Americas as a hostile act. In return, the United States pledged non-interference in European affairs.

Secretary of State John Quincy Adams was the primary architect of the doctrine. It responded to fears that European powers, through the Holy Alliance, might help Spain reclaim its newly independent Latin American colonies.

Britain, with its powerful navy, tacitly supported the doctrine since it served British commercial interests. However, the United States lacked the military power to enforce the doctrine independently for decades.

The Monroe Doctrine evolved over time. Theodore Roosevelt added the "Roosevelt Corollary" in 1904, asserting the right of the United States to intervene in Latin American countries. The doctrine shaped American policy throughout the Cold War and continues to influence hemispheric relations.""",
            metadata={"domain": "foreign-policy", "tags": ["monroe-doctrine", "foreign-policy", "latin-america"], "difficulty": "intermediate", "era": "early-republic"}
        ))

        # Antebellum and Civil War (docs 15-24)
        docs.append(DocumentSpec(
            doc_id="hist_015",
            corpus_id=self.corpus_id,
            title="The Missouri Compromise (1820)",
            content="""The Missouri Compromise of 1820 temporarily resolved the crisis over slavery's expansion into new territories, but it also deepened sectional divisions that would eventually lead to Civil War.

When Missouri applied for statehood as a slave state in 1819, it threatened to upset the balance of power in the Senate, where free and slave states held equal representation. Representative James Tallmadge of New York proposed gradual emancipation in Missouri, igniting fierce debate.

Henry Clay of Kentucky brokered the compromise. Missouri entered as a slave state while Maine, previously part of Massachusetts, entered as a free state, maintaining the balance. More significantly, the compromise drew a line at 36°30' latitude: slavery would be prohibited in Louisiana Purchase territories north of this line, except for Missouri.

Thomas Jefferson famously called the Missouri controversy a "fire bell in the night" that awakened him to the existential threat slavery posed to the Union. The compromise held for three decades but established that slavery's expansion would remain the central political issue in American life.""",
            metadata={"domain": "slavery", "tags": ["missouri-compromise", "slavery", "clay"], "difficulty": "intermediate", "era": "antebellum"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_016",
            corpus_id=self.corpus_id,
            title="The Trail of Tears (1838)",
            content="""The Trail of Tears refers to the forced relocation of approximately 60,000 Native Americans from their ancestral homelands in the southeastern United States to Indian Territory (present-day Oklahoma) during the 1830s.

The Indian Removal Act of 1830, signed by President Andrew Jackson, authorized the federal government to negotiate removal treaties with Native American tribes. The Cherokee, Creek, Chickasaw, Choctaw, and Seminole nations—known as the "Five Civilized Tribes"—faced intense pressure to relocate.

The Cherokee Nation challenged Georgia's attempts to extend state law over their territory. In Worcester v. Georgia (1832), the Supreme Court ruled in the Cherokee's favor, but Jackson reportedly defied the ruling. Ultimately, a small faction of Cherokee signed the Treaty of New Echota in 1835, ceding all Cherokee lands.

The forced march westward occurred primarily in 1838-1839. Poor planning, inadequate supplies, exposure, and disease resulted in an estimated 4,000 Cherokee deaths along the journey. Similar tragedies befell other tribes.

The Trail of Tears stands as one of the most shameful episodes in American history, representing the devastating human cost of westward expansion and the failure to honor treaty obligations.""",
            metadata={"domain": "native-american", "tags": ["trail-of-tears", "cherokee", "jackson", "removal"], "difficulty": "intermediate", "era": "antebellum"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_017",
            corpus_id=self.corpus_id,
            title="The Compromise of 1850",
            content="""The Compromise of 1850 was a series of five bills that temporarily defused sectional tensions over slavery following the Mexican-American War and the acquisition of vast new territories.

The Mexican Cession raised the question of whether slavery would expand into California and the Southwest. Henry Clay, now elderly but still the "Great Compromiser," proposed a comprehensive package. Stephen Douglas of Illinois shepherded individual bills through Congress.

The compromise admitted California as a free state; organized Utah and New Mexico territories with popular sovereignty on slavery; abolished the slave trade (but not slavery) in Washington, D.C.; established a stronger Fugitive Slave Act; and settled the Texas boundary dispute.

The Fugitive Slave Act proved particularly controversial in the North, requiring citizens to assist in capturing escaped slaves and denying accused fugitives jury trials. It galvanized abolitionist sentiment and inspired Harriet Beecher Stowe's Uncle Tom's Cabin (1852).

The compromise bought time but did not resolve the fundamental conflict. Within four years, the Kansas-Nebraska Act would reopen the territorial question with violent consequences.""",
            metadata={"domain": "slavery", "tags": ["compromise-1850", "clay", "douglas", "fugitive-slave"], "difficulty": "advanced", "era": "antebellum"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_018",
            corpus_id=self.corpus_id,
            title="The Dred Scott Decision (1857)",
            content="""The Dred Scott v. Sandford decision of 1857 was perhaps the most consequential and controversial Supreme Court ruling in American history, pushing the nation closer to civil war.

Dred Scott, an enslaved man, sued for his freedom on the grounds that he had lived with his owner in free territories (Illinois and Wisconsin Territory). His case reached the Supreme Court, which saw an opportunity to settle the slavery question definitively.

Chief Justice Roger Taney's majority opinion went far beyond the immediate case. Taney ruled that African Americans, whether free or enslaved, were not citizens and could not sue in federal court. He declared that Congress had no power to prohibit slavery in the territories, effectively invalidating the Missouri Compromise.

The decision outraged the North and energized the Republican Party. Abraham Lincoln debated Stephen Douglas extensively on its implications in 1858. Rather than settling the slavery question, the decision convinced many Northerners that a "slave power conspiracy" controlled the federal government.

The ruling remains a prime example of judicial overreach and a reminder of the Court's capacity for profound error.""",
            metadata={"domain": "slavery", "tags": ["dred-scott", "supreme-court", "taney"], "difficulty": "advanced", "era": "antebellum"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_019",
            corpus_id=self.corpus_id,
            title="John Brown's Raid on Harpers Ferry (1859)",
            content="""John Brown's raid on the federal arsenal at Harpers Ferry, Virginia, on October 16, 1859, was a failed attempt to spark a slave uprising that nonetheless intensified sectional tensions on the eve of the Civil War.

Brown, a radical abolitionist who had participated in violent clashes in "Bleeding Kansas," planned to seize weapons at Harpers Ferry and distribute them to enslaved people in the surrounding area, triggering a widespread rebellion.

With a small band of 21 men, including five African Americans, Brown captured the arsenal. However, no slave uprising materialized. Local militia pinned down Brown's force, and a company of Marines commanded by Colonel Robert E. Lee stormed the engine house where Brown had barricaded himself.

Brown was captured, tried for treason against Virginia, and hanged on December 2, 1859. He became a martyr to abolitionists; Ralph Waldo Emerson called him a "new saint." Southern whites saw the raid as proof of Northern intentions and accelerated preparations for secession.

"John Brown's Body" became a Union marching song, later inspiring "The Battle Hymn of the Republic."""",
            metadata={"domain": "slavery", "tags": ["john-brown", "harpers-ferry", "abolition"], "difficulty": "intermediate", "era": "antebellum"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_020",
            corpus_id=self.corpus_id,
            title="The Election of 1860 and Secession",
            content="""The election of Abraham Lincoln in November 1860 triggered the secession of Southern states and the beginning of the Civil War.

The Democratic Party split along sectional lines. Northern Democrats nominated Stephen Douglas; Southern Democrats chose John Breckinridge. The Constitutional Union Party nominated John Bell. Republicans united behind Lincoln, who opposed slavery's expansion but did not advocate its immediate abolition.

Lincoln won with less than 40% of the popular vote, carrying every free state but none of the slave states. His name did not even appear on ballots in ten Southern states.

South Carolina seceded on December 20, 1860, followed by Mississippi, Florida, Alabama, Georgia, Louisiana, and Texas before Lincoln's inauguration. These states formed the Confederate States of America in February 1861, electing Jefferson Davis as president.

Lincoln's inaugural address sought to reassure the South while firmly opposing secession: "We are not enemies, but friends." However, the attack on Fort Sumter on April 12, 1861, began the bloodiest conflict in American history.""",
            metadata={"domain": "civil-war", "tags": ["lincoln", "secession", "election-1860"], "difficulty": "intermediate", "era": "civil-war"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_021",
            corpus_id=self.corpus_id,
            title="The Battle of Gettysburg (1863)",
            content="""The Battle of Gettysburg, fought July 1-3, 1863, was the bloodiest battle of the Civil War and a turning point that ended Confederate hopes of winning independence through military victory.

General Robert E. Lee led the Army of Northern Virginia into Pennsylvania, seeking to relieve pressure on Virginia, gather supplies, and potentially threaten Northern cities. The Union Army of the Potomac, under General George Meade, intercepted Lee near the small town of Gettysburg.

The first day saw Confederate success as Union forces fell back through the town to defensive positions on Cemetery Hill and Cemetery Ridge. On July 2, fierce fighting at locations like Little Round Top, Devil's Den, and the Wheatfield resulted in thousands of casualties but failed to dislodge the Union line.

On July 3, Lee ordered Pickett's Charge, a frontal assault of 12,500 men across open ground. The attack was devastated by Union artillery and rifle fire. Confederate casualties over three days exceeded 28,000; Union losses were approximately 23,000.

Lee retreated to Virginia. The Confederacy would never again launch a major offensive in the North. Four months later, Lincoln delivered the Gettysburg Address at the dedication of the soldiers' cemetery.""",
            metadata={"domain": "civil-war", "tags": ["gettysburg", "lee", "meade"], "difficulty": "intermediate", "era": "civil-war"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_022",
            corpus_id=self.corpus_id,
            title="The Emancipation Proclamation (1863)",
            content="""The Emancipation Proclamation, issued by President Abraham Lincoln on January 1, 1863, declared that all enslaved people in Confederate-held territory "shall be then, thenceforward, and forever free."

Lincoln had long opposed slavery but initially framed the war as a struggle to preserve the Union rather than end slavery. Military setbacks, pressure from abolitionists and Radical Republicans, and the realization that weakening slavery would weaken the Confederacy led him to change course.

After the Union victory at Antietam in September 1862, Lincoln issued a preliminary proclamation warning that he would free slaves in rebellious states. The final proclamation took effect on New Year's Day 1863.

The proclamation did not free slaves in border states loyal to the Union or in Confederate areas already under Union control. Critics noted these limitations. However, the proclamation transformed the war's purpose, making Union victory synonymous with slavery's destruction.

The proclamation authorized the enlistment of African American soldiers. By war's end, nearly 200,000 Black men served in the Union Army and Navy. The Thirteenth Amendment (1865) completed the work of abolition.""",
            metadata={"domain": "civil-war", "tags": ["emancipation", "lincoln", "slavery"], "difficulty": "basic", "era": "civil-war"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_023",
            corpus_id=self.corpus_id,
            title="Reconstruction and Its End (1865-1877)",
            content="""Reconstruction, the period following the Civil War, represented America's first attempt at interracial democracy, ultimately abandoned in favor of white supremacy.

Following Lincoln's assassination, President Andrew Johnson pursued a lenient policy toward the former Confederacy. Southern states enacted Black Codes restricting African Americans' rights. Radical Republicans in Congress responded with the Civil Rights Act of 1866 and the Fourteenth Amendment, guaranteeing citizenship and equal protection.

The Reconstruction Acts of 1867 divided the South into military districts and required states to ratify the Fourteenth Amendment and guarantee Black male suffrage. The Fifteenth Amendment (1870) prohibited denying the vote based on race.

During Radical Reconstruction, African Americans voted, held office, and built schools and churches. Hiram Revels and Blanche Bruce became the first Black U.S. Senators. However, white terrorist groups like the Ku Klux Klan used violence to suppress Black political participation.

The contested election of 1876 effectively ended Reconstruction. The Compromise of 1877 gave Republican Rutherford Hayes the presidency in exchange for withdrawing federal troops from the South, abandoning Black citizens to decades of Jim Crow segregation and disenfranchisement.""",
            metadata={"domain": "reconstruction", "tags": ["reconstruction", "civil-rights", "jim-crow"], "difficulty": "advanced", "era": "reconstruction"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_024",
            corpus_id=self.corpus_id,
            title="The Assassination of Abraham Lincoln (1865)",
            content="""The assassination of President Abraham Lincoln on April 14, 1865, just five days after Lee's surrender at Appomattox, shocked the nation and shaped the course of Reconstruction.

John Wilkes Booth, a famous actor and Confederate sympathizer, shot Lincoln while he watched the play "Our American Cousin" at Ford's Theatre in Washington, D.C. Booth leaped to the stage shouting "Sic semper tyrannis" (Thus always to tyrants) and escaped on horseback.

Booth had originally planned to kidnap Lincoln and exchange him for Confederate prisoners. As the Confederacy collapsed, he changed his plan to assassination. Conspirators simultaneously attacked Secretary of State William Seward, seriously wounding him, while another conspirator failed to attack Vice President Andrew Johnson.

Lincoln died the following morning at a boarding house across from the theater. Booth was tracked to a Virginia barn and shot dead on April 26. Eight conspirators were tried by military tribunal; four, including Mary Surratt, were hanged.

Lincoln's death transformed him into a martyr for the Union cause. His absence during Reconstruction meant that the task of reunification and Black rights fell to Andrew Johnson, whose hostility to these goals shaped the turbulent years that followed.""",
            metadata={"domain": "civil-war", "tags": ["lincoln", "assassination", "booth"], "difficulty": "basic", "era": "civil-war"}
        ))

        # Gilded Age and Progressive Era (docs 25-30)
        docs.append(DocumentSpec(
            doc_id="hist_025",
            corpus_id=self.corpus_id,
            title="The Transcontinental Railroad (1869)",
            content="""The completion of the First Transcontinental Railroad on May 10, 1869, united the nation physically and accelerated economic development, westward expansion, and the displacement of Native American peoples.

The Pacific Railroad Acts of 1862 and 1864 authorized construction by two companies: the Union Pacific, building westward from Omaha, and the Central Pacific, building eastward from Sacramento. The federal government provided land grants and loans to finance construction.

The Union Pacific employed thousands of Civil War veterans and Irish immigrants. The Central Pacific relied heavily on Chinese workers, who constituted up to 90% of the workforce and performed the most dangerous tasks, including blasting tunnels through the Sierra Nevada.

The two lines met at Promontory Summit, Utah, where Leland Stanford drove the ceremonial golden spike. The journey from coast to coast, previously taking months, could now be completed in days.

The railroad transformed the American economy, enabling the settlement of the Great Plains, the development of the cattle industry, and the exploitation of Western resources. It also facilitated the destruction of the buffalo herds and the confinement of Native Americans to reservations.""",
            metadata={"domain": "industrial", "tags": ["railroad", "transcontinental", "expansion"], "difficulty": "intermediate", "era": "gilded-age"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_026",
            corpus_id=self.corpus_id,
            title="The Gilded Age and Industrial Growth",
            content="""The Gilded Age, a term coined by Mark Twain, describes the period from roughly 1870 to 1900, characterized by rapid industrialization, massive wealth accumulation, political corruption, and growing inequality.

Industrial titans like Andrew Carnegie (steel), John D. Rockefeller (oil), J.P. Morgan (banking), and Cornelius Vanderbilt (railroads) built vast business empires. These "robber barons" or "captains of industry" (depending on perspective) used vertical and horizontal integration to dominate markets.

Technological innovations transformed daily life: Edison's electric light, Bell's telephone, and advances in steel production enabled urban growth and new industries. Immigration from Southern and Eastern Europe provided labor for factories and mines.

However, workers faced long hours, dangerous conditions, and low wages. Labor conflicts erupted, including the Great Railroad Strike of 1877, the Haymarket Affair (1886), and the Homestead Strike (1892). The gap between wealthy industrialists and struggling workers defined the era.

Political machines controlled urban governments while national politics was marked by close elections and modest reform efforts. The era's contradictions—growth alongside inequality, democracy alongside corruption—would fuel the Progressive reforms of the early twentieth century.""",
            metadata={"domain": "industrial", "tags": ["gilded-age", "industrialization", "inequality"], "difficulty": "intermediate", "era": "gilded-age"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_027",
            corpus_id=self.corpus_id,
            title="The Spanish-American War (1898)",
            content="""The Spanish-American War of 1898 marked America's emergence as a global imperial power, resulting in the acquisition of overseas territories and a new role in world affairs.

Tensions with Spain centered on Cuba, where a rebellion against Spanish colonial rule had generated American sympathy. Yellow journalism, led by William Randolph Hearst and Joseph Pulitzer, sensationalized Spanish atrocities. The mysterious explosion of the USS Maine in Havana Harbor on February 15, 1898, killing 266 sailors, provided the catalyst for war.

The war lasted only four months. Commodore George Dewey destroyed the Spanish fleet at Manila Bay in the Philippines. In Cuba, Theodore Roosevelt led his "Rough Riders" in the famous charge up San Juan Hill. Spanish resistance collapsed quickly.

The Treaty of Paris granted the United States control of Puerto Rico, Guam, and the Philippines. Cuba gained nominal independence under American supervision. The U.S. paid Spain $20 million for the Philippines.

The acquisition of the Philippines sparked fierce debate between imperialists and anti-imperialists. Filipino resistance to American rule led to a brutal counterinsurgency war that lasted until 1902, costing far more lives than the Spanish-American War itself.""",
            metadata={"domain": "foreign-policy", "tags": ["spanish-american-war", "imperialism", "philippines"], "difficulty": "intermediate", "era": "gilded-age"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_028",
            corpus_id=self.corpus_id,
            title="Women's Suffrage Movement",
            content="""The women's suffrage movement in the United States spanned over seven decades, culminating in the ratification of the Nineteenth Amendment in 1920, which prohibited denying the vote based on sex.

The movement's roots lay in the abolitionist movement of the 1830s and 1840s. The Seneca Falls Convention of 1848, organized by Elizabeth Cady Stanton and Lucretia Mott, issued the Declaration of Sentiments, proclaiming that "all men and women are created equal."

After the Civil War, the movement split over whether to support the Fifteenth Amendment, which enfranchised Black men but not women. Susan B. Anthony and Stanton formed the National Woman Suffrage Association, while Lucy Stone led the American Woman Suffrage Association. The groups reunited in 1890.

A new generation of leaders, including Carrie Chapman Catt and Alice Paul, employed both traditional lobbying and more militant tactics. Western states granted women's suffrage first; Wyoming Territory in 1869. Paul's National Woman's Party picketed the White House and staged hunger strikes.

World War I accelerated progress. President Wilson endorsed the amendment in 1918. The Nineteenth Amendment was ratified on August 18, 1920, though many Black women in the South remained disenfranchised by other means until the Voting Rights Act of 1965.""",
            metadata={"domain": "civil-rights", "tags": ["suffrage", "women", "nineteenth-amendment"], "difficulty": "intermediate", "era": "progressive"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_029",
            corpus_id=self.corpus_id,
            title="Theodore Roosevelt and Progressive Reform",
            content="""Theodore Roosevelt's presidency (1901-1909) ushered in the Progressive Era, an age of reform that sought to address the problems of industrialization through government action.

Roosevelt became president after William McKinley's assassination. Though a Republican, he challenged the power of large corporations, earning the nickname "trustbuster" for his antitrust actions against the Northern Securities Company and other monopolies.

The Pure Food and Drug Act and Meat Inspection Act of 1906 responded to muckraking journalism exposing unsafe practices in food production. Upton Sinclair's novel "The Jungle," depicting horrific conditions in meatpacking plants, catalyzed these reforms.

Roosevelt championed conservation, setting aside millions of acres as national forests, parks, and monuments. He mediated the 1902 coal strike, marking unprecedented federal intervention in labor disputes. His "Square Deal" promised fair treatment for workers, consumers, and businesses alike.

In foreign policy, Roosevelt's motto was "speak softly and carry a big stick." He oversaw the construction of the Panama Canal and issued the Roosevelt Corollary to the Monroe Doctrine. He won the Nobel Peace Prize for mediating the end of the Russo-Japanese War.""",
            metadata={"domain": "progressive", "tags": ["roosevelt", "progressive", "reform", "conservation"], "difficulty": "intermediate", "era": "progressive"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_030",
            corpus_id=self.corpus_id,
            title="World War I and American Involvement",
            content="""American involvement in World War I (1917-1918) marked a decisive shift in the nation's role in world affairs, though the subsequent rejection of the League of Nations reflected continued isolationist sentiment.

When war erupted in Europe in August 1914, President Woodrow Wilson declared American neutrality. However, economic ties to Britain and France, German submarine warfare, and the Zimmermann Telegram (proposing a German-Mexican alliance) pushed the nation toward intervention.

The U.S. declared war on Germany on April 6, 1917. The American Expeditionary Forces, commanded by General John Pershing, arrived in France that summer. By 1918, two million American soldiers were in Europe, providing crucial reinforcement as Allied forces launched their final offensive.

The armistice on November 11, 1918, ended the fighting. Wilson's Fourteen Points proposed a peace based on national self-determination, open diplomacy, and a League of Nations. However, the Treaty of Versailles included harsh terms for Germany that Wilson reluctantly accepted.

The Senate rejected the treaty and League of Nations membership, reflecting concerns about entangling alliances and restrictions on American sovereignty. America returned to its traditional isolation, a posture that would endure until Pearl Harbor.""",
            metadata={"domain": "war", "tags": ["world-war-i", "wilson", "league-of-nations"], "difficulty": "intermediate", "era": "progressive"}
        ))

        # Depression and WWII (docs 31-38)
        docs.append(DocumentSpec(
            doc_id="hist_031",
            corpus_id=self.corpus_id,
            title="The Roaring Twenties",
            content="""The 1920s, known as the "Roaring Twenties" or the "Jazz Age," was an era of cultural dynamism, economic prosperity, and social change that transformed American life.

The decade saw the rise of consumer culture, fueled by new technologies like automobiles, radios, and electrical appliances. Henry Ford's assembly line made cars affordable to the middle class, while advertising and installment buying encouraged consumption.

Cultural changes challenged traditional norms. Flappers—young women with bobbed hair, short skirts, and independent attitudes—symbolized new freedoms. Jazz music, originating in African American communities, gained mainstream popularity. The Harlem Renaissance celebrated Black culture and produced writers like Langston Hughes and Zora Neale Hurston.

However, the era also saw reactionary movements. Prohibition (1920-1933) banned alcohol but spawned organized crime. The Ku Klux Klan experienced a resurgence, targeting not only African Americans but also Catholics, Jews, and immigrants. Immigration restriction acts in 1921 and 1924 severely limited newcomers.

The decade's prosperity was built on shaky foundations. Agricultural prices remained depressed. Wealth was concentrated at the top. Stock market speculation soared. These imbalances would culminate in the crash of 1929.""",
            metadata={"domain": "social", "tags": ["1920s", "jazz-age", "prohibition"], "difficulty": "intermediate", "era": "interwar"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_032",
            corpus_id=self.corpus_id,
            title="The Great Depression: Causes and Effects",
            content="""The Great Depression, beginning with the stock market crash of October 1929 and lasting through the 1930s, was the most severe economic crisis in American history.

Multiple factors caused the Depression: overproduction in agriculture and industry, unequal income distribution, excessive stock speculation, weak banking systems, and international economic instability following World War I. The Federal Reserve's tight monetary policy worsened the crisis.

By 1933, unemployment reached 25%. Banks failed by the thousands, wiping out savings. Industrial production fell by nearly half. Farmers faced foreclosure as crop prices collapsed. Breadlines and Hoovervilles (shantytowns named after President Herbert Hoover) became symbols of the era.

The human toll was immense. Families lost homes and savings. Malnutrition increased. Birth rates fell. Migration, most famously of "Okies" fleeing the Dust Bowl for California, disrupted communities. Psychological effects—shame, anxiety, loss of hope—scarred a generation.

Hoover's response, though more active than often remembered, proved insufficient. His belief in voluntary cooperation and limited government action gave way to Franklin Roosevelt's aggressive New Deal.""",
            metadata={"domain": "economic", "tags": ["great-depression", "economy", "crash"], "difficulty": "intermediate", "era": "depression"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_033",
            corpus_id=self.corpus_id,
            title="The New Deal",
            content="""The New Deal, President Franklin D. Roosevelt's response to the Great Depression, represented the most significant expansion of federal government activity in American history.

Roosevelt took office in March 1933 promising a "new deal for the American people." The first hundred days saw an unprecedented flurry of legislation: the Emergency Banking Act stabilized banks; the Civilian Conservation Corps employed young men in conservation work; the Agricultural Adjustment Act supported farm prices; the National Industrial Recovery Act regulated business.

The "Second New Deal" (1935-1936) included landmark measures: Social Security provided old-age pensions and unemployment insurance; the Wagner Act guaranteed workers' right to organize unions; the Works Progress Administration employed millions in public works projects, including artists and writers.

The New Deal faced criticism from both left and right. Conservatives attacked it as socialistic; radicals like Huey Long demanded more redistribution. The Supreme Court struck down several programs, prompting Roosevelt's controversial "court-packing" plan.

While the New Deal did not end the Depression—World War II did—it created the modern welfare state, established the principle of federal responsibility for economic welfare, and forged a political coalition that dominated American politics for decades.""",
            metadata={"domain": "economic", "tags": ["new-deal", "fdr", "social-security"], "difficulty": "intermediate", "era": "depression"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_034",
            corpus_id=self.corpus_id,
            title="Pearl Harbor and American Entry into World War II",
            content="""The Japanese attack on Pearl Harbor on December 7, 1941—"a date which will live in infamy," in Roosevelt's words—brought the United States into World War II.

As war consumed Europe and Asia in the late 1930s, Americans debated whether to intervene. The Neutrality Acts reflected isolationist sentiment, but Roosevelt gradually assisted Britain through measures like Lend-Lease. Tensions with Japan grew over its expansion in Asia and the American oil embargo.

On Sunday morning, December 7, Japanese aircraft attacked the U.S. naval base at Pearl Harbor, Hawaii, without warning. The assault killed 2,403 Americans and destroyed or damaged 21 ships and 323 aircraft. The battleship USS Arizona alone lost 1,177 crew members.

Congress declared war on Japan on December 8, with only one dissenting vote. Germany and Italy declared war on the United States on December 11. America was now fighting on two fronts.

The attack united a divided nation. Industrial mobilization transformed the economy, ending the Depression. Women entered the workforce in unprecedented numbers. Japanese Americans faced unjust internment. The war would cost over 400,000 American lives but end with victory and global preeminence.""",
            metadata={"domain": "war", "tags": ["pearl-harbor", "world-war-ii", "japan"], "difficulty": "basic", "era": "world-war-ii"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_035",
            corpus_id=self.corpus_id,
            title="D-Day and the Liberation of Europe",
            content="""D-Day, June 6, 1944, was the largest amphibious invasion in history, marking the beginning of the liberation of Nazi-occupied Western Europe.

Operation Overlord, planned for over two years, aimed to establish a beachhead in Normandy, France. Supreme Allied Commander Dwight D. Eisenhower led forces from the United States, Britain, Canada, and other nations. Elaborate deception operations convinced the Germans that the main attack would come at Calais.

On D-Day, approximately 156,000 Allied troops landed by sea and air across five beaches: Utah, Omaha, Gold, Juno, and Sword. The fiercest resistance came at Omaha Beach, where American forces suffered heavy casualties. By day's end, all beachheads were secured, though casualties exceeded 10,000, with over 4,000 killed.

The Normandy campaign continued for two months. Paris was liberated on August 25, 1944. Allied forces pushed into Germany, facing a German counteroffensive in the Battle of the Bulge (December 1944-January 1945).

Germany surrendered unconditionally on May 8, 1945—V-E Day. The liberation of concentration camps revealed the full horror of the Holocaust. D-Day remains a symbol of Allied unity, sacrifice, and the triumph over fascism.""",
            metadata={"domain": "war", "tags": ["d-day", "normandy", "world-war-ii"], "difficulty": "intermediate", "era": "world-war-ii"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_036",
            corpus_id=self.corpus_id,
            title="The Atomic Bomb and Japan's Surrender",
            content="""The atomic bombings of Hiroshima and Nagasaki in August 1945 ended World War II and ushered in the nuclear age, raising profound ethical questions that persist today.

The Manhattan Project, a secret $2 billion effort, developed the atomic bomb. Physicist J. Robert Oppenheimer led the Los Alamos laboratory where the bomb was designed and built. The first successful test occurred at Trinity Site, New Mexico, on July 16, 1945.

President Harry Truman, who had assumed office after Roosevelt's death in April, authorized the bomb's use against Japan. On August 6, the B-29 "Enola Gay" dropped a uranium bomb on Hiroshima, killing approximately 80,000 people instantly; tens of thousands more died later from radiation. On August 9, a plutonium bomb destroyed Nagasaki, killing approximately 40,000 immediately.

Japan announced its surrender on August 15 (V-J Day) and formally surrendered on September 2 aboard the USS Missouri. Truman and supporters argued the bombs saved lives by avoiding a costly invasion of Japan. Critics contend Japan was near surrender and that racial animosity influenced the decision.

The bombings began the Cold War nuclear arms race and established the terrible precedent of nuclear warfare. They remain the only wartime uses of atomic weapons.""",
            metadata={"domain": "war", "tags": ["atomic-bomb", "hiroshima", "nagasaki"], "difficulty": "intermediate", "era": "world-war-ii"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_037",
            corpus_id=self.corpus_id,
            title="The Cold War Begins",
            content="""The Cold War, the ideological and geopolitical struggle between the United States and the Soviet Union, shaped international relations and American domestic politics for over four decades.

Wartime cooperation dissolved as the Soviet Union imposed communist regimes in Eastern Europe. Winston Churchill's 1946 speech described an "iron curtain" dividing the continent. The Truman Doctrine (1947) committed the U.S. to containing Soviet expansion, while the Marshall Plan (1948) provided massive economic aid to rebuild Western Europe.

In 1949, the Soviet Union detonated its first atomic bomb, ending the American nuclear monopoly. Communist victory in China that same year intensified fears. Senator Joseph McCarthy's anti-communist crusade ruined lives and careers based on dubious accusations.

The Cold War turned hot in Korea (1950-1953), where U.S. forces led a UN coalition against communist North Korea and Chinese intervention. The armistice left Korea divided, as it remains today.

The nuclear arms race accelerated with the development of hydrogen bombs. The doctrine of mutual assured destruction (MAD) created a terrifying balance. Proxy conflicts, espionage, and competition for influence in the developing world characterized the rivalry that would not end until the Soviet Union's collapse in 1991.""",
            metadata={"domain": "cold-war", "tags": ["cold-war", "containment", "truman-doctrine"], "difficulty": "intermediate", "era": "cold-war"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_038",
            corpus_id=self.corpus_id,
            title="The Civil Rights Movement",
            content="""The Civil Rights Movement of the 1950s and 1960s transformed American society, dismantling legal segregation and advancing African American equality through nonviolent protest and legal action.

The movement built on decades of activism. The Supreme Court's Brown v. Board of Education decision (1954) declared school segregation unconstitutional, overturning Plessy v. Ferguson (1896). Rosa Parks's refusal to give up her bus seat sparked the Montgomery Bus Boycott (1955-1956), bringing Martin Luther King Jr. to prominence.

Key events included the Little Rock Nine's integration of an Arkansas high school (1957), sit-ins at segregated lunch counters (1960), the Freedom Rides challenging segregated interstate travel (1961), and the Birmingham Campaign (1963), where police violence against peaceful protesters shocked the nation.

The March on Washington (August 1963) brought 250,000 people to hear King's "I Have a Dream" speech. The Civil Rights Act of 1964 outlawed discrimination in public accommodations and employment. The Voting Rights Act of 1965 eliminated barriers to Black voting in the South.

The movement faced violence: the bombing of Birmingham's 16th Street Baptist Church killed four girls; Medgar Evers, Malcolm X, and Martin Luther King Jr. were assassinated. Yet it achieved fundamental change, inspiring subsequent movements for women's rights, LGBTQ+ rights, and disability rights.""",
            metadata={"domain": "civil-rights", "tags": ["civil-rights", "king", "desegregation"], "difficulty": "basic", "era": "civil-rights"}
        ))

        # Vietnam and Modern Era (docs 39-50)
        docs.append(DocumentSpec(
            doc_id="hist_039",
            corpus_id=self.corpus_id,
            title="The Vietnam War",
            content="""The Vietnam War (1955-1975) was America's longest and most divisive conflict of the twentieth century, claiming over 58,000 American lives and fundamentally reshaping the nation's politics and culture.

American involvement escalated gradually. Following French defeat at Dien Bien Phu (1954), the U.S. supported South Vietnam against communist North Vietnam and the Viet Cong insurgency. The Gulf of Tonkin Resolution (1964) gave President Johnson broad authority to expand the war.

By 1968, over 500,000 American troops were in Vietnam. Despite superior firepower, the U.S. struggled against guerrilla tactics and faced a determined enemy. The Tet Offensive (January 1968), though a military defeat for the communists, shattered American confidence that victory was near.

Opposition to the war grew, especially among young people. Protests escalated, from teach-ins to massive marches. The draft became a flashpoint. Kent State shootings (1970), where National Guard troops killed four student protesters, further polarized the nation.

President Nixon pursued "Vietnamization," gradually withdrawing American troops while seeking a negotiated settlement. The Paris Peace Accords (1973) ended American involvement. South Vietnam fell to communist forces in April 1975. The war left lasting scars on American society and foreign policy.""",
            metadata={"domain": "war", "tags": ["vietnam", "cold-war", "protest"], "difficulty": "intermediate", "era": "vietnam"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_040",
            corpus_id=self.corpus_id,
            title="The Watergate Scandal",
            content="""The Watergate scandal (1972-1974) led to the resignation of President Richard Nixon and remains the benchmark for political corruption and abuse of power in American history.

The scandal began with the June 17, 1972 break-in at Democratic National Committee headquarters in the Watergate complex in Washington, D.C. Five men, connected to Nixon's reelection campaign, were caught attempting to bug the offices.

Initially dismissed as a "third-rate burglary," investigative reporting by Washington Post journalists Bob Woodward and Carl Bernstein, aided by the anonymous source "Deep Throat" (later revealed as FBI official Mark Felt), uncovered a wider pattern of political espionage and sabotage.

Senate hearings in 1973 revealed the existence of a White House taping system. Nixon's resistance to releasing the tapes prompted the "Saturday Night Massacre," in which he fired the special prosecutor and key Justice Department officials resigned in protest. The Supreme Court unanimously ordered the tapes released.

The tapes revealed Nixon's direct involvement in the cover-up. The House Judiciary Committee approved articles of impeachment for obstruction of justice, abuse of power, and contempt of Congress. Nixon resigned on August 9, 1974. President Gerald Ford's subsequent pardon of Nixon proved deeply controversial.""",
            metadata={"domain": "political", "tags": ["watergate", "nixon", "impeachment"], "difficulty": "intermediate", "era": "modern"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_041",
            corpus_id=self.corpus_id,
            title="The Reagan Revolution",
            content="""The election of Ronald Reagan in 1980 marked a conservative resurgence that reshaped American politics, economics, and the nation's role in the world.

Reagan, a former actor and California governor, defeated incumbent Jimmy Carter amid economic malaise—high inflation, unemployment, and interest rates—and the Iranian hostage crisis. His sunny optimism contrasted with Carter's talk of national "malaise."

Reaganomics, or supply-side economics, promised that tax cuts for businesses and wealthy individuals would stimulate economic growth benefiting all Americans. The Economic Recovery Tax Act of 1981 cut the top marginal tax rate from 70% to 50%, later reduced to 28%. Deregulation accompanied tax cuts.

The economy recovered from recession, though critics noted that benefits flowed disproportionately to the wealthy and that deficits exploded. Union power declined after Reagan fired striking air traffic controllers in 1981.

In foreign policy, Reagan pursued a confrontational stance toward the Soviet Union, calling it an "evil empire" and dramatically increasing military spending. His relationship with Soviet leader Mikhail Gorbachev eventually contributed to Cold War's end. The Reagan era established conservative dominance in American politics that persisted for decades.""",
            metadata={"domain": "political", "tags": ["reagan", "conservatism", "economics"], "difficulty": "intermediate", "era": "modern"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_042",
            corpus_id=self.corpus_id,
            title="The End of the Cold War",
            content="""The end of the Cold War (1989-1991) was one of history's most remarkable peaceful transformations, as the Soviet bloc collapsed and the ideological struggle that defined the postwar era came to a close.

Soviet leader Mikhail Gorbachev's reforms—glasnost (openness) and perestroika (restructuring)—loosened Communist Party control. His refusal to use force to maintain Soviet dominance in Eastern Europe proved decisive.

In 1989, popular movements swept Eastern Europe. Poland held free elections; Hungary opened its border with Austria; the Berlin Wall fell on November 9, 1989. Czechoslovakia's "Velvet Revolution" and Romania's violent overthrow of its dictator followed.

Germany reunified in October 1990. The Warsaw Pact dissolved. Within the Soviet Union itself, nationalist movements demanded independence. A failed coup against Gorbachev in August 1991 accelerated collapse.

On December 25, 1991, Gorbachev resigned as the Soviet Union formally dissolved into fifteen independent republics. The United States stood as the world's sole superpower. President George H.W. Bush declared a "new world order" based on collective security and democracy.

The Cold War's end brought hope but also new challenges: ethnic conflicts, nuclear proliferation concerns, and questions about America's role in a transformed world.""",
            metadata={"domain": "cold-war", "tags": ["cold-war", "soviet-union", "berlin-wall"], "difficulty": "intermediate", "era": "modern"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_043",
            corpus_id=self.corpus_id,
            title="September 11, 2001 and the War on Terror",
            content="""The terrorist attacks of September 11, 2001, were the deadliest in American history, killing nearly 3,000 people and launching the nation into a global "War on Terror" with profound consequences.

On the morning of September 11, 19 hijackers from the al-Qaeda terrorist network seized four commercial airplanes. Two planes struck the Twin Towers of the World Trade Center in New York City, causing both to collapse. A third hit the Pentagon. The fourth, United Flight 93, crashed in Pennsylvania after passengers fought the hijackers.

President George W. Bush declared war on terrorism and demanded Afghanistan's Taliban government surrender al-Qaeda leader Osama bin Laden. When they refused, U.S. forces invaded in October 2001, quickly toppling the Taliban.

In March 2003, the U.S. invaded Iraq, claiming Saddam Hussein possessed weapons of mass destruction and had ties to al-Qaeda. No such weapons were found. Both wars became prolonged counterinsurgency conflicts.

The USA PATRIOT Act expanded government surveillance powers, raising civil liberties concerns. "Enhanced interrogation techniques" and the Guantánamo Bay detention camp sparked controversy. The attacks and their aftermath reshaped American foreign policy, domestic security, and the nation's psyche.""",
            metadata={"domain": "modern", "tags": ["9/11", "terrorism", "afghanistan", "iraq"], "difficulty": "intermediate", "era": "modern"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_044",
            corpus_id=self.corpus_id,
            title="The 2008 Financial Crisis",
            content="""The financial crisis of 2008 was the worst economic disaster since the Great Depression, triggering a severe recession, massive government intervention, and lasting political consequences.

The crisis originated in the housing market. Banks had issued risky subprime mortgages and bundled them into complex securities. When housing prices fell and borrowers defaulted, these securities became toxic, threatening the entire financial system.

In September 2008, the investment bank Lehman Brothers collapsed—the largest bankruptcy in American history. Insurance giant AIG required a $182 billion government rescue. Credit markets froze; stock markets plummeted.

Congress passed the $700 billion Troubled Asset Relief Program (TARP) to stabilize banks, though the bailouts proved deeply unpopular. The Federal Reserve took unprecedented actions to inject liquidity into the economy.

The recession officially lasted from December 2007 to June 2009, but its effects lingered for years. Unemployment peaked at 10%. Millions lost homes to foreclosure. Household wealth declined by trillions.

The crisis fueled political polarization. On the left, the Occupy Wall Street movement protested inequality and bank bailouts. On the right, the Tea Party movement opposed government spending and intervention. Trust in institutions declined.""",
            metadata={"domain": "economic", "tags": ["financial-crisis", "recession", "bailout"], "difficulty": "intermediate", "era": "modern"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_045",
            corpus_id=self.corpus_id,
            title="The Election of Barack Obama",
            content="""The election of Barack Obama as the 44th president in 2008 was a historic milestone, making him the first African American to hold the nation's highest office.

Obama, a first-term senator from Illinois, built his campaign on themes of hope and change. His opposition to the Iraq War and inspiring oratory attracted enthusiastic supporters, especially young voters. He defeated Hillary Clinton in a closely contested Democratic primary.

The financial crisis dominated the final weeks of the campaign. Obama's calm response contrasted with Republican John McCain's dramatic suspension of his campaign. Obama won decisively, with 53% of the popular vote and 365 electoral votes.

His inauguration on January 20, 2009, drew nearly two million people to the National Mall. For many, the moment represented the fulfillment of civil rights movement dreams, though some cautioned that racism remained a powerful force.

Obama's presidency saw significant achievements—the Affordable Care Act, economic recovery from the Great Recession, the killing of Osama bin Laden—but also intense partisan opposition. The Tea Party movement energized conservative resistance. Debates over Obama's presidency reflected deeper divisions over race, government's role, and American identity.""",
            metadata={"domain": "political", "tags": ["obama", "election", "milestone"], "difficulty": "basic", "era": "modern"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_046",
            corpus_id=self.corpus_id,
            title="The Rise of Social Media and Digital Culture",
            content="""The rise of social media in the 2000s and 2010s transformed American communication, politics, commerce, and social life in ways still being understood.

Facebook (2004), Twitter (2006), and Instagram (2010) created new platforms for connection and expression. By 2020, over 70% of Americans used social media. Smartphones made constant connectivity possible, fundamentally changing daily routines.

Social media enabled new forms of political mobilization. The Arab Spring, Black Lives Matter, and the Tea Party movement all leveraged these platforms. The 2008 and subsequent elections saw campaigns master social media organizing and advertising.

However, concerns mounted. Algorithms promoted engagement over accuracy, spreading misinformation and conspiracy theories. Russian interference in the 2016 election exploited social media. Polarization intensified as users inhabited echo chambers.

Mental health effects, especially among young people, drew attention. Cyberbullying, comparison culture, and addiction to engagement became subjects of research and concern. Debates over content moderation, free speech, and platform power intensified.

The technology giants—Facebook, Google, Amazon, Apple—became among the world's most valuable companies, raising questions about monopoly power, data privacy, and regulation. The digital transformation continues to reshape American life.""",
            metadata={"domain": "social", "tags": ["social-media", "technology", "digital"], "difficulty": "intermediate", "era": "modern"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_047",
            corpus_id=self.corpus_id,
            title="Marriage Equality and LGBTQ+ Rights",
            content="""The movement for LGBTQ+ rights achieved historic victories in the 2000s and 2010s, culminating in nationwide marriage equality and broader acceptance, though challenges remain.

For decades, LGBTQ+ Americans faced discrimination, criminalization, and violence. The Stonewall Riots of 1969 in New York City catalyzed the modern gay rights movement. The AIDS crisis of the 1980s devastated the community but also galvanized activism.

The Defense of Marriage Act (1996) defined marriage as between a man and woman for federal purposes. However, Massachusetts became the first state to legalize same-sex marriage in 2004. The movement grew, with court decisions and state legislation gradually expanding marriage rights.

Public opinion shifted dramatically. In 2004, 60% of Americans opposed same-sex marriage; by 2015, 60% supported it. On June 26, 2015, the Supreme Court's Obergefell v. Hodges decision legalized same-sex marriage nationwide, ruling that the Constitution guarantees this right.

Progress extended beyond marriage. The repeal of "Don't Ask, Don't Tell" (2011) allowed LGBTQ+ individuals to serve openly in the military. Transgender visibility increased, though discrimination and violence against transgender individuals remained significant concerns. Debates over religious liberty exemptions, bathroom access, and healthcare continued.""",
            metadata={"domain": "civil-rights", "tags": ["lgbtq", "marriage-equality", "civil-rights"], "difficulty": "intermediate", "era": "modern"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_048",
            corpus_id=self.corpus_id,
            title="The COVID-19 Pandemic in America",
            content="""The COVID-19 pandemic, beginning in early 2020, was the most severe public health crisis in a century, killing over one million Americans and transforming nearly every aspect of life.

The coronavirus emerged in Wuhan, China, in late 2019 and spread globally. The first confirmed U.S. case came on January 20, 2020. By March, cities and states were implementing lockdowns as cases surged.

The pandemic exposed deep inequalities. African Americans, Latinos, and Native Americans died at disproportionately high rates. Essential workers faced risks while professionals worked from home. Schools closed, disrupting education especially for disadvantaged students.

Economic effects were severe. Unemployment spiked to 14.7% in April 2020. Congress passed trillions in relief spending, including direct payments to individuals, enhanced unemployment benefits, and business loans.

Vaccines, developed with unprecedented speed, became available in December 2020. However, vaccine hesitancy and misinformation hindered efforts to reach herd immunity. Debates over masks, lockdowns, and mandates became intensely politicized, reflecting broader divisions.

The pandemic accelerated existing trends: remote work, e-commerce, telemedicine. It also exposed vulnerabilities in public health infrastructure, supply chains, and social safety nets, prompting calls for reform.""",
            metadata={"domain": "modern", "tags": ["covid-19", "pandemic", "public-health"], "difficulty": "basic", "era": "modern"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_049",
            corpus_id=self.corpus_id,
            title="Racial Justice Movements: From Ferguson to Floyd",
            content="""The movement for racial justice gained new urgency in the 2010s and 2020s, as high-profile killings of African Americans by police sparked protests and demands for systemic change.

The shooting of Michael Brown by a police officer in Ferguson, Missouri, in August 2014, ignited protests and drew attention to police violence against Black Americans. The Black Lives Matter movement, founded in 2013 after Trayvon Martin's killing, became a powerful force.

Subsequent killings—of Tamir Rice, Eric Garner, Philando Castile, Breonna Taylor, and many others—sustained the movement. Each incident became a flashpoint, with protests, debates over police reform, and contested narratives.

The murder of George Floyd by Minneapolis police officer Derek Chauvin on May 25, 2020, recorded on video, sparked the largest protests in American history. Demonstrations occurred in all 50 states and internationally. Calls to "defund the police" and invest in communities became central demands.

The movement achieved some victories: Chauvin's conviction, the removal of Confederate monuments, corporate commitments to diversity. However, comprehensive police reform stalled in Congress. Debates over systemic racism, critical race theory, and American history intensified, reflecting fundamental disagreements about the nation's past and future.""",
            metadata={"domain": "civil-rights", "tags": ["blm", "racial-justice", "police-reform"], "difficulty": "intermediate", "era": "modern"}
        ))

        docs.append(DocumentSpec(
            doc_id="hist_050",
            corpus_id=self.corpus_id,
            title="January 6, 2021: Attack on the Capitol",
            content="""The attack on the United States Capitol on January 6, 2021, was an unprecedented assault on American democracy, as supporters of President Donald Trump stormed the building to disrupt the certification of the 2020 presidential election.

Trump had spent months claiming without evidence that the election was stolen from him. On January 6, as Congress met to certify Joe Biden's Electoral College victory, Trump addressed supporters near the White House, urging them to "fight like hell."

A mob of thousands marched to the Capitol and breached security barriers. Rioters broke windows, occupied the Senate chamber, and ransacked offices. Members of Congress were evacuated or sheltered in place. Vice President Mike Pence, who was presiding over certification, was among those evacuated. Five people died in connection with the attack.

Congress reconvened that evening and completed certification early on January 7. Trump was impeached by the House for "incitement of insurrection" but acquitted by the Senate. Hundreds of participants have faced criminal charges.

The January 6 Select Committee conducted extensive investigations, holding public hearings in 2022. The attack raised profound questions about democratic stability, political violence, and the peaceful transfer of power that had defined American government for over two centuries.""",
            metadata={"domain": "political", "tags": ["january-6", "capitol", "democracy"], "difficulty": "intermediate", "era": "modern"}
        ))

        return docs
