from functools import lru_cache

import pandas as pd

ECONOMICS = {
    "econ.EM": "Econometrics",
    "econ.GN": "General Economics",
    "econ.TH": "Theoretical Economics",
}


COMPUTER_SCIENCE = {
    "cs.AI": "Artificial Intelligence",
    "cs.AR": "Hardware Architecture",
    "cs.CC": "Computational Complexity",
    "cs.CE": "Computational Engineering, Finance, and Science",
    "cs.CG": "Computational Geometry",
    "cs.CL": "Computation and Language",
    "cs.CR": "Cryptography and Security",
    "cs.CV": "Computer Vision and Pattern Recognition",
    "cs.CY": "Computers and Society",
    "cs.DB": "Databases",
    "cs.DC": "Distributed, Parallel, and Cluster Computing",
    "cs.DL": "Digital Libraries",
    "cs.DM": "Discrete Mathematics",
    "cs.DS": "Data Structures and Algorithms",
    "cs.ET": "Emerging Technologies",
    "cs.FL": "Formal Languages and Automata Theory",
    "cs.GL": "General Literature",
    "cs.GR": "Graphics",
    "cs.GT": "Computer Science and Game Theory",
    "cs.HC": "Human-Computer Interaction",
    "cs.IR": "Information Retrieval",
    "cs.IT": "Information Theory",
    "cs.LG": "Machine Learning",
    "cs.LO": "Logic in Computer Science",
    "cs.MA": "Multiagent Systems",
    "cs.MM": "Multimedia",
    "cs.MS": "Mathematical Software",
    "cs.NA": "Numerical Analysis",
    "cs.NE": "Neural and Evolutionary Computing",
    "cs.NI": "Networking and Internet Architecture",
    "cs.OH": "Other Computer Science",
    "cs.OS": "Operating Systems",
    "cs.PF": "Performance",
    "cs.PL": "Programming Languages",
    "cs.RO": "Robotics",
    "cs.SC": "Symbolic Computation",
    "cs.SD": "Sound - Audio and Speech Processing",
    "cs.SE": "Software Engineering",
    "cs.SI": "Social and Information Networks",
    "cs.SY": "Systems and Control",
}


ELECTRICAL_ENGINEERING = {
    "eess.AS": "Audio and Speech Processing",
    "eess.IV": "Image and Video Processing",
    "eess.SP": "Signal Processing",
    "eess.SY": "Systems and Control",
}


MATHEMATICS = {
    "math.AG": "Algebraic Geometry",
    "math.AT": "Algebraic Topology",
    "math.AP": "Analysis of PDEs",
    "math.CT": "Category Theory",
    "math.CA": "Classical Analysis and ODEs",
    "math.CO": "Combinatorics",
    "math.AC": "Commutative Algebra",
    "math.CV": "Complex Variables",
    "math.DG": "Differential Geometry",
    "math.DS": "Dynamical Systems",
    "math.FA": "Functional Analysis",
    "math.GM": "General Mathematics",
    "math.GN": "General Topology",
    "math.GT": "Geometric Topology",
    "math.GR": "Group Theory",
    "math.HO": "History and Overview",
    "math.IT": "Information Theory",
    "math.KT": "K-Theory and Homology",
    "math.LO": "Logic",
    "math.MP": "Mathematical Physics",
    "math.MG": "Metric Geometry",
    "math.NT": "Number Theory",
    "math.NA": "Numerical Analysis",
    "math.OA": "Operator Algebras",
    "math.OC": "Optimization and Control",
    "math.PR": "Probability",
    "math.QA": "Quantum Algebra",
    "math.RT": "Representation Theory",
    "math.RA": "Rings and Algebras",
    "math.SP": "Spectral Theory",
    "math.ST": "Statistics Theory",
    "math.SG": "Symplectic Geometry",
}


QUANTITATIVE_BIOLOGY = {
    "q-bio.BM": "Biomolecules",
    "q-bio.CB": "Cell Behavior",
    "q-bio.GN": "Genomics",
    "q-bio.MN": "Molecular Networks",
    "q-bio.NC": "Neurons and Cognition",
    "q-bio.OT": "Other Quantitative Biology",
    "q-bio.PE": "Populations and Evolution",
    "q-bio.QM": "Quantitative Methods",
    "q-bio.SC": "Subcellular Processes",
    "q-bio.TO": "Tissues and Organs",
}


