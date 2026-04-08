"""
Ontological Engine - Creative Math RAG Dataset
===============================================

Creative mathematical content for the CREATIVITY domain (O2_FORMING).
Focuses on mathematical art, patterns, storytelling, and imaginative exploration.

Categories:
- patterns: Fractals, tessellations, symmetry, visual patterns
- golden_ratio: Golden ratio in nature, art, architecture
- math_art: Mathematical art, generative designs, visual beauty
- math_stories: Mathematical storytelling and narratives
- wonder: Surprising/beautiful mathematical phenomena
- design: Mathematical principles in architecture, music, nature

Usage:
    from symbolu_core.ontological.creative_math_dataset import CreativeMathDataset

    # Generate and save dataset
    dataset = CreativeMathDataset.generate(count=500)
    dataset.save("data/creative_math_rag.json")
"""

import json
import random
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class CreativeMathItem:
    """A creative math exploration item."""
    title: str
    content: str
    exploration: str  # Creative prompt or exploration
    category: str  # patterns, golden_ratio, math_art, math_stories, wonder, design
    tags: List[str]

    def to_text(self) -> str:
        """Convert to training text format."""
        return f"{self.title}\n\n{self.content}\n\nExploration: {self.exploration}"


class CreativeMathDataset:
    """
    Creative math dataset generator for the CREATIVITY domain.

    This generates content that should activate O2_FORMING (creativity)
    rather than O7_REASONING (logic).
    """

    DOMAIN = "creativity"

    def __init__(self, items: List[CreativeMathItem] = None):
        self.items = items or []

    def __len__(self) -> int:
        return len(self.items)

    def get_texts(self) -> List[str]:
        """Get all items as training texts."""
        return [item.to_text() for item in self.items]

    def get_by_category(self, category: str) -> List[CreativeMathItem]:
        """Filter items by category."""
        return [item for item in self.items if item.category == category]

    def save(self, path: str) -> None:
        """Save dataset to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "domain": self.DOMAIN,
            "count": len(self.items),
            "items": [asdict(item) for item in self.items]
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"Saved {len(self.items)} creative math items to {path}")

    @classmethod
    def load(cls, path: str) -> "CreativeMathDataset":
        """Load dataset from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = [CreativeMathItem(**item) for item in data["items"]]
        print(f"Loaded {len(items)} creative math items from {path}")
        return cls(items)

    @classmethod
    def generate(cls, count: int = 500, seed: int = None) -> "CreativeMathDataset":
        """
        Generate creative math dataset.

        Args:
            count: Total number of items to generate
            seed: Random seed for reproducibility
        """
        if seed is not None:
            random.seed(seed)

        items = []
        per_category = count // 6

        items.extend(cls._generate_patterns(per_category))
        items.extend(cls._generate_golden_ratio(per_category))
        items.extend(cls._generate_math_art(per_category))
        items.extend(cls._generate_math_stories(per_category))
        items.extend(cls._generate_wonder(per_category))
        items.extend(cls._generate_design(count - 5 * per_category))

        random.shuffle(items)

        print(f"Generated {len(items)} creative math items")
        return cls(items)

    @classmethod
    def _generate_patterns(cls, count: int) -> List[CreativeMathItem]:
        """Generate pattern-based creative math content."""
        items = []

        pattern_templates = [
            {
                "title": "The Infinite Dance of the Mandelbrot Set",
                "content": "Imagine zooming into a shape that never ends. The Mandelbrot set is a boundary between chaos and order, where each magnification reveals new spirals, seahorses, and islands that echo the whole. It's born from the simple equation z = z² + c, yet creates infinite complexity.",
                "exploration": "Close your eyes and imagine you're shrinking, diving into the Mandelbrot set. What creatures and landscapes do you see as you fall deeper into infinity?",
                "tags": ["fractals", "infinity", "self-similarity", "complex numbers"]
            },
            {
                "title": "Tessellation: Tiling the Infinite Plane",
                "content": "M.C. Escher saw what mathematicians knew: certain shapes can cover a surface forever without gaps or overlaps. From honeycomb hexagons to interlocking birds and fish, tessellations reveal how geometry can dance across infinity.",
                "exploration": "Design your own tessellation using a simple shape. How does the shape transform as it repeats? What story does your infinite pattern tell?",
                "tags": ["tessellation", "Escher", "symmetry", "tiling"]
            },
            {
                "title": "Spirals: Nature's Favorite Curve",
                "content": "The nautilus shell, hurricane clouds, spiral galaxies, sunflower seeds - why does nature love spirals so much? The logarithmic spiral grows while maintaining its shape, a mathematical whisper of 'as above, so below' across scales.",
                "exploration": "Take a walk and count the spirals you find - in plants, shells, water draining, even the curl of your ear. What makes spirals so universal?",
                "tags": ["spirals", "logarithmic", "nature", "growth"]
            },
            {
                "title": "The Koch Snowflake: Infinite Perimeter, Finite Area",
                "content": "Start with a triangle. Add smaller triangles to each edge. Repeat forever. The Koch snowflake has a perimeter that grows infinitely long while the area stays bounded. It's a coastline that goes on forever inside a teacup.",
                "exploration": "Draw the first 4 iterations of a Koch snowflake. As you add more detail, imagine being an ant walking its edge - when would your journey end?",
                "tags": ["fractals", "infinity", "paradox", "self-similarity"]
            },
            {
                "title": "Symmetry: The Universe's Mirror",
                "content": "A butterfly's wings, a snowflake's arms, your own face - symmetry appears everywhere. Mathematicians classify symmetries into groups, revealing that a crystal's structure and a kaleidoscope's patterns speak the same geometric language.",
                "exploration": "Create a design with exactly 5-fold rotational symmetry (like a starfish). Why might 5-fold symmetry be rare in crystals but common in living things?",
                "tags": ["symmetry", "groups", "reflection", "rotation"]
            },
            {
                "title": "The Sierpinski Triangle: A Shape Made of Holes",
                "content": "Take a triangle. Remove the middle. Do it again to what remains. The Sierpinski triangle is more hole than substance, yet perfectly ordered. It has zero area but infinite perimeter - a ghost of geometry.",
                "exploration": "Build a Sierpinski triangle from paper or draw one. What do you notice about the number of triangles at each level? Can you find other shapes hiding within?",
                "tags": ["fractals", "recursion", "self-similarity", "void"]
            },
            {
                "title": "Penrose Tiles: Order Without Repetition",
                "content": "Two simple shapes - kites and darts - can tile a floor forever without ever repeating. Roger Penrose discovered patterns that have five-fold symmetry and infinite variation, later found in actual crystals that shouldn't exist.",
                "exploration": "Try tiling a surface with Penrose tiles. Notice how local rules create global patterns. What does it mean for something to be ordered but not periodic?",
                "tags": ["aperiodic", "Penrose", "quasicrystals", "tiling"]
            },
            {
                "title": "Celtic Knots: Where Lines Never End",
                "content": "Follow any thread in a Celtic knot and you'll return to where you started, having woven over and under in an eternal dance. These ancient patterns embody the mathematical concept of a single closed curve - one line creating infinite complexity.",
                "exploration": "Design a Celtic knot that uses only one continuous line. How does the crossing pattern create the illusion of depth and weaving?",
                "tags": ["topology", "knots", "curves", "ancient mathematics"]
            },
        ]

        # Generate variations
        for i in range(count):
            template = pattern_templates[i % len(pattern_templates)]
            items.append(CreativeMathItem(
                title=template["title"],
                content=template["content"],
                exploration=template["exploration"],
                category="patterns",
                tags=template["tags"]
            ))

        return items[:count]

    @classmethod
    def _generate_golden_ratio(cls, count: int) -> List[CreativeMathItem]:
        """Generate golden ratio content."""
        items = []

        golden_templates = [
            {
                "title": "Phi: The Number That Creates Itself",
                "content": "1.618033988749... The golden ratio φ is the only number that equals its own reciprocal plus one. It emerges from the simplest continued fraction, appears in the growth of rabbits, and whispers through the petals of flowers. Some call it divine.",
                "exploration": "Measure rectangles you find beautiful - picture frames, book covers, windows. How many are close to golden rectangles (ratio about 1.618)?",
                "tags": ["golden ratio", "phi", "aesthetics", "proportion"]
            },
            {
                "title": "The Fibonacci Spiral: Nature's Blueprint",
                "content": "1, 1, 2, 3, 5, 8, 13... Each Fibonacci number is the sum of the two before it. Draw quarter-circles through squares of these sizes and a spiral emerges - the same spiral in nautilus shells, hurricanes, and the arms of galaxies.",
                "exploration": "Count the spirals in a pinecone or sunflower. You'll almost always find two Fibonacci numbers. Why would plants grow this way?",
                "tags": ["Fibonacci", "spirals", "phyllotaxis", "growth"]
            },
            {
                "title": "Golden Architecture: From Parthenon to Le Corbusier",
                "content": "The Greeks built the Parthenon with golden proportions. Renaissance artists composed with it. Le Corbusier based his Modulor on a golden-proportioned human body. Whether by design or discovery, φ shapes our built environment.",
                "exploration": "Sketch a building using only golden rectangles. How does it feel compared to buildings made of squares or arbitrary rectangles?",
                "tags": ["architecture", "golden ratio", "design", "proportion"]
            },
            {
                "title": "The Golden Angle: Why Sunflowers Are Optimal",
                "content": "137.5 degrees - the golden angle. Sunflowers arrange their seeds at this angle to pack the most seeds in the least space. No two seeds ever line up, creating those mesmerizing spirals. It's evolution discovering mathematics.",
                "exploration": "Place dots on paper, each rotated 137.5° from the last. Watch the spiral patterns emerge. What happens if you use a different angle?",
                "tags": ["golden angle", "phyllotaxis", "optimization", "nature"]
            },
            {
                "title": "The Human Body: φ in Flesh",
                "content": "Your navel divides your body at roughly the golden ratio. Your finger bones relate by φ. The spiral of your ear, the proportions of your face - are we golden creatures, or do we just see gold where we want to?",
                "exploration": "Measure the ratios in your own body. How close do they come to φ? Do you find the matches convincing or coincidental?",
                "tags": ["human body", "golden ratio", "proportion", "aesthetics"]
            },
            {
                "title": "Golden Music: The Ratio in Sound",
                "content": "Composers from Bach to Bartók have structured music around the golden ratio, placing climaxes at φ points in compositions. The octave itself contains twelve semitones - and 8/5 and 5/3, both Fibonacci ratios, create pleasing intervals.",
                "exploration": "Listen to a favorite piece of music. Where does the climax occur? Is it near the golden point (about 62% through)?",
                "tags": ["music", "golden ratio", "composition", "harmony"]
            },
            {
                "title": "The Pentagon and the Golden Star",
                "content": "Draw a five-pointed star inside a pentagon. The ratio of the star's edge to the pentagon's edge is exactly φ. And inside each point of the star? Another pentagon. Inside that? Another star. Phi nests within itself forever.",
                "exploration": "Draw a pentagram and measure its segments. Find all the places where the golden ratio appears. How is the pentagon connected to the dodecahedron?",
                "tags": ["pentagon", "pentagram", "geometry", "recursion"]
            },
        ]

        for i in range(count):
            template = golden_templates[i % len(golden_templates)]
            items.append(CreativeMathItem(
                title=template["title"],
                content=template["content"],
                exploration=template["exploration"],
                category="golden_ratio",
                tags=template["tags"]
            ))

        return items[:count]

    @classmethod
    def _generate_math_art(cls, count: int) -> List[CreativeMathItem]:
        """Generate mathematical art content."""
        items = []

        art_templates = [
            {
                "title": "Generative Art: When Algorithms Dream",
                "content": "Feed a computer simple rules and watch it paint. Generative art emerges from mathematical recipes - random walks, cellular automata, L-systems. Each piece is unique yet follows invisible laws, like snowflakes falling from digital clouds.",
                "exploration": "Write three rules for how a point should move on paper. Execute them randomly 1000 times. What emerges? How do simple rules create complex beauty?",
                "tags": ["generative art", "algorithms", "emergence", "randomness"]
            },
            {
                "title": "String Art: Lines Creating Curves",
                "content": "Stretch straight strings between pins in a pattern, and curves mysteriously appear. A parabola emerges from nowhere, circles from lines that never bend. The envelope of lines creates what no single line contains.",
                "exploration": "Create string art using only straight lines that produces a perfect circle. How many lines do you need before the curve becomes smooth?",
                "tags": ["string art", "envelopes", "curves", "construction"]
            },
            {
                "title": "Islamic Geometric Patterns: Infinity in Repetition",
                "content": "For centuries, Islamic artists have created stunning geometric patterns without depicting living things. Circles become stars become polygons in infinite interlocking dances. Each pattern encodes mathematical symmetry groups in colored stone.",
                "exploration": "Start with a circle grid and construct an Islamic star pattern. How do the same starting circles create such different final designs?",
                "tags": ["Islamic art", "geometry", "symmetry", "tessellation"]
            },
            {
                "title": "Origami: Folding Mathematics",
                "content": "A single sheet of paper, no cuts, yet dragons and cranes emerge from folds. Origami is applied geometry - every crease a reflection, every fold an axiom. Mathematicians have proven what can and cannot be folded from flat sheets.",
                "exploration": "Fold a crane and trace the crease pattern when unfolded. What symmetries do you see? Why must the number of creases meeting at any point be even?",
                "tags": ["origami", "paper folding", "geometry", "axioms"]
            },
            {
                "title": "The Art of Topology: When Shape Doesn't Matter",
                "content": "To a topologist, a coffee cup is a donut. Stretch, bend, squish - as long as you don't tear or glue, they're the same. This abstract way of seeing has inspired artists to create sculptures that twist through impossible dimensions.",
                "exploration": "Can you draw a shape on a coffee cup that would become impossible on a donut? What does it mean for two shapes to be 'topologically equivalent'?",
                "tags": ["topology", "transformation", "equivalence", "sculpture"]
            },
            {
                "title": "Voronoi Diagrams: Territory Maps of Space",
                "content": "Scatter seeds across a field. Each point of land belongs to its nearest seed. The boundaries form a Voronoi diagram - seen in giraffe spots, dragonfly wings, and soap bubbles. Nature's way of dividing territory creates accidental art.",
                "exploration": "Drop 10 random points on paper and construct their Voronoi cells. Then add more points - how does the diagram change? What makes some Voronoi patterns beautiful?",
                "tags": ["Voronoi", "spatial partitioning", "nature", "patterns"]
            },
            {
                "title": "Cellular Automata: Patterns from Nothing",
                "content": "Start with one black square. Apply a simple rule: look at three squares, color the next row based on a pattern. From this trivial beginning, John Conway's Game of Life and Stephen Wolfram's Rule 110 create universes of emergent complexity.",
                "exploration": "Implement Rule 110 by hand for 20 generations. Watch order, chaos, and structure compete. Can simple rules create computation itself?",
                "tags": ["cellular automata", "emergence", "computation", "patterns"]
            },
            {
                "title": "Mathematical Sculptures: Form in Three Dimensions",
                "content": "Bathsheba Grossman prints mathematical surfaces in metal. Helaman Ferguson carves theorems in stone. These artists make abstract mathematics touchable - Möbius strips, Klein bottles, minimal surfaces frozen in matter.",
                "exploration": "Design a sculpture based on a mathematical surface (sphere, torus, hyperboloid). How does the physical form reveal properties invisible in equations?",
                "tags": ["sculpture", "3D printing", "mathematical surfaces", "form"]
            },
        ]

        for i in range(count):
            template = art_templates[i % len(art_templates)]
            items.append(CreativeMathItem(
                title=template["title"],
                content=template["content"],
                exploration=template["exploration"],
                category="math_art",
                tags=template["tags"]
            ))

        return items[:count]

    @classmethod
    def _generate_math_stories(cls, count: int) -> List[CreativeMathItem]:
        """Generate mathematical storytelling content."""
        items = []

        story_templates = [
            {
                "title": "The Library of Babel",
                "content": "Jorge Luis Borges imagined a library containing every possible 410-page book. Most are gibberish, but somewhere sits your biography, a cure for cancer, and this very sentence. The library is finite but unimaginably vast - 25^1,312,000 books.",
                "exploration": "If you could search the Library of Babel, how would you find the one book that contains the truth about your future? What does infinite possibility mean for meaning?",
                "tags": ["infinity", "combinatorics", "Borges", "possibility"]
            },
            {
                "title": "Flatland: A Romance of Many Dimensions",
                "content": "Edwin Abbott wrote of a world of two dimensions, where creatures are shapes who cannot imagine 'up.' When a sphere visits Flatland, the square sees only a circle that grows and shrinks. We are Flatlanders too, blind to dimensions beyond our perception.",
                "exploration": "Imagine explaining a cube to a Flatlander. Now imagine a 4D being trying to explain a tesseract to you. What would its shadow look like?",
                "tags": ["dimensions", "perception", "Flatland", "geometry"]
            },
            {
                "title": "The Story of π: A Number Without End",
                "content": "Pi goes on forever, never repeating. Somewhere in its digits is your phone number, your birthday, the works of Shakespeare encoded. We've calculated trillions of digits, yet each new one is a surprise. Pi is a universe of randomness born from a perfect circle.",
                "exploration": "Write a story that takes place in the millionth digit of pi. Who lives there? What does 'location' mean in an infinite, structureless sequence?",
                "tags": ["pi", "infinity", "transcendental", "randomness"]
            },
            {
                "title": "The Mathematician's Nightmare",
                "content": "A mathematician dreams of a world where 2+2=5. At first, nothing changes. Then buildings fall, bridges collapse, music becomes dissonant. The dream reveals how arithmetic isn't a game we invented, but the bones of reality itself.",
                "exploration": "Write about a world where one mathematical law is different. What would change if circles had rational pi? If there were finitely many primes?",
                "tags": ["logic", "necessity", "thought experiment", "foundations"]
            },
            {
                "title": "The Infinite Hotel: Hilbert's Paradox",
                "content": "A hotel with infinite rooms is full. A new guest arrives. 'No problem,' says the manager. 'Everyone moves to the next room.' Now room 1 is free. A bus with infinite passengers arrives. Everyone moves to room 2n. All odd rooms are free. Infinity plus infinity equals infinity.",
                "exploration": "Continue the story: what happens when infinitely many infinite buses arrive? Can the hotel ever truly be full?",
                "tags": ["infinity", "Hilbert", "paradox", "set theory"]
            },
            {
                "title": "The Bridges of Königsberg: A Walk That Changed Mathematics",
                "content": "In 1736, the people of Königsberg asked: can you cross all seven bridges exactly once? Euler proved it impossible, inventing graph theory along the way. Sometimes the most playful questions lead to the deepest mathematics.",
                "exploration": "Design a city with bridges where such a walk IS possible. What condition must your bridges satisfy? Can you create a city where multiple such walks exist?",
                "tags": ["graph theory", "Euler", "puzzles", "impossibility"]
            },
            {
                "title": "The Unreasonable Effectiveness of Mathematics",
                "content": "Physicist Eugene Wigner marveled at how mathematics, created by pure thought, describes the physical universe with uncanny precision. Equations written for beauty alone later explain electrons. Is math discovered or invented? Why does the universe speak geometry?",
                "exploration": "Write a dialogue between a mathematician and a physicist about why their languages are the same. Are they discovering one truth or creating parallel fictions?",
                "tags": ["philosophy", "physics", "discovery", "invention"]
            },
            {
                "title": "The Ship of Theseus Equation",
                "content": "A ship's planks are replaced one by one. When all are new, is it the same ship? Math faces similar questions: is the number 2 in '2+3' the same as in '2×4'? Identity in mathematics is both trivial and profound - things are equal by definition, yet definitions encode deep choices.",
                "exploration": "Write about two numbers that argue about whether they're the same. What would convince them? What does equality really mean?",
                "tags": ["identity", "philosophy", "paradox", "meaning"]
            },
        ]

        for i in range(count):
            template = story_templates[i % len(story_templates)]
            items.append(CreativeMathItem(
                title=template["title"],
                content=template["content"],
                exploration=template["exploration"],
                category="math_stories",
                tags=template["tags"]
            ))

        return items[:count]

    @classmethod
    def _generate_wonder(cls, count: int) -> List[CreativeMathItem]:
        """Generate mathematical wonder/surprise content."""
        items = []

        wonder_templates = [
            {
                "title": "e^(iπ) + 1 = 0: The Most Beautiful Equation",
                "content": "Five fundamental constants - e, i, π, 1, and 0 - connected by three basic operations - addition, multiplication, exponentiation. Euler's identity emerges from the infinite, ties together analysis and geometry, and fits in a tweet. Some mathematicians weep at its beauty.",
                "exploration": "What makes an equation 'beautiful'? Can beauty be defined mathematically? Write a poem about Euler's identity.",
                "tags": ["Euler", "beauty", "constants", "elegance"]
            },
            {
                "title": "Cantor's Paradise: Infinities Beyond Infinity",
                "content": "Georg Cantor proved the impossible: some infinities are bigger than others. The integers are infinite, but the real numbers are infinitely more infinite. There are more ways to arrange points on a line than there are counting numbers. The paradise of set theory has no ceiling.",
                "exploration": "Imagine counting to different infinities. What would it feel like to 'reach' aleph-null versus the continuum? Write about the experience of bigger infinities.",
                "tags": ["infinity", "Cantor", "set theory", "cardinality"]
            },
            {
                "title": "Gödel's Incompleteness: The Limits of Logic",
                "content": "Kurt Gödel proved that any logical system powerful enough to describe arithmetic contains true statements it cannot prove. Mathematics is forever incomplete, always able to see truths it cannot reach. The mind exceeds its own machinery.",
                "exploration": "What does it feel like to know something is true but be unable to prove it? Write about a mathematician confronting an unprovable truth.",
                "tags": ["Gödel", "incompleteness", "logic", "limits"]
            },
            {
                "title": "The Banach-Tarski Paradox: Doubling Spheres",
                "content": "Take a sphere. Cut it into five pieces. Reassemble them into two spheres identical to the original. This is mathematically proven, using the Axiom of Choice. The pieces are so strange they have no meaningful volume - ghosts that multiply matter.",
                "exploration": "If you could perform the Banach-Tarski transformation in real life, what would you duplicate first? What does this paradox say about continuity and choice?",
                "tags": ["paradox", "set theory", "infinity", "impossibility"]
            },
            {
                "title": "The Monster Group: Symmetry's Final Boss",
                "content": "The Monster is a mathematical object with 808,017,424,794,512,875,886,459,904,961,710,757,005,754,368,000,000,000 symmetries. It lives in 196,883 dimensions. It connects to string theory, modular functions, and moonshine. We don't fully understand why it exists.",
                "exploration": "The Monster was discovered, not invented - it had to exist given the axioms. What does it mean for such strange objects to be 'out there' waiting to be found?",
                "tags": ["group theory", "Monster", "symmetry", "discovery"]
            },
            {
                "title": "Zero: The Number That Shouldn't Exist",
                "content": "For centuries, zero was nothing - a placeholder, a blank. Then Indian mathematicians dared to call it a number. Suddenly you could subtract 3 from 3, divide by shrinking quantities, and fall into negative realms. Zero is the void that created modern mathematics.",
                "exploration": "Imagine mathematics without zero. How would you write 102? Calculate 5-5? Describe nothing? Write about the person who first dared to count nothing.",
                "tags": ["zero", "history", "India", "nothing"]
            },
            {
                "title": "The Riemann Hypothesis: A Million-Dollar Mystery",
                "content": "The zeros of a certain function seem to lie on a line. Prove it and win a million dollars - and transform our understanding of prime numbers. For 160 years, the greatest mathematicians have tried and failed. The primes keep their secret.",
                "exploration": "Write a detective story where the criminal is the Riemann Hypothesis. What clues has it left? Why does it hide? Will it ever be caught?",
                "tags": ["Riemann", "primes", "unsolved", "mystery"]
            },
            {
                "title": "i: The Imaginary Revolution",
                "content": "The square root of -1 doesn't exist. So mathematicians invented it anyway, called it i, and discovered it was essential. Imaginary numbers describe alternating current, quantum mechanics, and signal processing. The impossible is necessary.",
                "exploration": "What does it feel like to be an imaginary number? Neither positive nor negative, sideways to reality? Write from i's perspective.",
                "tags": ["imaginary numbers", "complex", "invention", "reality"]
            },
        ]

        for i in range(count):
            template = wonder_templates[i % len(wonder_templates)]
            items.append(CreativeMathItem(
                title=template["title"],
                content=template["content"],
                exploration=template["exploration"],
                category="wonder",
                tags=template["tags"]
            ))

        return items[:count]

    @classmethod
    def _generate_design(cls, count: int) -> List[CreativeMathItem]:
        """Generate math-in-design content."""
        items = []

        design_templates = [
            {
                "title": "The Mathematics of Music: Harmony in Numbers",
                "content": "Pythagoras heard the blacksmith's hammers and discovered that pleasing harmonies come from simple ratios. A string halved plays an octave (2:1). A fifth is 3:2, a fourth is 4:3. Music is applied arithmetic, frequencies dancing in geometric proportion.",
                "exploration": "Create a musical scale using only integer ratios. How does it sound compared to our modern equal-tempered scale? What do we gain and lose?",
                "tags": ["music", "ratios", "harmony", "Pythagoras"]
            },
            {
                "title": "Nature's Geometry: Why Honeycombs Are Hexagons",
                "content": "Bees need to store honey efficiently. The hexagon uses the least wax to enclose the most space when tiling a plane. Nature solved an optimization problem without calculus, through millions of years of blind trial and selection.",
                "exploration": "Design a different storage system using mathematics. Could you beat the hexagon? What if you weren't constrained to a plane?",
                "tags": ["optimization", "nature", "hexagons", "efficiency"]
            },
            {
                "title": "Bridge Mathematics: Forces in Balance",
                "content": "A suspension bridge is a catenary curve - the shape a hanging chain naturally forms. Cables carry tension, towers carry compression, and mathematics balances forces across spans that would crush any solid beam. Engineering is applied geometry.",
                "exploration": "Design a bridge using only tension (like a spider web) or only compression (like an arch). What shapes emerge? What spans become possible?",
                "tags": ["engineering", "curves", "forces", "bridges"]
            },
            {
                "title": "The Logarithmic Spiral in Shells and Galaxies",
                "content": "A nautilus shell grows by adding chambers that maintain the same shape at every size. This self-similar growth traces a logarithmic spiral - the same curve in hurricanes, spiral galaxies, and the arms of a thrown fern frond.",
                "exploration": "Design a building or object that grows like a nautilus - maintaining proportion at any scale. How does logarithmic growth feel different from linear growth?",
                "tags": ["spirals", "growth", "self-similarity", "architecture"]
            },
            {
                "title": "Minimal Surfaces: Soap Bubbles as Architects",
                "content": "Dip a wire frame in soap solution and the film that forms has minimal surface area - nature solving calculus instantly. Frei Otto designed stadium roofs by photographing soap films. Mathematics minimizes material while maximizing strength.",
                "exploration": "Create an unusual wire frame and predict what soap film would form inside it. Then test it (or imagine testing it). Were you right?",
                "tags": ["minimal surfaces", "optimization", "architecture", "soap bubbles"]
            },
            {
                "title": "Tree Branching: The Mathematics of Reaching",
                "content": "Trees branch to maximize sunlight capture with minimum material. The angles follow predictable patterns - younger branches at sharper angles, older at wider. L-systems can generate realistic trees from simple grammatical rules. Life grows in algorithms.",
                "exploration": "Write rules for a branching system and draw what grows. Adjust one rule and watch the tree transform. What rule changes make trees look sick, healthy, alien?",
                "tags": ["L-systems", "branching", "growth", "biology"]
            },
            {
                "title": "The Pentagon in Nature: Starfish and Flowers",
                "content": "Five-fold symmetry is common in life but almost unknown in crystals. Starfish, many flowers, some fruits - the number five protects against efficient packing, perhaps defending against viruses and parasites that need geometric keys.",
                "exploration": "Design a life form with 7-fold symmetry. What advantages and disadvantages would it have? Why is 5 more common than 7 in nature?",
                "tags": ["symmetry", "five-fold", "biology", "design"]
            },
            {
                "title": "Dome Mathematics: Buckminster Fuller's Vision",
                "content": "Geodesic domes distribute stress across triangles, creating maximum enclosed space with minimum material. Buckminster Fuller dreamed of doming cities. The same geometry appears in carbon molecules called fullerenes - a 60-atom soccer ball named after him.",
                "exploration": "Design a structure using only triangles. How does it compare in stability to one using squares? What can't you build with triangles alone?",
                "tags": ["geodesic", "Fuller", "triangles", "architecture"]
            },
        ]

        for i in range(count):
            template = design_templates[i % len(design_templates)]
            items.append(CreativeMathItem(
                title=template["title"],
                content=template["content"],
                exploration=template["exploration"],
                category="design",
                tags=template["tags"]
            ))

        return items[:count]


