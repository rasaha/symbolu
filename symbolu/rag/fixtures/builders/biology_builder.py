"""
Biology & Medicine Corpus Builder
==================================

Generates 50 documents covering biology from cellular to ecosystem level,
including genetics, human anatomy, evolution, and medical topics.
"""

from typing import List
from .base import CorpusBuilder, DocumentSpec


class BiologyCorpusBuilder(CorpusBuilder):
    """Builder for Biology & Medicine corpus."""

    @property
    def corpus_id(self) -> str:
        return "biology"

    @property
    def description(self) -> str:
        return "Biology and Medicine from cellular to ecosystem level"

    @property
    def domain(self) -> str:
        return "biology"

    def build_documents(self) -> List[DocumentSpec]:
        docs = []

        # Cell Biology (docs 1-8)
        docs.append(DocumentSpec(
            doc_id="bio_001",
            corpus_id=self.corpus_id,
            title="The Cell: Basic Unit of Life",
            content="""The cell is the fundamental unit of life, the smallest structure capable of performing all the functions necessary for living. All organisms, from single-celled bacteria to complex multicellular humans, are composed of cells.

Cells were first discovered by Robert Hooke in 1665 when he observed cork tissue under a microscope. The cell theory, developed in the 1830s by Matthias Schleiden and Theodor Schwann, established that all living things are made of cells, cells are the basic units of structure and function, and all cells come from pre-existing cells.

Cells are broadly divided into two categories: prokaryotic and eukaryotic. Prokaryotic cells, found in bacteria and archaea, lack a membrane-bound nucleus and organelles. Eukaryotic cells, found in plants, animals, fungi, and protists, contain a nucleus and specialized organelles that compartmentalize cellular functions.

Despite their diversity, all cells share common features: a plasma membrane that regulates what enters and exits, genetic material (DNA) that stores hereditary information, ribosomes for protein synthesis, and cytoplasm where metabolic reactions occur.""",
            metadata={"domain": "cellular", "tags": ["cell", "cell-theory", "prokaryote", "eukaryote"], "difficulty": "basic", "focus": "cell-biology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_002",
            corpus_id=self.corpus_id,
            title="Cell Membrane Structure and Function",
            content="""The cell membrane, also called the plasma membrane, is a selectively permeable barrier that surrounds all cells. Its structure follows the fluid mosaic model proposed by Singer and Nicolson in 1972.

The membrane consists of a phospholipid bilayer, with hydrophilic (water-loving) heads facing outward and hydrophobic (water-fearing) tails facing inward. This arrangement creates a stable barrier that prevents most water-soluble molecules from freely crossing.

Embedded within this lipid bilayer are various proteins. Integral proteins span the entire membrane and often serve as channels or transporters. Peripheral proteins attach to the membrane surface and typically function in cell signaling or structural support. Cholesterol molecules interspersed among phospholipids help maintain membrane fluidity.

The membrane performs crucial functions: it maintains cell integrity, controls the passage of substances through passive diffusion, facilitated diffusion, and active transport, enables cell communication through receptors, and provides attachment points for the cytoskeleton. Glycoproteins and glycolipids on the outer surface form the glycocalyx, which aids in cell recognition and immune function.""",
            metadata={"domain": "cellular", "tags": ["membrane", "phospholipid", "transport", "fluid-mosaic"], "difficulty": "intermediate", "focus": "cell-biology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_003",
            corpus_id=self.corpus_id,
            title="Mitochondria: The Powerhouse of the Cell",
            content="""Mitochondria are membrane-bound organelles found in nearly all eukaryotic cells, often called the "powerhouse of the cell" because they generate most of the cell's supply of adenosine triphosphate (ATP), the primary energy currency.

Mitochondria have a distinctive double-membrane structure. The outer membrane is smooth and permeable to small molecules. The inner membrane is highly folded into structures called cristae, which increase surface area for ATP production. The space between the membranes is the intermembrane space, while the interior is called the matrix.

Cellular respiration occurs in mitochondria through three main stages: glycolysis (in the cytoplasm), the citric acid cycle (Krebs cycle) in the matrix, and oxidative phosphorylation on the inner membrane. Through these processes, one glucose molecule can yield approximately 36-38 ATP molecules.

Remarkably, mitochondria contain their own circular DNA and ribosomes, evidence supporting the endosymbiotic theory that they evolved from ancient bacteria engulfed by ancestral eukaryotic cells. Mitochondria are inherited maternally and mutations in mitochondrial DNA can cause various diseases affecting high-energy organs like muscles and the brain.""",
            metadata={"domain": "cellular", "tags": ["mitochondria", "atp", "respiration", "endosymbiosis"], "difficulty": "intermediate", "focus": "cell-biology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_004",
            corpus_id=self.corpus_id,
            title="The Nucleus: Control Center of the Cell",
            content="""The nucleus is the largest organelle in eukaryotic cells, serving as the control center that houses genetic material and coordinates cellular activities including growth, metabolism, protein synthesis, and reproduction.

The nucleus is bounded by a double membrane called the nuclear envelope, which contains nuclear pores that regulate the transport of molecules between the nucleus and cytoplasm. Inside, the nucleoplasm contains chromatin—DNA wrapped around histone proteins—which condenses into visible chromosomes during cell division.

Within the nucleus lies the nucleolus, a dense region where ribosomal RNA (rRNA) is synthesized and ribosomal subunits are assembled. A typical cell may have one or more nucleoli, depending on its protein synthesis demands.

The nucleus controls the cell by regulating gene expression. DNA serves as the template for transcription, producing messenger RNA (mRNA) that carries genetic instructions to ribosomes in the cytoplasm. Through selective gene expression, cells can differentiate into specialized types despite containing identical genetic information. Nuclear dysfunction is implicated in cancer, aging, and various genetic disorders.""",
            metadata={"domain": "cellular", "tags": ["nucleus", "dna", "chromatin", "gene-expression"], "difficulty": "intermediate", "focus": "cell-biology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_005",
            corpus_id=self.corpus_id,
            title="Cell Division: Mitosis",
            content="""Mitosis is the process of cell division that produces two genetically identical daughter cells from a single parent cell. It is essential for growth, tissue repair, and asexual reproduction in eukaryotic organisms.

The cell cycle consists of interphase (G1, S, and G2 phases) and mitotic phase (M phase). During interphase, the cell grows and replicates its DNA. The S phase specifically involves DNA synthesis, resulting in duplicated chromosomes consisting of two sister chromatids joined at the centromere.

Mitosis itself consists of four stages. In prophase, chromatin condenses into visible chromosomes, the nuclear envelope breaks down, and the mitotic spindle forms. During metaphase, chromosomes align at the cell's equator (metaphase plate). In anaphase, sister chromatids separate and move to opposite poles. Finally, in telophase, nuclear envelopes reform around each set of chromosomes, and chromatin decondenses.

Cytokinesis, the division of the cytoplasm, typically occurs alongside telophase. In animal cells, a cleavage furrow pinches the cell in two. In plant cells, a cell plate forms between daughter cells. Checkpoints throughout the cell cycle ensure accurate DNA replication and chromosome segregation, preventing errors that could lead to cancer.""",
            metadata={"domain": "cellular", "tags": ["mitosis", "cell-cycle", "chromosomes", "division"], "difficulty": "intermediate", "focus": "cell-biology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_006",
            corpus_id=self.corpus_id,
            title="Meiosis and Sexual Reproduction",
            content="""Meiosis is a specialized form of cell division that produces gametes (sex cells) with half the chromosome number of the parent cell. This reduction is essential for sexual reproduction, ensuring offspring receive the correct chromosome number when gametes fuse.

Unlike mitosis, meiosis involves two successive divisions: meiosis I and meiosis II. Before meiosis begins, DNA replicates during interphase. Meiosis I is the reductional division, where homologous chromosome pairs separate. Meiosis II resembles mitosis, with sister chromatids separating. The result is four haploid cells from one diploid parent cell.

A crucial event during prophase I is crossing over (recombination), where homologous chromosomes exchange genetic segments. This, combined with the random assortment of chromosomes during metaphase I, generates genetic diversity. Each human can produce over 8 million genetically different gametes through independent assortment alone.

Errors in meiosis can result in aneuploidy—abnormal chromosome numbers. Nondisjunction, the failure of chromosomes to separate properly, causes conditions like Down syndrome (trisomy 21), Turner syndrome (monosomy X), and Klinefelter syndrome (XXY). Understanding meiosis is fundamental to genetics and reproductive medicine.""",
            metadata={"domain": "genetics", "tags": ["meiosis", "gametes", "crossing-over", "reproduction"], "difficulty": "intermediate", "focus": "cell-biology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_007",
            corpus_id=self.corpus_id,
            title="Endoplasmic Reticulum and Golgi Apparatus",
            content="""The endoplasmic reticulum (ER) and Golgi apparatus form an interconnected membrane system responsible for synthesizing, modifying, and transporting proteins and lipids within eukaryotic cells.

The endoplasmic reticulum is a network of membranous tubules and flattened sacs extending from the nuclear envelope. Rough ER, studded with ribosomes, synthesizes proteins destined for secretion, membranes, or lysosomes. Smooth ER lacks ribosomes and functions in lipid synthesis, carbohydrate metabolism, and detoxification. In muscle cells, specialized smooth ER called sarcoplasmic reticulum stores calcium ions for muscle contraction.

The Golgi apparatus, discovered by Camillo Golgi in 1898, consists of stacked, flattened membrane sacs called cisternae. It receives proteins and lipids from the ER via transport vesicles. Within the Golgi, these molecules are modified—glycosylated, phosphorylated, or cleaved—sorted, and packaged for delivery to specific destinations.

The cis face of the Golgi receives materials from the ER, while the trans face dispatches them in vesicles. This secretory pathway is essential for producing digestive enzymes, hormones, neurotransmitters, and extracellular matrix components. Dysfunction in this system underlies various diseases, including some forms of muscular dystrophy.""",
            metadata={"domain": "cellular", "tags": ["endoplasmic-reticulum", "golgi", "protein-synthesis", "secretion"], "difficulty": "intermediate", "focus": "cell-biology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_008",
            corpus_id=self.corpus_id,
            title="Lysosomes and Cellular Digestion",
            content="""Lysosomes are membrane-bound organelles containing digestive enzymes that break down waste materials and cellular debris. Often called the cell's "recycling centers," they play crucial roles in cellular maintenance and defense.

Discovered by Christian de Duve in the 1950s, lysosomes contain approximately 50 different hydrolytic enzymes capable of digesting proteins, lipids, carbohydrates, and nucleic acids. These enzymes function optimally at acidic pH (around 5), maintained by proton pumps in the lysosomal membrane.

Lysosomes participate in several processes. Phagocytosis involves engulfing large particles like bacteria, which fuse with lysosomes for digestion. Autophagy is the recycling of the cell's own damaged organelles. Receptor-mediated endocytosis brings in specific molecules like cholesterol. These processes are essential for nutrient recycling, immune defense, and cellular renewal.

Lysosomal storage diseases result from deficiencies in specific lysosomal enzymes. Tay-Sachs disease involves accumulation of lipids in neurons due to hexosaminidase A deficiency. Gaucher disease, the most common lysosomal storage disorder, results from glucocerebrosidase deficiency. Understanding lysosomal function has led to enzyme replacement therapies for some of these conditions.""",
            metadata={"domain": "cellular", "tags": ["lysosome", "digestion", "autophagy", "enzymes"], "difficulty": "intermediate", "focus": "cell-biology"}
        ))

        # Genetics and DNA (docs 9-16)
        docs.append(DocumentSpec(
            doc_id="bio_009",
            corpus_id=self.corpus_id,
            title="DNA Structure: The Double Helix",
            content="""Deoxyribonucleic acid (DNA) is the molecule that carries genetic information in all living organisms. Its structure, elucidated by James Watson and Francis Crick in 1953, is one of the most significant discoveries in biological history.

DNA consists of two polynucleotide strands wound around each other in a double helix. Each strand is composed of nucleotides, which contain three components: a deoxyribose sugar, a phosphate group, and one of four nitrogenous bases—adenine (A), guanine (G), cytosine (C), or thymine (T).

The two strands are held together by hydrogen bonds between complementary base pairs: adenine pairs with thymine (two hydrogen bonds), and guanine pairs with cytosine (three hydrogen bonds). This base-pairing rule ensures that DNA can be accurately replicated.

The strands run antiparallel—one runs 5' to 3' while the other runs 3' to 5'. The sugar-phosphate backbone forms the outer rails of the helix, while the bases stack in the center like rungs on a ladder. The major and minor grooves created by this structure provide access points for proteins that read and regulate genetic information.""",
            metadata={"domain": "genetics", "tags": ["dna", "double-helix", "watson-crick", "nucleotides"], "difficulty": "basic", "focus": "genetics"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_010",
            corpus_id=self.corpus_id,
            title="DNA Replication: Copying the Genetic Code",
            content="""DNA replication is the process by which a cell copies its DNA before division, ensuring that each daughter cell receives an identical copy of the genetic information. This semi-conservative process uses each original strand as a template for a new strand.

Replication begins at specific sequences called origins of replication, where the enzyme helicase unwinds the double helix, creating a replication fork. Single-strand binding proteins stabilize the separated strands, while topoisomerase relieves tension ahead of the fork.

DNA polymerase is the primary enzyme of replication, synthesizing new DNA in the 5' to 3' direction. Because the two template strands run antiparallel, replication differs on each strand. The leading strand is synthesized continuously toward the fork. The lagging strand is synthesized discontinuously in short segments called Okazaki fragments, which are later joined by DNA ligase.

DNA polymerase requires a primer—a short RNA sequence synthesized by primase—to begin synthesis. Proofreading mechanisms achieve remarkable accuracy, with error rates of approximately one mistake per billion nucleotides. Defects in replication machinery are associated with cancer and aging. Telomeres, protective caps at chromosome ends, shorten with each replication, contributing to cellular senescence.""",
            metadata={"domain": "genetics", "tags": ["replication", "dna-polymerase", "helicase", "okazaki"], "difficulty": "intermediate", "focus": "genetics"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_011",
            corpus_id=self.corpus_id,
            title="Transcription: From DNA to RNA",
            content="""Transcription is the first step of gene expression, in which the information encoded in DNA is copied into messenger RNA (mRNA). This process allows genetic information stored in the nucleus to be transported to ribosomes in the cytoplasm for protein synthesis.

Transcription begins when RNA polymerase binds to a promoter region upstream of a gene. In eukaryotes, transcription factors must first bind to the promoter to recruit RNA polymerase II. The enzyme then unwinds a short segment of DNA and begins synthesizing RNA using one DNA strand (the template strand) as a guide.

Unlike DNA polymerase, RNA polymerase does not require a primer and synthesizes RNA in the 5' to 3' direction. The resulting RNA is complementary to the template strand and identical to the coding strand, except that uracil (U) replaces thymine (T).

In eukaryotes, the initial transcript (pre-mRNA) undergoes processing before leaving the nucleus. A 5' cap and 3' poly-A tail are added for stability and translation initiation. Introns (non-coding sequences) are removed through splicing, leaving only exons (coding sequences). Alternative splicing allows one gene to produce multiple protein variants, greatly expanding the proteome.""",
            metadata={"domain": "genetics", "tags": ["transcription", "rna", "mrna", "gene-expression"], "difficulty": "intermediate", "focus": "genetics"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_012",
            corpus_id=self.corpus_id,
            title="Translation: Protein Synthesis",
            content="""Translation is the process by which ribosomes decode messenger RNA (mRNA) to synthesize proteins. This remarkable molecular machinery reads the genetic code in three-nucleotide units called codons, each specifying a particular amino acid.

The genetic code consists of 64 codons: 61 encode the 20 standard amino acids, while three serve as stop signals. The code is degenerate (multiple codons can specify the same amino acid) but unambiguous (each codon specifies only one amino acid). AUG serves as the start codon and also codes for methionine.

Translation occurs in three phases. During initiation, the small ribosomal subunit binds to mRNA and locates the start codon. The initiator tRNA carrying methionine binds, and the large subunit joins. During elongation, aminoacyl-tRNAs enter the A site, peptide bonds form between amino acids in the P site, and the ribosome translocates along the mRNA. During termination, a stop codon triggers release factors to free the completed polypeptide.

Ribosomes can form polyribosomes (polysomes), with multiple ribosomes translating the same mRNA simultaneously, increasing protein production efficiency. Post-translational modifications, including folding, cleavage, and chemical modifications, complete protein maturation.""",
            metadata={"domain": "genetics", "tags": ["translation", "protein", "ribosome", "genetic-code"], "difficulty": "intermediate", "focus": "genetics"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_013",
            corpus_id=self.corpus_id,
            title="Mendelian Genetics: Principles of Inheritance",
            content="""Gregor Mendel, an Austrian monk, established the fundamental principles of heredity through his experiments with pea plants in the 1860s. His work, rediscovered in 1900, forms the foundation of classical genetics.

Mendel's first law, the Law of Segregation, states that each organism carries two alleles for each trait, and these alleles separate during gamete formation so that each gamete carries only one allele. When gametes unite, offspring receive one allele from each parent.

Mendel's second law, the Law of Independent Assortment, states that alleles for different traits are distributed independently of one another during gamete formation. This explains the 9:3:3:1 ratio observed in dihybrid crosses and assumes genes are on different chromosomes or far apart on the same chromosome.

Key terms in Mendelian genetics include: genotype (genetic makeup), phenotype (observable traits), homozygous (two identical alleles), heterozygous (two different alleles), dominant (expressed when present), and recessive (expressed only when homozygous). Punnett squares visually predict offspring ratios.

While many traits follow Mendelian patterns, extensions include incomplete dominance, codominance, multiple alleles, polygenic inheritance, and epistasis. Understanding inheritance patterns is crucial for genetic counseling, agriculture, and medicine.""",
            metadata={"domain": "genetics", "tags": ["mendel", "inheritance", "alleles", "dominance"], "difficulty": "basic", "focus": "genetics"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_014",
            corpus_id=self.corpus_id,
            title="Mutations: Changes in DNA",
            content="""Mutations are permanent changes in the DNA sequence that can affect gene function and organismal phenotype. While often associated with disease, mutations are also the raw material for evolution, generating genetic variation upon which natural selection acts.

Point mutations affect single nucleotides. Silent mutations do not change the amino acid due to codon degeneracy. Missense mutations substitute one amino acid for another, with effects ranging from negligible to severe. Nonsense mutations create premature stop codons, typically producing nonfunctional truncated proteins.

Frameshift mutations, caused by insertions or deletions not divisible by three, shift the reading frame and typically produce completely altered, nonfunctional proteins. Larger chromosomal mutations include deletions, duplications, inversions, and translocations, which can affect thousands of genes.

Mutations arise from various sources. Spontaneous mutations occur during DNA replication or from reactive oxygen species. Induced mutations result from mutagens: radiation (UV light, X-rays), chemical agents (benzene, tobacco smoke), or biological agents (certain viruses). Cells possess DNA repair mechanisms—mismatch repair, nucleotide excision repair, and homologous recombination—but these systems are imperfect.

Germline mutations are heritable and present in every cell of offspring. Somatic mutations occur in body cells and are not inherited but may cause cancer if they affect cell cycle control genes.""",
            metadata={"domain": "genetics", "tags": ["mutation", "dna-repair", "point-mutation", "frameshift"], "difficulty": "intermediate", "focus": "genetics"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_015",
            corpus_id=self.corpus_id,
            title="Human Genetic Disorders",
            content="""Human genetic disorders result from mutations in one or more genes and affect millions of people worldwide. Understanding their genetic basis has revolutionized diagnosis, treatment, and prevention.

Single-gene disorders follow Mendelian inheritance patterns. Autosomal dominant disorders like Huntington's disease require only one mutant allele. Autosomal recessive disorders like cystic fibrosis and sickle cell disease require two mutant alleles. X-linked disorders like hemophilia and Duchenne muscular dystrophy predominantly affect males.

Chromosomal disorders involve changes in chromosome number or structure. Down syndrome results from trisomy 21 (three copies of chromosome 21). Turner syndrome (45,X) and Klinefelter syndrome (47,XXY) involve sex chromosome abnormalities. Deletions and duplications of chromosomal segments cause conditions like Cri-du-chat syndrome and Williams syndrome.

Multifactorial disorders like heart disease, diabetes, and most cancers result from interactions between multiple genes and environmental factors. These are more common than single-gene disorders but harder to predict and treat.

Genetic testing, including prenatal screening, carrier testing, and direct-to-consumer testing, allows identification of genetic risks. Gene therapy, which introduces functional genes to treat genetic diseases, has achieved success in some conditions and represents a frontier of medical treatment.""",
            metadata={"domain": "genetics", "tags": ["genetic-disorders", "cystic-fibrosis", "down-syndrome", "gene-therapy"], "difficulty": "intermediate", "focus": "medical"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_016",
            corpus_id=self.corpus_id,
            title="Epigenetics: Beyond the DNA Sequence",
            content="""Epigenetics is the study of heritable changes in gene expression that occur without changes to the DNA sequence itself. These modifications help explain how cells with identical DNA can become vastly different cell types and how environmental factors influence gene activity.

DNA methylation is the most studied epigenetic mechanism. The addition of methyl groups to cytosine bases, typically at CpG sites, generally silences gene expression. Methylation patterns are established during development and can be influenced by diet, stress, and environmental exposures.

Histone modifications alter chromatin structure and gene accessibility. Histones are proteins around which DNA wraps to form nucleosomes. Acetylation, methylation, phosphorylation, and other modifications of histone tails affect how tightly DNA is packaged. Generally, acetylation opens chromatin and promotes transcription, while certain methylation patterns can either activate or repress genes.

Non-coding RNAs, including microRNAs and long non-coding RNAs, also regulate gene expression epigenetically. These molecules can silence genes or influence chromatin structure.

Epigenetic changes can be transmitted across generations, a phenomenon observed in studies of famine survivors and their descendants. Aberrant epigenetic patterns are associated with cancer, autoimmune diseases, and neurological disorders. Unlike genetic mutations, epigenetic changes are potentially reversible, making them attractive therapeutic targets.""",
            metadata={"domain": "genetics", "tags": ["epigenetics", "methylation", "histones", "chromatin"], "difficulty": "advanced", "focus": "genetics"}
        ))

        # Evolution (docs 17-22)
        docs.append(DocumentSpec(
            doc_id="bio_017",
            corpus_id=self.corpus_id,
            title="Darwin's Theory of Evolution by Natural Selection",
            content="""Charles Darwin's theory of evolution by natural selection, published in "On the Origin of Species" (1859), provides the unifying framework for understanding the diversity of life on Earth.

Darwin's theory rests on several key observations. First, organisms produce more offspring than can survive. Second, individuals within a population vary in their traits. Third, some variations are heritable. From these observations, Darwin reasoned that individuals with traits better suited to their environment are more likely to survive and reproduce, passing these advantageous traits to their offspring.

Over many generations, natural selection leads to adaptation—the accumulation of traits that enhance survival and reproduction in a particular environment. Given enough time and geographic isolation, populations can diverge sufficiently to become separate species.

Darwin's theory was developed independently by Alfred Russel Wallace. While Darwin lacked knowledge of genetics, the Modern Synthesis in the 1930s-1940s integrated Mendelian inheritance with natural selection, explaining how variation arises and is transmitted.

Evidence for evolution comes from multiple sources: the fossil record showing transitional forms, comparative anatomy revealing homologous structures, molecular biology demonstrating genetic relationships, biogeography explaining species distributions, and direct observation of evolution in action in bacteria, insects, and other rapidly reproducing organisms.""",
            metadata={"domain": "evolution", "tags": ["darwin", "natural-selection", "adaptation", "origin-of-species"], "difficulty": "basic", "focus": "evolution"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_018",
            corpus_id=self.corpus_id,
            title="Evidence for Evolution: Fossils and Comparative Anatomy",
            content="""Multiple independent lines of evidence support the theory of evolution, with paleontology and comparative anatomy providing particularly compelling demonstrations of life's evolutionary history.

The fossil record documents the history of life through preserved remains and traces of organisms. Fossils reveal that life has changed dramatically over time, with many extinct species unlike anything alive today. Transitional fossils, like Tiktaalik (fish-to-tetrapod) and Archaeopteryx (dinosaur-to-bird), demonstrate evolutionary links between major groups. The sequence of fossils in geological strata consistently shows simpler organisms in older rocks and more complex forms in younger layers.

Comparative anatomy reveals evolutionary relationships through structural similarities. Homologous structures—like the forelimbs of humans, whales, bats, and dogs—share underlying bone arrangements despite different functions, indicating common ancestry. In contrast, analogous structures (like bird and insect wings) serve similar functions but evolved independently.

Vestigial structures are evolutionary remnants that have lost their original function. Human examples include the appendix, wisdom teeth, and the coccyx (tailbone). The presence of non-functional or reduced structures makes sense only in light of evolutionary history.

Embryological comparisons show that vertebrate embryos share striking similarities in early development, including pharyngeal pouches and tails, reflecting shared ancestry despite adult differences.""",
            metadata={"domain": "evolution", "tags": ["fossils", "homology", "vestigial", "comparative-anatomy"], "difficulty": "intermediate", "focus": "evolution"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_019",
            corpus_id=self.corpus_id,
            title="Molecular Evidence for Evolution",
            content="""Molecular biology provides powerful evidence for evolution, revealing genetic relationships between organisms and allowing reconstruction of evolutionary history with unprecedented precision.

DNA sequence comparisons demonstrate that all life shares a common genetic code, strongly suggesting common ancestry. The more closely related two species are, the more similar their DNA sequences. Humans and chimpanzees share approximately 98-99% of their DNA, reflecting recent common ancestry. Even distantly related organisms share genes for fundamental processes like cellular respiration.

Molecular clocks use the rate of DNA mutation accumulation to estimate when species diverged. By comparing sequences and applying calibrated mutation rates, scientists can date evolutionary splits. This technique has refined our understanding of human evolution, disease origins, and the timing of major evolutionary events.

Pseudogenes are non-functional copies of genes that accumulate mutations freely. Shared pseudogenes at the same chromosomal locations in different species indicate common ancestry. For example, humans and other primates share broken copies of the gene for vitamin C synthesis, explaining why we require dietary vitamin C.

Endogenous retroviruses (ERVs), remnants of ancient viral infections integrated into host genomes, provide additional molecular evidence. Humans share numerous ERVs with other primates at identical locations, indicating these viral insertions occurred in common ancestors.""",
            metadata={"domain": "evolution", "tags": ["molecular-evolution", "dna-comparison", "molecular-clock", "pseudogenes"], "difficulty": "intermediate", "focus": "evolution"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_020",
            corpus_id=self.corpus_id,
            title="Speciation: The Origin of New Species",
            content="""Speciation is the evolutionary process by which new species arise from existing ones. Understanding speciation explains how the millions of species on Earth diversified from common ancestors.

The biological species concept, proposed by Ernst Mayr, defines species as groups of interbreeding natural populations that are reproductively isolated from other such groups. Reproductive isolation can be prezygotic (preventing mating or fertilization) or postzygotic (producing inviable or infertile offspring).

Allopatric speciation, the most common mode, occurs when populations become geographically separated. Isolated populations experience different selective pressures and genetic drift, accumulating differences that eventually prevent interbreeding if reunited. The finches of the Galápagos Islands, which Darwin studied, exemplify allopatric speciation.

Sympatric speciation occurs within a single geographic area, often through polyploidy (chromosome duplication) in plants or through ecological specialization. Parapatric speciation occurs across environmental gradients where gene flow is reduced but not eliminated.

Adaptive radiation, the rapid diversification of a lineage into multiple species occupying different ecological niches, often follows the colonization of new habitats or the extinction of competitors. Hawaiian honeycreepers and African cichlid fishes are classic examples of adaptive radiation.""",
            metadata={"domain": "evolution", "tags": ["speciation", "reproductive-isolation", "allopatric", "adaptive-radiation"], "difficulty": "intermediate", "focus": "evolution"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_021",
            corpus_id=self.corpus_id,
            title="Human Evolution",
            content="""Human evolution traces our lineage from ancestral primates through a series of hominin species to modern Homo sapiens. This journey, reconstructed through fossils, artifacts, and genetic analysis, reveals our place in the tree of life.

Humans belong to the great ape family, sharing a common ancestor with chimpanzees approximately 6-7 million years ago. Early hominins like Sahelanthropus and Ardipithecus show a mix of ape-like and human-like features. Australopithecines, including the famous "Lucy" (Australopithecus afarensis), walked upright but had small brains and ape-like faces.

The genus Homo emerged around 2-3 million years ago. Homo habilis used simple stone tools. Homo erectus had larger brains, more sophisticated tools, and was the first hominin to leave Africa. Homo heidelbergensis may have been ancestral to both Neanderthals in Europe and Homo sapiens in Africa.

Homo sapiens appeared in Africa approximately 300,000 years ago. Modern humans migrated out of Africa beginning around 70,000-100,000 years ago, eventually colonizing every continent. Genetic evidence reveals that our ancestors interbred with Neanderthals and Denisovans, whose DNA persists in modern human populations.

Key human adaptations include bipedalism, enlarged brains, language capacity, and extended childhood for learning. These traits enabled the development of complex culture, technology, and societies that characterize our species.""",
            metadata={"domain": "evolution", "tags": ["human-evolution", "hominins", "homo-sapiens", "australopithecus"], "difficulty": "intermediate", "focus": "evolution"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_022",
            corpus_id=self.corpus_id,
            title="Population Genetics and Evolutionary Forces",
            content="""Population genetics studies the distribution and change of allele frequencies in populations, providing the mathematical foundation for understanding evolution at the genetic level.

The Hardy-Weinberg principle describes a population in genetic equilibrium—one where allele frequencies remain constant across generations. This equilibrium requires no mutation, no selection, random mating, infinite population size, and no migration. Real populations rarely meet these conditions, so evolution (allele frequency change) is the norm.

Natural selection is the primary mechanism of adaptive evolution. Directional selection favors one extreme phenotype. Stabilizing selection favors intermediate phenotypes. Disruptive selection favors both extremes. Sexual selection, acting through mate choice and competition for mates, can produce elaborate traits like peacock tails.

Genetic drift, random changes in allele frequencies, is especially important in small populations. The founder effect occurs when a small group establishes a new population with limited genetic variation. Population bottlenecks reduce genetic diversity when populations crash dramatically.

Gene flow (migration) introduces new alleles to populations, potentially counteracting differentiation between populations. Mutation is the ultimate source of new alleles, though individual mutations are rare. Non-random mating, including inbreeding, alters genotype frequencies without changing allele frequencies. These forces interact to shape the genetic structure of populations.""",
            metadata={"domain": "evolution", "tags": ["population-genetics", "hardy-weinberg", "genetic-drift", "selection"], "difficulty": "advanced", "focus": "evolution"}
        ))

        # Human Anatomy and Physiology (docs 23-32)
        docs.append(DocumentSpec(
            doc_id="bio_023",
            corpus_id=self.corpus_id,
            title="The Cardiovascular System: Heart and Circulation",
            content="""The cardiovascular system transports blood throughout the body, delivering oxygen and nutrients to tissues while removing carbon dioxide and metabolic wastes. This closed circulatory system consists of the heart, blood vessels, and approximately 5 liters of blood.

The heart is a muscular pump divided into four chambers: two atria that receive blood and two ventricles that pump blood out. The right side pumps deoxygenated blood to the lungs (pulmonary circulation), while the left side pumps oxygenated blood to the body (systemic circulation). One-way valves ensure blood flows in the correct direction.

The cardiac cycle consists of systole (contraction) and diastole (relaxation). The sinoatrial (SA) node, the heart's natural pacemaker, initiates each heartbeat by generating electrical impulses that spread through the atria, then through the atrioventricular (AV) node to the ventricles. A normal resting heart rate is 60-100 beats per minute.

Blood vessels form an extensive network. Arteries carry blood away from the heart; their thick, elastic walls withstand high pressure. Capillaries, with walls just one cell thick, enable exchange between blood and tissues. Veins return blood to the heart; their valves prevent backflow.

Cardiovascular disease, including coronary artery disease, heart failure, and stroke, is the leading cause of death worldwide. Risk factors include hypertension, high cholesterol, smoking, diabetes, and sedentary lifestyle.""",
            metadata={"domain": "anatomy", "tags": ["heart", "circulation", "blood-vessels", "cardiovascular"], "difficulty": "intermediate", "focus": "human-body"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_024",
            corpus_id=self.corpus_id,
            title="The Respiratory System: Gas Exchange",
            content="""The respiratory system enables gas exchange between the body and the external environment, taking in oxygen for cellular respiration and expelling carbon dioxide, a metabolic waste product.

Air enters through the nose or mouth, passing through the pharynx, larynx (voice box), and trachea (windpipe). The trachea branches into two bronchi, which enter the lungs and subdivide repeatedly into smaller bronchioles. These terminate in clusters of tiny air sacs called alveoli, where gas exchange occurs.

The lungs contain approximately 300 million alveoli, providing an enormous surface area (about 70 square meters) for gas exchange. Each alveolus is surrounded by capillaries. Oxygen diffuses from the alveoli into the blood, binding to hemoglobin in red blood cells. Carbon dioxide diffuses from the blood into the alveoli to be exhaled.

Breathing is controlled by the respiratory center in the brainstem. During inhalation, the diaphragm contracts and moves downward, while intercostal muscles expand the rib cage. This creates negative pressure, drawing air in. Exhalation is largely passive, resulting from elastic recoil of the lungs.

Respiratory disorders include asthma (airway inflammation and constriction), chronic obstructive pulmonary disease (COPD, including emphysema and chronic bronchitis), pneumonia (lung infection), and lung cancer. Smoking is the leading preventable cause of respiratory disease.""",
            metadata={"domain": "anatomy", "tags": ["lungs", "respiration", "gas-exchange", "breathing"], "difficulty": "intermediate", "focus": "human-body"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_025",
            corpus_id=self.corpus_id,
            title="The Nervous System: Structure and Function",
            content="""The nervous system controls and coordinates body functions through rapid electrical and chemical signaling. It consists of the central nervous system (CNS)—the brain and spinal cord—and the peripheral nervous system (PNS)—nerves throughout the body.

Neurons are the functional units of the nervous system. A typical neuron has a cell body, dendrites that receive signals, and an axon that transmits signals. Neurons communicate at synapses, where electrical impulses trigger the release of neurotransmitters that bind to receptors on the next cell.

The brain, protected by the skull and meninges, contains approximately 86 billion neurons. The cerebrum, divided into left and right hemispheres, handles higher functions including thought, memory, and voluntary movement. The cerebellum coordinates movement and balance. The brainstem controls vital functions like breathing and heart rate.

The spinal cord serves as a highway for signals between the brain and body. It also coordinates simple reflexes independently. The PNS includes sensory neurons carrying information to the CNS and motor neurons carrying commands to muscles and glands.

The autonomic nervous system regulates involuntary functions. Its sympathetic division activates "fight or flight" responses, while the parasympathetic division promotes "rest and digest" activities. Neurological disorders include Alzheimer's disease, Parkinson's disease, multiple sclerosis, and epilepsy.""",
            metadata={"domain": "anatomy", "tags": ["nervous-system", "brain", "neurons", "neurotransmitters"], "difficulty": "intermediate", "focus": "human-body"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_026",
            corpus_id=self.corpus_id,
            title="The Immune System: Defense Against Disease",
            content="""The immune system defends the body against pathogens—bacteria, viruses, fungi, and parasites—through a complex network of cells, tissues, and organs. It distinguishes self from non-self and mounts appropriate responses to eliminate threats.

Innate immunity provides immediate, non-specific defense. Physical barriers include skin and mucous membranes. Chemical barriers include stomach acid and antimicrobial proteins. Cellular components include phagocytes (neutrophils and macrophages) that engulf pathogens, and natural killer cells that destroy infected cells. Inflammation, fever, and the complement system are also innate responses.

Adaptive immunity develops more slowly but provides specific, targeted responses and immunological memory. Lymphocytes are the key players. B cells produce antibodies—proteins that bind specific antigens (foreign molecules) and mark them for destruction. T cells include helper T cells that coordinate immune responses and cytotoxic T cells that directly kill infected cells.

The lymphatic system, including lymph nodes, spleen, and thymus, houses immune cells and filters pathogens from lymph fluid. After initial exposure, memory cells remain, enabling faster, stronger responses to subsequent encounters with the same pathogen—the basis of vaccination.

Immune dysfunction causes disease. Allergies result from overreaction to harmless substances. Autoimmune diseases like rheumatoid arthritis involve attacks on self-tissues. Immunodeficiencies, whether inherited or acquired (as in HIV/AIDS), leave the body vulnerable to infections.""",
            metadata={"domain": "physiology", "tags": ["immune-system", "antibodies", "lymphocytes", "immunity"], "difficulty": "intermediate", "focus": "human-body"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_027",
            corpus_id=self.corpus_id,
            title="The Digestive System: Nutrient Processing",
            content="""The digestive system breaks down food into nutrients that can be absorbed and used by the body for energy, growth, and repair. This process involves mechanical and chemical digestion along a continuous tube from mouth to anus.

Digestion begins in the mouth, where teeth mechanically break down food and salivary amylase begins starch digestion. The tongue forms food into a bolus, which is swallowed and travels down the esophagus to the stomach via peristalsis—rhythmic muscular contractions.

The stomach churns food with gastric juice containing hydrochloric acid and pepsin, which begins protein digestion. The acidic environment also kills many pathogens. Food becomes a semi-liquid called chyme, released into the small intestine.

The small intestine is the primary site of digestion and absorption. Bile from the liver (stored in the gallbladder) emulsifies fats. Pancreatic enzymes digest carbohydrates, proteins, and lipids. Intestinal enzymes complete digestion. The intestinal wall, with its villi and microvilli, provides enormous surface area for nutrient absorption.

The large intestine (colon) absorbs water and electrolytes from remaining material, forming feces. Beneficial bacteria in the colon produce some vitamins and ferment dietary fiber. Feces are stored in the rectum and eliminated through the anus.

Digestive disorders include gastroesophageal reflux disease (GERD), peptic ulcers, inflammatory bowel disease, and colorectal cancer.""",
            metadata={"domain": "anatomy", "tags": ["digestive-system", "stomach", "intestine", "nutrition"], "difficulty": "intermediate", "focus": "human-body"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_028",
            corpus_id=self.corpus_id,
            title="The Endocrine System: Hormonal Regulation",
            content="""The endocrine system regulates body functions through hormones—chemical messengers secreted by glands into the bloodstream. It works more slowly than the nervous system but produces longer-lasting effects on metabolism, growth, development, and reproduction.

Major endocrine glands include the pituitary, thyroid, parathyroid, adrenal glands, pancreas, and gonads. The hypothalamus links the nervous and endocrine systems, controlling the pituitary gland, which in turn regulates many other glands.

The thyroid gland produces hormones (T3 and T4) that regulate metabolism. The parathyroid glands control blood calcium levels. The adrenal glands produce cortisol (stress hormone), aldosterone (regulates salt and water balance), and adrenaline (epinephrine).

The pancreas produces insulin and glucagon, which regulate blood glucose levels. Insulin promotes glucose uptake by cells; glucagon stimulates glucose release from the liver. Diabetes mellitus results from insufficient insulin production (Type 1) or insulin resistance (Type 2).

The gonads (testes and ovaries) produce sex hormones—testosterone, estrogen, and progesterone—that control reproductive development and function. Hormones are regulated by feedback loops that maintain homeostasis.

Endocrine disorders include thyroid diseases (hyperthyroidism, hypothyroidism), Addison's disease (adrenal insufficiency), Cushing's syndrome (excess cortisol), and growth hormone abnormalities (dwarfism, gigantism).""",
            metadata={"domain": "physiology", "tags": ["hormones", "endocrine", "glands", "insulin"], "difficulty": "intermediate", "focus": "human-body"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_029",
            corpus_id=self.corpus_id,
            title="The Skeletal and Muscular Systems",
            content="""The skeletal and muscular systems work together to support the body, enable movement, and protect internal organs. Together they form the musculoskeletal system, essential for posture, locomotion, and physical function.

The adult human skeleton contains 206 bones divided into the axial skeleton (skull, vertebral column, and rib cage) and the appendicular skeleton (limbs and girdles). Bones provide structural support, protect organs, produce blood cells in the marrow, store minerals (calcium and phosphorus), and serve as attachment points for muscles.

Bone is living tissue containing osteocytes (bone cells), collagen (providing flexibility), and calcium phosphate (providing hardness). Bones are continuously remodeled by osteoblasts (bone-building cells) and osteoclasts (bone-resorbing cells). Joints where bones meet are classified by their structure and range of motion.

Skeletal muscles, attached to bones by tendons, generate voluntary movement. Muscle fibers contain myofibrils with repeating units called sarcomeres. Contraction occurs when the proteins actin and myosin slide past each other, shortening the sarcomere. This sliding filament mechanism requires ATP and calcium ions.

Muscles work in antagonistic pairs: when one contracts, the other relaxes. Motor neurons stimulate contraction through neuromuscular junctions. Muscle strength increases with exercise, which causes hypertrophy (muscle fiber enlargement).

Musculoskeletal disorders include osteoporosis, arthritis, muscular dystrophy, and tendinitis.""",
            metadata={"domain": "anatomy", "tags": ["bones", "muscles", "skeleton", "movement"], "difficulty": "intermediate", "focus": "human-body"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_030",
            corpus_id=self.corpus_id,
            title="The Urinary System: Waste Elimination and Homeostasis",
            content="""The urinary system eliminates metabolic wastes, regulates blood volume and pressure, controls electrolyte levels, and maintains acid-base balance. Its primary organs are the kidneys, which filter blood and produce urine.

The kidneys are bean-shaped organs located in the posterior abdominal cavity. Each kidney contains about one million nephrons, the functional units of filtration. Blood enters the nephron at the glomerulus, a capillary tuft where water, salts, glucose, and wastes are filtered into Bowman's capsule.

As the filtrate passes through the tubular system—the proximal convoluted tubule, loop of Henle, and distal convoluted tubule—most water, all glucose, and variable amounts of salts are reabsorbed. Wastes and excess substances are secreted into the tubule. The remaining fluid becomes urine.

Urine collects in the renal pelvis, flows through the ureters to the bladder, and is expelled through the urethra during urination. An adult produces about 1-2 liters of urine daily, though this varies with fluid intake and other factors.

Hormones regulate kidney function. Antidiuretic hormone (ADH) promotes water reabsorption. Aldosterone promotes sodium reabsorption. The renin-angiotensin-aldosterone system regulates blood pressure.

Kidney diseases include acute and chronic kidney failure, kidney stones, glomerulonephritis, and polycystic kidney disease. Dialysis can replace kidney function when the kidneys fail; kidney transplantation offers another option.""",
            metadata={"domain": "anatomy", "tags": ["kidneys", "urinary", "nephron", "filtration"], "difficulty": "intermediate", "focus": "human-body"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_031",
            corpus_id=self.corpus_id,
            title="The Reproductive System and Development",
            content="""The reproductive system enables the production of offspring, ensuring species continuity. Human reproduction is sexual, involving the fusion of gametes (egg and sperm) from two parents to form a genetically unique individual.

The male reproductive system produces sperm in the testes through spermatogenesis. Sperm mature in the epididymis and travel through the vas deferens during ejaculation. Accessory glands (seminal vesicles, prostate, and bulbourethral glands) add fluids forming semen. Testosterone, produced by the testes, regulates male development and function.

The female reproductive system produces eggs (ova) in the ovaries. Each month, typically one egg matures and is released during ovulation, traveling through the fallopian tube toward the uterus. If fertilized by sperm, the embryo implants in the uterine lining. If not, the lining sheds during menstruation. Estrogen and progesterone regulate the menstrual cycle.

Fertilization typically occurs in the fallopian tube. The zygote divides as it travels to the uterus, becoming a blastocyst that implants in the endometrium. The placenta develops to nourish the embryo. Pregnancy lasts approximately 40 weeks, during which the embryo (first 8 weeks) and then fetus develop all organ systems.

Labor is triggered by hormonal changes. Uterine contractions dilate the cervix and expel the baby, followed by the placenta. Reproductive technologies like IVF assist with fertility issues.""",
            metadata={"domain": "anatomy", "tags": ["reproduction", "pregnancy", "development", "fertilization"], "difficulty": "intermediate", "focus": "human-body"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_032",
            corpus_id=self.corpus_id,
            title="Blood: Composition and Functions",
            content="""Blood is a specialized connective tissue that circulates through the cardiovascular system, performing vital transport, regulatory, and protective functions. An adult human contains approximately 5 liters of blood.

Blood consists of plasma (55%) and formed elements (45%). Plasma is a yellowish fluid containing water, proteins (albumin, globulins, fibrinogen), nutrients, hormones, wastes, and electrolytes. It transports substances throughout the body and maintains osmotic pressure.

Red blood cells (erythrocytes) are the most numerous formed elements, numbering about 5 million per microliter. They lack nuclei, maximizing space for hemoglobin, the iron-containing protein that transports oxygen. Red blood cells live about 120 days before being recycled in the spleen.

White blood cells (leukocytes) defend against infection. Neutrophils and macrophages phagocytose pathogens. Lymphocytes (B and T cells) provide adaptive immunity. Eosinophils and basophils participate in allergic and inflammatory responses. White blood cells are far less numerous than red cells, numbering 5,000-10,000 per microliter.

Platelets (thrombocytes) are cell fragments essential for blood clotting. When vessels are damaged, platelets aggregate at the injury site. The coagulation cascade produces fibrin, which forms a mesh trapping blood cells and sealing the wound.

Blood types (A, B, AB, O) are determined by antigens on red blood cells. Transfusion compatibility is essential to prevent potentially fatal immune reactions. The Rh factor is another important blood type antigen.""",
            metadata={"domain": "physiology", "tags": ["blood", "erythrocytes", "hemoglobin", "platelets"], "difficulty": "intermediate", "focus": "human-body"}
        ))

        # Microbiology (docs 33-38)
        docs.append(DocumentSpec(
            doc_id="bio_033",
            corpus_id=self.corpus_id,
            title="Bacteria: Structure and Diversity",
            content="""Bacteria are single-celled prokaryotic organisms found in virtually every environment on Earth. They are incredibly diverse, playing essential roles in ecosystems, human health, and industry—while some cause disease.

Bacteria are typically 1-5 micrometers in size. They lack membrane-bound organelles but contain ribosomes, a nucleoid region with circular DNA, and often plasmids (small circular DNA molecules). The cell membrane is surrounded by a cell wall, typically containing peptidoglycan.

Bacterial cell walls determine Gram staining: Gram-positive bacteria have thick peptidoglycan walls and stain purple, while Gram-negative bacteria have thin walls with an outer membrane and stain pink. This distinction affects antibiotic susceptibility.

Bacteria exhibit diverse shapes: cocci (spherical), bacilli (rod-shaped), and spirilla (spiral). Many have flagella for motility and pili for attachment. Some form protective endospores that can survive extreme conditions.

Bacteria reproduce asexually through binary fission, dividing rapidly under favorable conditions. Genetic variation arises through mutation and horizontal gene transfer (transformation, transduction, conjugation).

Most bacteria are harmless or beneficial. They decompose organic matter, fix nitrogen, produce vitamins, and comprise our microbiome. However, pathogenic bacteria cause diseases from strep throat to tuberculosis. Antibiotic resistance is a growing threat to public health.""",
            metadata={"domain": "microbiology", "tags": ["bacteria", "prokaryotes", "gram-staining", "pathogens"], "difficulty": "intermediate", "focus": "microbiology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_034",
            corpus_id=self.corpus_id,
            title="Viruses: Structure and Replication",
            content="""Viruses are non-cellular infectious agents that can only replicate inside living host cells. They exist at the boundary between living and non-living, possessing genetic material but lacking the machinery for independent metabolism or reproduction.

A typical virus particle (virion) consists of genetic material (DNA or RNA, single- or double-stranded) enclosed in a protein coat called a capsid. Some viruses have an additional lipid envelope derived from host cell membranes. Capsids exhibit either helical or icosahedral symmetry.

Viral replication follows general steps. Attachment involves binding to specific host cell receptors—determining host range and tissue tropism. Entry occurs through fusion, endocytosis, or injection. The viral genome is uncoated and either transcribed (DNA viruses) or directly translated (some RNA viruses).

Using host cell machinery, viral genomes are replicated and viral proteins synthesized. Components assemble into new virions, which exit by budding (enveloped viruses) or cell lysis (non-enveloped viruses). Some viruses, like HIV, integrate into host DNA, establishing latent infections.

Viruses cause numerous diseases: influenza, common cold, COVID-19, HIV/AIDS, measles, hepatitis, and certain cancers. Antiviral drugs target specific steps in the viral life cycle. Vaccines prevent many viral infections by stimulating immunity without causing disease.

Bacteriophages (viruses that infect bacteria) are being explored as alternatives to antibiotics.""",
            metadata={"domain": "microbiology", "tags": ["viruses", "viral-replication", "capsid", "pathogens"], "difficulty": "intermediate", "focus": "microbiology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_035",
            corpus_id=self.corpus_id,
            title="The Human Microbiome",
            content="""The human microbiome comprises the trillions of microorganisms—bacteria, archaea, viruses, and fungi—living in and on our bodies. These microbial communities profoundly influence human health, metabolism, and disease.

The gut microbiome is the most studied and populous community, containing hundreds of species and trillions of cells. Gut bacteria help digest dietary fiber, producing short-chain fatty acids that nourish intestinal cells. They synthesize vitamins (K, B12, biotin), metabolize drugs, and break down toxins.

The microbiome develops from birth, influenced by delivery mode, diet, and environment. Breastfed infants develop different microbiomes than formula-fed infants. By adulthood, each person's microbiome is unique but shares core functions.

The microbiome interacts extensively with the immune system. Early microbial exposure trains immune tolerance. Gut bacteria influence inflammation and may affect autoimmune disease risk. The "gut-brain axis" links the microbiome to mental health through neural, hormonal, and immune pathways.

Dysbiosis—microbial imbalance—is associated with conditions including inflammatory bowel disease, obesity, diabetes, allergies, and even neurological disorders. Antibiotics can disrupt the microbiome, sometimes leading to Clostridioides difficile infection.

Probiotics (beneficial live bacteria) and prebiotics (compounds that promote beneficial bacteria) aim to support microbiome health. Fecal microbiota transplantation treats recurrent C. difficile infection by restoring a healthy microbial community.""",
            metadata={"domain": "microbiology", "tags": ["microbiome", "gut-bacteria", "probiotics", "dysbiosis"], "difficulty": "intermediate", "focus": "microbiology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_036",
            corpus_id=self.corpus_id,
            title="Fungi: Biology and Importance",
            content="""Fungi are eukaryotic organisms that include yeasts, molds, and mushrooms. Once classified with plants, they are now recognized as a distinct kingdom more closely related to animals. Fungi play crucial ecological roles and have significant medical and economic importance.

Fungi are heterotrophs, obtaining nutrients by absorbing organic matter from their environment. They secrete digestive enzymes externally and absorb the resulting nutrients. Most fungi have cell walls containing chitin, a tough polysaccharide also found in arthropod exoskeletons.

Fungal structure varies widely. Unicellular yeasts reproduce by budding. Multicellular fungi grow as networks of thread-like hyphae, collectively called mycelium. The visible mushroom is actually a reproductive structure (fruiting body) that releases spores.

Fungi reproduce both sexually and asexually, primarily through spores. Sexual reproduction involves fusion of specialized hyphae from compatible mating types. Spores can disperse widely and survive harsh conditions.

Ecologically, fungi are essential decomposers, recycling nutrients from dead organisms. Mycorrhizal fungi form symbiotic relationships with plant roots, enhancing nutrient uptake. Lichens are symbioses between fungi and photosynthetic organisms.

Fungi are used to produce antibiotics (penicillin), foods (bread, cheese, beer), and industrial enzymes. However, some cause human diseases (candidiasis, aspergillosis, ringworm), plant diseases (rusts, smuts), and food spoilage. Toxic mushrooms can be deadly if consumed.""",
            metadata={"domain": "microbiology", "tags": ["fungi", "mushrooms", "yeast", "decomposers"], "difficulty": "intermediate", "focus": "microbiology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_037",
            corpus_id=self.corpus_id,
            title="Infectious Disease and Epidemiology",
            content="""Infectious diseases are caused by pathogenic microorganisms—bacteria, viruses, fungi, or parasites—that can spread between individuals. Epidemiology studies disease patterns in populations to understand, prevent, and control outbreaks.

Transmission occurs through various routes. Respiratory pathogens spread via droplets or aerosols. Fecal-oral transmission occurs through contaminated food or water. Contact transmission involves direct touch or fomites (contaminated objects). Vector-borne diseases are transmitted by insects like mosquitoes and ticks.

Koch's postulates, developed in the 1880s, established criteria for proving that a specific microorganism causes a particular disease: the pathogen must be present in all cases, isolated and grown in pure culture, cause disease when introduced into a healthy host, and be re-isolated from that host.

The chain of infection includes the infectious agent, reservoir (where the pathogen lives), portal of exit, mode of transmission, portal of entry, and susceptible host. Breaking any link can prevent infection.

Key epidemiological concepts include incidence (new cases), prevalence (total cases), endemic (constant presence), epidemic (sudden increase), and pandemic (global spread). The basic reproduction number (R0) indicates how many people one infected person typically infects.

Control measures include vaccination, sanitation, quarantine, contact tracing, and antimicrobial treatment. Emerging infectious diseases, like COVID-19, pose ongoing global health challenges.""",
            metadata={"domain": "medical", "tags": ["infectious-disease", "epidemiology", "transmission", "pathogens"], "difficulty": "intermediate", "focus": "medical"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_038",
            corpus_id=self.corpus_id,
            title="Antibiotics and Antimicrobial Resistance",
            content="""Antibiotics are drugs that kill or inhibit bacteria, revolutionizing medicine since Alexander Fleming's discovery of penicillin in 1928. However, antibiotic resistance now threatens to return us to an era when minor infections could be fatal.

Antibiotics work through various mechanisms. Beta-lactams (penicillins, cephalosporins) inhibit cell wall synthesis. Aminoglycosides and tetracyclines interfere with protein synthesis. Fluoroquinolones block DNA replication. Sulfonamides disrupt metabolic pathways.

Bacteria develop resistance through several mechanisms. They may produce enzymes that destroy antibiotics (beta-lactamases). They may alter the antibiotic's target site. They may reduce drug uptake or actively pump it out. Resistance genes can spread through horizontal gene transfer.

Resistance evolves because antibiotics exert selection pressure. Resistant bacteria survive and multiply while susceptible ones die. Overuse and misuse of antibiotics accelerate resistance development. This includes inappropriate prescribing, patient non-compliance, and agricultural use.

Antibiotic-resistant infections cause an estimated 1.27 million deaths annually worldwide. MRSA (methicillin-resistant Staphylococcus aureus), drug-resistant tuberculosis, and carbapenem-resistant Enterobacteriaceae are serious threats. Some infections are becoming untreatable.

Combating resistance requires antibiotic stewardship (using antibiotics only when necessary), developing new antibiotics, exploring alternatives (phage therapy, antimicrobial peptides), improving infection prevention, and global surveillance. This is one of the most urgent public health challenges of our time.""",
            metadata={"domain": "medical", "tags": ["antibiotics", "resistance", "mrsa", "penicillin"], "difficulty": "intermediate", "focus": "medical"}
        ))

        # Ecology (docs 39-44)
        docs.append(DocumentSpec(
            doc_id="bio_039",
            corpus_id=self.corpus_id,
            title="Ecosystems: Structure and Energy Flow",
            content="""An ecosystem encompasses all the living organisms (biotic factors) in an area and their interactions with non-living components (abiotic factors) like climate, soil, and water. Ecosystems range from small ponds to vast forests and include the entire biosphere.

Ecosystems are organized into trophic levels based on how organisms obtain energy. Producers (autotrophs), mainly photosynthetic plants and algae, form the base, converting solar energy into chemical energy. Primary consumers (herbivores) eat producers. Secondary consumers eat herbivores. Tertiary consumers and decomposers complete the food web.

Energy flows through ecosystems but is not recycled. At each trophic level, approximately 90% of energy is lost as heat during metabolism. This explains why ecosystems support fewer organisms at higher trophic levels and why food chains rarely exceed four or five levels.

Nutrients, unlike energy, are recycled through biogeochemical cycles. The carbon cycle involves photosynthesis, respiration, decomposition, and combustion. The nitrogen cycle includes nitrogen fixation, nitrification, and denitrification. The water cycle moves water through evaporation, precipitation, and runoff.

Primary productivity—the rate at which producers capture energy—varies among ecosystems. Tropical rainforests and coral reefs are highly productive; deserts and open oceans are less so. Human activities have significantly altered energy flow and nutrient cycles, with consequences for ecosystem function.""",
            metadata={"domain": "ecology", "tags": ["ecosystem", "food-web", "energy-flow", "nutrients"], "difficulty": "intermediate", "focus": "ecology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_040",
            corpus_id=self.corpus_id,
            title="Population Ecology: Growth and Regulation",
            content="""Population ecology studies the factors affecting population size, density, distribution, and growth. Understanding these dynamics is essential for conservation, pest management, and predicting how populations respond to environmental change.

Populations can grow exponentially when resources are unlimited, following the equation dN/dt = rN, where r is the intrinsic rate of increase. However, no population can grow indefinitely. Resource limitation leads to logistic growth, where growth slows as population approaches carrying capacity (K), the maximum population an environment can support.

Various factors regulate population size. Density-dependent factors, like competition, predation, parasitism, and disease, have greater impact as population density increases. Density-independent factors, like weather and natural disasters, affect populations regardless of density.

Life history strategies describe how organisms allocate resources between reproduction and survival. K-selected species (elephants, whales) have few offspring, extended parental care, and long lifespans. R-selected species (bacteria, insects) produce many offspring with little parental investment and high mortality.

Population age structure—the distribution of individuals among age classes—affects future growth potential. Populations with many young individuals will grow; those dominated by older individuals may decline. Survivorship curves describe mortality patterns across the lifespan.

Human population has grown exponentially since the Industrial Revolution, reaching 8 billion in 2022. This growth has profound implications for resource consumption, environmental impact, and sustainability.""",
            metadata={"domain": "ecology", "tags": ["population", "carrying-capacity", "growth", "density"], "difficulty": "intermediate", "focus": "ecology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_041",
            corpus_id=self.corpus_id,
            title="Community Ecology: Species Interactions",
            content="""Community ecology examines interactions among species living in the same area. These interactions—competition, predation, parasitism, mutualism, and commensalism—shape community structure and influence species evolution.

Competition occurs when species require the same limited resources. Interspecific competition can lead to competitive exclusion, where one species outcompetes another, or to resource partitioning, where species divide resources to coexist. Competition drives niche differentiation and character displacement.

Predation benefits predators at prey expense. Predator-prey dynamics often show cycling, with prey increases followed by predator increases. Prey evolve defenses: camouflage, warning coloration, toxins, mimicry. Predators evolve countermeasures. This coevolutionary arms race produces remarkable adaptations.

Parasitism benefits parasites at host expense. Parasites can be ectoparasites (ticks, lice) or endoparasites (tapeworms, malaria). They often have complex life cycles involving multiple hosts. Parasitoids, like many wasps, lay eggs in hosts that are eventually killed.

Mutualism benefits both species. Pollinators and plants, mycorrhizal fungi and plant roots, and cleaner fish and their clients exemplify mutualism. Commensalism benefits one species without affecting the other, as when barnacles attach to whales.

Keystone species have disproportionate effects on community structure relative to their abundance. Their removal can trigger cascading changes. Understanding species interactions is crucial for predicting how communities will respond to species losses or invasions.""",
            metadata={"domain": "ecology", "tags": ["community", "competition", "predation", "mutualism"], "difficulty": "intermediate", "focus": "ecology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_042",
            corpus_id=self.corpus_id,
            title="Biodiversity and Conservation",
            content="""Biodiversity encompasses the variety of life at all levels: genetic diversity within species, species diversity within communities, and ecosystem diversity across landscapes. It provides essential ecosystem services and has intrinsic value.

Scientists have described approximately 2 million species, but estimates of total species range from 8 million to over 100 million. Biodiversity is unevenly distributed, with tropical regions harboring the greatest richness. Hotspots—areas with exceptional biodiversity and significant habitat loss—are conservation priorities.

We are currently experiencing the sixth mass extinction, driven primarily by human activities. Habitat destruction is the leading cause of species loss. Other threats include overexploitation, invasive species, pollution, and climate change. Current extinction rates are 100-1,000 times higher than background rates.

Biodiversity loss has serious consequences. Ecosystem services—pollination, water purification, climate regulation, pest control—depend on species interactions. Genetic diversity provides raw material for adaptation. Many medicines derive from natural products.

Conservation strategies operate at multiple scales. Protected areas preserve habitat. Captive breeding and reintroduction programs aid endangered species. Habitat restoration reverses degradation. Sustainable resource management balances use and preservation. International agreements like the Convention on Biological Diversity coordinate global efforts.

Community-based conservation recognizes that local people must benefit from and participate in conservation. Climate change adaptation is increasingly important as species distributions shift.""",
            metadata={"domain": "ecology", "tags": ["biodiversity", "conservation", "extinction", "habitat"], "difficulty": "intermediate", "focus": "ecology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_043",
            corpus_id=self.corpus_id,
            title="Climate Change: Biological Impacts",
            content="""Climate change, driven primarily by anthropogenic greenhouse gas emissions, is altering biological systems worldwide. Rising temperatures, changing precipitation, ocean acidification, and extreme weather events affect organisms from microbes to ecosystems.

Many species are shifting their geographic ranges poleward or to higher elevations as temperatures rise. Some plants bloom earlier; some birds migrate sooner. However, not all species can shift equally, leading to mismatches between interacting species—pollinators may miss flowering, or predators may miss prey availability.

Phenological changes—alterations in the timing of life cycle events—can disrupt food webs. If caterpillars emerge before migratory birds arrive, bird populations may decline. Such trophic mismatches threaten ecosystem function.

Coral reefs are particularly vulnerable. Ocean warming causes coral bleaching when heat-stressed corals expel their symbiotic algae. Ocean acidification from absorbed CO2 reduces the availability of carbonate ions that corals and shellfish need to build skeletons.

Climate change interacts with other stressors—habitat loss, pollution, invasive species—to compound threats to biodiversity. Species with limited dispersal ability, narrow environmental tolerances, or small population sizes face the highest extinction risk.

Biological responses to climate change include evolutionary adaptation, behavioral and physiological plasticity, and shifts in distribution. Conservation strategies must account for climate change through habitat connectivity, assisted migration, and protecting climate refugia.""",
            metadata={"domain": "ecology", "tags": ["climate-change", "global-warming", "phenology", "coral-bleaching"], "difficulty": "intermediate", "focus": "ecology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_044",
            corpus_id=self.corpus_id,
            title="Photosynthesis: Capturing Light Energy",
            content="""Photosynthesis is the process by which plants, algae, and some bacteria convert light energy into chemical energy stored in glucose. This fundamental process supports nearly all life on Earth and produces the oxygen we breathe.

Photosynthesis occurs in chloroplasts, organelles containing the green pigment chlorophyll. The process has two stages: the light-dependent reactions and the Calvin cycle (light-independent reactions).

In the light reactions, occurring in thylakoid membranes, chlorophyll absorbs light energy, exciting electrons that pass through an electron transport chain. This process generates ATP through chemiosmosis and produces NADPH. Water molecules are split, releasing oxygen as a byproduct.

The Calvin cycle occurs in the stroma. Using ATP and NADPH from the light reactions, the enzyme RuBisCO fixes carbon dioxide into organic molecules. Through a series of reactions, three-carbon sugars are produced that can be used to synthesize glucose and other organic compounds.

C4 and CAM plants have evolved adaptations to hot, dry environments that minimize photorespiration—a wasteful process where RuBisCO fixes oxygen instead of CO2. C4 plants spatially separate initial carbon fixation from the Calvin cycle. CAM plants temporally separate these processes, opening stomata only at night.

Photosynthesis is the basis of the global carbon cycle and primary productivity. Understanding it is crucial for agriculture, biofuel development, and addressing climate change through carbon sequestration.""",
            metadata={"domain": "botany", "tags": ["photosynthesis", "chloroplast", "calvin-cycle", "chlorophyll"], "difficulty": "intermediate", "focus": "plant-biology"}
        ))

        # Biotechnology and Modern Biology (docs 45-50)
        docs.append(DocumentSpec(
            doc_id="bio_045",
            corpus_id=self.corpus_id,
            title="Genetic Engineering and Recombinant DNA",
            content="""Genetic engineering uses molecular techniques to manipulate an organism's DNA, enabling the transfer of genes between species and the creation of organisms with novel traits. This technology has transformed research, medicine, and agriculture.

Recombinant DNA technology combines DNA from different sources. Restriction enzymes cut DNA at specific sequences, creating fragments that can be joined with DNA ligase. Vectors, typically plasmids or viruses, carry foreign DNA into host cells. Bacteria transformed with recombinant plasmids can produce large quantities of proteins.

The first genetically engineered product, human insulin produced in bacteria, was approved in 1982. Since then, recombinant technology has produced growth hormone, clotting factors, vaccines, and numerous other pharmaceuticals. Gene therapy aims to treat genetic diseases by introducing functional genes.

Genetically modified organisms (GMOs) have genes deliberately altered for specific purposes. Transgenic crops may resist pests, tolerate herbicides, or contain enhanced nutrients (like Golden Rice with vitamin A). GM animals may produce pharmaceutical proteins in their milk or serve as research models.

PCR (polymerase chain reaction) revolutionized molecular biology by enabling rapid amplification of specific DNA sequences. DNA sequencing technologies have advanced dramatically, making whole-genome sequencing increasingly affordable.

Genetic engineering raises ethical concerns about environmental impacts of GMOs, equitable access to technologies, and the boundaries of human genetic modification. Regulations vary widely between countries.""",
            metadata={"domain": "biotechnology", "tags": ["genetic-engineering", "recombinant-dna", "gmo", "pcr"], "difficulty": "intermediate", "focus": "biotechnology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_046",
            corpus_id=self.corpus_id,
            title="CRISPR-Cas9: Gene Editing Revolution",
            content="""CRISPR-Cas9 is a revolutionary gene-editing technology that allows precise, efficient modification of DNA sequences. Derived from bacterial immune systems, it has transformed biological research and holds promise for treating genetic diseases.

CRISPR (Clustered Regularly Interspaced Short Palindromic Repeats) refers to DNA sequences in bacteria that store snippets of viral DNA. Cas9 is a protein that uses these sequences to recognize and cut matching DNA. Scientists repurposed this system for targeted gene editing.

The CRISPR-Cas9 system has two components: a guide RNA (gRNA) that matches the target DNA sequence and the Cas9 enzyme that cuts the DNA at that location. The cell's repair mechanisms then modify the sequence—either disrupting a gene (knockout) or inserting new sequences (knock-in) if a template is provided.

Compared to earlier gene-editing tools (ZFNs, TALENs), CRISPR is simpler, cheaper, and more efficient. It has accelerated research in genetics, disease modeling, and drug development. Applications include creating disease-resistant crops, developing gene therapies, and potentially eliminating disease-carrying mosquitoes.

CRISPR has been used in clinical trials for sickle cell disease, beta-thalassemia, and certain cancers. In 2020, its developers, Jennifer Doudna and Emmanuelle Charpentier, received the Nobel Prize in Chemistry.

However, CRISPR raises profound ethical questions, especially regarding germline editing that would pass changes to future generations. The 2018 announcement of CRISPR-edited babies in China sparked international condemnation and calls for moratoriums on certain applications.""",
            metadata={"domain": "biotechnology", "tags": ["crispr", "gene-editing", "cas9", "genetic-therapy"], "difficulty": "intermediate", "focus": "biotechnology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_047",
            corpus_id=self.corpus_id,
            title="Stem Cells and Regenerative Medicine",
            content="""Stem cells are undifferentiated cells capable of self-renewal and differentiation into specialized cell types. They hold enormous potential for regenerative medicine—repairing or replacing damaged tissues and organs.

Stem cells are classified by their potency. Totipotent cells (like the zygote) can form any cell type plus placental tissue. Pluripotent cells (embryonic stem cells) can differentiate into any cell type but not placental tissue. Multipotent cells (adult stem cells) can form several related cell types within a tissue.

Embryonic stem cells (ESCs), derived from early embryos, are pluripotent but raise ethical concerns about embryo destruction. Adult stem cells exist in many tissues (bone marrow, skin, brain) and are used in treatments like bone marrow transplants.

Induced pluripotent stem cells (iPSCs), created by Shinya Yamanaka in 2006, are adult cells reprogrammed to a pluripotent state using specific transcription factors. This discovery earned the 2012 Nobel Prize and circumvents ethical issues of ESCs while enabling patient-specific therapies.

Regenerative medicine applications include growing replacement tissues in the laboratory, treating heart disease with cardiac progenitor cells, using neural stem cells for neurodegenerative diseases, and engineering organs for transplantation.

Challenges include controlling differentiation, preventing tumor formation (stem cells can become cancerous), immune rejection, and scaling up production. Despite these hurdles, stem cell therapies are advancing rapidly, with some already approved and many in clinical trials.""",
            metadata={"domain": "biotechnology", "tags": ["stem-cells", "regenerative-medicine", "ipsc", "pluripotent"], "difficulty": "intermediate", "focus": "biotechnology"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_048",
            corpus_id=self.corpus_id,
            title="Cancer Biology: Causes and Treatments",
            content="""Cancer is a group of diseases characterized by uncontrolled cell division and the ability to invade other tissues. It results from accumulated genetic and epigenetic changes that transform normal cells into malignant ones.

Normal cell division is tightly regulated by oncogenes (which promote growth) and tumor suppressor genes (which inhibit growth). Cancer arises when mutations activate oncogenes or inactivate tumor suppressors. Multiple mutations, typically 3-7, are required for cancer to develop.

Carcinogens—agents that cause cancer—include radiation, chemicals (in tobacco smoke, for example), and certain viruses (HPV, hepatitis B and C). Inherited mutations in genes like BRCA1 and BRCA2 increase cancer risk.

Cancers develop through stages: initiation (initial mutations), promotion (clonal expansion), and progression (acquisition of invasive properties). Metastasis—the spread of cancer to distant sites—makes cancer particularly deadly. It involves local invasion, entry into blood or lymph vessels, survival in circulation, exit at distant sites, and establishment of secondary tumors.

Cancer treatment includes surgery, radiation, and chemotherapy. Targeted therapies attack specific molecular features of cancer cells. Immunotherapies, including checkpoint inhibitors and CAR-T cell therapy, harness the immune system. Personalized medicine tailors treatment to tumor genetics.

Cancer prevention includes avoiding known carcinogens (especially tobacco), vaccination (HPV, hepatitis B), screening for early detection (mammography, colonoscopy), and lifestyle factors (diet, exercise, limiting alcohol). Research continues to advance understanding and treatment.""",
            metadata={"domain": "medical", "tags": ["cancer", "oncogenes", "tumor-suppressor", "metastasis"], "difficulty": "intermediate", "focus": "medical"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_049",
            corpus_id=self.corpus_id,
            title="Vaccines and Immunization",
            content="""Vaccines stimulate the immune system to produce protection against specific pathogens without causing disease. They are among the most successful public health interventions, having eradicated smallpox and nearly eliminated polio.

Traditional vaccines use weakened (attenuated) or killed pathogens, or purified components like proteins or polysaccharides. Live attenuated vaccines (measles, mumps, rubella) produce strong immunity but cannot be used in immunocompromised individuals. Inactivated vaccines (flu shots, polio) are safer but may require boosters.

Newer vaccine technologies include recombinant protein vaccines, virus-like particles, and DNA vaccines. The COVID-19 pandemic accelerated mRNA vaccine development. Pfizer and Moderna vaccines deliver mRNA encoding the spike protein; cells produce this protein, triggering immune responses without any viral infection.

Vaccines work by exposing the immune system to antigens, stimulating production of antibodies and memory cells. Upon subsequent exposure to the real pathogen, the immune system responds quickly and effectively, preventing or reducing disease severity.

Herd immunity occurs when enough people are immune to limit pathogen spread, protecting those who cannot be vaccinated. The threshold varies by disease—measles requires about 95% immunity due to its high transmissibility.

Vaccine hesitancy poses a significant public health challenge. Misinformation about vaccine safety, despite extensive scientific evidence of their benefits, has contributed to outbreaks of preventable diseases. Global vaccination campaigns continue to save millions of lives annually.""",
            metadata={"domain": "medical", "tags": ["vaccines", "immunization", "mrna", "herd-immunity"], "difficulty": "intermediate", "focus": "medical"}
        ))

        docs.append(DocumentSpec(
            doc_id="bio_050",
            corpus_id=self.corpus_id,
            title="The Human Genome Project and Genomic Medicine",
            content="""The Human Genome Project (HGP), completed in 2003, was a landmark international effort that sequenced the entire human genome. This achievement has transformed biology and medicine, ushering in the era of genomic medicine.

The HGP took 13 years and cost approximately $3 billion. It revealed that humans have about 20,000-25,000 protein-coding genes—far fewer than expected—spanning 3 billion base pairs. Most of the genome consists of non-coding sequences, once dismissed as "junk DNA" but now recognized as having regulatory and other functions.

Since the HGP, sequencing technology has advanced dramatically. What once took years and billions of dollars now takes days and costs under $1,000. This has enabled large-scale genomic studies linking genetic variants to disease risk.

Pharmacogenomics uses genetic information to predict drug responses, enabling personalized prescribing. Genetic testing identifies individuals at risk for hereditary conditions. Prenatal testing and newborn screening detect genetic abnormalities early. Direct-to-consumer testing allows individuals to explore their ancestry and health-related genetic variants.

Cancer genomics characterizes tumor mutations to guide treatment selection. Liquid biopsies detect circulating tumor DNA in blood, enabling non-invasive cancer monitoring. Whole genome sequencing is increasingly used to diagnose rare genetic disorders.

The HGP raised ethical, legal, and social issues regarding genetic privacy, discrimination, and access to genetic technologies. The field continues to grapple with these challenges as genomic medicine becomes increasingly integrated into healthcare.""",
            metadata={"domain": "biotechnology", "tags": ["human-genome-project", "genomics", "sequencing", "personalized-medicine"], "difficulty": "intermediate", "focus": "biotechnology"}
        ))

        return docs
