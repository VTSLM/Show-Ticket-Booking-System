"""
Demo catalogue: cities, venues, seat layouts, movies, live events and showtimes.

Fills Browse with realistic data for demos and testing:

  - 10 cities (8 metros + Vadodara and Gandhinagar)
  - multiplexes with 3-4 screens each (cinema layouts: Classic / Prime / Recliner rows, an IMAX screen in some)
  - a concert arena in every metro (stage, standing fan pit and lawn, seated grandstand)
  - an auditorium (stage, Premium / Stalls / Balcony) and a comedy club (stage, small seated room) in every city
  - 10 real movies (catalogue re-runs), each shown about 4-5 times a day in every city
  - live events (concerts, stand-up, plays, workshops) with FICTIONAL performers
  - showtimes for the next --days days (default 7, about 15 MB of database space per day);
    run it again any day to extend the window

Every row has a fixed id derived from its name (uuid5), so running the script again never
creates duplicates. Everything belongs to the organizer "TicketFlow Demo Entertainment".
Posters are original title cards (scripts/generate_demo_posters.py) served from the public Supabase
Storage bucket demo-posters; set DEMO_POSTER_BASE_URL in backend/.env to serve them from elsewhere.

Run from backend/ (uses its .env database connection):
    venv/bin/python ../database/seeds/005_demo_catalogue.py              # add / extend
    venv/bin/python ../database/seeds/005_demo_catalogue.py --days 14    # longer window
    venv/bin/python ../database/seeds/005_demo_catalogue.py --dry-run    # report only, change nothing
    venv/bin/python ../database/seeds/005_demo_catalogue.py --no-posters # before the posters are uploaded
    venv/bin/python ../database/seeds/005_demo_catalogue.py --remove     # take the demo catalogue down

Everything runs in one transaction: if anything fails, nothing is changed.
"""
import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.abspath(os.path.join(HERE, "..", "..", "backend"))
sys.path.insert(0, BACKEND)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(BACKEND, ".env"))

import asyncpg  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
NS = uuid.UUID("6f1c3a52-9d1e-4b8f-a2a4-5c0de7ca7a10")  # namespace for every demo id
ORG_NAME = "TicketFlow Demo Entertainment"
DEMO_MANAGER_UID = "demo-catalogue-manager"


def uid(*parts) -> uuid.UUID:
    return uuid.uuid5(NS, "|".join(str(p) for p in parts))