QUANTITATIVE_FINANCE = {
    "q-fin.CP": "Computational Finance",
    "q-fin.EC": "Economics",
    "q-fin.GN": "General Finance",
    "q-fin.MF": "Mathematical Finance",
    "q-fin.PM": "Portfolio Management",
    "q-fin.PR": "Pricing of Securities",
    "q-fin.RM": "Risk Management",
    "q-fin.ST": "Statistical Finance",
    "q-fin.TR": "Trading and Market Microstructure",
}


STATISTICS = {
    "stat.AP": "Applications",
    "stat.CO": "Computation",
    "stat.ME": "Methodology",
    "stat.ML": "Machine Learning",
    "stat.OT": "Other Statistics",
    "stat.TH": "Statistics Theory",
}


NONLINEAR_SCIENCES = {
    "nlin.AO": "Adaptation and Self-Organizing Systems",
    "nlin.CG": "Cellular Automata and Lattice Gases",
    "nlin.CD": "Chaotic Dynamics",
    "nlin.SI": "Exactly Solvable and Integrable Systems",
    "nlin.PS": "Pattern Formation and Solitons",
}


ASTRO_PHYSICS = {
    "astro-ph.CO": "Cosmology and Nongalactic Astrophysics",
    "astro-ph.EP": "Earth and Planetary Astrophysics",
    "astro-ph.GA": "Astrophysics of Galaxies",
    "astro-ph.HE": "High Energy Astrophysical Phenomena",
    "astro-ph.IM": "Instrumentation and Methods for Astrophysics",
    "astro-ph.SR": "Solar and Stellar Astrophysics",
}

CONDENSED_MATTER = {
    "cond-mat.dis-nn": "Disordered Systems and Neural Networks",
    "cond-mat.mes-hall": "Mesoscale and Nanoscale Physics",
    "cond-mat.mtrl-sci": "Materials Science",
    "cond-mat.other": "Other Condensed Matter",
    "cond-mat.quant-gas": "Quantum Gases",
    "cond-mat.soft": "Soft Condensed Matter",
    "cond-mat.stat-mech": "Statistical Mechanics",
    "cond-mat.str-el": "Strongly Correlated Electrons",
    "cond-mat.supr-con": "Superconductivity",
}

GENERAL_PHYSICS = {
    "physics.acc-ph": "Accelerator Physics",
    "physics.ao-ph": "Atmospheric and Oceanic Physics",
    "physics.app-ph": "Applied Physics",
    "physics.atm-clus": "Atomic and Molecular Clusters",
    "physics.atom-ph": "Atomic Physics",
    "physics.bio-ph": "Biological Physics",
    "physics.chem-ph": "Chemical Physics",
    "physics.class-ph": "Classical Physics",
    "physics.comp-ph": "Computational Physics",
    "physics.data-an": "Data Analysis, Statistics and Probability",
    "physics.flu-dyn": "Fluid Dynamics",
    "physics.gen-ph": "General Physics",
    "physics.geo-ph": "Geophysics",
    "physics.hist-ph": "History and Philosophy of Physics",
    "physics.ins-det": "Instrumentation and Detectors",
    "physics.med-ph": "Medical Physics",
    "physics.optics": "Optics",
    "physics.ed-ph": "Physics Education",
    "physics.soc-ph": "Physics and Society",
    "physics.plasma-ph": "Plasma Physics",
    "physics.pop-ph": "Popular Physics",
    "physics.space-ph": "Space Physics",
}

HIGH_ENERGY_AND_NUCLEAR = {
    "gr-qc": "General Relativity and Quantum Cosmology",
    "hep-ex": "High Energy Physics - Experiment",
    "hep-lat": "High Energy Physics - Lattice",
    "hep-ph": "High Energy Physics - Phenomenology",
    "hep-th": "High Energy Physics - Theory",
    "nucl-ex": "Nuclear Experiment",
    "nucl-th": "Nuclear Theory",
    "quant-ph": "Quantum Physics",
    "math-ph": "Mathematical Physics",
}

