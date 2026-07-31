#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Fill the empty `motivation` for the 64 historical Max Planck Medal laureates.

The Max Planck Medal is a lifetime-achievement honour; for awards before ~2001 the
German Physical Society published no per-work citation, so `motivation` is blank.
This backfills a super-short achievement blurb per laureate, authored from general
knowledge and spot-checked against Wikipedia.

Guarded and idempotent: only rows that are still blank are touched, and all 64 keyed
rows must match or the transaction is rolled back.
"""

import sqlite3
import sys

DB = "awards.sqlite3"
PRIZE = "Max Planck Medal"

# (year, full_name, motivation) — names must match the DB exactly.
BLURBS = [
    ("1929", "Albert Einstein", "Relativity and the photoelectric effect (light quanta)."),
    ("1929", "Max Planck", "Originated quantum theory with the law of black-body radiation."),
    ("1930", "Niels Bohr", "Quantum model of the atom and the principle of complementarity."),
    ("1931", "Arnold Sommerfeld", "Extended atomic theory; the fine-structure constant and the free-electron model."),
    ("1932", "Max von Laue", "Discovered X-ray diffraction by crystals."),
    ("1933", "Werner Heisenberg", "Founded matrix mechanics and the uncertainty principle."),
    ("1937", "Erwin Schrödinger", "Formulated wave mechanics (the Schrödinger equation)."),
    ("1938", "Louis de Broglie", "Proposed the wave nature of matter (matter waves)."),
    ("1942", "Pascual Jordan", "Co-founded matrix mechanics and quantum field theory."),
    ("1943", "Friedrich Hund", "Hund's rules and the molecular-orbital theory of chemical bonding."),
    ("1944", "Walther Kossel", "Theory of the ionic chemical bond and of X-ray spectra."),
    ("1948", "Max Born", "Probabilistic interpretation of the wavefunction (the Born rule)."),
    ("1949", "Lise Meitner", "Co-discovered and gave the theoretical explanation of nuclear fission."),
    ("1949", "Otto Hahn", "Discovered nuclear fission."),
    ("1950", "Peter Debye", "Molecular dipole moments and the Debye theory of specific heats."),
    ("1951", "Gustav Hertz", "Franck–Hertz experiment confirming quantized atomic energy levels."),
    ("1951", "James Franck", "Franck–Hertz experiment and the Franck–Condon principle."),
    ("1952", "Paul Dirac", "Relativistic wave equation of the electron; predicted antimatter."),
    ("1953", "Walther Bothe", "Coincidence method for nuclear and cosmic-ray measurements."),
    ("1954", "Enrico Fermi", "Fermi–Dirac statistics, the theory of beta decay, and the first nuclear reactor."),
    ("1955", "Hans Bethe", "Explained energy production in stars (stellar nucleosynthesis)."),
    ("1956", "Victor Weisskopf", "Quantum electrodynamics of radiation and nuclear theory."),
    ("1957", "Carl Friedrich von Weizsäcker", "Nuclear mass formula and the stellar CNO fusion cycle."),
    ("1958", "Wolfgang Pauli", "The exclusion principle and the neutrino hypothesis."),
    ("1959", "Oskar Klein", "Klein–Gordon equation and Kaluza–Klein unification."),
    ("1960", "Lev Landau", "Theory of condensed matter, including superfluidity and phase transitions."),
    ("1961", "Eugene Wigner", "Symmetry principles in quantum mechanics."),
    ("1962", "Ralph Kronig", "Kramers–Kronig relations and the Kronig–Penney model; early proposal of electron spin."),
    ("1963", "Rudolf Peierls", "Solid-state and nuclear theory (the Peierls transition; the fission memorandum)."),
    ("1964", "George Uhlenbeck", "Co-discovered electron spin."),
    ("1964", "Samuel Goudsmit", "Co-discovered electron spin."),
    ("1966", "Gerhart Lüders", "Discovery and general proof of the CPT theorem."),
    ("1967", "Harry Lehmann", "The LSZ reduction formula and the Lehmann spectral representation."),
    ("1968", "Walter Heitler", "Quantum theory of the covalent bond (Heitler–London) and of radiation."),
    ("1969", "Freeman Dyson", "Unified the formulations of quantum electrodynamics."),
    ("1970", "Rudolf Haag", "Founded algebraic (axiomatic) quantum field theory."),
    ("1972", "Herbert Fröhlich", "Electron–phonon theory (the polaron) and superconductivity."),
    ("1973", "Nikolay Bogolyubov", "Microscopic theory of superfluidity and superconductivity (the Bogoliubov transformation)."),
    ("1974", "Léon Van Hove", "Van Hove singularities and rigorous statistical mechanics."),
    ("1975", "Gregor Wentzel", "The WKB approximation and early quantum field theory."),
    ("1976", "Ernst Stueckelberg", "Covariant perturbation theory and the Stueckelberg mechanism."),
    ("1977", "Walter Thirring", "Mathematical physics; the exactly solvable Thirring model."),
    ("1978", "Paul Peter Ewald", "Dynamical theory of X-ray diffraction (the Ewald sphere and summation)."),
    ("1979", "Markus Fierz", "Fierz identities and the spin–statistics theorem."),
    ("1981", "Kurt Symanzik", "LSZ formalism; the Callan–Symanzik equation and lattice improvement."),
    ("1982", "Hans-Arwed Weidenmüller", "Statistical theory of nuclear reactions and quantum chaos."),
    ("1983", "Nicholas Kemmer", "Meson field theory and the charge independence of nuclear forces."),
    ("1984", "Res Jost", "The Jost function in scattering theory; rigorous quantum field theory."),
    ("1985", "Yoichiro Nambu", "Spontaneous symmetry breaking in particle physics."),
    ("1986", "Franz Wegner", "Invented lattice gauge theory and flow-equation methods."),
    ("1987", "Julius Wess", "Co-created supersymmetry (the Wess–Zumino model)."),
    ("1988", "Valentine Bargmann", "Bargmann–Wigner equations and the Bargmann representation."),
    ("1989", "Bruno Zumino", "Co-created supersymmetry and supergravity."),
    ("1990", "Hermann Haken", "Laser theory and the science of self-organization (synergetics)."),
    ("1991", "Wolfhart Zimmermann", "BPHZ renormalization (the forest formula) and the LSZ formalism."),
    ("1992", "Elliott H. Lieb", "Rigorous mathematical physics, including the stability of matter."),
    ("1993", "Kurt Binder", "Monte Carlo methods for statistical physics (the Binder cumulant)."),
    ("1994", "Hans-Jürgen Borchers", "Algebraic quantum field theory (Borchers algebras and classes)."),
    ("1995", "Siegfried Grossmann", "Theory of turbulence and thermal convection."),
    ("1996", "Ludvig Faddeev", "Quantization of gauge fields (Faddeev–Popov ghosts) and quantum integrable systems."),
    ("1997", "Gerald E. Brown", "Nuclear many-body theory (Brown–Rho scaling)."),
    ("1998", "Raymond Stora", "BRST symmetry in gauge theories."),
    ("1999", "Pierre Hohenberg", "Foundations of density functional theory (the Hohenberg–Kohn theorem)."),
    ("2000", "Martin Lüscher", "Non-perturbative and lattice quantum field theory."),
]


def main() -> int:
    con = sqlite3.connect(DB)
    con.execute("BEGIN")
    updated, misses = 0, []
    for year, name, motivation in BLURBS:
        cur = con.execute(
            "UPDATE awards SET motivation = ? "
            "WHERE prize_name = ? AND year = ? AND full_name = ? AND (motivation = '' OR motivation IS NULL)",
            (motivation, PRIZE, year, name),
        )
        if cur.rowcount == 1:
            updated += 1
            print(f"motivation set: {year} {name}")
        else:
            misses.append((year, name, cur.rowcount))
            print(f"MISS ({cur.rowcount}): {year} {name}")

    if misses or updated != len(BLURBS):
        con.rollback()
        print(f"rolled back: {updated}/{len(BLURBS)} matched, {len(misses)} miss(es)")
        return 1

    con.commit()
    print(f"committed: {updated} motivations backfilled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