# ── Cities and venues ─────────────────────────────────────────────────────────
# (city, state, metro?, multiplexes [(chain, area, lat, lng, has_imax)], arena, auditorium, club)
CITIES = [
    ("Mumbai", "Maharashtra", True,
     [("Reelhouse", "Andheri West", 19.1364, 72.8296, True),
      ("Starlight Cinemas", "Lower Parel", 18.9953, 72.8302, False),
      ("Marquee Multiplex", "Ghatkopar", 19.0860, 72.9081, False)],
     ("Mumbai Arena", "Worli", 19.0176, 72.8162),
     ("Rangmanch Auditorium", "Bandra West", 19.0596, 72.8295),
     ("The Laugh Lounge", "Khar West", 19.0728, 72.8347)),
    ("Delhi", "Delhi", True,
     [("Reelhouse", "Saket", 28.5245, 77.2066, True),
      ("Starlight Cinemas", "Connaught Place", 28.6315, 77.2167, False),
      ("Marquee Multiplex", "Rajouri Garden", 28.6415, 77.1209, False)],
     ("Delhi Arena", "Pragati Maidan", 28.6180, 77.2430),
     ("Rangmanch Auditorium", "Mandi House", 28.6262, 77.2337),
     ("The Laugh Lounge", "Hauz Khas", 28.5494, 77.2001)),
    ("Bengaluru", "Karnataka", True,
     [("Reelhouse", "Koramangala", 12.9352, 77.6245, True),
      ("Starlight Cinemas", "Whitefield", 12.9698, 77.7500, False),
      ("Marquee Multiplex", "Malleshwaram", 13.0035, 77.5710, False)],
     ("Bengaluru Arena", "Palace Grounds", 13.0057, 77.5920),
     ("Rangmanch Auditorium", "Jayanagar", 12.9250, 77.5938),
     ("The Laugh Lounge", "Indiranagar", 12.9784, 77.6408)),
    ("Hyderabad", "Telangana", True,
     [("Reelhouse", "Gachibowli", 17.4401, 78.3489, True),
      ("Starlight Cinemas", "Banjara Hills", 17.4156, 78.4347, False),
      ("Marquee Multiplex", "Kukatpally", 17.4948, 78.3996, False)],
     ("Hyderabad Arena", "HITEC City", 17.4435, 78.3772),
     ("Rangmanch Auditorium", "Abids", 17.3930, 78.4760),
     ("The Laugh Lounge", "Jubilee Hills", 17.4326, 78.4071)),
    ("Chennai", "Tamil Nadu", True,
     [("Reelhouse", "Velachery", 12.9815, 80.2180, True),
      ("Starlight Cinemas", "T. Nagar", 13.0418, 80.2341, False),
      ("Marquee Multiplex", "Anna Nagar", 13.0850, 80.2101, False)],
     ("Chennai Arena", "Nandanam", 13.0298, 80.2412),
     ("Rangmanch Auditorium", "Mylapore", 13.0368, 80.2676),
     ("The Laugh Lounge", "Adyar", 13.0012, 80.2565)),
    ("Kolkata", "West Bengal", True,
     [("Reelhouse", "Salt Lake", 22.5867, 88.4171, True),
      ("Starlight Cinemas", "Park Street", 22.5535, 88.3523, False),
      ("Marquee Multiplex", "Gariahat", 22.5186, 88.3657, False)],
     ("Kolkata Arena", "New Town", 22.5958, 88.4795),
     ("Rangmanch Auditorium", "Esplanade", 22.5646, 88.3517),
     ("The Laugh Lounge", "Ballygunge", 22.5272, 88.3638)),
    ("Pune", "Maharashtra", True,
     [("Reelhouse", "Viman Nagar", 18.5679, 73.9143, True),
      ("Starlight Cinemas", "Kothrud", 18.5074, 73.8077, False),
      ("Marquee Multiplex", "Hinjewadi", 18.5913, 73.7389, False)],
     ("Pune Arena", "Balewadi", 18.5794, 73.7700),
     ("Rangmanch Auditorium", "Shivajinagar", 18.5314, 73.8446),
     ("The Laugh Lounge", "Koregaon Park", 18.5362, 73.8940)),
    ("Ahmedabad", "Gujarat", True,
     [("Reelhouse", "SG Highway", 23.0300, 72.5070, True),
      ("Starlight Cinemas", "Navrangpura", 23.0365, 72.5611, False),
      ("Marquee Multiplex", "Maninagar", 22.9962, 72.6036, False)],
     ("Ahmedabad Arena", "Motera", 23.0916, 72.5975),
     ("Rangmanch Auditorium", "Ellisbridge", 23.0225, 72.5650),
     ("The Laugh Lounge", "Prahlad Nagar", 23.0120, 72.5108)),
    ("Vadodara", "Gujarat", False,
     [("Reelhouse", "Alkapuri", 22.3108, 73.1690, False),
      ("Starlight Cinemas", "Akota", 22.2987, 73.1663, False),
      ("Marquee Multiplex", "Manjalpur", 22.2708, 73.1937, False)],
     None,
     ("Rangmanch Auditorium", "Sayajigunj", 22.3156, 73.1857),
     ("The Laugh Lounge", "Gotri", 22.3170, 73.1350)),
    ("Gandhinagar", "Gujarat", False,
     [("Reelhouse", "Sector 21", 23.2343, 72.6497, False),
      ("Starlight Cinemas", "Infocity", 23.1920, 72.6290, False),
      ("Marquee Multiplex", "Sargasan", 23.1928, 72.6210, False)],
     None,
     ("Rangmanch Auditorium", "Sector 17", 23.2238, 72.6501),
     ("The Laugh Lounge", "Kudasan", 23.1846, 72.6345)),
]

# ── Seat layouts ──────────────────────────────────────────────────────────────
ROWS = "ABCDEFGHIJKLMNOP"

# screen kind -> (layout_type, seats per row, [(section, rows, seat_type)])
LAYOUTS = {
    # 10 rows x 16 = 160 seats; recliners at the back, wheelchair spaces in row A
    "audi": ("cinema", 16, [("Classic", "ABC", "standard"), ("Prime", "DEFGH", "standard"), ("Recliner", "IJ", "premium")]),
    # 10 rows x 14 = 140 seats
    "audi_3d": ("cinema", 14, [("Classic", "ABC", "standard"), ("Prime", "DEFGHIJ", "standard")]),
    # 12 rows x 18 = 216 seats
    "imax": ("cinema", 18, [("Classic", "AB", "standard"), ("Prime", "CDEFGHIJ", "standard"), ("Recliner", "KL", "premium")]),
    # 6 rows x 10 = 60 recliners
    "gold": ("cinema", 10, [("Recliner", "ABCDEF", "premium")]),
    # arena grandstand: 6 rows x 20 = 120 seats (standing zones are added per show)
    "arena": ("concert", 20, [("Grandstand Premium", "AB", "premium"), ("Grandstand", "CDEF", "standard")]),
    # auditorium: 12 rows x 18 = 216 seats
    "auditorium": ("theatre", 18, [("Premium", "ABC", "premium"), ("Stalls", "DEFGHI", "standard"), ("Balcony", "JKL", "standard")]),
    # comedy club: 8 rows x 12 = 96 seats
    "club": ("theatre", 12, [("Front Row", "AB", "premium"), ("House", "CDEFGH", "standard")]),
}