PHYSICS = {
    **ASTRO_PHYSICS,
    **CONDENSED_MATTER,
    **GENERAL_PHYSICS,
    **HIGH_ENERGY_AND_NUCLEAR,
}


# Retired archive names still present on pre-2007 papers in the snapshot.
# Without these, an inner join against the taxonomy silently drops them.
LEGACY = {
    "acc-phys": "Accelerator Physics",
    "adap-org": "Adaptation and Self-Organizing Systems",
    "alg-geom": "Algebraic Geometry",
    "ao-sci": "Atmospheric-Oceanic Sciences",
    "atom-ph": "Atomic Physics",
    "bayes-an": "Bayesian Analysis",
    "chao-dyn": "Chaotic Dynamics",
    "chem-ph": "Chemical Physics",
    "cmp-lg": "Computation and Language",
    "comp-gas": "Cellular Automata and Lattice Gases",
    "dg-ga": "Differential Geometry",
    "funct-an": "Functional Analysis",
    "mtrl-th": "Materials Theory",
    "patt-sol": "Pattern Formation and Solitons",
    "plasm-ph": "Plasma Physics",
    "q-alg": "Quantum Algebra",
    "solv-int": "Exactly Solvable and Integrable Systems",
    "supr-con": "Superconductivity",
}

# Pairs arXiv treats as the same category under two names, plus legacy
# redirects. Group by the canonical code or a cross-listed paper is counted
# twice.
ALIASES = {
    "cs.IT": "math.IT",
    "cs.LG": "stat.ML",
    "cs.NA": "math.NA",
    "cs.SY": "eess.SY",
    "econ.GN": "q-fin.EC",
    "math.MP": "math-ph",
    "stat.TH": "math.ST",
    "acc-phys": "physics.acc-ph",
    "adap-org": "nlin.AO",
    "alg-geom": "math.AG",
    "ao-sci": "physics.ao-ph",
    "atom-ph": "physics.atom-ph",
    "bayes-an": "physics.data-an",
    "chao-dyn": "nlin.CD",
    "chem-ph": "physics.chem-ph",
    "cmp-lg": "cs.CL",
    "comp-gas": "nlin.CG",
    "dg-ga": "math.DG",
    "funct-an": "math.FA",
    "mtrl-th": "cond-mat.mtrl-sci",
    "patt-sol": "nlin.PS",
    "plasm-ph": "physics.plasma-ph",
    "q-alg": "math.QA",
    "solv-int": "nlin.SI",
    "supr-con": "cond-mat.supr-con",
}


CATEGORIES_DICT = {
    **ECONOMICS,
    **COMPUTER_SCIENCE,
    **ELECTRICAL_ENGINEERING,
    **MATHEMATICS,
    **NONLINEAR_SCIENCES,
    **QUANTITATIVE_BIOLOGY,
    **QUANTITATIVE_FINANCE,
    **STATISTICS,
    **PHYSICS,
    **LEGACY,
}

TAXONOMY_MAP = {
    "computer science": COMPUTER_SCIENCE,
    "economics": ECONOMICS,
    "electrical engineering": ELECTRICAL_ENGINEERING,
    "mathematics": MATHEMATICS,
    "nonlinear sciences": NONLINEAR_SCIENCES,
    "physics": PHYSICS,
    "quantitative biology": QUANTITATIVE_BIOLOGY,
    "quantitative finance": QUANTITATIVE_FINANCE,
    "statistics": STATISTICS,
    "legacy": LEGACY,
}


def get_main_categories():
    return list(TAXONOMY_MAP.keys())


@lru_cache(maxsize=1)
def humanize_categories() -> pd.DataFrame:
    """One row per arXiv category code.
    canonical_acro collapses arXiv's alias pairs (cs.LG / stat.ML and
    friends). Group on it when counting papers, or cross-listed papers get
    counted once per alias.
    """
    rows = [
        {
            "main_category": main_cat,
            "readable_name": readable_name,
            "acro": acro,
            "canonical_acro": ALIASES.get(acro, acro),
            "is_legacy": main_cat == "legacy",
        }
        for main_cat, sub_dict in TAXONOMY_MAP.items()
        for acro, readable_name in sub_dict.items()
    ]
    return pd.DataFrame(rows)
