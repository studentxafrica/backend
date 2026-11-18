"""
StudentXmas drop wording, from the "Website Placeholders" and "Giveaway
Schedule" tabs of the StudentX Festive Season Promotion Tracker.

Kept word for word except where the team decided otherwise (18 Nov 2026):
  - Instagram handle is @studentxafrica (the tracker says @studentx).
  - Students must join StudentXmas to be picked, so "How to Qualify" says so.
  - Following on Instagram is encouraged, not a condition, until confirmed.
Brand is the tracker's Partner/Brand column.
"""

# The terms on studentx.co.ke/drops/terms; recorded on each member when they join.
STUDENTXMAS_TERMS_VERSION = "2026-11-18"

_AIRTIME_250 = {
    "title": "Safaricom Airtime Top-Up - KSh 250",
    "brand": "Safaricom",
    "badge": "DROPS MON & FRI",
    "subtext": "12 Student Spots • Instant Mobile Credit",
    "description": (
        "Stay connected all holiday season. StudentX is unlocking KSh 250 in instant airtime for 4 verified "
        "students every week (2 every Monday, 2 every Friday).\n\n"
        "Drop Dates: Nov 20, Nov 23, Nov 27, Nov 30, Dec 4, Dec 7\n\n"
        "Total Winners: 12 Students\n\n"
        "How to Qualify: Join StudentXmas and maintain a verified StudentX profile, and follow @studentxafrica "
        "on Instagram to catch every drop. Top-ups are credited directly to your registered Safaricom number."
    ),
}

# Pick date -> wording. The six KSh 250 airtime drops share one card.
STUDENTXMAS_COPY = {
    "2026-11-20": _AIRTIME_250,
    "2026-11-23": _AIRTIME_250,
    "2026-11-25": {
        "title": "Food Voucher - KSh 1,500",
        "brand": "Dining",
        "badge": "DROPS NOV 25",
        "subtext": "1 Voucher • City Eats",
        "description": (
            "Your mid-week lunch or dinner date, covered. Enjoy a KSh 1,500 dining voucher redeemable at our "
            "featured partner eatery, perfect for treating yourself or splitting a meal with a friend.\n\n"
            "Drop Date: Wednesday, November 25\n\n"
            "Total Winners: 1 Student\n\n"
            "Redemption Rules: Valid for 10 days from issue. Present your digital StudentX ID and voucher code "
            "to the cashier at the point of purchase. Non-transferable; no cash refunds."
        ),
    },
    "2026-11-27": _AIRTIME_250,
    "2026-11-30": _AIRTIME_250,
    "2026-12-02": {
        "title": "Bowling Experience for 4",
        "brand": "Bowling",
        "badge": "SQUAD DROP • DEC 2",
        "subtext": "4 Winner Spots • Shoe Rental & Games Included",
        "description": (
            "Trade lecture halls for the bowling lanes. Grab three friends and enjoy an all-inclusive group "
            "bowling session designed for your squad’s post-exam hangout.\n\n"
            "Drop Date: Wednesday, December 2\n\n"
            "Total Winners: 1 Group (4 Students)\n\n"
            "Redemption Rules: Valid for 10 days from issue. All 4 group members must be signed up and verified "
            "on StudentX and present their StudentX IDs at check-in."
        ),
    },
    "2026-12-04": _AIRTIME_250,
    "2026-12-07": _AIRTIME_250,
    "2026-12-09": {
        "title": "SHOPZETU Voucher - KSh 2,500",
        "brand": "ShopZetu",
        "badge": "DROPS DEC 9",
        "subtext": "1 Voucher • Holiday Fit Check",
        "description": (
            "Upgrade your holiday rotation on us. Step into the festive season with a KSh 2,500 SHOPZETU "
            "shopping voucher to pick out fresh fits, accessories, or summer essentials.\n\n"
            "Drop Date: Wednesday, December 9\n\n"
            "Total Winners: 1 Student\n\n"
            "Redemption Rules: Valid for 10 days from issue. Must present your verified StudentX ID at checkout "
            "alongside your official voucher code. No extensions or cash exchanges."
        ),
    },
    "2026-12-11": {
        "title": "Safaricom Power Airtime - KSh 1,000",
        "brand": "Safaricom",
        "badge": "POWER DROP • DEC 11",
        "subtext": "1 Student Spot • Heavy Data & Talk Time",
        "description": (
            "One major top-up to fuel your December streaming and calls. One verified StudentX member will "
            "unlock a lump-sum KSh 1,000 Safaricom airtime credit during Week 3 of the Festive Access Series.\n\n"
            "Drop Date: Friday, December 11\n\n"
            "Total Winners: 1 Student\n\n"
            "How to Qualify: Verified StudentX account + StudentXmas joined. Follow @studentxafrica to catch "
            "every drop. Delivered directly to the recipient's registered phone number upon verification."
        ),
    },
    "2026-12-14": {
        "title": "Bowling + Arcade Pass for 4",
        "brand": "Bowling",
        "badge": "ULTIMATE HANGOUT • DEC 14",
        "subtext": "4 Winner Spots • Bowling, Air Hockey, Pool & Foosball",
        "description": (
            "The all-access pass to game night. One verified member and three friends unlock an extended "
            "entertainment package featuring Bowling, Air Hockey, Pool, and Foosball under one roof.\n\n"
            "Drop Date: Monday, December 14\n\n"
            "Total Winners: 1 Group (4 Students)\n\n"
            "Redemption Rules: Valid for 10 days from issue. Every member of the group must hold a verified "
            "StudentX account and present their StudentX ID upon arrival."
        ),
    },
    "2026-12-18": {
        "title": "Go-Karting Grand Prix for 5",
        "brand": "Mad Max",
        "badge": "GRAND FINALE • DEC 18",
        "subtext": "5 Winner Spots • Track Session & Gear Included",
        "description": (
            "Our biggest festive drop of the year. Close out 2026 at full throttle with an exclusive Go-Karting "
            "race package for you and 4 friends, complete with helmets, briefing, and timed track laps.\n\n"
            "Drop Date: Friday, December 18\n\n"
            "Total Winners: 1 Group (5 Students)\n\n"
            "Redemption Rules: Valid for 10 days from issue. All 5 participants must be registered and verified "
            "on StudentX and present their StudentX IDs at check-in. No transfers or extensions."
        ),
    },
}