# cinema price per section (metro); smaller cities pay 80 %
CINEMA_PRICES = {
    "audi": {"Classic": 190, "Prime": 260, "Recliner": 520},
    "audi_3d": {"Classic": 230, "Prime": 300},
    "imax": {"Classic": 360, "Prime": 450, "Recliner": 750},
    "gold": {"Recliner": 650},
}

# ── Movies (real titles, our own short descriptions, no posters copied) ─────
MOVIES = [
    dict(slug="avengers-endgame", title="Avengers: Endgame", language="English", genre="Action, Sci-Fi",
         runtime=181, certificate="UA", release="2019-04-26", imax=True,
         about="The surviving Avengers regroup for one last mission to undo the snap and bring back everyone who was lost.",
         cast=[("Robert Downey Jr.", "Tony Stark"), ("Chris Evans", "Steve Rogers"), ("Scarlett Johansson", "Natasha Romanoff"),
               ("Anthony Russo, Joe Russo", "Directors")]),
    dict(slug="spider-man-no-way-home", title="Spider-Man: No Way Home", language="English", genre="Action, Adventure",
         runtime=148, certificate="UA", release="2021-12-16", imax=True,
         about="With his identity revealed, Peter Parker asks for a spell that goes wrong and pulls in visitors from other worlds.",
         cast=[("Tom Holland", "Peter Parker"), ("Zendaya", "MJ"), ("Benedict Cumberbatch", "Doctor Strange"),
               ("Jon Watts", "Director")]),
    dict(slug="interstellar", title="Interstellar", language="English", genre="Sci-Fi, Drama",
         runtime=169, certificate="UA", release="2014-11-07", imax=True,
         about="A former pilot leads a crew through a wormhole to find a new home for humanity while time runs out on Earth.",
         cast=[("Matthew McConaughey", "Cooper"), ("Anne Hathaway", "Brand"), ("Jessica Chastain", "Murph"),
               ("Christopher Nolan", "Director")]),
    dict(slug="dune-part-two", title="Dune: Part Two", language="English", genre="Sci-Fi, Adventure",
         runtime=166, certificate="UA", release="2024-03-01", imax=True,
         about="Paul Atreides joins the Fremen of Arrakis and faces a choice between love and the fate of the known universe.",
         cast=[("Timothée Chalamet", "Paul Atreides"), ("Zendaya", "Chani"), ("Rebecca Ferguson", "Lady Jessica"),
               ("Denis Villeneuve", "Director")]),
    dict(slug="oppenheimer", title="Oppenheimer", language="English", genre="Biography, Drama",
         runtime=180, certificate="UA", release="2023-07-21", imax=True,
         about="The story of the physicist who led the Manhattan Project, and of what the bomb cost him afterwards.",
         cast=[("Cillian Murphy", "J. Robert Oppenheimer"), ("Emily Blunt", "Kitty Oppenheimer"), ("Robert Downey Jr.", "Lewis Strauss"),
               ("Christopher Nolan", "Director")]),
    dict(slug="3-idiots", title="3 Idiots", language="Hindi", genre="Comedy, Drama",
         runtime=170, certificate="U", release="2009-12-25", imax=False,
         about="Two friends search for the college classmate who taught them to chase excellence instead of marks.",
         cast=[("Aamir Khan", "Rancho"), ("R. Madhavan", "Farhan"), ("Sharman Joshi", "Raju"),
               ("Rajkumar Hirani", "Director")]),
    dict(slug="dangal", title="Dangal", language="Hindi", genre="Sports, Drama",
         runtime=161, certificate="U", release="2016-12-23", imax=False,
         about="A former wrestler trains his daughters against all odds to compete for India on the world stage.",
         cast=[("Aamir Khan", "Mahavir Singh Phogat"), ("Fatima Sana Shaikh", "Geeta Phogat"), ("Sanya Malhotra", "Babita Kumari"),
               ("Nitesh Tiwari", "Director")]),
    dict(slug="zindagi-na-milegi-dobara", title="Zindagi Na Milegi Dobara", language="Hindi", genre="Comedy, Drama",
         runtime=155, certificate="UA", release="2011-07-15", imax=False,
         about="Three old friends take a road trip across Spain and each faces the fear that has been holding him back.",
         cast=[("Hrithik Roshan", "Arjun"), ("Farhan Akhtar", "Imraan"), ("Abhay Deol", "Kabir"),
               ("Zoya Akhtar", "Director")]),
    dict(slug="rrr", title="RRR", language="Telugu", genre="Action, Drama",
         runtime=187, certificate="UA", release="2022-03-25", imax=False,
         about="Two revolutionaries on opposite sides of the law form an unlikely friendship in 1920s India.",
         cast=[("N. T. Rama Rao Jr.", "Komaram Bheem"), ("Ram Charan", "Alluri Sitarama Raju"), ("Alia Bhatt", "Sita"),
               ("S. S. Rajamouli", "Director")]),
    dict(slug="jawan", title="Jawan", language="Hindi", genre="Action, Thriller",
         runtime=169, certificate="UA", release="2023-09-07", imax=False,
         about="A man with a mysterious past sets out to right the wrongs of a corrupt system, one daring heist at a time.",
         cast=[("Shah Rukh Khan", "Azad / Vikram Rathore"), ("Nayanthara", "Narmada"), ("Vijay Sethupathi", "Kalee"),
               ("Atlee", "Director")]),
]

