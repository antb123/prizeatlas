#!/usr/bin/env python3
"""
Populate affiliations.application_url in awards.sqlite3.

Maps:
- Universities -> Undergraduate admissions / apply link
- Companies -> Careers / jobs / internships link
- Research institutes / Labs -> Education / fellowships / student programmes / careers link
"""

import sqlite3
import sys

DB_PATH = "awards.sqlite3"

# Comprehensive dictionary mapping affiliation QIDs to curated Application / Admissions / Careers URLs
APPLICATION_URLS = {
    # --- Top Universities (Undergraduate Admissions / Apply) ---
    "Q13371": "https://college.harvard.edu/admissions",  # Harvard University
    "Q49108": "https://mitadmissions.org/",  # Massachusetts Institute of Technology
    "Q41506": "https://admission.stanford.edu/",  # Stanford University
    "Q21578": "https://admission.princeton.edu/",  # Princeton University
    "Q184478": "https://admission.universityofcalifornia.edu/",  # University of California
    "Q161562": "https://www.admissions.caltech.edu/",  # California Institute of Technology
    "Q350": "https://www.undergraduate.study.cam.ac.uk/",  # University of Cambridge
    "Q49088": "https://undergrad.admissions.columbia.edu/",  # Columbia University
    "Q131252": "https://collegeadmissions.uchicago.edu/",  # University of Chicago
    "Q34433": "https://www.ox.ac.uk/admissions/undergraduate",  # University of Oxford
    "Q193727": "https://apply.jhu.edu/",  # Johns Hopkins University
    "Q180865": "https://future.utoronto.ca/apply/",  # University of Toronto
    "Q49112": "https://admissions.yale.edu/",  # Yale University
    "Q1061104": "https://admissions.ucsf.edu/",  # UCSF
    "Q49117": "https://admissions.upenn.edu/",  # University of Pennsylvania
    "Q49115": "https://admissions.cornell.edu/",  # Cornell University
    "Q168756": "https://admissions.berkeley.edu/",  # UC Berkeley
    "Q132197": "https://admissions.ucla.edu/",  # UCLA
    "Q168057": "https://admissions.ucsd.edu/",  # UC San Diego
    "Q230492": "https://admissions.umich.edu/",  # University of Michigan
    "Q309350": "https://admissions.northwestern.edu/",  # Northwestern University
    "Q168751": "https://admissions.duke.edu/",  # Duke University
    "Q168752": "https://admissions.unc.edu/",  # UNC Chapel Hill
    "Q1136919": "https://www.admissions.iastate.edu/",  # Iowa State University
    "Q1035745": "https://www.cardiff.ac.uk/study/undergraduate",  # Cardiff University
    "Q1057199": "https://www.global.hokudai.ac.jp/admissions/",  # Hokkaido University
    "Q1137665": "https://www.ugent.be/en/education",  # Ghent University
    "Q1145306": "https://www.caluniv.ac.in/admission/admission.html",  # Calcutta University
    "Q219563": "https://admissions.illinois.edu/",  # UIUC
    "Q133285": "https://admissions.wisc.edu/",  # UW-Madison
    "Q184837": "https://admit.washington.edu/",  # University of Washington
    "Q200208": "https://www.brown.edu/admission/undergraduate",  # Brown University
    "Q168750": "https://admissions.dartmouth.edu/",  # Dartmouth College
    "Q49037": "https://www.ethz.ch/en/studies.html",  # ETH Zurich
    "Q83151": "https://www.epfl.ch/education/admission/",  # EPFL
    "Q7827": "https://www.kyoto-u.ac.jp/en/education-campus/admissions",  # Kyoto University
    "Q112328210": "https://www.kyoto-u.ac.jp/en/education-campus/admissions",  # Kyoto Imperial University -> Kyoto Univ
    "Q131901": "https://www.u-tokyo.ac.jp/en/prospective-students/admissions.html",  # University of Tokyo
    "Q211130": "https://www.uni-heidelberg.de/en/study",  # Heidelberg University
    "Q200044": "https://www.lmu.de/en/study/",  # LMU Munich
    "Q157808": "https://www.tum.de/en/studies/application",  # TU Munich
    "Q152918": "https://www.uu.se/en/admissions",  # Uppsala University
    "Q219612": "https://ki.se/en/education",  # Karolinska Institutet
    "Q20266894": "https://www.hu-berlin.de/en/studies/counseling/admissions-office",  # Humboldt Univ Berlin
    "Q1804763": "https://www.hu-berlin.de/en/studies/counseling/admissions-office",  # Landwirtschaftliche Hochschule
    "Q135840532": "https://www.uni-halle.de/studium/",  # Martin Luther Univ Halle-Wittenberg
    "Q19952130": "https://www.ulb.be/en/studies/admissions",  # Université libre de Bruxelles
    "Q25105063": "https://www.uniroma1.it/en/pagina/admissions",  # Sapienza Univ of Rome
    "Q4894094": "https://www.unibe.ch/studies/admissions/index_eng.html",  # University of Bern
    "Q73043462": "https://www.bcm.edu/education/admissions",  # Baylor College of Medicine
    "Q101251452": "https://drexel.edu/medicine/academics/md-program/",  # Hahnemann / Drexel Med
    "Q24638021": "https://www.ucl.ac.uk/prospective-students/undergraduate/",  # UCL / Middlesex Med
    "Q7374735": "https://www.imperial.ac.uk/study/ug/",  # Imperial College London
    "Q777039": "https://www.kcl.ac.uk/study/undergraduate",  # King's College London / Guy's
    "Q111722916": "https://cau.ac.in/academics/admission/",  # Central Agricultural Univ
    "Q1188786": "https://www.kyushu-u.ac.jp/en/admission/",  # Kyushu University
    "Q151336": "https://www.strath.ac.uk/studywithus/",  # Strathclyde

    # --- Companies & Corporate Labs (Careers / Jobs / Internships) ---
    "Q956": "https://www.ibm.com/careers",  # IBM
    "Q2283": "https://www.microsoft.com/en-us/research/careers/",  # Microsoft Research
    "Q1144725": "https://www.microsoft.com/en-us/research/careers/",  # Microsoft Research
    "Q95": "https://www.google.com/about/careers/",  # Google
    "Q226207": "https://www.bell-labs.com/about/careers/",  # Bell Labs
    "Q1016927": "https://www.gsk.com/en-gb/careers/",  # Burroughs Wellcome -> GSK
    "Q18627472": "https://www.dupont.com/careers.html",  # DuPont
    "Q5065711": "https://www.novartis.com/careers",  # Cetus -> Novartis
    "Q65045874": "https://www.sanofi.com/en/careers",  # Connaught Labs -> Sanofi
    "Q100604548": "https://www.rpbw.com/contact",  # Renzo Piano Building Workshop
    "Q121299458": "http://www.kurosawa-drawings.com/",  # Kurosawa Production

    # --- Research Institutes, Hospitals & Foundations (Student / Fellowships / Careers / Education) ---
    "Q270272": "https://www.rockefeller.edu/education-and-training/",  # Rockefeller University
    "Q635642": "https://www.ias.edu/scholars",  # Institute for Advanced Study
    "Q390551": "https://www.training.nih.gov/",  # NIH
    "Q1133630": "https://jobs.lbl.gov/",  # Berkeley Lab (LBNL)
    "Q1130172": "https://jobs.mayoclinic.org/",  # Mayo Clinic
    "Q1000479": "https://www.childrenshospital.org/careers",  # Boston Children's Hospital
    "Q120908545": "https://jobs.clevelandclinic.org/",  # Cleveland Clinic
    "Q1159198": "https://www.dana-farber.org/about/careers",  # Dana-Farber Cancer Institute
    "Q6019423": "https://www.mpg.de/job-offers",  # Max Planck Society
    "Q110636214": "https://www.mpinat.mpg.de/career-opportunities",  # Max Planck Multidisciplinary
    "Q1043963": "https://carnegiescience.edu/careers",  # Carnegie Institution
    "Q1146254": "https://www.rsc.org.uk/about-us/careers",  # Royal Shakespeare Company
    "Q1149028": "https://www.lister-institute.org.uk/",  # Lister Institute
    "Q1153275": "https://www.riken.jp/en/careers/",  # RIKEN
    "Q1156553": "https://www.ihes.fr/en/join-ihes/",  # IHES
    "Q11589396": "https://www.kanagawa-iri.jp/",  # Kanagawa Academy
    "Q1190606": "https://www.ictp.it/opportunity",  # ICTP
    "Q15760688": "https://cdaonline.org/",  # Colorado Dental Assoc
    "Q17007257": "https://www.claws.in/",  # CLAWS
    "Q17513775": "https://www.callaghaninnovation.govt.nz/careers",  # DSIR -> Callaghan
    "Q22061059": "https://omh.ny.gov/omhweb/facilities/ropc/careers.html",  # Rockland State Hospital
    "Q3735235": "https://www.menningerclinic.org/careers",  # Menninger Foundation
    "Q414147": "https://www.academie-sciences.fr/fr/Colloques-conferences-et-debats/evenements-jeunesse.html",  # Académie des sciences
    "Q757600": "https://www.harwellcampus.com/careers/",  # Atomic Energy Research Est.
    "Q809921": "https://careers.roche.com/",  # Basel Institute -> Roche
    "Q85413125": "https://www.desy.de/career/index_eng.html",  # DESY
    "Q11087599": "https://www.img.cas.cz/education-and-careers/",  # Institute of Molecular Genetics Prague
    "Q11396095": "https://www.ims.ac.jp/en/recruit/",  # Institute for Molecular Science Japan
}


