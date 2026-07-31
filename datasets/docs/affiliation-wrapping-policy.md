# Institutional Wrapping Rule for Prize-Affiliation Data

## Goal

Normalize affiliation names so that laureates are counted under the correct overarching institution.

The controlling rule is:

> **Merge or wrap entities when they share the same ultimate budget and governance.**

The decision is not based mainly on branding, campus location, legal naming, or whether the affiliation text exactly matches the parent institution.

## Core test

For each affiliation, determine:

1. Who controls the institution or unit?
2. Who approves its leadership and major policies?
3. Who ultimately controls or allocates its operating budget?
4. Is it an ordinary department, school, hospital, laboratory, extension unit, or research centre within that structure?

When the same organization ultimately controls both governance and budget, normalize the smaller or historical entity to the overarching institution.

## Merge these cases

### Exact duplicates and translations

Merge spelling variants, translated names, abbreviations, and reordered names.

Examples:

```text
Pasteur Institute
Institut Pasteur
    → Institut Pasteur
```

```text
Strasbourg University
University of Strasbourg
    → University of Strasbourg
```

### Internal departments and schools

Merge an ordinary school, faculty, department, division, unit, or laboratory into its parent when it does not have genuinely separate budget and governance.

Examples:

```text
University of Pittsburgh School of Medicine
    → University of Pittsburgh
```

```text
Viral Oncology Unit, Institut Pasteur
    → Institut Pasteur
```

```text
UW–Madison Division of Extension
University of Wisconsin agricultural unit
    → University of Wisconsin–Madison
```

The affiliation name does not need to match the parent name exactly.

### Hospitals within one governed hospital system

Merge hospitals when they operate under the same overarching hospital administration and budget.

Example:

```text
Hôpital Européen Georges-Pompidou
Saint-Louis Hospital
    → Assistance Publique–Hôpitaux de Paris
```

### Historical names and direct successors

Merge an old name into the current institution when there is clear institutional continuity or legal succession.

Examples:

```text
University of Paris VI
    → Sorbonne University
```

```text
Université Louis Pasteur
    → University of Strasbourg
```

```text
Joseph Fourier University
    → Université Grenoble Alpes
```

```text
Université Paris-Sud
    → Université Paris-Saclay
```

```text
École municipale de physique et de chimie industrielles
    → ESPCI Paris
```

A predecessor and successor may use different legal names while still belonging to the same institutional wrapper for this database.

### Statewide or distributed internal units

A unit may be geographically separate and still be wrapped when the parent institution controls its governance and budget.

Examples include agricultural extension offices, research stations, county extension programs, hospitals, and branch laboratories.

Physical separation alone is not a reason to keep an entity separate.

## Do not merge these cases

### Jointly governed laboratories

Do not automatically merge a laboratory into one parent when several institutions jointly supervise, fund, or govern it.

Examples:

```text
Institut de Mathématiques de Jussieu–Paris Rive Gauche
Institut Fourier
Institut d’Astrophysique Spatiale
Institut Henri Poincaré
```

A CNRS affiliation alone does not mean the laboratory should be reduced to CNRS.

Check whether it is a joint research unit, such as a French UMR, with multiple supervisory institutions.

### Separate legal institutions inside a federation or university group

Do not merge institutions merely because they belong to the same alliance, university system, federation, consortium, or umbrella brand.

Examples:

```text
CentraleSupélec
AgroParisTech
ENS Paris-Saclay
Institut d’Optique
```

These may participate in Université Paris-Saclay while retaining separate governance, leadership, and budgets.

### Institutions sharing only a board or system umbrella

Sharing a statewide board is not always sufficient.

The question is whether the institutions function under the same actual institutional budget and governance, or whether the board merely oversees several separately managed campuses.

For example, separate University of California campuses should normally remain separate even though they share a system-level Board of Regents.

```text
UC Berkeley ≠ UC Davis
```

The same applies to separate campuses in many public university systems.

### Independent international branches

Institutions with a related name should remain separate when they have their own governance and budget.

Example:

```text
Institut Pasteur de Tunis
    ≠ Institut Pasteur, Paris
```

Name affiliation or participation in an international network is not enough.

## Important distinction: “same parent” versus “same wrapper”

A unit should be wrapped when the parent is the actual governing and budgeting institution.

A mere partner, funder, member organization, host campus, or research collaborator is not enough.

Use this hierarchy:

```text
Ordinary internal unit
    → merge

Historical name or direct legal successor
    → merge

Shared budget and governance
    → merge

Joint governance by multiple institutions
    → keep separate

Independent institution in a system or federation
    → keep separate

Shared branding or network membership only
    → keep separate
```

## QID handling

Use the QID of the chosen overarching institution.

Example:

```text
University of Pittsburgh School of Medicine — Q7896139
University of Pittsburgh — Q235034

Normalize:
Q7896139 → Q235034
```

For a missing QID where the affiliation is already clearly the parent institution, fill the parent QID.

Example:

```text
Harvard University — <empty>
    → Q13371
```

Do not retain a subunit QID when the record is being institutionally wrapped into its parent.

## Handling ambiguous historical names

Do not reject a merge solely because the historical affiliation lacks the modern suffix.

Example:

```text
University of Wisconsin
```

In an older agricultural or Madison-based context, this may be the historical name of the institution now known as University of Wisconsin–Madison.

Use the date, city, faculty, discipline, and institutional history to identify the correct wrapper.

Similarly, distinguish carefully between:

```text
historic University of Paris
Université de Paris created in 2019–2020
Université Paris Cité
```

Similar names do not necessarily represent the same institution.

## Required research output

For every proposed merge, provide:

```text
Original affiliation
Canonical institution
Original QID
Canonical QID
Decision: MERGE / KEEP SEPARATE / NEEDS REVIEW
Reason: budget and governance explanation
```

Keep the reason focused on institutional control rather than general association.

Good reason:

```text
MERGE — the named unit is an internal department whose leadership and operating budget are controlled by Institut Pasteur.
```

Bad reason:

```text
MERGE — the organizations work closely together.
```

## Final principle

> Normalize according to the institution that ultimately controls the affiliation’s budget and governance.

Do not let an exact-name requirement override clear institutional structure. Conversely, do not collapse legally or administratively independent institutions merely because they share a name, system, consortium, campus, or research partnership.