# ── Live events (fictional performers) ───────────────────────────────────────
# type, slug, title, genre, language, minutes, age, about, artists, venue kind, cities (index), dates (day offsets), start
LIVE = [
    # concerts at arenas
    ("concert", "monsoon-ragas-live", "Monsoon Ragas Live", "Indian Fusion", "Hindi", 150, "All ages",
     "An evening of classical ragas meeting electronic beats, with a 20-piece ensemble and a full light show.",
     [("The Monsoon Collective", "Band")], "arena", [0, 2, 6], [2, 4, 9], "19:00"),
    ("concert", "bollywood-symphony", "Bollywood Symphony Night", "Bollywood, Orchestra", "Hindi", 180, "All ages",
     "Six decades of film songs, played by a live symphony orchestra and choir.",
     [("City Philharmonic Orchestra", "Orchestra"), ("Aarohi Choir", "Choir")], "arena", [1, 3, 7], [3, 5, 10], "19:30"),
    ("concert", "neon-skyline-tour", "Neon Skyline Tour", "Electronic, Pop", "English", 180, "16+",
     "A late-night electronic set with lasers, confetti and a standing fan pit right at the stage.",
     [("DJ Northstar", "DJ"), ("Lumen", "Opening act")], "arena", [0, 4, 5], [4, 6, 11], "20:00"),
    ("concert", "sufi-under-the-stars", "Sufi Under the Stars", "Sufi, Qawwali", "Urdu", 150, "All ages",
     "Qawwali and Sufi poetry in an open-air setting, from soft ghazals to full-voiced finales.",
     [("Noor Ensemble", "Qawwali group")], "arena", [1, 6, 7], [2, 5, 12], "19:00"),
    ("concert", "indie-express", "Indie Express", "Indie, Rock", "English", 210, "All ages",
     "Four independent bands, one stage: guitars, harmonies and a crowd that sings along.",
     [("Paper Boats", "Band"), ("Kite Season", "Band"), ("Static Bloom", "Band")], "arena", [2, 3, 4], [5, 6, 13], "18:30"),
    # stand-up at comedy clubs
    ("other", "overthinking-live", "Overthinking: Live", "Stand-up Comedy", "Hinglish", 75, "16+",
     "A stand-up hour about group chats, parents on WhatsApp and the fine art of replying 'ok'.",
     [("Kabir Saxena (fictional)", "Comedian")], "club", [0, 1, 2, 6, 8], [1, 3, 5, 8, 10, 12], "20:00"),
    ("other", "middle-class-millionaire", "Middle Class Millionaire", "Stand-up Comedy", "Hindi", 70, "16+",
     "Budgets, EMIs and why every uncle is a stock-market expert, in one fast-paced set.",
     [("Ritu Bhandari (fictional)", "Comedian")], "club", [3, 4, 5, 7, 9], [2, 4, 6, 9, 11, 13], "20:30"),
    ("other", "engineer-not-by-choice", "Engineer, Not by Choice", "Stand-up Comedy", "English", 60, "16+",
     "Four years of engineering, zero regrets (mostly): a set for everyone who survived semester exams.",
     [("Arjun Pillai (fictional)", "Comedian")], "club", [2, 3, 6, 7, 8, 9], [1, 4, 7, 10, 13], "19:30"),
    ("other", "open-mic-sundays", "Open Mic Sundays", "Stand-up Comedy", "Hinglish", 90, "16+",
     "Eight new comedians, five minutes each. Some will be great; all will be brave.",
     [("Rotating line-up", "Comedians")], "club", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [2, 9], "18:00"),
    # plays at auditoriums
    ("theatre", "hamlet-retold", "Hamlet, Retold", "Drama", "English", 140, "13+",
     "Shakespeare's tragedy in a modern setting: a family business, a missing father and a son who cannot decide.",
     [("Footlights Repertory", "Theatre company")], "auditorium", [0, 1, 2, 5], [3, 4, 10, 11], "19:30"),
    ("theatre", "the-cherry-orchard", "The Cherry Orchard", "Drama", "English", 120, "13+",
     "Chekhov's play about a family about to lose its estate, and everything they cannot let go of.",
     [("Blue Door Theatre", "Theatre company")], "auditorium", [1, 3, 4, 6], [4, 5, 11, 12], "19:00"),
    ("theatre", "godaan-on-stage", "Godaan on Stage", "Drama", "Hindi", 130, "All ages",
     "Premchand's novel of a farmer's dream of owning a cow, adapted for the stage.",
     [("Lok Rang Mandal", "Theatre company")], "auditorium", [0, 7, 8, 9], [3, 5, 10, 12], "18:30"),
    ("theatre", "midsummer-musical", "A Midsummer Night's Musical", "Musical, Comedy", "English", 125, "All ages",
     "Lovers, fairies and a troupe of terrible actors, now with songs.",
     [("Footlights Repertory", "Theatre company")], "auditorium", [2, 3, 5, 6, 7], [6, 7, 13], "17:00"),
    ("theatre", "raktakarabi", "Raktakarabi (Red Oleanders)", "Drama", "Bengali", 110, "13+",
     "Tagore's play about a kingdom of gold miners and the woman who brings them hope.",
     [("Kalpana Natya Sangha", "Theatre company")], "auditorium", [5, 1, 4], [5, 6, 12], "18:30"),
    # workshops and others
    ("other", "pottery-for-beginners", "Pottery for Beginners", "Workshop", "English", 120, "12+",
     "Learn to centre clay and throw your first bowl on the wheel. All materials included.",
     [("Clay Studio Collective", "Hosts")], "club", [0, 2, 6, 7, 8], [2, 9], "11:00"),
    ("other", "kids-science-show", "Kids Science Show", "Kids, Workshop", "English", 90, "All ages",
     "Bubbles, slime and safe explosions: a hands-on science show for children aged 6 to 12.",
     [("Curious Minds Lab", "Hosts")], "auditorium", [1, 3, 4, 5, 9], [2, 3, 9, 10], "11:00"),
    ("other", "board-game-night", "Board Game Night", "Games", "English", 180, "12+",
     "Fifty board games, a friendly host and new people to play with.",
     [("Dice & Tea", "Hosts")], "club", [1, 2, 3, 4, 7], [4, 11], "18:00"),
]