def populate_application_urls(db_path: str, dry_run: bool = False) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Read current state
    cur.execute("SELECT affiliation_wikidata_qid, logo_url, description, application_url FROM affiliations;")
    rows = cur.fetchall()

    updates = []
    already_set = 0

    for qid, logo, desc, current_app_url in rows:
        target_url = APPLICATION_URLS.get(qid, "")

        # Generic fallback for unlisted universities/institutions with logo or description
        if not target_url and "university" in desc.lower():
            target_url = f"https://www.wikidata.org/wiki/{qid}"

        if current_app_url == target_url:
            already_set += 1
        else:
            updates.append((target_url, qid))

    print(f"Affiliation application_url: {len(updates)} updates prepared, {already_set} unchanged.")

    if not dry_run and updates:
        cur.executemany("UPDATE affiliations SET application_url = ? WHERE affiliation_wikidata_qid = ?;", updates)
        conn.commit()

        cur.execute("PRAGMA integrity_check;")
        check = cur.fetchone()[0]
        if check != "ok":
            conn.rollback()
            raise RuntimeError(f"PRAGMA integrity_check failed: {check}")
        print("Database transaction committed successfully. Integrity check: ok.")

    conn.close()


def main() -> None:
    dry_run = "--apply" not in sys.argv
    populate_application_urls(DB_PATH, dry_run=dry_run)


if __name__ == "__main__":
    main()
