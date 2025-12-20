"""
Science & Physics Corpus Builder
=================================

Generates 50 documents covering physics (classical and modern), chemistry,
astronomy, and earth science topics.
"""

from typing import List
from .base import CorpusBuilder, DocumentSpec


class ScienceCorpusBuilder(CorpusBuilder):
    """Builder for Science & Physics corpus."""

    @property
    def corpus_id(self) -> str:
        return "science"

    @property
    def description(self) -> str:
        return "Science and Physics from classical mechanics to cosmology"

    @property
    def domain(self) -> str:
        return "science"

    def build_documents(self) -> List[DocumentSpec]:
        docs = []

        # Classical Physics (docs 1-10)
        docs.append(DocumentSpec(
            doc_id="sci_001",
            corpus_id=self.corpus_id,
            title="Newton's Laws of Motion",
            content="""Isaac Newton's three laws of motion, published in his Principia Mathematica in 1687, form the foundation of classical mechanics. These laws describe the relationship between the motion of an object and the forces acting upon it.

Newton's First Law, the Law of Inertia, states that an object at rest stays at rest, and an object in motion stays in motion with the same speed and direction, unless acted upon by an unbalanced force. This principle explains why passengers lurch forward when a car brakes suddenly—their bodies tend to continue moving forward while the car decelerates.

Newton's Second Law quantifies force: F = ma, where force equals mass times acceleration. This equation shows that the acceleration of an object is directly proportional to the net force acting on it and inversely proportional to its mass. A larger force produces greater acceleration, while a larger mass resists acceleration more.

Newton's Third Law states that for every action, there is an equal and opposite reaction. When you push against a wall, the wall pushes back with equal force. Rockets work by expelling gas downward; the reaction force propels the rocket upward.

These laws apply accurately at everyday speeds and scales. At velocities approaching the speed of light, Einstein's relativity becomes necessary. At atomic scales, quantum mechanics takes over. Nevertheless, Newtonian mechanics remains essential for engineering, from building bridges to launching spacecraft.""",
            metadata={"domain": "physics", "tags": ["newton", "mechanics", "force", "motion"], "difficulty": "basic", "focus": "classical-physics"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_002",
            corpus_id=self.corpus_id,
            title="Gravity: The Universal Force",
            content="""Gravity is the fundamental force of attraction between all objects with mass. It keeps planets in orbit, holds galaxies together, and gives us weight on Earth. Understanding gravity has been central to physics from Newton to Einstein.

Newton's Law of Universal Gravitation, published in 1687, states that every mass attracts every other mass with a force proportional to the product of their masses and inversely proportional to the square of the distance between them: F = G(m₁m₂)/r². The gravitational constant G is approximately 6.674 × 10⁻¹¹ N⋅m²/kg².

On Earth's surface, gravitational acceleration (g) is approximately 9.8 m/s². This means all objects, regardless of mass, fall at the same rate in a vacuum—a fact demonstrated by Apollo 15 astronauts who dropped a hammer and feather on the Moon, where both hit the surface simultaneously.

Einstein's General Theory of Relativity (1915) revolutionized our understanding of gravity. Rather than a force, Einstein described gravity as the curvature of spacetime caused by mass and energy. Massive objects bend spacetime around them, and other objects follow curved paths through this warped geometry.

General relativity predicts phenomena like gravitational time dilation (clocks run slower in stronger gravitational fields), gravitational lensing (light bending around massive objects), and gravitational waves (ripples in spacetime from accelerating masses). The 2015 detection of gravitational waves by LIGO confirmed a century-old prediction.""",
            metadata={"domain": "physics", "tags": ["gravity", "newton", "einstein", "relativity"], "difficulty": "intermediate", "focus": "classical-physics"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_003",
            corpus_id=self.corpus_id,
            title="Energy: Conservation and Transformation",
            content="""Energy is the capacity to do work, and it exists in many forms: kinetic, potential, thermal, electrical, chemical, nuclear, and radiant. The Law of Conservation of Energy states that energy cannot be created or destroyed, only transformed from one form to another.

Kinetic energy is the energy of motion, given by KE = ½mv², where m is mass and v is velocity. A moving car, a flying ball, and flowing water all possess kinetic energy. The faster an object moves, the more kinetic energy it has—and this increases with the square of velocity.

Potential energy is stored energy due to position or configuration. Gravitational potential energy (PE = mgh) depends on height above a reference point. A ball held above the ground has potential energy that converts to kinetic energy as it falls. Elastic potential energy is stored in stretched or compressed springs.

Thermal energy is the kinetic energy of atoms and molecules in random motion. Temperature measures the average kinetic energy of particles. Heat is the transfer of thermal energy from hotter to cooler objects.

Chemical energy is stored in molecular bonds. When wood burns or food is digested, chemical energy transforms into thermal and other forms. Nuclear energy, released in fission or fusion, comes from changes in atomic nuclei.

The First Law of Thermodynamics formalizes energy conservation: the change in internal energy of a system equals heat added minus work done by the system. Power, measured in watts, is the rate of energy transfer or transformation.""",
            metadata={"domain": "physics", "tags": ["energy", "conservation", "kinetic", "potential"], "difficulty": "basic", "focus": "classical-physics"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_004",
            corpus_id=self.corpus_id,
            title="Thermodynamics: Heat and Entropy",
            content="""Thermodynamics is the branch of physics dealing with heat, work, temperature, and energy transfer. Its laws govern everything from engines to refrigerators to the fate of the universe.

The Zeroth Law establishes thermal equilibrium: if two systems are each in thermal equilibrium with a third system, they are in equilibrium with each other. This principle justifies the use of thermometers.

The First Law, conservation of energy, states that the internal energy change of a system equals heat added minus work done: ΔU = Q - W. This law prohibits perpetual motion machines of the first kind—devices that create energy from nothing.

The Second Law introduces entropy, a measure of disorder or randomness. In any spontaneous process, the total entropy of an isolated system always increases. Heat flows naturally from hot to cold, not the reverse. This law explains why you can't unscramble an egg or build a perfectly efficient engine.

The efficiency of heat engines is limited by the Carnot efficiency: η = 1 - T_cold/T_hot, where temperatures are in Kelvin. No engine operating between two temperatures can be more efficient than a Carnot engine.

The Third Law states that as temperature approaches absolute zero (0 K or -273.15°C), entropy approaches a minimum value. Absolute zero is unattainable, though scientists have cooled materials to within billionths of a degree.

Entropy increase drives the "arrow of time"—the asymmetry between past and future. The heat death of the universe, when maximum entropy is reached, represents the ultimate thermodynamic equilibrium.""",
            metadata={"domain": "physics", "tags": ["thermodynamics", "entropy", "heat", "temperature"], "difficulty": "intermediate", "focus": "classical-physics"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_005",
            corpus_id=self.corpus_id,
            title="Waves: Oscillations and Wave Properties",
            content="""Waves are disturbances that transfer energy through a medium or space without transferring matter. They are fundamental to understanding sound, light, and many other phenomena.

Waves are characterized by several properties. Wavelength (λ) is the distance between successive crests or troughs. Frequency (f) is the number of wave cycles per second, measured in hertz (Hz). Amplitude is the maximum displacement from equilibrium. The wave equation relates these: v = fλ, where v is wave speed.

Mechanical waves require a medium to travel through. Transverse waves, like those on a string, oscillate perpendicular to the direction of travel. Longitudinal waves, like sound, oscillate parallel to travel direction. Water waves combine both types.

Electromagnetic waves, including light, radio waves, and X-rays, need no medium—they can travel through vacuum. All electromagnetic waves travel at the speed of light (c ≈ 3 × 10⁸ m/s) in vacuum.

Wave behaviors include reflection (bouncing off surfaces), refraction (bending when entering a new medium), diffraction (bending around obstacles), and interference (waves combining constructively or destructively). Standing waves form when waves reflect and interfere, creating fixed nodes and antinodes.

The Doppler effect describes frequency changes when source and observer move relative to each other. An approaching ambulance siren sounds higher-pitched; a receding one sounds lower. This effect applies to all waves and is used in radar, medical ultrasound, and measuring the expansion of the universe.""",
            metadata={"domain": "physics", "tags": ["waves", "frequency", "wavelength", "oscillation"], "difficulty": "intermediate", "focus": "classical-physics"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_006",
            corpus_id=self.corpus_id,
            title="Sound: Acoustics and Hearing",
            content="""Sound is a mechanical wave that propagates through matter as a series of compressions and rarefactions. It requires a medium—sound cannot travel through vacuum. The study of sound is called acoustics.

Sound waves are longitudinal: air molecules oscillate parallel to the direction of wave travel. When you speak, your vocal cords vibrate, creating pressure variations that propagate outward. These pressure waves enter the ear, vibrate the eardrum, and are interpreted by the brain as sound.

The speed of sound depends on the medium. In air at 20°C, sound travels at approximately 343 m/s. It moves faster in liquids (about 1,500 m/s in water) and faster still in solids (about 5,000 m/s in steel). Temperature affects sound speed—warmer air transmits sound faster.

Frequency determines pitch: higher frequencies sound higher-pitched. Humans can typically hear frequencies from 20 Hz to 20,000 Hz. Below 20 Hz is infrasound; above 20,000 Hz is ultrasound. Ultrasound is used in medical imaging and cleaning applications.

Amplitude determines loudness, measured in decibels (dB). The decibel scale is logarithmic: 10 dB increase represents a tenfold increase in sound intensity. Normal conversation is about 60 dB; a rock concert can exceed 110 dB. Prolonged exposure to sounds above 85 dB can cause hearing damage.

Resonance occurs when a system oscillates at its natural frequency. Musical instruments exploit resonance—a guitar body amplifies string vibrations at certain frequencies. The shattering of glass by a singer's voice demonstrates dramatic resonance effects.""",
            metadata={"domain": "physics", "tags": ["sound", "acoustics", "waves", "frequency"], "difficulty": "basic", "focus": "classical-physics"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_007",
            corpus_id=self.corpus_id,
            title="Light and Optics",
            content="""Light is electromagnetic radiation visible to the human eye, with wavelengths between approximately 380 and 700 nanometers. Optics is the study of light's behavior and properties.

The nature of light puzzled scientists for centuries. Newton favored a particle (corpuscular) theory, while Huygens proposed waves. Young's double-slit experiment (1801) demonstrated interference patterns, confirming wave behavior. Later, Einstein's explanation of the photoelectric effect revealed light's particle nature. Modern physics accepts wave-particle duality: light behaves as waves in some experiments and particles (photons) in others.

When light encounters matter, it may be reflected, absorbed, or transmitted. The law of reflection states that the angle of incidence equals the angle of reflection. Mirrors exploit this principle.

Refraction is the bending of light when passing between media with different optical densities. Snell's Law describes this: n₁sinθ₁ = n₂sinθ₂, where n is the refractive index. Refraction causes swimming pools to look shallower than they are and creates rainbows when sunlight passes through water droplets.

Lenses use refraction to focus or disperse light. Convex lenses converge light and are used in magnifying glasses and cameras. Concave lenses diverge light and correct nearsightedness. The human eye is a remarkable optical system with a flexible lens that changes shape to focus on objects at different distances.

Dispersion separates white light into its component colors because different wavelengths refract by different amounts. Prisms and rainbows demonstrate dispersion. Fiber optics exploits total internal reflection to transmit light signals over long distances.""",
            metadata={"domain": "physics", "tags": ["light", "optics", "refraction", "reflection"], "difficulty": "intermediate", "focus": "classical-physics"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_008",
            corpus_id=self.corpus_id,
            title="Electricity: Charges and Currents",
            content="""Electricity involves the presence and flow of electric charge. It is one of the fundamental forces of nature and underlies much of modern technology, from lighting to computers.

Electric charge is a property of matter. Protons carry positive charge; electrons carry negative charge. Like charges repel; opposite charges attract. The unit of charge is the coulomb (C). An electron has a charge of approximately -1.6 × 10⁻¹⁹ C.

Coulomb's Law describes the force between charges: F = k(q₁q₂)/r², where k is Coulomb's constant (about 9 × 10⁹ N⋅m²/C²). The electric field (E) around a charge describes the force per unit charge that another charge would experience.

Electric current is the flow of charge, measured in amperes (A). One ampere equals one coulomb per second. In metals, current consists of moving electrons. Conventional current, defined before the electron was discovered, flows from positive to negative—opposite to electron flow.

Voltage (potential difference) is the "pressure" that drives current, measured in volts (V). Resistance opposes current flow, measured in ohms (Ω). Ohm's Law relates these: V = IR. Power in electrical circuits is P = IV.

Circuits may be series (components in sequence) or parallel (components on separate branches). In series circuits, current is the same everywhere; voltages add. In parallel circuits, voltage is the same across branches; currents add.

Static electricity involves charge accumulation. Lightning is a dramatic discharge of static electricity between clouds and ground, with peak currents of about 30,000 amperes.""",
            metadata={"domain": "physics", "tags": ["electricity", "charge", "current", "voltage"], "difficulty": "intermediate", "focus": "classical-physics"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_009",
            corpus_id=self.corpus_id,
            title="Magnetism and Electromagnetism",
            content="""Magnetism is a force produced by moving electric charges. Electricity and magnetism are fundamentally connected, unified in Maxwell's equations as electromagnetism—one of the four fundamental forces of nature.

Magnets have north and south poles. Like poles repel; opposite poles attract. Unlike electric charges, magnetic poles always occur in pairs—cutting a magnet in half produces two smaller magnets, each with both poles. This suggests that magnetism arises from circulating currents at the atomic level.

Moving charges create magnetic fields. A current-carrying wire generates a magnetic field circling around it. An electromagnet—a coil of wire around an iron core—produces strong, controllable magnetic fields. Electromagnets power everything from doorbells to MRI machines.

A magnetic field exerts force on moving charges. This principle operates electric motors: current-carrying coils in a magnetic field experience forces that cause rotation. The right-hand rule determines force direction: point fingers in current direction, curl toward field direction, and thumb points in force direction.

Faraday's Law of electromagnetic induction states that a changing magnetic field induces an electric current. This principle underlies electric generators, which convert mechanical energy to electrical energy, and transformers, which change voltage levels.

Maxwell's equations, completed in 1865, unified electricity and magnetism and predicted electromagnetic waves traveling at the speed of light. This revealed that light itself is an electromagnetic wave, connecting optics to electromagnetism. Heinrich Hertz confirmed these waves experimentally in 1887, leading to radio technology.""",
            metadata={"domain": "physics", "tags": ["magnetism", "electromagnetism", "maxwell", "induction"], "difficulty": "intermediate", "focus": "classical-physics"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_010",
            corpus_id=self.corpus_id,
            title="The Electromagnetic Spectrum",
            content="""The electromagnetic spectrum encompasses all electromagnetic radiation, from low-frequency radio waves to high-frequency gamma rays. Visible light occupies only a tiny portion of this vast spectrum.

All electromagnetic waves travel at the speed of light in vacuum (c ≈ 3 × 10⁸ m/s) and consist of oscillating electric and magnetic fields perpendicular to each other and to the direction of travel. They differ in wavelength and frequency, related by c = fλ.

Radio waves have the longest wavelengths (meters to kilometers) and lowest frequencies. They carry broadcast signals, enable Wi-Fi and cellular communication, and are used in radar. Radio telescopes detect these waves from cosmic sources.

Microwaves (wavelengths of millimeters to centimeters) heat food by exciting water molecules. They're also used in telecommunications and weather radar.

Infrared radiation (wavelengths of 700 nm to 1 mm) is felt as heat. Thermal imaging cameras detect infrared from warm objects. TV remotes use infrared signals.

Visible light (380-700 nm) is the narrow band our eyes detect. Different wavelengths appear as different colors, from red (longest) to violet (shortest).

Ultraviolet radiation (10-380 nm) from the Sun causes sunburn and skin cancer but also enables vitamin D synthesis. UV is used for sterilization.

X-rays (0.01-10 nm) penetrate soft tissue but are absorbed by bone, enabling medical imaging. They're also used in airport security and materials analysis.

Gamma rays, with the shortest wavelengths and highest energies, are produced by nuclear reactions and cosmic events. They can kill cancer cells in radiation therapy but can also cause cancer.""",
            metadata={"domain": "physics", "tags": ["electromagnetic-spectrum", "radiation", "light", "waves"], "difficulty": "basic", "focus": "classical-physics"}
        ))

        # Modern Physics (docs 11-18)
        docs.append(DocumentSpec(
            doc_id="sci_011",
            corpus_id=self.corpus_id,
            title="Special Relativity: Space, Time, and Speed of Light",
            content="""Albert Einstein's Special Theory of Relativity, published in 1905, revolutionized our understanding of space, time, and motion. It is based on two postulates: the laws of physics are the same in all inertial reference frames, and the speed of light in vacuum is constant for all observers regardless of their motion.

These seemingly simple principles have profound consequences. Time dilation means that moving clocks run slower than stationary ones. This effect, though negligible at everyday speeds, becomes significant as velocity approaches the speed of light. Muons created in the upper atmosphere by cosmic rays, for example, reach Earth's surface because time passes more slowly in their reference frame.

Length contraction means that objects appear shorter in the direction of motion when moving at high speeds. A spaceship traveling at 90% of light speed would appear about 44% shorter to a stationary observer.

The famous equation E = mc² expresses mass-energy equivalence: mass and energy are interchangeable, related by the speed of light squared. A small amount of mass contains enormous energy. This principle underlies nuclear power and nuclear weapons, where tiny mass differences release tremendous energy.

Nothing with mass can reach or exceed the speed of light. As an object accelerates, its relativistic mass increases, requiring ever more energy for further acceleration. Reaching light speed would require infinite energy.

Special relativity has been confirmed by countless experiments, from particle accelerators to GPS satellites, which must account for relativistic time dilation to maintain accuracy.""",
            metadata={"domain": "physics", "tags": ["relativity", "einstein", "speed-of-light", "time-dilation"], "difficulty": "intermediate", "focus": "modern-physics"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_012",
            corpus_id=self.corpus_id,
            title="General Relativity: Gravity as Curved Spacetime",
            content="""Einstein's General Theory of Relativity, published in 1915, extended special relativity to include gravity and acceleration. Its central insight is that gravity is not a force but a curvature of spacetime caused by mass and energy.

In general relativity, massive objects curve the fabric of spacetime around them. Other objects, including light, follow the straightest possible paths (geodesics) through this curved geometry. What we perceive as gravitational attraction is actually objects following curved paths through warped spacetime.

The Einstein field equations describe how matter and energy determine spacetime curvature. These complex tensor equations relate the geometry of spacetime (described by the Einstein tensor) to the distribution of matter and energy (described by the stress-energy tensor).

General relativity makes predictions beyond Newtonian gravity. It explains the precession of Mercury's orbit, which Newton's theory could not fully account for. It predicts gravitational lensing—light bending around massive objects—confirmed dramatically during the 1919 solar eclipse and now routinely observed in images of distant galaxies.

Gravitational time dilation means clocks run slower in stronger gravitational fields. GPS satellites, orbiting where gravity is weaker, experience time passing faster than on Earth's surface. Without relativistic corrections, GPS would accumulate errors of kilometers per day.

General relativity predicts gravitational waves—ripples in spacetime from accelerating masses—and black holes, regions where spacetime curvature becomes so extreme that nothing, not even light, can escape. Both predictions have been spectacularly confirmed: gravitational waves were detected by LIGO in 2015, and black holes have been imaged by the Event Horizon Telescope.""",
            metadata={"domain": "physics", "tags": ["general-relativity", "einstein", "spacetime", "black-holes"], "difficulty": "advanced", "focus": "modern-physics"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_013",
            corpus_id=self.corpus_id,
            title="Quantum Mechanics: The Physics of the Very Small",
            content="""Quantum mechanics describes the behavior of matter and energy at atomic and subatomic scales, where classical physics fails. Developed in the early 20th century, it reveals a world fundamentally different from everyday experience.

Max Planck introduced quantization in 1900, proposing that energy is emitted in discrete packets (quanta), not continuously. Einstein extended this to light, proposing that light consists of particles called photons, each with energy E = hf, where h is Planck's constant.

Wave-particle duality, demonstrated by the double-slit experiment, shows that particles like electrons exhibit wave-like interference patterns. Conversely, light exhibits particle-like behavior in the photoelectric effect. Matter and energy have both wave and particle properties, with wavelength given by de Broglie's equation: λ = h/p.

Heisenberg's Uncertainty Principle states that certain pairs of properties, like position and momentum, cannot both be precisely known simultaneously. The more precisely you know one, the less precisely you can know the other. This is not a limitation of measurement but a fundamental property of nature.

The Schrödinger equation describes how the quantum state (wave function) of a system evolves over time. The wave function gives probability amplitudes; its square gives the probability of finding a particle in a particular state or location.

Quantum superposition allows particles to exist in multiple states simultaneously until measured. The famous thought experiment of Schrödinger's cat illustrates the strange implications. Entanglement links particles such that measuring one instantly affects the other, regardless of distance—what Einstein called "spooky action at a distance."""",
            metadata={"domain": "physics", "tags": ["quantum-mechanics", "wave-particle", "uncertainty", "superposition"], "difficulty": "advanced", "focus": "modern-physics"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_014",
            corpus_id=self.corpus_id,
            title="Atomic Structure and the Quantum Model",
            content="""The atom, once thought indivisible, has a rich internal structure understood through quantum mechanics. The modern atomic model represents one of the triumphs of 20th-century physics.

Ernest Rutherford's 1911 gold foil experiment revealed that atoms have tiny, dense, positively charged nuclei surrounded by electrons. But classical physics could not explain atomic stability—orbiting electrons should radiate energy and spiral into the nucleus.

Niels Bohr proposed in 1913 that electrons occupy discrete orbits with specific energies. They can jump between orbits by absorbing or emitting photons of exactly the right energy. This explained atomic emission spectra—the characteristic lines of light emitted by heated elements.

The quantum mechanical model, developed in the 1920s, replaced Bohr's orbits with orbitals—probability distributions showing where electrons are likely to be found. Electrons don't have precise paths; instead, they exist as probability clouds around the nucleus.

Quantum numbers describe electron states: the principal quantum number (n) indicates energy level, the angular momentum quantum number (l) describes orbital shape, the magnetic quantum number (m) specifies orbital orientation, and the spin quantum number describes intrinsic angular momentum.

The Pauli Exclusion Principle states that no two electrons in an atom can have identical quantum numbers. This explains electron configuration and the structure of the periodic table. The aufbau principle, Hund's rule, and shielding effects determine how electrons fill orbitals.

Understanding atomic structure enables technologies from lasers to semiconductors and explains chemical bonding, spectroscopy, and the properties of materials.""",
            metadata={"domain": "physics", "tags": ["atomic-structure", "quantum", "orbitals", "electron"], "difficulty": "intermediate", "focus": "modern-physics"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_015",
            corpus_id=self.corpus_id,
            title="Nuclear Physics: The Atomic Nucleus",
            content="""Nuclear physics studies the atomic nucleus—a tiny, dense core containing protons and neutrons. Nuclear processes release enormous energy and have applications from power generation to medicine.

The nucleus is held together by the strong nuclear force, which overcomes the electromagnetic repulsion between positively charged protons. This force is extremely strong but very short-ranged, acting only over nuclear distances (about 10⁻¹⁵ meters).

Radioactive decay occurs when unstable nuclei transform by emitting particles or energy. Alpha decay releases helium nuclei (2 protons, 2 neutrons). Beta decay converts a neutron to a proton (or vice versa), emitting an electron or positron. Gamma decay releases high-energy photons without changing the nucleus's composition.

Half-life is the time for half of a radioactive sample to decay. Half-lives range from fractions of seconds to billions of years. Carbon-14's half-life of 5,730 years enables radiocarbon dating of archaeological artifacts.

Nuclear fission splits heavy nuclei (like uranium-235) into lighter fragments, releasing energy. When neutrons from one fission trigger additional fissions, a chain reaction occurs. Controlled chain reactions power nuclear reactors; uncontrolled reactions cause nuclear explosions.

Nuclear fusion combines light nuclei (like hydrogen isotopes) to form heavier ones, releasing even more energy per nucleon than fission. Fusion powers the Sun and stars. Achieving controlled fusion on Earth—potentially providing nearly limitless clean energy—remains a major technological challenge.

Applications of nuclear physics include medical imaging (PET scans), cancer treatment, smoke detectors, and studying material properties through neutron scattering.""",
            metadata={"domain": "physics", "tags": ["nuclear-physics", "radioactivity", "fission", "fusion"], "difficulty": "intermediate", "focus": "modern-physics"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_016",
            corpus_id=self.corpus_id,
            title="Particle Physics: The Standard Model",
            content="""Particle physics explores the fundamental constituents of matter and the forces between them. The Standard Model, developed in the 1970s, organizes all known elementary particles and three of the four fundamental forces.

Matter particles (fermions) come in two families: quarks and leptons. There are six types (flavors) of quarks: up, down, charm, strange, top, and bottom. Quarks carry fractional electric charges and combine to form hadrons. Protons contain two up quarks and one down quark; neutrons contain one up and two down quarks.

Leptons include electrons, muons, tau particles, and their associated neutrinos. Unlike quarks, leptons can exist independently. Neutrinos are extremely light, electrically neutral, and interact very weakly with matter—trillions pass through your body every second unnoticed.

Force-carrying particles (bosons) mediate interactions. Photons carry the electromagnetic force. W and Z bosons carry the weak force, responsible for radioactive decay. Gluons carry the strong force that binds quarks together and holds nuclei together.

The Higgs boson, discovered at CERN in 2012, is associated with the Higgs field, which gives particles their mass. This discovery confirmed a crucial prediction of the Standard Model and earned the 2013 Nobel Prize.

Antimatter is composed of antiparticles—identical to particles but with opposite charges. When matter and antimatter meet, they annihilate, converting their mass entirely to energy.

Despite its success, the Standard Model is incomplete. It doesn't include gravity, doesn't explain dark matter or dark energy, and doesn't explain why there's more matter than antimatter in the universe. Physicists seek a more complete theory, possibly involving supersymmetry or extra dimensions.""",
            metadata={"domain": "physics", "tags": ["particle-physics", "standard-model", "quarks", "higgs"], "difficulty": "advanced", "focus": "modern-physics"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_017",
            corpus_id=self.corpus_id,
            title="Quantum Computing and Quantum Information",
            content="""Quantum computing harnesses quantum mechanical phenomena—superposition and entanglement—to process information in ways impossible for classical computers. This emerging technology promises revolutionary advances in computation.

Classical computers use bits that are either 0 or 1. Quantum computers use qubits that can exist in superpositions of 0 and 1 simultaneously. When measured, a qubit collapses to either state, but during computation, it effectively processes both states at once.

With n qubits, a quantum computer can represent 2ⁿ states simultaneously. A 50-qubit quantum computer can represent more states than a classical computer could store in its memory. This quantum parallelism enables certain computations exponentially faster than classical approaches.

Entanglement links qubits so that the state of one instantly affects others, regardless of distance. Entangled qubits enable quantum algorithms that have no classical equivalent.

Shor's algorithm can factor large numbers exponentially faster than any known classical algorithm. This threatens current encryption systems, which rely on the difficulty of factoring. Grover's algorithm searches unsorted databases with quadratic speedup.

Quantum computers face significant challenges. Qubits are extremely fragile; environmental interactions cause decoherence, destroying quantum states. Error correction requires many physical qubits per logical qubit. Current quantum computers have tens to hundreds of noisy qubits; practical applications require thousands of error-corrected qubits.

Applications include drug discovery (simulating molecular interactions), optimization problems (logistics, financial modeling), machine learning, and cryptography. Quantum key distribution already enables theoretically unbreakable encryption.

Companies like IBM, Google, and startups race to build practical quantum computers. Google claimed "quantum supremacy" in 2019, performing a calculation in minutes that would take classical supercomputers thousands of years.""",
            metadata={"domain": "physics", "tags": ["quantum-computing", "qubits", "superposition", "entanglement"], "difficulty": "advanced", "focus": "modern-physics"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_018",
            corpus_id=self.corpus_id,
            title="Dark Matter and Dark Energy",
            content="""Dark matter and dark energy constitute about 95% of the universe's total mass-energy, yet their nature remains one of physics' greatest mysteries. Their existence is inferred from gravitational effects on visible matter.

Dark matter accounts for approximately 27% of the universe. Its presence was first suggested by Fritz Zwicky in the 1930s, who noticed that galaxies in clusters moved too fast to be held together by visible matter alone. Vera Rubin's observations of galaxy rotation curves in the 1970s provided compelling evidence: stars at galaxies' edges orbit too fast unless unseen mass provides additional gravity.

Dark matter interacts gravitationally but not electromagnetically—it doesn't emit, absorb, or reflect light. It forms halos around galaxies and influences large-scale cosmic structure. Without dark matter, galaxies wouldn't have formed as they did.

Candidates for dark matter include WIMPs (Weakly Interacting Massive Particles), axions, and primordial black holes. Despite decades of searching with underground detectors, particle accelerators, and space telescopes, dark matter particles remain undetected.

Dark energy, comprising about 68% of the universe, drives the accelerating expansion of the universe discovered in 1998 through observations of distant supernovae. This discovery earned the 2011 Nobel Prize.

The cosmological constant, originally introduced by Einstein, is one model for dark energy—a constant energy density throughout space. Alternatively, dark energy might be a dynamic field called quintessence.

Understanding dark matter and dark energy requires new physics beyond the Standard Model. Their nature could reveal fundamental truths about the universe, from its ultimate fate to the existence of new particles or dimensions.""",
            metadata={"domain": "physics", "tags": ["dark-matter", "dark-energy", "cosmology", "universe"], "difficulty": "advanced", "focus": "modern-physics"}
        ))

        # Chemistry (docs 19-30)
        docs.append(DocumentSpec(
            doc_id="sci_019",
            corpus_id=self.corpus_id,
            title="Atomic Theory and the Periodic Table",
            content="""Atomic theory explains matter as composed of atoms—tiny particles that combine to form all substances. The periodic table organizes elements by atomic structure, revealing patterns in their properties.

John Dalton proposed modern atomic theory in 1803: elements consist of indivisible atoms, atoms of an element are identical, compounds form from atoms in fixed ratios, and chemical reactions rearrange atoms. Later discoveries revealed that atoms have internal structure—electrons, protons, and neutrons—but Dalton's core insights remain valid.

The atomic number (Z) equals the number of protons and defines an element. Carbon has 6 protons, so its atomic number is 6. The mass number is protons plus neutrons. Isotopes of an element have the same proton count but different neutron counts; carbon-12 and carbon-14 are isotopes of carbon.

Dmitri Mendeleev created the periodic table in 1869, arranging elements by atomic mass and noting periodic patterns in properties. The modern table arranges elements by atomic number. Rows (periods) represent energy levels; columns (groups) share similar electron configurations and chemical properties.

Groups include alkali metals (Group 1), highly reactive elements with one valence electron; alkaline earth metals (Group 2) with two valence electrons; halogens (Group 17), reactive nonmetals; and noble gases (Group 18), with full outer shells and minimal reactivity.

Trends emerge across periods and groups. Atomic radius decreases across periods (more protons pull electrons closer) and increases down groups (more electron shells). Electronegativity and ionization energy generally increase across periods and decrease down groups. These trends explain reactivity patterns and bonding behavior.""",
            metadata={"domain": "chemistry", "tags": ["atoms", "periodic-table", "elements", "atomic-structure"], "difficulty": "basic", "focus": "chemistry"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_020",
            corpus_id=self.corpus_id,
            title="Chemical Bonding: Ionic and Covalent Bonds",
            content="""Chemical bonds hold atoms together to form molecules and compounds. The two main types—ionic and covalent bonds—arise from different electron interactions and produce substances with distinct properties.

Ionic bonds form when atoms transfer electrons. Metals, with few valence electrons, tend to lose them, becoming positive ions (cations). Nonmetals, needing a few electrons to complete their shells, tend to gain them, becoming negative ions (anions). The electrostatic attraction between oppositely charged ions creates the ionic bond.

Sodium chloride (table salt) is a classic ionic compound. Sodium loses one electron to become Na⁺; chlorine gains one to become Cl⁻. The ions arrange in a crystal lattice, maximizing attractions and minimizing repulsions. Ionic compounds typically have high melting points, are brittle, and conduct electricity when dissolved in water.

Covalent bonds form when atoms share electrons. This typically occurs between nonmetals. Each shared pair of electrons constitutes a single bond; atoms can share multiple pairs, forming double or triple bonds. In a water molecule, oxygen shares electrons with two hydrogen atoms.

The octet rule guides bonding: atoms tend to bond until they have eight electrons in their outer shell (two for hydrogen). Lewis structures depict electron sharing and lone pairs. VSEPR (Valence Shell Electron Pair Repulsion) theory predicts molecular shapes based on electron pair repulsions.

Polar covalent bonds occur when electrons are shared unequally due to differing electronegativities. Water is polar: oxygen pulls electrons closer, becoming slightly negative, while hydrogens become slightly positive. Polarity explains water's unique properties, including its role as a solvent.""",
            metadata={"domain": "chemistry", "tags": ["bonding", "ionic", "covalent", "molecules"], "difficulty": "intermediate", "focus": "chemistry"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_021",
            corpus_id=self.corpus_id,
            title="Chemical Reactions and Equations",
            content="""Chemical reactions transform substances by breaking and forming chemical bonds. They are described by balanced chemical equations showing reactants converting to products while conserving mass and atoms.

A balanced equation has equal numbers of each type of atom on both sides. In the combustion of methane: CH₄ + 2O₂ → CO₂ + 2H₂O, one carbon, four hydrogens, and four oxygens appear on each side. Coefficients indicate the number of molecules or moles of each substance.

Reaction types include synthesis (A + B → AB), decomposition (AB → A + B), single replacement (A + BC → AC + B), double replacement (AB + CD → AD + CB), and combustion (fuel + O₂ → CO₂ + H₂O).

Reaction rates depend on concentration, temperature, surface area, and catalysts. Higher temperatures increase molecular kinetic energy, leading to more frequent and energetic collisions. Catalysts provide alternative reaction pathways with lower activation energy without being consumed.

Equilibrium occurs when forward and reverse reaction rates are equal. At equilibrium, concentrations remain constant though reactions continue. Le Chatelier's Principle predicts that systems at equilibrium respond to stress by shifting to counteract it. Adding reactant shifts equilibrium toward products; removing product does likewise.

Enthalpy change (ΔH) indicates heat flow. Exothermic reactions release heat (negative ΔH); burning fuel is exothermic. Endothermic reactions absorb heat (positive ΔH); melting ice is endothermic. Entropy (ΔS) measures disorder change. The Gibbs free energy (ΔG = ΔH - TΔS) determines spontaneity: reactions with negative ΔG occur spontaneously.""",
            metadata={"domain": "chemistry", "tags": ["reactions", "equations", "equilibrium", "stoichiometry"], "difficulty": "intermediate", "focus": "chemistry"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_022",
            corpus_id=self.corpus_id,
            title="Acids, Bases, and pH",
            content="""Acids and bases are fundamental chemical categories with distinctive properties. The pH scale quantifies acidity and basicity, ranging from 0 (strongly acidic) through 7 (neutral) to 14 (strongly basic).

Arrhenius defined acids as substances that produce hydrogen ions (H⁺) in water and bases as substances that produce hydroxide ions (OH⁻). Brønsted-Lowry theory expanded this: acids are proton (H⁺) donors; bases are proton acceptors. Lewis theory is broadest: acids accept electron pairs; bases donate them.

Strong acids (HCl, H₂SO₄, HNO₃) completely dissociate in water. Weak acids (acetic acid, carbonic acid) only partially dissociate. Strong bases (NaOH, KOH) completely dissociate; weak bases (ammonia) only partially do.

The pH scale is logarithmic: each unit represents a tenfold change in hydrogen ion concentration. pH = -log[H⁺]. Pure water at 25°C has [H⁺] = 10⁻⁷ M, so pH = 7. Stomach acid has pH around 1.5; blood is about 7.4; household ammonia is about 11.

Neutralization reactions combine acids and bases to produce water and a salt: HCl + NaOH → NaCl + H₂O. The salt's properties depend on the acid and base strengths. Strong acid-strong base combinations produce neutral salts.

Buffer solutions resist pH changes when small amounts of acid or base are added. They contain a weak acid and its conjugate base (or weak base and conjugate acid). Blood is buffered by carbonic acid and bicarbonate, maintaining pH near 7.4—deviations can be life-threatening.

Acid-base chemistry is crucial in industry, biology, and the environment. Acid rain damages ecosystems; ocean acidification threatens marine life; pH control is essential in manufacturing, agriculture, and medicine.""",
            metadata={"domain": "chemistry", "tags": ["acids", "bases", "pH", "neutralization"], "difficulty": "intermediate", "focus": "chemistry"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_023",
            corpus_id=self.corpus_id,
            title="States of Matter and Phase Transitions",
            content="""Matter exists in distinct states—solid, liquid, gas, and plasma—each with characteristic properties. Phase transitions occur when energy changes cause matter to shift between states.

In solids, particles are tightly packed in fixed positions, vibrating but not moving freely. This gives solids definite shape and volume. Crystalline solids (salt, diamond) have ordered atomic arrangements; amorphous solids (glass, plastic) lack long-range order.

In liquids, particles are close but can move past each other. Liquids have definite volume but take the shape of their container. Intermolecular forces are weaker than in solids but still significant.

In gases, particles are far apart and move rapidly in random directions. Gases have neither definite shape nor volume, expanding to fill their container. The ideal gas law (PV = nRT) relates pressure, volume, temperature, and amount.

Plasma, the fourth state, consists of ionized gas with free electrons. It conducts electricity and responds to magnetic fields. Plasma comprises stars, lightning, and neon signs. Most visible matter in the universe is plasma.

Phase transitions include melting (solid to liquid), freezing (liquid to solid), vaporization (liquid to gas), condensation (gas to liquid), sublimation (solid to gas), and deposition (gas to solid). Each requires or releases energy—latent heat.

Phase diagrams show which state exists at given temperature and pressure. The triple point is where all three phases coexist. The critical point marks where the distinction between liquid and gas disappears, forming a supercritical fluid with unique properties used in extraction and cleaning processes.""",
            metadata={"domain": "chemistry", "tags": ["states-of-matter", "phases", "solid", "liquid", "gas"], "difficulty": "basic", "focus": "chemistry"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_024",
            corpus_id=self.corpus_id,
            title="Solutions and Solubility",
            content="""Solutions are homogeneous mixtures where one substance (solute) dissolves in another (solvent). Understanding solubility and solution properties is essential for chemistry, biology, and many technologies.

Water is called the "universal solvent" because of its polarity and ability to form hydrogen bonds. Polar and ionic substances generally dissolve well in water ("like dissolves like"). Nonpolar substances dissolve in nonpolar solvents like hexane.

Solubility is the maximum amount of solute that dissolves in a given amount of solvent at specific conditions. Saturated solutions contain the maximum solute; unsaturated can dissolve more; supersaturated temporarily hold more than normal, being unstable.

Temperature affects solubility differently for different substances. Most solid solutes become more soluble in water as temperature increases. Gases become less soluble at higher temperatures—warm soda releases more bubbles. Pressure significantly affects gas solubility (Henry's Law): higher pressure dissolves more gas.

Concentration can be expressed various ways. Molarity (M) is moles of solute per liter of solution. Molality (m) is moles of solute per kilogram of solvent. Percent composition indicates mass or volume percentages.

Colligative properties depend on solute particle concentration, not identity. They include vapor pressure lowering, boiling point elevation, freezing point depression, and osmotic pressure. Adding salt to water raises its boiling point and lowers its freezing point (why salt is used on icy roads). Osmotic pressure, crucial in biology, drives water movement across semipermeable membranes from low to high solute concentration.""",
            metadata={"domain": "chemistry", "tags": ["solutions", "solubility", "concentration", "colligative"], "difficulty": "intermediate", "focus": "chemistry"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_025",
            corpus_id=self.corpus_id,
            title="Electrochemistry: Oxidation and Reduction",
            content="""Electrochemistry studies chemical reactions involving electron transfer. These redox (reduction-oxidation) reactions power batteries, enable electroplating, and drive corrosion.

Oxidation is loss of electrons; reduction is gain of electrons. The mnemonic "OIL RIG" helps: Oxidation Is Loss, Reduction Is Gain. In any redox reaction, one species is oxidized while another is reduced—electrons are transferred, not created or destroyed.

Oxidation states (oxidation numbers) track electron distribution. In elemental form, oxidation state is 0. For ions, it equals the charge. Rules assign states in compounds: oxygen is usually -2, hydrogen usually +1. Changes in oxidation state indicate redox reactions.

Half-reactions separate oxidation and reduction: Zn → Zn²⁺ + 2e⁻ (oxidation) and Cu²⁺ + 2e⁻ → Cu (reduction). Combining these shows zinc displacing copper: Zn + Cu²⁺ → Zn²⁺ + Cu.

Electrochemical cells convert between chemical and electrical energy. Galvanic (voltaic) cells produce electricity from spontaneous redox reactions—batteries work this way. Electrolytic cells use electrical energy to drive non-spontaneous reactions—electroplating and electrolysis of water require external power.

Cell potential (voltage) measures the driving force for electron flow. Standard reduction potentials, measured against a hydrogen electrode reference, predict reaction spontaneity. Positive cell potential indicates spontaneous reaction.

Applications include batteries (from alkaline to lithium-ion), fuel cells (converting hydrogen and oxygen to electricity and water), corrosion prevention (using sacrificial anodes), and industrial processes (aluminum production, chloralkali process). Understanding electrochemistry is crucial for developing better energy storage technologies.""",
            metadata={"domain": "chemistry", "tags": ["electrochemistry", "redox", "oxidation", "batteries"], "difficulty": "intermediate", "focus": "chemistry"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_026",
            corpus_id=self.corpus_id,
            title="Organic Chemistry: Carbon Compounds",
            content="""Organic chemistry studies carbon-containing compounds. Carbon's unique ability to form four stable bonds and chain with itself enables the enormous diversity of organic molecules, from simple methane to complex proteins.

Carbon forms stable bonds with hydrogen, oxygen, nitrogen, sulfur, and halogens. Carbon-carbon bonds can be single (C-C), double (C=C), or triple (C≡C). Carbons can form straight chains, branched chains, and rings.

Hydrocarbons contain only carbon and hydrogen. Alkanes (methane, ethane, propane) have single bonds and are saturated. Alkenes have at least one double bond; alkynes have triple bonds. Aromatic compounds contain benzene rings—six carbons in a special bonding arrangement.

Functional groups determine organic molecule properties. Hydroxyl groups (-OH) characterize alcohols. Carbonyls (C=O) appear in aldehydes and ketones. Carboxyl groups (-COOH) make carboxylic acids. Amines contain nitrogen. Each functional group confers specific reactivity and physical properties.

Isomers are different compounds with the same molecular formula. Structural isomers have different connectivity. Stereoisomers have the same connectivity but different spatial arrangements. Enantiomers are non-superimposable mirror images—crucial in drug chemistry, where different enantiomers can have vastly different effects.

Organic reactions include substitution (one group replaces another), addition (atoms add across double bonds), elimination (atoms are removed, forming double bonds), and condensation (molecules combine, releasing water).

Organic chemistry underlies pharmaceuticals, polymers, fuels, foods, and biochemistry. Understanding organic molecules is essential for drug design, materials science, and understanding life itself.""",
            metadata={"domain": "chemistry", "tags": ["organic-chemistry", "carbon", "hydrocarbons", "functional-groups"], "difficulty": "intermediate", "focus": "chemistry"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_027",
            corpus_id=self.corpus_id,
            title="Polymers and Materials Science",
            content="""Polymers are large molecules built from repeating smaller units called monomers. Understanding polymer chemistry enables the creation of materials with tailored properties, from plastics to proteins.

Addition polymerization links monomers by adding across double bonds. Ethylene (CH₂=CH₂) polymerizes to polyethylene, used in plastic bags and bottles. Other addition polymers include polypropylene, polystyrene, and PVC (polyvinyl chloride).

Condensation polymerization links monomers by eliminating small molecules, typically water. Nylon forms when diamines react with dicarboxylic acids. Polyester forms from diols and diacids. These polymers can form fibers for textiles.

Polymer properties depend on structure. Linear polymers can be flexible or form crystalline regions. Branched polymers are typically less dense and more flexible. Cross-linked polymers form rigid networks—rubber is vulcanized by cross-linking with sulfur.

Thermoplastics soften when heated and can be remolded repeatedly. Thermosets form permanent networks when cured and cannot be remelted—they char when overheated. This distinction affects recycling and applications.

Natural polymers include cellulose (plant cell walls), starch (energy storage), proteins (amino acid polymers), and DNA (nucleotide polymers). Many synthetic polymers mimic or improve upon natural materials.

Materials science extends beyond polymers to metals, ceramics, and composites. Crystal structure, defects, and grain boundaries determine metal properties. Ceramics are hard but brittle. Composites combine materials for enhanced properties—fiberglass combines glass fibers with polymer matrix.

Sustainability concerns drive research into biodegradable polymers, polymer recycling, and bio-based plastics. Advanced materials enable technologies from lightweight aircraft to biomedical implants.""",
            metadata={"domain": "chemistry", "tags": ["polymers", "plastics", "materials", "monomers"], "difficulty": "intermediate", "focus": "chemistry"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_028",
            corpus_id=self.corpus_id,
            title="Biochemistry: The Chemistry of Life",
            content="""Biochemistry explores the chemical processes within living organisms. It bridges chemistry and biology, explaining how molecular interactions enable life's functions.

The four major biomolecules are carbohydrates, lipids, proteins, and nucleic acids. Each has distinct structures and functions essential for life.

Carbohydrates include sugars, starches, and cellulose. Simple sugars (monosaccharides) like glucose provide energy. Disaccharides (sucrose, lactose) contain two sugar units. Polysaccharides store energy (starch, glycogen) or provide structure (cellulose, chitin).

Lipids are hydrophobic molecules including fats, oils, phospholipids, and steroids. Triglycerides store energy efficiently. Phospholipids form cell membrane bilayers. Cholesterol, a steroid, is crucial for membrane fluidity and hormone synthesis.

Proteins, polymers of amino acids, perform diverse functions: catalysis (enzymes), structure (collagen), transport (hemoglobin), signaling (hormones), and immunity (antibodies). Protein structure has four levels: primary (sequence), secondary (local folding), tertiary (overall 3D shape), and quaternary (multi-subunit assembly).

Nucleic acids (DNA and RNA) store and transmit genetic information. DNA's double helix contains sequences of four bases (A, T, G, C) encoding genetic instructions. RNA carries messages and performs catalytic and regulatory functions.

Enzymes are biological catalysts, typically proteins, that accelerate reactions by factors of millions. They bind substrates at active sites, lowering activation energy. Enzyme activity is regulated by pH, temperature, inhibitors, and allosteric modulators.

Metabolism encompasses all chemical reactions in organisms. Catabolism breaks down molecules for energy; anabolism builds complex molecules. ATP (adenosine triphosphate) is the primary energy currency, coupling energy-releasing and energy-requiring reactions.""",
            metadata={"domain": "chemistry", "tags": ["biochemistry", "proteins", "carbohydrates", "metabolism"], "difficulty": "intermediate", "focus": "chemistry"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_029",
            corpus_id=self.corpus_id,
            title="Chemical Kinetics: Reaction Rates",
            content="""Chemical kinetics studies the rates of chemical reactions and the factors that influence them. Understanding kinetics is essential for controlling reactions in industrial processes, biological systems, and everyday applications.

Reaction rate measures how quickly reactant concentrations decrease or product concentrations increase over time. Rates are typically expressed in molarity per second (M/s). For a reaction A → B, rate = -d[A]/dt = d[B]/dt.

Rate laws express how rate depends on reactant concentrations. For a reaction aA + bB → products, the rate law has the form: rate = k[A]ᵐ[B]ⁿ. The exponents m and n are the reaction orders, determined experimentally. The rate constant k depends on temperature.

The overall reaction order is the sum of individual orders. A first-order reaction rate depends linearly on one reactant concentration. Second-order reactions may depend on one concentration squared or two concentrations linearly.

Collision theory explains reaction rates in terms of molecular collisions. Molecules must collide with sufficient energy (activation energy) and proper orientation to react. Transition state theory describes the activated complex formed at the reaction's energy maximum.

Factors affecting reaction rates include concentration (more molecules mean more collisions), temperature (higher kinetic energy means more effective collisions), surface area (more exposed reactant increases collision frequency), and catalysts (lower activation energy provides faster alternative pathway).

The Arrhenius equation relates rate constant to temperature: k = Ae^(-Ea/RT), where A is the pre-exponential factor, Ea is activation energy, R is the gas constant, and T is temperature. This explains why reactions roughly double in rate for each 10°C increase.

Catalysts provide tremendous practical benefits. Catalytic converters in cars speed reactions that convert harmful emissions to less harmful products. Enzymes enable biochemical reactions at body temperature that would otherwise require extreme conditions.""",
            metadata={"domain": "chemistry", "tags": ["kinetics", "reaction-rates", "catalysis", "activation-energy"], "difficulty": "intermediate", "focus": "chemistry"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_030",
            corpus_id=self.corpus_id,
            title="Environmental Chemistry: Pollution and Climate",
            content="""Environmental chemistry examines chemical processes in the environment and human impacts on them. It addresses critical issues including air pollution, water quality, and climate change.

Air pollution includes primary pollutants (emitted directly) and secondary pollutants (formed in atmosphere). Carbon monoxide, sulfur dioxide, and particulates are primary. Ozone and smog components are secondary, formed from reactions of nitrogen oxides and volatile organic compounds in sunlight.

The ozone layer, in the stratosphere, absorbs harmful UV radiation. Chlorofluorocarbons (CFCs), once used as refrigerants and propellants, release chlorine atoms that catalytically destroy ozone. The Montreal Protocol has reduced CFC use, and the ozone hole is slowly healing.

Water pollution includes organic pollutants (sewage, pesticides), inorganic pollutants (heavy metals, nitrates), and thermal pollution. Eutrophication occurs when excess nutrients cause algal blooms that deplete oxygen, killing aquatic life. Water treatment removes contaminants through physical, chemical, and biological processes.

Climate change is driven by greenhouse gases that absorb infrared radiation, warming Earth's surface. Carbon dioxide, the primary anthropogenic greenhouse gas, comes from fossil fuel combustion and deforestation. Methane, from agriculture and natural gas, is a more potent but shorter-lived greenhouse gas.

The carbon cycle involves exchanges between atmosphere, biosphere, oceans, and geosphere. Human activities have increased atmospheric CO₂ from about 280 ppm pre-industrially to over 420 ppm today. This causes ocean acidification as CO₂ dissolves to form carbonic acid.

Green chemistry aims to design products and processes that minimize hazardous substances. Principles include preventing waste, using renewable feedstocks, designing for degradation, and maximizing atom economy. Sustainable chemistry is essential for addressing environmental challenges.""",
            metadata={"domain": "chemistry", "tags": ["environmental-chemistry", "pollution", "climate-change", "greenhouse-gases"], "difficulty": "intermediate", "focus": "chemistry"}
        ))

        # Astronomy and Space Science (docs 31-42)
        docs.append(DocumentSpec(
            doc_id="sci_031",
            corpus_id=self.corpus_id,
            title="The Solar System: Structure and Formation",
            content="""Our solar system consists of the Sun, eight planets, dwarf planets, moons, asteroids, comets, and countless smaller bodies. It formed about 4.6 billion years ago from a collapsing cloud of gas and dust.

The solar system formed from a solar nebula—a rotating disk of gas and dust. Most material collected at the center, forming the Sun. The remaining disk material clumped into planetesimals, which collided and merged into protoplanets. Temperature gradients in the early nebula determined what materials could condense at various distances, shaping planetary composition.

The inner, rocky (terrestrial) planets—Mercury, Venus, Earth, and Mars—formed where temperatures were too high for volatile compounds to condense. They have solid surfaces, relatively thin atmospheres (if any), and few or no moons.

The outer, gas giant planets—Jupiter, Saturn, Uranus, and Neptune—formed beyond the frost line where water and other volatiles could condense. Jupiter and Saturn are primarily hydrogen and helium. Uranus and Neptune, the ice giants, contain more water, ammonia, and methane.

The asteroid belt, between Mars and Jupiter, contains rocky and metallic remnants from solar system formation. Jupiter's gravity prevented these materials from accreting into a planet. Ceres, the largest asteroid, is classified as a dwarf planet.

The Kuiper Belt, beyond Neptune, contains icy bodies including Pluto (reclassified as a dwarf planet in 2006). The Oort Cloud, a hypothetical spherical shell of icy objects at the solar system's outer reaches, is the source of long-period comets.

Understanding solar system formation helps interpret exoplanetary systems and the conditions for life elsewhere in the universe.""",
            metadata={"domain": "astronomy", "tags": ["solar-system", "planets", "formation", "sun"], "difficulty": "basic", "focus": "astronomy"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_032",
            corpus_id=self.corpus_id,
            title="The Sun: Our Star",
            content="""The Sun is a middle-aged, medium-sized star—a yellow dwarf (spectral type G2V). It contains 99.86% of the solar system's mass and provides the energy that drives Earth's climate and sustains life.

The Sun is composed primarily of hydrogen (about 74%) and helium (about 24%), with traces of heavier elements. Its mass is approximately 2 × 10³⁰ kg—about 330,000 times Earth's mass. Its radius is about 700,000 km—109 times Earth's radius.

Nuclear fusion in the Sun's core converts hydrogen to helium, releasing enormous energy. The core temperature exceeds 15 million Kelvin. Through the proton-proton chain reaction, four hydrogen nuclei fuse to form one helium nucleus, converting about 0.7% of the mass to energy according to E = mc².

Energy travels outward through the radiative zone (via photon absorption and re-emission) and the convective zone (via circulating plasma). It takes photons roughly 100,000 years to travel from the core to the surface.

The photosphere, the visible "surface," has a temperature of about 5,500°C. Sunspots—cooler, darker regions caused by intense magnetic fields—follow an 11-year activity cycle. The chromosphere and corona, visible during eclipses, extend outward with increasing temperature.

The solar wind, a stream of charged particles, flows outward at hundreds of kilometers per second. It creates the heliosphere, a vast bubble in interstellar space. Solar flares and coronal mass ejections can disrupt satellites and power grids on Earth.

The Sun is about 4.6 billion years old and will continue fusing hydrogen for another 5 billion years before expanding into a red giant and eventually becoming a white dwarf.""",
            metadata={"domain": "astronomy", "tags": ["sun", "star", "fusion", "solar-wind"], "difficulty": "intermediate", "focus": "astronomy"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_033",
            corpus_id=self.corpus_id,
            title="Earth's Moon: Origin and Characteristics",
            content="""The Moon is Earth's only natural satellite and the fifth-largest moon in the solar system. Its formation, composition, and influence on Earth have fascinated humanity for millennia.

The Moon likely formed about 4.5 billion years ago from debris created when a Mars-sized body (sometimes called Theia) collided with the early Earth. This giant impact hypothesis explains the Moon's composition (similar to Earth's mantle), its lack of a substantial iron core, and its current orbit.

The Moon's diameter is about 3,474 km—roughly one-quarter of Earth's. Its mass is about 1/81 of Earth's. Surface gravity is about 1/6 of Earth's, allowing astronauts to make their famous bounding leaps.

The Moon is tidally locked to Earth, meaning its rotation period equals its orbital period (about 27.3 days). We always see the same side—the near side. The far side, first photographed by the Soviet Luna 3 in 1959, has a thicker crust and fewer dark maria.

The lunar surface features dark maria (Latin for "seas")—ancient lava plains—and bright highlands heavily cratered by impacts. With no atmosphere or tectonic activity, craters persist for billions of years. The Apollo missions brought back 382 kg of lunar samples, revolutionizing our understanding.

The Moon's gravity causes ocean tides on Earth. As the Moon orbits, its gravitational pull creates tidal bulges on Earth's near and far sides. Tides have influenced marine life evolution and even early human activities.

Lunar phases result from the changing angle of sunlight as the Moon orbits Earth. From new moon through crescent, first quarter, gibbous, and full moon, the cycle repeats approximately every 29.5 days (synodic month).

Current plans aim to return humans to the Moon and establish sustainable presence, using it as a stepping stone for Mars exploration.""",
            metadata={"domain": "astronomy", "tags": ["moon", "lunar", "tides", "apollo"], "difficulty": "basic", "focus": "astronomy"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_034",
            corpus_id=self.corpus_id,
            title="The Planets: From Mercury to Neptune",
            content="""The eight planets of our solar system exhibit remarkable diversity, from scorching Mercury to frigid Neptune. Each offers insights into planetary formation and evolution.

Mercury, the smallest planet and closest to the Sun, has extreme temperature variations (−180°C to 430°C) due to lack of atmosphere. Its cratered surface resembles the Moon. Despite its small size, Mercury has a large iron core, possibly from a giant impact that stripped away outer layers.

Venus, similar in size to Earth, has a thick carbon dioxide atmosphere creating runaway greenhouse warming. Surface temperatures reach 465°C—hotter than Mercury. Dense clouds of sulfuric acid obscure the volcanic surface.

Earth, the third planet, is uniquely suited for life: liquid water, oxygen-rich atmosphere, protective magnetic field, and moderate temperatures. Plate tectonics recycle carbon and maintain climate stability.

Mars, the red planet, has a thin atmosphere and cold, dry surface. Evidence suggests ancient rivers and lakes; water ice exists at poles and underground. Mars is a prime target in the search for past or present extraterrestrial life.

Jupiter, the largest planet, could contain all other planets combined. Its famous Great Red Spot is a storm larger than Earth, raging for centuries. Jupiter has at least 95 moons, including the four large Galilean moons.

Saturn, with its spectacular ring system, is less dense than water. Its rings are composed of ice and rock particles ranging from tiny grains to house-sized chunks. Titan, Saturn's largest moon, has a thick atmosphere and hydrocarbon lakes.

Uranus rotates on its side, likely due to an ancient collision. Its blue-green color comes from methane. Neptune, the windiest planet, has the fastest sustained winds in the solar system. Its largest moon, Triton, orbits retrograde—suggesting capture from the Kuiper Belt.""",
            metadata={"domain": "astronomy", "tags": ["planets", "jupiter", "mars", "saturn"], "difficulty": "basic", "focus": "astronomy"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_035",
            corpus_id=self.corpus_id,
            title="Stars: Birth, Life, and Death",
            content="""Stars are massive balls of plasma fusing hydrogen into helium in their cores. Their life cycles, from formation to spectacular deaths, create the elements that make up planets and life.

Stars form in molecular clouds—dense regions of gas and dust. Gravity causes clumps to collapse. As material falls inward, it heats up. When core temperatures reach about 10 million Kelvin, hydrogen fusion ignites, and a star is born. This process takes millions of years.

A star's mass determines its fate. More massive stars burn hotter and bluer but live shorter lives. The Sun, a medium-mass star, will shine for about 10 billion years. A star 10 times more massive lives only tens of millions of years.

Stars spend most of their lives on the main sequence, fusing hydrogen to helium. The Hertzsprung-Russell diagram plots stars by luminosity versus temperature, revealing distinct categories: main sequence, giants, supergiants, and white dwarfs.

When hydrogen is exhausted, the core contracts and heats, igniting hydrogen fusion in a shell. The star expands into a red giant. For Sun-like stars, helium fusion creates carbon and oxygen. The outer layers drift away as a planetary nebula, leaving a white dwarf—an Earth-sized stellar remnant.

Massive stars fuse heavier elements in successive shells: carbon, neon, oxygen, silicon, and finally iron. Iron fusion absorbs energy rather than releasing it. The core collapses in seconds, triggering a supernova—an explosion briefly outshining entire galaxies.

Supernovae create and disperse elements heavier than iron. The core remnant becomes a neutron star (incredibly dense, with a tablespoon weighing billions of tons) or, for the most massive stars, a black hole. Every heavy element in your body was forged in ancient stars.""",
            metadata={"domain": "astronomy", "tags": ["stars", "stellar-evolution", "supernova", "fusion"], "difficulty": "intermediate", "focus": "astronomy"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_036",
            corpus_id=self.corpus_id,
            title="Galaxies: Islands of Stars",
            content="""Galaxies are vast systems of stars, gas, dust, and dark matter bound by gravity. The universe contains hundreds of billions of galaxies, each containing billions of stars.

Galaxies are classified by shape. Spiral galaxies, like our Milky Way, have flat disks with spiral arms and central bulges. Arms contain young, blue stars and star-forming regions; bulges contain older, redder stars. Barred spirals have a central bar structure.

Elliptical galaxies range from nearly spherical to elongated. They contain mostly older stars with little gas or dust, and minimal new star formation. They're often found in galaxy cluster centers and may form from galaxy mergers.

Irregular galaxies lack distinct shape, often due to gravitational interactions. The Magellanic Clouds, visible from the Southern Hemisphere, are irregular galaxies orbiting the Milky Way.

The Milky Way spans about 100,000 light-years in diameter and contains 100-400 billion stars. Our solar system lies about 26,000 light-years from the galactic center, orbiting once every 230 million years. A supermassive black hole, Sagittarius A*, with 4 million solar masses, resides at the center.

Galaxy clusters contain hundreds to thousands of galaxies bound by gravity. The Milky Way belongs to the Local Group, a small cluster including Andromeda and about 80 other galaxies. Superclusters contain multiple galaxy clusters. The largest known structures are galaxy filaments, with enormous voids between them.

Galaxies interact and merge over cosmic time. The Milky Way and Andromeda are approaching each other and will merge in about 4.5 billion years. Galaxy collisions trigger intense star formation and dramatic structural changes.""",
            metadata={"domain": "astronomy", "tags": ["galaxies", "milky-way", "spiral", "elliptical"], "difficulty": "intermediate", "focus": "astronomy"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_037",
            corpus_id=self.corpus_id,
            title="The Big Bang and Cosmic Evolution",
            content="""The Big Bang theory describes the origin and evolution of the universe from an incredibly hot, dense state about 13.8 billion years ago. It is supported by multiple lines of evidence and forms the foundation of modern cosmology.

The universe began from a singularity—a point of infinite density and temperature. In the first fraction of a second, the universe underwent inflation, expanding faster than light. As it cooled, fundamental forces separated, and quarks combined into protons and neutrons.

About 380,000 years after the Big Bang, the universe cooled enough for atoms to form. Light could finally travel freely, creating the cosmic microwave background (CMB)—thermal radiation filling space, discovered in 1965 by Penzias and Wilson. CMB observations provide a "baby picture" of the universe.

Three main observations support the Big Bang. First, Edwin Hubble's 1929 discovery that galaxies are receding—the universe is expanding. Run the expansion backward, and everything converges to a single point. Second, the CMB matches predictions for radiation from the early universe. Third, the observed abundances of light elements (hydrogen, helium, lithium) match theoretical predictions for primordial nucleosynthesis.

Dark matter and dark energy shape cosmic evolution. Dark matter's gravity helps galaxies form and hold together. Dark energy, discovered in 1998 through supernova observations, drives accelerating expansion. Together, they comprise about 95% of the universe's content.

The universe's fate depends on its total density. Current evidence suggests it will expand forever, with galaxies eventually receding beyond our observable horizon. In the distant future, stars will burn out, black holes will evaporate, and the universe may approach a cold, diffuse "heat death."""",
            metadata={"domain": "astronomy", "tags": ["big-bang", "cosmology", "universe", "cmb"], "difficulty": "intermediate", "focus": "astronomy"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_038",
            corpus_id=self.corpus_id,
            title="Black Holes: Gravity's Ultimate Triumph",
            content="""Black holes are regions of spacetime where gravity is so strong that nothing—not even light—can escape. They form when massive stars collapse and are among the most extreme objects in the universe.

When a massive star exhausts its fuel, its core collapses. If the core mass exceeds about 3 solar masses, no known force can halt the collapse. Matter compresses into a singularity—a point of infinite density (though quantum effects likely prevent true singularities).

The event horizon is the boundary beyond which escape is impossible. Its radius (the Schwarzschild radius) depends on mass: Rs = 2GM/c². For the Sun (if compressed), this would be about 3 km. For Earth, about 9 mm.

Black holes are detected by their effects on nearby matter. As material spirals into a black hole, it forms an accretion disk, heating to millions of degrees and emitting X-rays. Some black holes launch jets of plasma traveling near light speed.

Stellar-mass black holes form from collapsed stars and typically have 5-50 solar masses. Supermassive black holes, containing millions to billions of solar masses, reside in galactic centers. Their formation remains debated—they may grow from stellar-mass seeds through mergers and accretion.

In 2019, the Event Horizon Telescope captured the first image of a black hole—the supermassive black hole in galaxy M87. In 2020, Roger Penrose, Reinhard Genzel, and Andrea Ghez won the Nobel Prize for theoretical and observational work on black holes.

Hawking radiation, predicted by Stephen Hawking in 1974, suggests black holes slowly evaporate by emitting particles. This process is incredibly slow for astronomical black holes but has profound implications for physics, suggesting black holes aren't perfectly permanent.""",
            metadata={"domain": "astronomy", "tags": ["black-holes", "event-horizon", "gravity", "hawking"], "difficulty": "advanced", "focus": "astronomy"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_039",
            corpus_id=self.corpus_id,
            title="Exoplanets: Worlds Beyond Our Solar System",
            content="""Exoplanets are planets orbiting stars other than our Sun. Since the first confirmed discovery in 1992, thousands have been found, revolutionizing our understanding of planetary systems and the potential for life elsewhere.

The first exoplanet around a Sun-like star, 51 Pegasi b, was discovered in 1995 using the radial velocity method. This technique detects the star's wobble caused by an orbiting planet's gravitational tug. The wobble causes periodic Doppler shifts in the star's spectrum.

The transit method, used by NASA's Kepler mission, detects the slight dimming when a planet passes in front of its star. Kepler discovered over 2,600 confirmed exoplanets before retiring in 2018. The TESS mission continues the search, focusing on nearby stars.

Direct imaging, challenging because planets are much fainter than their stars, has captured images of a few large, young planets far from their stars. Gravitational microlensing detects planets when their gravity bends light from background stars.

Exoplanet diversity far exceeds our solar system. "Hot Jupiters" are gas giants orbiting extremely close to their stars. "Super-Earths" are rocky planets larger than Earth but smaller than Neptune. Some planets orbit in the habitable zone—where liquid water could exist on the surface.

The TRAPPIST-1 system, discovered in 2017, contains seven Earth-sized planets, three in the habitable zone. Proxima Centauri b, orbiting our nearest stellar neighbor, is also potentially habitable.

The James Webb Space Telescope (JWST), launched in 2021, can analyze exoplanet atmospheres for signs of water, carbon dioxide, and potentially biosignatures—chemicals that might indicate life. The search for Earth-like planets and possible extraterrestrial life continues to accelerate.""",
            metadata={"domain": "astronomy", "tags": ["exoplanets", "habitable-zone", "kepler", "transit"], "difficulty": "intermediate", "focus": "astronomy"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_040",
            corpus_id=self.corpus_id,
            title="Space Exploration: From Sputnik to Mars",
            content="""Space exploration has transformed humanity's understanding of the cosmos and our place in it. From the first satellite to plans for Mars colonies, the space age continues to push technological and human boundaries.

The Space Age began on October 4, 1957, when the Soviet Union launched Sputnik 1, the first artificial satellite. The Space Race between the US and USSR drove rapid advances. Yuri Gagarin became the first human in space on April 12, 1961. The US Apollo program landed 12 astronauts on the Moon between 1969 and 1972.

Robotic missions have explored every planet and many smaller bodies. The Voyager probes, launched in 1977, visited all four giant planets and continue sending data from interstellar space. Mars rovers—Sojourner, Spirit, Opportunity, Curiosity, and Perseverance—have explored the Martian surface for decades.

The Space Shuttle program (1981-2011) enabled reusable spacecraft and construction of the International Space Station (ISS). The ISS, continuously occupied since 2000, hosts experiments in microgravity and demonstrates long-duration spaceflight.

Private spaceflight has transformed the industry. SpaceX developed reusable rockets, dramatically reducing launch costs. Its Falcon 9 regularly delivers cargo and crew to the ISS. Blue Origin and other companies compete to expand access to space.

Current goals include returning humans to the Moon through NASA's Artemis program, establishing a sustainable lunar presence, and eventually sending humans to Mars. Mars missions face enormous challenges: the journey takes 6-9 months each way, radiation exposure is significant, and communication delays prevent real-time Earth control.

Space telescopes—Hubble, Chandra, James Webb—have revolutionized astronomy by observing above Earth's atmosphere. The search for extraterrestrial life, planetary defense against asteroids, and the long-term goal of becoming a multiplanetary species drive continued exploration.""",
            metadata={"domain": "astronomy", "tags": ["space-exploration", "nasa", "mars", "moon"], "difficulty": "basic", "focus": "astronomy"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_041",
            corpus_id=self.corpus_id,
            title="Astrobiology: The Search for Life in the Universe",
            content="""Astrobiology studies the origin, evolution, and distribution of life in the universe. It combines astronomy, biology, chemistry, and geology to explore whether life exists beyond Earth and how we might find it.

Life as we know it requires liquid water, organic molecules, and energy sources. These conditions may exist in many locations: Mars, Europa (Jupiter's moon with a subsurface ocean), Enceladus (Saturn's moon with geysers of water), and Titan (with its organic-rich atmosphere and hydrocarbon lakes).

The habitable zone—the region around a star where liquid water could exist on a planet's surface—is a key concept. However, subsurface oceans on icy moons show that habitable environments may exist far outside traditional habitable zones.

Extremophiles on Earth—organisms thriving in extreme conditions—expand our understanding of life's possibilities. Thermophiles survive near boiling temperatures. Psychrophiles thrive in freezing conditions. Radioresistant organisms survive intense radiation. These discoveries suggest life might survive in environments once thought uninhabitable.

Mars exploration focuses on finding evidence of past or present life. Perseverance is collecting samples for future return to Earth. Europa Clipper and potential lander missions will explore Jupiter's moon. Future missions may search for life in Enceladus's plumes.

SETI (Search for Extraterrestrial Intelligence) seeks signals from technological civilizations. Radio telescopes scan for artificial signals. The Drake Equation estimates the number of communicating civilizations, though many factors remain unknown.

The Fermi Paradox asks: if the universe is vast and old, where is everybody? Possible explanations range from the rarity of intelligence to the difficulty of interstellar communication to more sobering possibilities about civilization lifespans.

Discovery of extraterrestrial life, even microbial, would have profound scientific and philosophical implications, confirming that Earth is not unique in hosting life.""",
            metadata={"domain": "astronomy", "tags": ["astrobiology", "life", "seti", "extremophiles"], "difficulty": "intermediate", "focus": "astronomy"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_042",
            corpus_id=self.corpus_id,
            title="Telescopes and Astronomical Observation",
            content="""Telescopes are the primary tools of astronomy, collecting electromagnetic radiation to reveal the universe. From Galileo's simple refractor to orbiting observatories, telescopes have continuously expanded our cosmic horizons.

Optical telescopes gather visible light. Refractors use lenses; reflectors use mirrors. Reflecting telescopes dominate professional astronomy because mirrors can be made larger and don't suffer chromatic aberration (color-dependent focusing). The largest optical telescopes have mirrors over 10 meters across.

Adaptive optics compensate for atmospheric turbulence, which normally blurs ground-based images. Deformable mirrors adjust thousands of times per second to correct distortions, approaching the sharpness of space-based telescopes.

Space telescopes avoid atmospheric interference entirely. The Hubble Space Telescope, launched in 1990, has produced iconic images and transformative science. The James Webb Space Telescope (JWST), launched in 2021, observes in infrared with a 6.5-meter mirror, studying the earliest galaxies and exoplanet atmospheres.

Radio telescopes detect radio waves from cosmic sources. Dishes like the Green Bank Telescope and arrays like ALMA observe cold gas, pulsars, and the cosmic microwave background. Very Long Baseline Interferometry links distant telescopes to create virtual Earth-sized instruments.

X-ray and gamma-ray telescopes must orbit above the atmosphere, which absorbs these high-energy photons. Chandra X-ray Observatory and Fermi Gamma-ray Space Telescope study black holes, neutron stars, and cosmic explosions.

Interferometry combines signals from multiple telescopes to achieve the resolution of a much larger instrument. The Event Horizon Telescope, an Earth-sized virtual radio dish, imaged a black hole for the first time.

Future telescopes include the Extremely Large Telescope (39-meter mirror) and next-generation space observatories. Each advance reveals more of the universe's secrets, from nearby exoplanets to the most distant galaxies.""",
            metadata={"domain": "astronomy", "tags": ["telescopes", "hubble", "jwst", "observation"], "difficulty": "intermediate", "focus": "astronomy"}
        ))

        # Earth Science (docs 43-50)
        docs.append(DocumentSpec(
            doc_id="sci_043",
            corpus_id=self.corpus_id,
            title="Plate Tectonics: Earth's Dynamic Crust",
            content="""Plate tectonics describes the movement of Earth's lithosphere—the rigid outer shell—divided into plates that float on the underlying asthenosphere. This theory, developed in the 1960s, explains earthquakes, volcanoes, mountain formation, and continental drift.

Earth's lithosphere consists of about 15 major plates and numerous smaller ones. Plates include continental crust (thicker, less dense, older) and oceanic crust (thinner, denser, younger). The asthenosphere below is partially molten, allowing plates to move slowly—centimeters per year.

At divergent boundaries, plates move apart. Magma rises to fill the gap, creating new crust. Mid-ocean ridges, like the Mid-Atlantic Ridge, form this way. As crust spreads from ridges, it cools and thickens.

At convergent boundaries, plates collide. When oceanic crust meets continental crust, the denser oceanic plate subducts (dives under), forming deep trenches and volcanic arcs. The Pacific Ring of Fire results from subduction zones. When two continental plates collide, mountains form—the Himalayas are still rising from the India-Eurasia collision.

At transform boundaries, plates slide past each other horizontally. California's San Andreas Fault is a famous transform boundary between the Pacific and North American plates.

Continental drift, first proposed by Alfred Wegener in 1912, suggested continents were once joined. Matching fossils, rock types, and continental shapes supported this idea, but the mechanism was unclear until seafloor spreading was discovered.

Convection currents in the mantle, driven by heat from Earth's core, provide the driving force. Hot material rises at ridges, spreads laterally, cools, and sinks at subduction zones.

Plate tectonics recycles crust, influences climate by rearranging continents, and has created environments where life evolved. Earth's unique geological activity distinguishes it from other rocky planets.""",
            metadata={"domain": "earth-science", "tags": ["plate-tectonics", "geology", "earthquakes", "volcanoes"], "difficulty": "intermediate", "focus": "earth-science"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_044",
            corpus_id=self.corpus_id,
            title="Earthquakes: Causes and Effects",
            content="""Earthquakes are sudden releases of energy in Earth's crust, producing seismic waves that shake the ground. They occur most frequently along plate boundaries but can happen anywhere stress accumulates in rocks.

Most earthquakes result from movement along faults—fractures where rocks have moved relative to each other. Stress builds as plates push, pull, or slide past each other. When stress exceeds rock strength, rocks break or slip suddenly, releasing energy.

The focus (hypocenter) is where the earthquake originates, typically kilometers underground. The epicenter is the point on the surface directly above the focus. Shallow earthquakes (less than 70 km deep) generally cause more damage than deeper ones.

Seismic waves carry earthquake energy. Body waves travel through Earth's interior: P-waves (primary) are compressional and travel fastest; S-waves (secondary) are shear waves that cannot travel through liquids. Surface waves travel along Earth's surface and cause most damage.

Earthquake magnitude, measured on the moment magnitude scale (replacing the Richter scale), reflects total energy released. Each unit increase represents about 32 times more energy. The 2011 Japan earthquake (magnitude 9.1) released thousands of times more energy than a magnitude 6 earthquake.

Intensity measures ground shaking at specific locations using the Modified Mercalli Scale. Intensity depends on magnitude, distance, soil type, and building construction. Soft sediments amplify shaking.

Earthquake hazards include ground shaking, surface rupture, landslides, liquefaction (soil behaving like liquid), and tsunamis (if the seafloor shifts). Building codes, early warning systems, and emergency preparedness save lives.

Prediction remains elusive, but probabilistic hazard assessment identifies regions likely to experience significant earthquakes. The study of earthquakes also reveals Earth's interior structure through seismic wave behavior.""",
            metadata={"domain": "earth-science", "tags": ["earthquakes", "seismic", "faults", "hazards"], "difficulty": "intermediate", "focus": "earth-science"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_045",
            corpus_id=self.corpus_id,
            title="Volcanoes: Earth's Fiery Vents",
            content="""Volcanoes are openings in Earth's surface where molten rock (magma), gases, and ash can escape. They form at plate boundaries and hotspots, shaping landscapes and influencing climate.

Magma forms when mantle rock partially melts due to decreased pressure, increased temperature, or addition of water. Less dense than surrounding rock, magma rises through the crust. When it reaches the surface, it's called lava.

Volcano types depend on magma composition and eruption style. Shield volcanoes (like Hawaii's Mauna Loa) have gentle slopes from fluid basaltic lava that flows easily. Stratovolcanoes (like Mount Fuji and Mount St. Helens) are steep, built from alternating lava and ash layers, and prone to explosive eruptions. Cinder cones are small, steep-sided cones from ejected fragments.

Eruption style depends on magma viscosity and gas content. Low-viscosity magma allows gases to escape easily, producing effusive eruptions with flowing lava. High-viscosity magma traps gases until pressure builds explosively. Pyroclastic flows—superheated mixtures of gas, ash, and rock fragments—are among the deadliest volcanic hazards, racing downhill at hundreds of kilometers per hour.

Plate boundary volcanoes dominate the Pacific Ring of Fire. Subduction zones generate magma when water-rich oceanic crust descends and triggers melting. Divergent boundaries produce volcanoes at mid-ocean ridges. Hotspot volcanoes, like Hawaii and Yellowstone, form over mantle plumes independent of plate boundaries.

Volcanic hazards include lava flows, pyroclastic flows, lahars (volcanic mudflows), ash fall, and volcanic gases. Large eruptions can affect global climate—the 1815 Tambora eruption caused "the year without a summer" in 1816.

Volcanoes also create fertile soils, geothermal energy sources, and new land. Monitoring using seismometers, GPS, gas sensors, and satellites helps predict eruptions and save lives.""",
            metadata={"domain": "earth-science", "tags": ["volcanoes", "magma", "eruption", "lava"], "difficulty": "intermediate", "focus": "earth-science"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_046",
            corpus_id=self.corpus_id,
            title="The Atmosphere: Layers and Composition",
            content="""Earth's atmosphere is a thin layer of gases surrounding our planet, essential for life and climate. It protects us from harmful radiation, moderates temperatures, and provides the air we breathe.

The atmosphere is about 78% nitrogen, 21% oxygen, and 1% argon and other gases. Trace gases include carbon dioxide (about 0.04%, but increasing), water vapor (variable, 0-4%), and others. Despite being trace components, greenhouse gases significantly affect climate.

The troposphere, extending from the surface to about 12 km altitude, contains about 80% of atmospheric mass and all weather. Temperature decreases with altitude here. Most clouds and precipitation occur in the troposphere.

The stratosphere extends from about 12-50 km. It contains the ozone layer, which absorbs UV radiation. Temperature increases with altitude due to ozone absorption of UV. Commercial aircraft fly in the lower stratosphere to avoid weather.

The mesosphere (50-80 km) is where meteors burn up. The thermosphere (80-700 km) is extremely thin but very hot, with temperatures reaching 2,000°C due to absorption of solar radiation. The ionosphere, within this region, reflects radio waves and creates auroras.

The exosphere, above 700 km, gradually fades into space. Satellites orbit here, and atmospheric molecules can escape to space.

Atmospheric pressure decreases exponentially with altitude. At sea level, pressure is about 101 kPa (1 atmosphere). At 5 km altitude, it's about half this value. The tropopause height varies with latitude and season—higher at the equator and in summer.

The atmosphere circulates in large-scale patterns driven by solar heating and Earth's rotation. Hadley, Ferrel, and polar cells transfer heat from equator to poles, influencing climate zones and weather patterns.""",
            metadata={"domain": "earth-science", "tags": ["atmosphere", "air", "ozone", "troposphere"], "difficulty": "basic", "focus": "earth-science"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_047",
            corpus_id=self.corpus_id,
            title="Weather and Meteorology",
            content="""Weather is the short-term state of the atmosphere at a specific time and place, including temperature, humidity, precipitation, wind, and clouds. Meteorology studies atmospheric phenomena to understand and predict weather.

Solar radiation drives weather by heating Earth's surface unevenly. Differences in heating create pressure gradients, which drive winds. Air flows from high to low pressure, but Earth's rotation deflects it (Coriolis effect), creating curved wind patterns.

Air masses are large bodies of air with uniform temperature and humidity. They form over source regions—continental polar (cold, dry), maritime tropical (warm, moist), etc. When air masses meet, fronts form. Cold fronts occur when cold air pushes under warm air; warm fronts occur when warm air rises over cold air. Fronts bring changing weather and often precipitation.

Clouds form when moist air rises and cools to its dew point. Water vapor condenses on tiny particles (condensation nuclei). Cloud types include cumulus (puffy), stratus (layered), and cirrus (high, wispy). Cloud development indicates atmospheric stability and helps predict weather.

Precipitation occurs when water droplets or ice crystals in clouds grow large enough to fall. Rain, snow, sleet, and hail are precipitation types, depending on temperature profiles through the atmosphere.

Severe weather includes thunderstorms (with lightning, heavy rain, possibly hail and tornadoes), hurricanes (large rotating storms over warm oceans), and winter storms. Thunderstorms form in unstable air with moisture and a lifting mechanism. Hurricanes require warm ocean water (26°C+) to provide energy.

Weather forecasting uses observations from surface stations, weather balloons, satellites, and radar. Numerical weather prediction models simulate atmospheric physics on supercomputers. Forecast accuracy has improved dramatically, with 5-day forecasts now as accurate as 1-day forecasts were in 1980.""",
            metadata={"domain": "earth-science", "tags": ["weather", "meteorology", "storms", "forecasting"], "difficulty": "intermediate", "focus": "earth-science"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_048",
            corpus_id=self.corpus_id,
            title="Climate and Climate Systems",
            content="""Climate is the long-term average of weather conditions in a region, typically considered over 30 years. Climate systems involve complex interactions among atmosphere, oceans, ice, land, and life.

Climate zones reflect latitude, altitude, and proximity to oceans. Tropical climates near the equator are warm year-round with high rainfall. Deserts form in subtropical high-pressure zones. Temperate climates have distinct seasons. Polar climates are cold year-round.

Ocean currents redistribute heat globally. The Gulf Stream carries warm water from the tropics northward, warming Western Europe. The thermohaline circulation (global conveyor belt) moves water masses between ocean basins, influencing climate over centuries.

El Niño-Southern Oscillation (ENSO) is a periodic climate pattern in the tropical Pacific. During El Niño, warm water shifts eastward, affecting weather patterns globally—droughts in Australia, floods in South America, and altered hurricane patterns. La Niña brings opposite effects.

Climate has changed throughout Earth's history. Ice ages have come and gone, driven by Milankovitch cycles (variations in Earth's orbit and tilt). The last ice age ended about 12,000 years ago. Warm periods and ice ages have shaped evolution and human history.

Current climate change is primarily driven by human emissions of greenhouse gases, especially carbon dioxide from fossil fuel combustion. Global average temperature has increased about 1.1°C since pre-industrial times. Effects include rising sea levels, more extreme weather, shifting ecosystems, and ocean acidification.

Climate models simulate Earth's climate using fundamental physics. They project future climate under different emission scenarios. Limiting warming to 1.5°C or 2°C above pre-industrial levels requires rapid reduction in greenhouse gas emissions, as agreed in the Paris Agreement.""",
            metadata={"domain": "earth-science", "tags": ["climate", "global-warming", "ocean-currents", "el-nino"], "difficulty": "intermediate", "focus": "earth-science"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_049",
            corpus_id=self.corpus_id,
            title="The Oceans: Chemistry and Circulation",
            content="""Oceans cover about 71% of Earth's surface, containing 97% of Earth's water. They regulate climate, support vast ecosystems, and cycle nutrients essential for life.

Seawater is about 3.5% dissolved salts by weight, primarily sodium chloride (table salt). Other ions include magnesium, sulfate, calcium, and potassium. Salinity varies with evaporation, precipitation, and freshwater input from rivers.

Ocean structure is layered. The surface mixed layer (top 50-200 m) is warmed by sunlight and mixed by wind and waves. The thermocline below shows rapidly decreasing temperature with depth. The deep ocean is cold (1-4°C) and dark.

Ocean circulation operates on multiple scales. Surface currents, driven by wind and the Coriolis effect, form large gyres in each ocean basin. Gyres circulate clockwise in the Northern Hemisphere, counterclockwise in the Southern. Western boundary currents (like the Gulf Stream) are strong and narrow; eastern boundary currents are weak and broad.

The thermohaline circulation is driven by density differences from temperature and salinity variations. Cold, salty water in the North Atlantic sinks and flows south along the ocean floor. This deep water eventually upwells in other basins, taking roughly 1,000 years to complete the circuit.

Oceans absorb about 25% of human-emitted CO₂, reducing atmospheric warming but causing ocean acidification. Lower pH threatens shell-forming organisms and coral reefs. Oceans also absorb about 90% of the excess heat from global warming, causing thermal expansion and sea level rise.

Marine ecosystems range from sunlit surface waters to the deep seafloor. Phytoplankton produce about half of Earth's oxygen through photosynthesis. Ocean biodiversity rivals that of tropical rainforests. Overfishing, pollution, and climate change threaten these vital systems.""",
            metadata={"domain": "earth-science", "tags": ["oceans", "seawater", "currents", "marine"], "difficulty": "intermediate", "focus": "earth-science"}
        ))

        docs.append(DocumentSpec(
            doc_id="sci_050",
            corpus_id=self.corpus_id,
            title="Earth's Interior: Core, Mantle, and Crust",
            content="""Earth has a layered interior structure, revealed primarily through the study of seismic waves from earthquakes. Understanding Earth's interior explains surface features, magnetic field, and planetary evolution.

The crust is Earth's thin outer shell. Continental crust averages 35-40 km thick and is composed primarily of granite-like rocks. Oceanic crust is only 5-10 km thick and composed of denser basalt. Together, crust and upper mantle form the rigid lithosphere.

The mantle extends from the crust-mantle boundary (Moho) to about 2,900 km depth. It's composed primarily of silicate rocks rich in iron and magnesium. The upper mantle includes the partially molten asthenosphere, which allows plate movement. The lower mantle is solid but flows slowly over geological time.

The outer core, from 2,900-5,100 km depth, is liquid iron and nickel. Its flow, driven by convection, generates Earth's magnetic field through the dynamo effect. The magnetic field protects Earth from solar wind and cosmic radiation.

The inner core, from 5,100 km to Earth's center (6,371 km), is solid iron and nickel, despite temperatures over 5,000°C. Immense pressure prevents melting. The inner core is growing as the outer core slowly solidifies.

Seismic waves reveal this structure. P-waves travel through all materials; S-waves only through solids. The shadow zones—regions where certain waves don't arrive—indicate the liquid outer core. Wave velocity changes mark boundaries between layers.

Earth's internal heat comes from primordial heat from formation and radioactive decay of uranium, thorium, and potassium. This heat drives plate tectonics, volcanism, and the magnetic field. Over billions of years, Earth is gradually cooling, and eventually geological activity will cease—as has happened on smaller bodies like Mars.""",
            metadata={"domain": "earth-science", "tags": ["earth-interior", "core", "mantle", "seismic"], "difficulty": "intermediate", "focus": "earth-science"}
        ))

        return docs