LIVE_PRICES = {
    "arena": {"Grandstand Premium": 2499, "Grandstand": 1499},
    "auditorium": {"Premium": 1200, "Stalls": 800, "Balcony": 500},
    "club": {"Front Row": 799, "House": 499},
}
ARENA_ZONES = [  # name, zone_type, capacity, price, colour
    ("VIP Fan Pit", "fan_pit", 400, 4999, "#ff0055"),
    ("Gold Standing", "standing", 1200, 2499, "#287cff"),
]
WORKSHOP_PRICE = {"Workshop": 0.6, "Kids, Workshop": 0.5, "Games": 0.4}  # share of the normal ticket price

TERMS = ("Demo listing for the TicketFlow course project. Tickets are test bookings only; "
         "no real event takes place and no real payment is taken.")


# ── Building blocks ───────────────────────────────────────────────────────────

def screen_plan(metro: bool, multiplex_idx: int, has_imax: bool):
    """Metro multiplexes have 4 screens, others 3: an IMAX or large audi, a 3D audi,
    a Gold recliner hall (or a third audi) and, in metros, a fourth audi."""
    first = ("IMAX", "imax") if has_imax else ("Audi 1", "audi")
    third = ("Gold Recliners", "gold") if multiplex_idx != 1 else ("Audi 3", "audi")
    plan = [first, ("Audi 2 3D", "audi_3d"), third]
    if metro:
        plan.append(("Audi 4", "audi_3d"))
    return plan


def layout_seats(kind: str):
    layout_type, per_row, sections = LAYOUTS[kind]
    seats = []
    for section, rows, seat_type in sections:
        for row in rows:
            for n in range(1, per_row + 1):
                stype = seat_type
                if kind in ("audi", "imax", "audi_3d") and row == "A" and n in (1, per_row):
                    stype = "accessible"
                seats.append((section, row, n, stype))
    return layout_type, seats


