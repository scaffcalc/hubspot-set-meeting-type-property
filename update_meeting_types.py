"""
HubSpot Meeting Type Bulk Updater
----------------------------------
Fetches all meetings where meeting_type is empty, classifies by name, updates.

Usage:
    python3 update_meeting_types.py --api-key YOUR_SERVICE_KEY
"""

import time
import argparse
import sys

try:
    import requests
except ImportError:
    print("Run: pip install requests")
    sys.exit(1)

PROPERTY = "meeting_type"

def classify(name):
    if not name or not name.strip():
        return None
    n = name.lower().strip()

    # New standardized naming convention (forward-looking)
    if n.startswith("demo:"):                           return "First sales meeting"
    if n.startswith("trial check-in:"):                return "Trial check-in"
    if n.startswith("anmeldung zur testversion:"):      return "Trial check-in"
    if n.startswith("follow-up:"):                     return "Follow-up sales meeting"
    if n.startswith("weiterführende informationen:"):   return "Follow-up sales meeting"
    if n.startswith("onboarding:"):                    return "CS onboarding"
    if n.startswith("einführung:"):                    return "CS onboarding"
    if n.startswith("training:"):                      return "CS training"
    if n.startswith("schulung:"):                      return "CS training"
    if n.startswith("product news:"):                  return "CS product meeting"
    if n.startswith("produktneuigkeiten:"):             return "CS product meeting"
    if n.startswith("license:"):                       return "CS license meeting"
    if n.startswith("lizenz:"):                        return "CS license meeting"
    if n.startswith("customer check-in:"):             return "CS check-in"
    if n.startswith("kunden-check-in:"):               return "CS check-in"
    if n.startswith("partnership:"):                   return "Partnership"

    # Legacy patterns (historical records)
    other_patterns = [
        "landvetter", "miami", "färja", "skidor", "cervinia", "ikea haul",
        "ellen fyller", "fira ", "julavslutning", "scafftrip", "skepp ohoj",
        "hissutskott", "hjälp vi har köpt", "kika i lokalen", "kolla kungsholmen",
        "falkenbergs strandbad", "hämta göteborgsvarvet", "nashville planning",
        "aw på stan", "cykla cykel", "customer night", "scaffcalc årsstämma",
        "årsstämma scaffcalc", "meeting recorded with tl;dv", "inbjudan sis/tk 173",
        "canceled:", "del frisco", "monthly recap", "fakturering", "genomgång: p&l",
        "gemensam lunch", "lunch!", "scaffcalc admin", "mötesbokning",
        "scaffcalc/scaffplan", "culture presentation", "hejdå-fika", "säljworkshop",
        "sales playbook by oskar", "david <> alex", "möte seb", "möte sb bokslut",
        "möte alphyddan", "möte i lokalen", "möte cse", "möte 2: anton.b x kevin",
        "hockey med scaffcalc", "coffee & contech", "boså x scaffcalc frukost",
        "leads-sharing", "marketing alignement", "daniel & viktor", "anton & viktor",
        "oliver & viktor", "johan & viktor", "erik / viktor", "fajt & viktor",
        "call oskar & igoris", "förslag: viktor & johan", "starteline x siikaluoma",
    ]
    internal_colleague = [
        "and anton boså", "and david gyllensten", "and kevin walian",
        "josefine skoglund and", "oskar  and gustaf", "oskar karnblad and david"
    ]
    for p in other_patterns:
        if p in n: return "Other"
    for p in internal_colleague:
        if p in n: return "Other"

    cs_license = ["cancel or continue", "continue or cancel", "prisförhandling",
                  "easy estimator - pricing", "follow up | easy estimator customer pricing",
                  "[ext] updated estimator licensing", "invoicing and quotation"]
    for p in cs_license:
        if p in n: return "CS license meeting"

    cs_checkin = ["cs case", "cs check-in", "x scaffcalc cs", "scaffcalc cs.",
                  "scaffcalc cs:", "storfika", "digital fika", "digitalt fika",
                  "fika: ", "kaffe med ", "lunch med ", "lunch,", "lunch @scaffex",
                  "lunch meeting", "scaffcalc: lunch", "scaffclac-aw"]
    for p in cs_checkin:
        if p in n: return "CS check-in"

    cs_onboard = ["cs onboarding", "set-up", "key account first setup",
                  "tapaaminen ja testitunnukset", "scaffcalc tipsit"]
    for p in cs_onboard:
        if p in n: return "CS onboarding"

    cs_training = ["cs training", "build example project", "co-create pdf",
                   "thomas & viktor, testa scaffcalc", "scaffolding industry presentation",
                   "scaffcalc organisationsgenomgång", "prel tid: case/workshop",
                   "case/workshop scaffcalc", "scaffcalc imperial focus meeting",
                   "beräkningsmodell scaffcalc x isab"]
    for p in cs_training:
        if p in n: return "CS training"

    cs_product = ["at-pac implementation general meeting", "at-pac quarterly meeting",
                  "beo at-pac quarterly", "scaffcalc sync", "sync | scaffcalc",
                  "sync | partner gerüstbau", "sync | ställningsprodukter",
                  "what's new in scaffcalc", "scaffcalc inventory and material list",
                  "pointcloud & aufmass", "engineering funktionalitet i scaffcalc",
                  "scaffcalc update ", "scaffcalc review", "easy estimator alignment",
                  "estimator discussions", "offertverktyg genomgång",
                  "genomgång av offertverktyg", "scaffcalc besöker layher",
                  "scaffcalc & bechtel |\u00a0estimator tool", "projektüberblick | scaffcalc"]
    for p in cs_product:
        if p in n: return "CS product meeting"

    followup = ["follow-up", "follow up", "followup", "entscheidung", "beschluss",
                "ende des trails", "decision | scaffcalc", "decision sync",
                "nächster schritt", "nächste schritte", "proposal", "überprüfung",
                "pricing structure", "price discussion", "prissättning", "prispaket",
                "prisförslag", "quotation sync", "quotation tool", "contract",
                "scaffcalc offer", "way forward", "next steps | scaffcalc",
                "finalizing partnership", "session 2", "second meeting", "third meeting",
                "2nd demo", "demo 2.0", "revisit scaffcalc", "catch-up:", "re: scaffcalc",
                "scaffcalc @ ", "möte scaffcalc ", "meeting scaffcalc - ",
                "scaffcalc comes by", "scaffcalc besøger", "scaffcalc besöker",
                "scaffcalc on site", "on site: scaffcalc", "platsbesök: scaffcalc",
                "scaffcalc kommer på besök", "scaffcalc hos ", "dinner: scaffcalc",
                "dinner & demo", "visning av scaffcalc", "genomgång scaffcalc",
                "genomgång | scaffcalc", "bilfinger & scaffcalc"]
    for p in followup:
        if p in n: return "Follow-up sales meeting"

    first_sales = ["demo", "demonstration", "démonstration", "esittely", "präsentation",
                   "presentasjon", "introductory call", "introduction meeting",
                   "meet & greet", "fwd: scaffcalc", "fw: scaffcalc",
                   "enhanza // scaffcalc", "scaffcalc & dealfront", "geda // introduction",
                   "genomgång av scaffcalc", "scaffcalc intro"]
    for p in first_sales:
        if p in n: return "First sales meeting"

    if any(x in n for x in ["scaffcalc", "scaffclac"]):
        return "Follow-up sales meeting"

    return None  # Don't set anything if we can't classify


