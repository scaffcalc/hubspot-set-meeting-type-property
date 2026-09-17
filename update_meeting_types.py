"""
HubSpot Meeting Type Bulk Updater
----------------------------------
Fetches all meetings where meeting_type is empty, classifies by name, updates.

Meetings owned by a team in TEAMS are always given one of that team's types:
anything the name-based classifier returns that isn't in the team's set — the
other team's types, Partnership, Other, or no match at all — is forced to the
team's fallback. For those owners the meetings that already carry an off-team
type are corrected too, not just the empty ones.

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


def hubspot_get(url, api_key, params, required=True):
    """GET that fails loudly — an unchecked error body reads as 'no results'.

    With required=False a failure returns None instead of aborting, for calls
    the run can do without.
    """
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        params=params,
    )
    if resp.status_code != 200:
        label = "ERROR" if required else "WARNING"
        print(f"{label}: GET {url} returned HTTP {resp.status_code}")
        print(f"  {resp.text[:400]}")
        if resp.status_code in (401, 403):
            print("  Check that the token is set and the private app has the "
                  "crm.objects.meetings.read/write and crm.objects.owners.read scopes.")
        if not required:
            return None
        sys.exit(1)
    return resp.json()

# Owners whose meetings always get their team's type, keyed by HubSpot owner id
# so the rule does not depend on the owners API being readable. The name is a
# label; it is cross-checked against the owners API when that call succeeds, and
# a mismatch warns rather than aborts.
TEAMS = {
    "CS": {
        "owners": [
            ("33027515", "Felicia Stuhlhofer"),
            ("1714569923", "Josefine Skoglund"),
            ("34685500", "Fanny Frostelind"),
        ],
        "types": {
            "CS onboarding",
            "CS training",
            "CS product meeting",
            "CS license meeting",
            "CS check-in",
        },
        "fallback": "CS check-in",
    },
    "Sales": {
        "owners": [
            ("77124688", "David Gyllensten"),
            ("31025881", "Anton Boså"),
            ("36611425", "Victor Johansson"),
            ("1640423630", "Oskar Karnblad"),
        ],
        "types": {
            "First sales meeting",
            "Follow-up sales meeting",
            "Trial check-in",
        },
        "fallback": "Follow-up sales meeting",
    },
}

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


def fetch_owner_names(api_key):
    """Every HubSpot owner as {id: "<first> <last>"}, for verifying TEAMS.

    Best-effort: returns {} if the owners scope is missing, since the team rules
    are keyed by owner id and only use these names to sanity-check the config.
    """
    index = {}
    after = None

    while True:
        params = {"limit": 100}
        if after:
            params["after"] = after

        data = hubspot_get("https://api.hubapi.com/crm/v3/owners", api_key,
                           params, required=False)
        if data is None:
            print("  Could not read the owner list; continuing with the "
                  "owner ids in TEAMS unverified.")
            return {}

        for o in data.get("results", []):
            full = f"{o.get('firstName') or ''} {o.get('lastName') or ''}".strip()
            index[str(o["id"])] = full or (o.get("email") or "")

        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break

        time.sleep(0.05)

    return index


def resolve_team_owners(owner_names):
    """Map each owner id to its team. Warns if a configured id looks wrong."""
    owner_team = {}

    for team, cfg in TEAMS.items():
        for oid, label in cfg["owners"]:
            if oid in owner_team:
                print(f"ERROR: owner {oid} ({label}) is listed under both "
                      f"{owner_team[oid]} and {team}.")
                sys.exit(1)
            owner_team[oid] = team

            actual = owner_names.get(oid) if owner_names else label
            if actual is None:
                print(f"  WARNING: {team} owner {label} ({oid}) is not in this "
                      f"portal's owner list — its meetings will never match.")
            elif actual.strip().lower() != label.strip().lower():
                print(f"  WARNING: owner {oid} is configured as {label} but HubSpot "
                      f"calls it {actual}. Using the id.")
            else:
                print(f"  {team} owner: {label} ({oid})")

    return owner_team


def fetch_candidates(api_key, owner_team):
    """Meetings needing a write: no type yet, or a team owner with an off-team type."""
    results = []
    after = None

    while True:
        params = {
            "limit": 100,
            "properties": "hs_meeting_title,meeting_type,hubspot_owner_id",
        }
        if after:
            params["after"] = after

        data = hubspot_get("https://api.hubapi.com/crm/v3/objects/meetings",
                           api_key, params)

        for obj in data.get("results", []):
            props = obj.get("properties", {})
            current = props.get("meeting_type")
            team = owner_team.get(str(props.get("hubspot_owner_id") or ""))
            off_team = team and current not in TEAMS[team]["types"]

            if current and not off_team:
                continue

            results.append({
                "id": obj["id"],
                "name": props.get("hs_meeting_title", "") or "",
                "current": current or "",
                "team": team,
            })

        paging = data.get("paging", {})
        after = paging.get("next", {}).get("after")
        if not after:
            break

        time.sleep(0.05)

    return results


def resolve_type(record):
    """Final meeting type for a record, or None to leave it alone."""
    meeting_type = classify(record["name"])
    team = record["team"]
    if team and meeting_type not in TEAMS[team]["types"]:
        return TEAMS[team]["fallback"]
    return meeting_type


def update_meetings(api_key, dry_run=False):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    if dry_run:
        print("DRY RUN — nothing will be written to HubSpot.\n")

    print("Resolving team owners...")
    owner_team = resolve_team_owners(fetch_owner_names(api_key))

    print("Fetching meetings to classify...")
    records = fetch_candidates(api_key, owner_team)
    empty = sum(1 for r in records if not r["current"])
    corrections = len(records) - empty
    print(f"Found {empty} meetings without Meeting Type"
          f" and {corrections} team-owned meetings with an off-team type to correct")

    if not records:
        print("Nothing to update.")
        return

    success, skipped, failed, overridden = 0, 0, [], []

    for i, r in enumerate(records):
        meeting_type = resolve_type(r)
        if not meeting_type:
            skipped += 1
            continue

        if r["current"] and r["current"] != meeting_type:
            overridden.append((r["team"], r["name"], r["current"], meeting_type))

        if dry_run:
            success += 1
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

    verb = "would be updated" if dry_run else "updated"
    print(f"\nDone. {success} {verb}, {skipped} skipped (unclassifiable), {len(failed)} failed.")
    if overridden:
        replaced = "would have their existing type replaced" if dry_run else "had their existing type replaced"
        print(f"\n{len(overridden)} team-owned meetings {replaced}:")
        for team, oname, old, new in sorted(overridden):
            print(f"  [{team}] {oname!r}: {old} -> {new}")
    if failed:
        for fid, fname, fcode, fmsg in failed:
            print(f"  FAILED {fid} ({fname!r}): HTTP {fcode} — {fmsg[:120]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would change without writing to HubSpot")
    args = parser.parse_args()
    update_meetings(api_key=args.api_key, dry_run=args.dry_run)