async def ensure_organizer(conn) -> uuid.UUID:
    user_id = uid("user", DEMO_MANAGER_UID)
    await conn.execute(
        """INSERT INTO users (id, firebase_uid, name, email, status)
           VALUES ($1, $2, 'TicketFlow Demo Manager', 'demo.catalogue@ticketflow.demo', 'active')
           ON CONFLICT DO NOTHING""",
        user_id, DEMO_MANAGER_UID)
    org_id = uid("organizer", ORG_NAME)
    await conn.execute(
        """INSERT INTO organizer_profiles (id, user_id, legal_name, business_type, state, verification_status, trust_tier)
           VALUES ($1, $2, $3, 'COMPANY', 'Gujarat', 'APPROVED', 'TIER_3')
           ON CONFLICT DO NOTHING""",
        org_id, user_id, ORG_NAME)
    return org_id


async def ensure_venue(conn, key, name, city, state, area, lat, lng, screens, stats):
    """Insert a venue with its screens and seats. Returns [(screen_id, kind, name)]."""
    venue_id = uid("venue", key)
    inserted = await conn.fetchval(
        """INSERT INTO venues (id, name, address, city, state, verification_status, latitude, longitude, licensed_capacity)
           VALUES ($1, $2, $3, $4, $5, 'approved', $6, $7, $8)
           ON CONFLICT (id) DO NOTHING RETURNING id""",
        venue_id, name, f"{area}, {city}", city, state, lat, lng, 5000)
    stats["venues"] += 1 if inserted else 0
    out = []
    for screen_name, kind in screens:
        screen_id = uid("screen", key, screen_name)
        layout_type, seats = layout_seats(kind)
        capacity = len(seats) + (sum(z[2] for z in ARENA_ZONES) if kind == "arena" else 0)
        new_screen = await conn.fetchval(
            """INSERT INTO screens (id, venue_id, name, capacity, layout_type, stage_position)
               VALUES ($1, $2, $3, $4, $5, 'front') ON CONFLICT (id) DO NOTHING RETURNING id""",
            screen_id, venue_id, screen_name, capacity, layout_type)
        if new_screen:
            stats["screens"] += 1
            await conn.executemany(
                """INSERT INTO seats (id, screen_id, row_label, seat_number, seat_type, section_name)
                   VALUES ($1, $2, $3, $4, $5::seat_type, $6) ON CONFLICT DO NOTHING""",
                [(uid("seat", screen_id, r, n), screen_id, r, n, t, sec) for sec, r, n, t in seats])
            stats["seats"] += len(seats)
        out.append((screen_id, kind, screen_name))
    return out


POSTERS = True  # --no-posters: leave poster_url empty until the posters are uploaded


def poster_base() -> str:
    """Where the poster files are served from: DEMO_POSTER_BASE_URL, else the public demo-posters bucket."""
    base = os.getenv("DEMO_POSTER_BASE_URL", "").strip()
    if not base and os.getenv("SUPABASE_URL"):
        base = os.environ["SUPABASE_URL"].strip().rstrip("/") + "/storage/v1/object/public/demo-posters"
    return base.rstrip("/")


def poster_url(slug: str) -> str | None:
    base = poster_base()
    return f"{base}/{slug}.svg" if POSTERS and base else None


async def ensure_event(conn, org_id, slug, *, title, event_type, about, language, genre, minutes,
                       certificate=None, age=None, release=None, formats=(), cast=(), artists=(), stats):
    event_id = uid("event", slug)
    inserted = await conn.fetchval(
        """INSERT INTO events (id, title, description, event_type, duration_minutes, language, genre,
                               poster_url, status, organizer_id, cast_crew, artists, formats, certificate,
                               age_rating, release_date, terms_and_conditions,
                               imdb_score, metacritic_score, match_rate)
           VALUES ($1, $2, $3, $4::event_type, $5, $6, $7, $8, 'published', $9, $10::jsonb, $11::jsonb,
                   $12::text[], $13, $14, $15::date, $16, NULL, NULL, NULL)
           ON CONFLICT (id) DO NOTHING RETURNING id""",
        event_id, title, about, event_type, minutes, language, genre,
        poster_url(slug), org_id,
        json.dumps([{"name": n, "role": r} for n, r in cast]),
        json.dumps([{"name": n, "role": r} for n, r in artists]),
        list(formats), certificate, age, date.fromisoformat(release) if release else None, TERMS)
    stats["events"] += 1 if inserted else 0
    if poster_url(slug) and not inserted:
        # an earlier --no-posters run left it empty: fill it in now
        await conn.execute("UPDATE events SET poster_url = $2 WHERE id = $1 AND poster_url IS NULL",
                           event_id, poster_url(slug))
    return event_id