def fetch_unclassified(api_key):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    results = []
    after = None

    while True:
        params = {
            "limit": 100,
            "properties": "hs_meeting_title,meeting_type",
        }
        if after:
            params["after"] = after

        resp = requests.get(
            "https://api.hubapi.com/crm/v3/objects/meetings",
            headers=headers,
            params=params
        )
        data = resp.json()

        for obj in data.get("results", []):
            props = obj.get("properties", {})
            if not props.get("meeting_type"):
                results.append({
                    "id": obj["id"],
                    "name": props.get("hs_meeting_title", "") or ""
                })

        paging = data.get("paging", {})
        after = paging.get("next", {}).get("after")
        if not after:
            break

        time.sleep(0.05)

    return results


def update_meetings(api_key):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    print("Fetching unclassified meetings...")
    records = fetch_unclassified(api_key)
    print(f"Found {len(records)} meetings without Meeting Type")

    if not records:
        print("Nothing to update.")
        return

    success, skipped, failed = 0, 0, []

    for i, r in enumerate(records):
        meeting_type = classify(r["name"])
        if not meeting_type:
            skipped += 1
            continue

        resp = requests.patch(
            f"https://api.hubapi.com/crm/v3/objects/meetings/{r['id']}",
            headers=headers,
            json={"properties": {PROPERTY: meeting_type}}
        )

        if resp.status_code in (200, 204):
            success += 1
        else:
            failed.append((r["id"], r["name"], resp.status_code, resp.text))

        if (i + 1) % 100 == 0:
            print(f"  Progress: {i+1}/{len(records)}")

        time.sleep(0.07)

    print(f"\nDone. {success} updated, {skipped} skipped (unclassifiable), {len(failed)} failed.")
    if failed:
        for fid, fname, fcode, fmsg in failed:
            print(f"  FAILED {fid} ({fname!r}): HTTP {fcode} — {fmsg[:120]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", required=True)
    args = parser.parse_args()
    update_meetings(api_key=args.api_key)