def create_creative_math_dataset(
    output_path: str = "data/creative_math_rag.json",
    count: int = 500,
    seed: int = 42,
) -> CreativeMathDataset:
    """
    Generate and save a creative math RAG dataset.

    Args:
        output_path: Where to save the dataset
        count: Number of items to generate
        seed: Random seed for reproducibility

    Returns:
        The generated dataset
    """
    dataset = CreativeMathDataset.generate(count=count, seed=seed)
    dataset.save(output_path)
    return dataset


# CLI support
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate Creative Math RAG Dataset")
    parser.add_argument("--count", type=int, default=500, help="Number of items")
    parser.add_argument("--output", type=str, default="data/creative_math_rag.json", help="Output path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    dataset = create_creative_math_dataset(
        output_path=args.output,
        count=args.count,
        seed=args.seed,
    )

    # Print sample
    print("\n" + "=" * 60)
    print("SAMPLE CREATIVE MATH ITEMS")
    print("=" * 60)

    categories = ["patterns", "golden_ratio", "math_art", "math_stories", "wonder", "design"]
    for cat in categories:
        cat_items = dataset.get_by_category(cat)
        if cat_items:
            print(f"\n--- {cat.upper()} ---")
            item = cat_items[0]
            print(f"Title: {item.title}")
            print(f"Content: {item.content[:150]}...")
            print(f"Tags: {', '.join(item.tags)}")