async def add_show(conn, event_id, screen_id, start, minutes, prices, seat_rows, zones, stats):
    """Insert one show with its seat prices (and standing zones). Skips shows that already exist."""
    show_id = uid("show", screen_id, start.isoformat())
    base = min(prices.values())
    inserted = await conn.fetchval(
        """INSERT INTO shows (id, event_id, screen_id, start_time, end_time, status, base_price, dynamic_pricing)
           VALUES ($1, $2, $3, $4, $5, 'scheduled', $6, false) ON CONFLICT (id) DO NOTHING RETURNING id""",
        show_id, event_id, screen_id, start, start + timedelta(minutes=minutes), base)
    if not inserted:
        return
    stats["shows"] += 1
    await conn.copy_records_to_table(
        "show_seats", columns=["show_id", "seat_id", "price", "status"],
        records=[(show_id, seat_id, prices[section], "available") for seat_id, section in seat_rows])
    stats["show_seats"] += len(seat_rows)
    for order, (name, ztype, cap, price, colour) in enumerate(zones, start=1):
        await conn.execute(
            """INSERT INTO show_zones (show_id, name, zone_type, total_capacity, booked_count, locked_count,
                                       price, color_hex, display_order)
               VALUES ($1, $2, $3, $4, 0, 0, $5, $6, $7)""",
            show_id, name, ztype, cap, price, colour, order)


def price_for(base: int, start: datetime, small_city: bool) -> int:
    p = base * (0.8 if small_city else 1.0)
    if start.weekday() >= 4:  # Friday to Sunday
        p *= 1.15
    if start.hour < 12:  # morning shows
        p *= 0.8
    return int(round(p / 10.0) * 10)


# ── Seed / remove ─────────────────────────────────────────────────────────────

async def seed(conn, days: int) -> dict:
    stats = dict(venues=0, screens=0, seats=0, events=0, shows=0, show_seats=0)
    org_id = await ensure_organizer(conn)
    now = datetime.now(IST)
    today = now.date()

    movie_ids = {}
    for m in MOVIES:
        movie_ids[m["slug"]] = await ensure_event(
            conn, org_id, m["slug"], title=m["title"], event_type="movie", about=m["about"],
            language=m["language"], genre=m["genre"], minutes=m["runtime"], certificate=m["certificate"],
            age="13+" if m["certificate"] == "UA" else "All ages", release=m["release"],
            formats=["2D", "IMAX 2D"] if m["imax"] else ["2D", "3D"], cast=m["cast"], stats=stats)

    live_ids = {}
    for (etype, slug, title, genre, language, minutes, age, about, artists, *_rest) in LIVE:
        live_ids[slug] = await ensure_event(
            conn, org_id, slug, title=title, event_type=etype, about=about, language=language, genre=genre,
            minutes=minutes, age=age, artists=artists, stats=stats)

    seat_cache = {}

    async def seats_of(screen_id):
        if screen_id not in seat_cache:
            seat_cache[screen_id] = [(r["id"], r["section_name"]) for r in await conn.fetch(
                "SELECT id, section_name FROM seats WHERE screen_id = $1", screen_id)]
        return seat_cache[screen_id]

    live_venues = {}  # (city_idx, kind) -> screen_id
    for c_idx, (city, state, metro, multiplexes, arena, auditorium, club) in enumerate(CITIES):
        small = not metro
        city_screens = []
        for m_idx, (chain, area, lat, lng, has_imax) in enumerate(multiplexes):
            key = f"{city}|{chain}|{area}"
            city_screens += await ensure_venue(
                conn, key, f"{chain} {area}", city, state, area, lat, lng,
                screen_plan(metro, m_idx, has_imax), stats)
        for kind, spec in (("arena", arena), ("auditorium", auditorium), ("club", club)):
            if not spec:
                continue
            name, area, lat, lng = spec
            screen_name = {"arena": "Main Stage", "auditorium": "Main Hall", "club": "Main Room"}[kind]
            [(screen_id, _, _)] = await ensure_venue(
                conn, f"{city}|{name}|{area}", f"{name}, {area}" if kind != "arena" else name,
                city, state, area, lat, lng, [(screen_name, kind)], stats)
            live_venues[(c_idx, kind)] = screen_id

        # Movies: every screen runs shows all day; movies rotate so each gets ~4-5 shows per city per day.
        imax_movies = [m for m in MOVIES if m["imax"]]
        for d in range(days):
            day = today + timedelta(days=d)
            pointer = (day.toordinal() * 3 + c_idx) % len(MOVIES)
            for s_idx, (screen_id, kind, _) in enumerate(city_screens):
                pool = imax_movies if kind == "imax" else MOVIES
                t = datetime.combine(day, time(9, 30), IST) + timedelta(minutes=15 * (s_idx % 3))
                last = datetime.combine(day, time(22, 45), IST)
                while t <= last:
                    movie = pool[pointer % len(pool)]
                    pointer += 1
                    if t > now + timedelta(minutes=30):
                        prices = {sec: price_for(p, t, small) for sec, p in CINEMA_PRICES[kind].items()}
                        await add_show(conn, movie_ids[movie["slug"]], screen_id, t, movie["runtime"],
                                       prices, await seats_of(screen_id), [], stats)
                    gap = ((movie["runtime"] + 25 + 14) // 15) * 15
                    t += timedelta(minutes=gap)

    # Live events on their set days (offsets beyond --days are skipped until a later run).
    for (etype, slug, title, genre, language, minutes, age, about, artists, kind, cities, offsets, start) in LIVE:
        hh, mm = map(int, start.split(":"))
        # A concert tour plays one night per city; club and auditorium shows repeat on every date.
        if etype == "concert":
            dates = list(zip(cities, offsets))
        else:
            dates = [(c, off) for c in cities for off in offsets]
        share = WORKSHOP_PRICE.get(genre, 1.0)
        prices = {sec: int(round(p * share / 10.0) * 10) for sec, p in LIVE_PRICES[kind].items()}
        zones = ARENA_ZONES if kind == "arena" else []
        for c_idx, off in dates:
            screen_id = live_venues.get((c_idx, kind))
            if not screen_id or off >= days:
                continue
            t = datetime.combine(today + timedelta(days=off), time(hh, mm), IST)
            if t <= now + timedelta(minutes=30):
                continue
            await add_show(conn, live_ids[slug], screen_id, t, minutes, prices, await seats_of(screen_id), zones, stats)
    return stats


async def remove(conn) -> dict:
    """Take the demo catalogue down. Shows with bookings are cancelled and their events hidden;
    everything without bookings is deleted."""
    org_id = uid("organizer", ORG_NAME)
    events = [r["id"] for r in await conn.fetch("SELECT id FROM events WHERE organizer_id = $1", org_id)]
    booked = {r["show_id"] for r in await conn.fetch(
        "SELECT DISTINCT b.show_id FROM bookings b JOIN shows s ON s.id = b.show_id WHERE s.event_id = ANY($1::uuid[])",
        events)}
    shows = [r["id"] for r in await conn.fetch("SELECT id FROM shows WHERE event_id = ANY($1::uuid[])", events)]
    free = [s for s in shows if s not in booked]
    await conn.execute("DELETE FROM shows WHERE id = ANY($1::uuid[])", free)
    await conn.execute("UPDATE shows SET status = 'cancelled' WHERE id = ANY($1::uuid[]) AND status = 'scheduled'",
                       list(booked))
    kept = {r["event_id"] for r in await conn.fetch("SELECT DISTINCT event_id FROM shows WHERE event_id = ANY($1::uuid[])", events)}
    await conn.execute("UPDATE events SET status = 'inactive' WHERE id = ANY($1::uuid[])", list(kept))
    await conn.execute("DELETE FROM events WHERE id = ANY($1::uuid[]) AND NOT (id = ANY($2::uuid[]))", events, list(kept))
    venue_keys = []
    for city, state, metro, multiplexes, arena, auditorium, club in CITIES:
        venue_keys += [f"{city}|{chain}|{area}" for chain, area, *_ in multiplexes]
        venue_keys += [f"{city}|{spec[0]}|{spec[1]}" for spec in (arena, auditorium, club) if spec]
    venue_ids = [uid("venue", k) for k in venue_keys]
    deleted_venues = await conn.fetch(
        """DELETE FROM venues v WHERE v.id = ANY($1::uuid[])
             AND NOT EXISTS (SELECT 1 FROM shows s JOIN screens sc ON sc.id = s.screen_id WHERE sc.venue_id = v.id)
           RETURNING v.id""", venue_ids)
    return dict(shows_deleted=len(free), shows_cancelled=len(booked), events_hidden=len(kept),
                events_deleted=len(events) - len(kept), venues_deleted=len(deleted_venues))


async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=7, help="how many days of showtimes to create (default 7; about 15 MB per day)")
    parser.add_argument("--dry-run", action="store_true", help="report what would be added, change nothing")
    parser.add_argument("--remove", action="store_true", help="take the demo catalogue down")
    parser.add_argument("--no-posters", action="store_true",
                        help="leave posters empty (use until the posters are uploaded; run again without it later)")
    args = parser.parse_args()
    global POSTERS
    POSTERS = not args.no_posters

    from config import DATABASE_URL  # loaded from backend/.env
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        tx = conn.transaction()
        await tx.start()
        try:
            result = await (remove(conn) if args.remove else seed(conn, args.days))
            size = await conn.fetchval("SELECT pg_size_pretty(pg_database_size(current_database()))")
        except Exception:
            await tx.rollback()
            raise
        if args.dry_run:
            await tx.rollback()
            print("Dry run, nothing changed. Would have:", result)
        else:
            await tx.commit()
            print("Done:", result)
        print("Database size now:", size)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
