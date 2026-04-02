# Vacation Planner — Design Spec

**Date:** 2026-04-01
**Status:** Approved
**Trip:** Chicago → Vienna → Crete → Zurich → Chicago | May 3–17, 2026
**Travelers:** Dan, Michelle, Owen (6 mo)

---

## Overview

A single-trip personal utility that provides a unified daily view of all reservations, flights, and bookings; an interactive map for logistics and exploration; and AI-curated activity/restaurant recommendations from trusted travel creators. Hosted on AWS as a mobile-first PWA, accessible via iOS Chrome.

### Constraints

- **One-time use** — optimized for this specific trip, not a generalizable product
- **Personal** — 2 adults + 1 infant, no multi-tenancy or auth beyond obscure URL
- **Budget** — ~$3-4/month AWS cost, free-tier APIs wherever possible
- **Timeline** — must be functional before May 3, 2026
- **Baby-friendly** — all recommendations filtered/tagged for stroller accessibility and infant suitability

---

## Trip Itinerary (Parsed from Gmail)

| Date | Type | Details |
|------|------|---------|
| May 3 (Sat) | ✈️ Travel | ORD → VIE, OS46, depart 4:20 PM, conf NZFNK5 |
| May 4–6 (Sun–Tue) | 🏠 Stay | Vienna, LUXUS-Apartment, 12 Arsenalstrasse, 1100 Vienna, Booking.com #6729256409 |
| May 7 (Wed) | 🔄 Transfer | Vienna checkout 10:30 AM → VIE T3 2:55 PM OS811 → HER 6:20 PM, conf 7O7964. Car rental pickup. Daios Cove check-in ~7:30 PM |
| May 8–13 (Thu–Tue) | 🏖️ Stay | Crete, Daios Cove Luxury Resort, Deluxe Sea View w/ Individual Pool, #57306164. Car rental active. |
| May 14 (Wed) | 🔄 Transfer | Daios Cove checkout → car return → HER 10:55 AM LX8349 → ZRH 12:50 PM, conf ZWQAO7/BO3KQS. Radisson Blu check-in. |
| May 15–16 (Thu–Fri) | 🏨 Stay | Zurich, Radisson Blu Zurich Airport, Chase #1013771579 |
| May 17 (Sat) | ✈️ Travel | ZRH → ORD, UA12, depart 9:50 AM, conf N0RGPN |

### Transport Modes by City

- **Vienna:** Public transit (U-Bahn, tram). No car.
- **Crete:** Rental car (Expedia #73378810976626). Driving times from Daios Cove.
- **Zurich:** Public transit (S-Bahn, tram). Hotel at airport — trains to city center.

### Open Items

- Car rental details incomplete (Expedia email body was empty) — check Expedia.com
- May 7 is a tight transfer day (4-hour buffer Vienna → VIE airport)
- May 14 early morning departure from Crete (car return + 10:55 AM flight)

---

## Architecture: Hybrid Static PWA + Smart Cron

### Why This Approach

For a single trip with 2 users, a full-stack app is overkill. The hybrid approach delivers near-real-time data (30-min refresh) at minimal cost and complexity. A static PWA on S3/CloudFront with a Lambda cron that regenerates the data file gives us 90% of the value of a real-time system at 10% of the complexity.

### Components

```
iPhone (Chrome PWA)
    ↕ HTTPS
CloudFront CDN (edge caching, HTTPS)
    → S3 Bucket (static PWA files + trip.json)
        ↑ writes trip.json
    Lambda: Trip Updater (EventBridge cron, every 30 min)
        ↓ calls:
        - Gmail API (new booking emails)
        - AviationStack (flight status, 48h before departure only)
        - OpenWeather (forecast per city per day)
        - Google Places (ratings, open/closed status)

    Secrets Manager (Gmail OAuth token, encrypted)
```

### Cost Estimate

| Service | Monthly Cost | Notes |
|---------|-------------|-------|
| S3 + CloudFront | ~$0.50 | Static hosting, minimal traffic |
| Lambda (EventBridge) | ~$0.50 | ~1,440 invocations/mo × ~10s each |
| Secrets Manager | ~$0.40 | 1 secret (OAuth token) |
| AviationStack | Free | 100 requests/mo free tier |
| OpenWeather | Free | 1,000 calls/day free tier |
| Mapbox | Free | 50K map loads/mo free tier |
| Claude Haiku (email parsing) | ~$1-2 | Parsing new booking emails |
| **Total** | **~$3-4/mo** | For ~6 weeks (pre-trip + trip + buffer) |

### Security

- CloudFront URL is obscure (not indexed). Optional basic auth via Lambda@Edge.
- Gmail token: encrypted in Secrets Manager, read-only scope only.
- Teardown: `cdk destroy` after trip → all resources deleted, Gmail token revoked.

---

## Section 1: Daily View & Data Model

### Day Types

Every day falls into one of three categories:

1. **Travel Day** (May 3, 17) — Flight card, airport info, route map
2. **Stay Day** (May 4–6, 8–13, 15–16) — Accommodation card, activities, restaurants, exploration map
3. **Transfer Day** (May 7, 14) — Split AM/PM: morning at origin city, flight in middle, evening at destination

### Navigation

- **Swipe left/right** between days. The day is the primary navigation unit.
- **Bottom tab bar:** Daily | Map | Bookings | Status
- Date header shows: day of week, date, city name, "Day X of Y" counter

### Daily View Content (Stay Day)

1. **Accommodation card** — hotel name, room type, night counter, confirmation number
2. **Weather widget** — temperature, conditions, water temp (Crete), sunrise/sunset
3. **Map preview** — interactive, tap to expand to full Map tab
4. **Activities section** — nearby activities with blogger badges, baby-friendly tags, drive/transit time
5. **Restaurant section** — picks with cuisine, price range, blogger consensus, ratings

### Transfer Day Split

- **AM section:** Origin city — checkout time, last-chance activities, transit to airport
- **Flight card:** Departure/arrival times, gate, terminal, real-time status
- **PM section:** Destination city — check-in time, nearby dinner options

### Data Model (per day)

```json
{
  "date": "2026-05-10",
  "day_type": "stay",
  "day_number": 4,
  "location": {
    "city": "Crete",
    "region": "Elounda",
    "country": "GR",
    "lat": 35.2601,
    "lng": 25.7314,
    "transport_mode": "driving"
  },
  "accommodation": {
    "name": "Daios Cove Luxury Resort",
    "confirmation": "57306164",
    "room": "Deluxe Room Sea View w/ Individual Pool",
    "night_n": 4,
    "total_nights": 7,
    "checkin_time": null,
    "checkout_time": null,
    "address": "Vathi, Agios Nikolaos, Crete 721 00",
    "lat": 35.2601,
    "lng": 25.7314,
    "baby_amenities": ["cot", "baby bath", "changing mat", "audio monitor", "bottle sterilizer", "high chair"]
  },
  "flights": [],
  "car_rental": {
    "active": true,
    "provider": "Expedia",
    "confirmation": "73378810976626"
  },
  "activities": [
    {
      "name": "Spinalonga Island",
      "type": "activity",
      "lat": 35.3023,
      "lng": 25.7453,
      "travel_time_min": 40,
      "travel_mode": "drive + boat",
      "bloggers": [
        { "name": "Rick Steves", "source": "youtube", "year": 2024, "sentiment": "positive", "quote": "..." },
        { "name": "Wolters World", "source": "blog", "year": 2023, "sentiment": "positive", "quote": "..." }
      ],
      "blogger_count": 2,
      "google_rating": 4.6,
      "baby_friendly": true,
      "baby_notes": "Stroller accessible on main paths, shaded areas available",
      "price": "€8 entry + boat",
      "visit_duration": "2-3 hours",
      "source": "blog_scrape"
    }
  ],
  "restaurants": [],
  "hotel_recommendations": {
    "on_property": [],
    "local_area": []
  },
  "weather": {
    "temp_high": 26,
    "temp_low": 17,
    "condition": "sunny",
    "water_temp": 21,
    "wind_kmh": 12,
    "sunrise": "06:22",
    "sunset": "20:15"
  },
  "user_additions": [],
  "notes": []
}
```

---

## Section 2: Map & Exploration View

### Two Modes

The map auto-switches based on day type but can be toggled manually:

**Logistics Mode** (travel/transfer days):
- Route line from accommodation → airport → destination
- Airport terminals labeled
- Transit/driving time estimates to airports
- Car rental pickup/dropoff markers (Crete)

**Exploration Mode** (stay days):
- Hotel pinned at center
- Activities as orange markers (📍)
- Restaurants as red markers (🍽️)
- Beaches as purple markers (🏖️)
- Tap marker → bottom sheet detail card

### Filter Chips

Toggle buttons at top of map: Activities | Restaurants | Beaches | Baby-safe | 2+ bloggers. Filters combine (AND logic).

### Marker Detail Card (bottom sheet on tap)

- Place name, type, description
- Baby-friendly badge + notes
- Google rating
- Travel time from hotel (driving for Crete, transit for Vienna/Zurich)
- Price range
- Blogger quotes section — which creators recommended it, what they said, source year
- Action buttons: Directions (deep-link to native maps) | Add to Day | Share

### Transport-Aware Directions

- **Vienna:** Deep-links open Google Maps in transit mode (U-Bahn/tram)
- **Crete:** Deep-links open Google Maps in driving mode
- **Zurich:** Deep-links open Google Maps in transit mode (S-Bahn/tram)

### Technical

- **Provider:** Mapbox GL JS — free 50K loads/month, dark theme, offline tile caching
- **Drive/transit times:** Precomputed during blog scraping, stored in trip.json
- **Directions:** Deep-link to Google Maps or Apple Maps (detects platform)
- **Trip overview mini-map:** In Bookings tab, shows full Chicago→Vienna→Crete→Zurich→Chicago route

---

## Section 3: Blog Scraping & AI Recommendation Engine

### Pipeline

Discover → Extract (LLM) → Geocode → Cross-reference → Score → Serve

### Source Creators

1. **TopJaw** — YouTube — Food & culture deep dives
2. **Rick Steves** — YouTube + Blog — Classic European travel authority
3. **Kara & Nate** — YouTube — Adventure & experience focused
4. **Flying the Nest** — YouTube — Off-the-beaten-path picks
5. **Wolters World** — YouTube + Blog — Practical tips & honest reviews
6. **Daios Cove website** — Hotel's own recommendations for local area + on-property activities

Additional sources may be added via the source research form (`source_research_form.md` in repo root — to be filled out by Dan & Michelle before the scraping pipeline runs).

### Step 1: Discover

**YouTube (primary):** Search "[creator] Vienna" / "[creator] Crete" / "[creator] Zurich" etc. Extract auto-generated captions via YouTube Data API (free tier: 10K units/day).

**Blog posts (secondary):** Site-specific Google search (`site:ricksteves.com Vienna`). Web scrape article text.

**Hotel website:** Scrape Daios Cove's local area guide and on-property activity pages.

**Crete regional targeting:** Specifically search for "[creator] eastern Crete", "Elounda", "Agios Nikolaos" to get recs near Daios Cove (most bloggers cover western Crete/Chania).

### Step 2: Extract (LLM)

Claude Haiku processes each video transcript / article and extracts:
- Place name (as stated by creator)
- Type: activity | restaurant | cafe | beach | museum | market | viewpoint
- City/region
- Creator quote (1-2 sentences)
- Sentiment: positive | mixed | negative
- Baby/stroller accessibility: yes | no | unknown
- Estimated visit duration
- Price range

**Cost:** ~50 pieces of content × ~2K tokens each = ~$0.50-1.00 total.

### Step 3: Geocode

Google Places API (or Mapbox Geocoding) resolves place names → lat/lng + Google rating + place ID. LLM normalizes fuzzy names before geocoding ("Ferryman Taverna" / "The Ferryman" / "Ferryman's" → same place).

### Step 4: Cross-Reference

Deduplicate by geocoded place ID. Merge mentions across creators. Each place gets a `bloggers[]` array with all creator mentions.

### Step 5: Score & Tag

**Ranking formula:**
- Blogger count (consensus) × 3
- Positive sentiment strength × 2
- Google rating (4.0+ baseline) × 1

**Baby-friendly tagging:** LLM assesses during extraction. Also filters out nightlife, strenuous hikes, long unshaded boat rides. Places marked "unknown" get "❓ Check suitability" tag.

**Staleness check:** Cross-reference with Google Places API `permanently_closed` flag. Prefer content from 2023+.

### Hotel Recommendations (Daios Cove)

Two categories in the data model:
- **On-property:** Spa, pools, restaurants, kids amenities, water sports → "At Your Hotel" section at top of Crete stay days
- **Local area:** Their recommended excursions, restaurants, beaches → mixed into activity/restaurant lists with "🏨 Hotel pick" badge

### Expected Output

- Vienna: ~30-50 places
- Crete: ~40-70 places
- Zurich: ~20-35 places

### Known Challenges

1. Not all creators cover all cities — some will have 2-3 sources, not all 5
2. Stale recommendations mitigated by Google Places status check and recency preference
3. Crete coverage may skew western — targeted searches for eastern Crete required

---

## Section 4: Gmail Sync (AWS)

### OAuth Token Flow

1. Local authentication creates `token.json` (already done)
2. Token uploaded to AWS Secrets Manager (encrypted at rest)
3. Lambda reads token at runtime, auto-refreshes when expired
4. Writes refreshed token back to Secrets Manager

### Incremental Sync

Lambda uses Gmail `historyId` for incremental sync — only fetches NEW emails since last run, not all 46 every time. New booking confirmations are parsed by Claude Haiku and merged into the correct day in trip.json.

### Flight Status Monitoring

- **Provider:** AviationStack API (free: 100 requests/month)
- **Strategy:** Only poll flights within 48 hours of departure to stay within free tier
- **Tracks:** Delays, gate changes, terminal changes, cancellations, aircraft changes
- **Display:** ⚠️ flags in Status tab and on relevant day card

---

## Section 5: PWA Frontend Stack

### Framework

Vanilla JS + Lit web components. No React/Next.js. Lit is ~5KB, fast on mobile, produces a static build for S3. Service worker for offline caching.

### PWA Features

- Web app manifest → installable on iOS via "Add to Home Screen"
- Launches full-screen, no browser chrome
- Service worker caches trip.json + map tiles for offline use
- Pull-to-refresh fetches latest trip.json from CloudFront

### Data Loading

Single `trip.json` file (~200-500KB) contains all 15 days, all bookings, all activities, all blog recs, weather, flight status. Fetched on load, cached by service worker. Regenerated by Lambda every 30 min.

---

## Section 6: On-the-Fly Editing

### Quick Add (FAB Button)

Floating + button visible on all screens. Tap → quick-add form:
- Type chips: Activity | Restaurant | Note
- Name input
- Day picker: Today | Tomorrow | Pick day...
- Optional note field
- Save button

### Sync Strategy

- **Local-first:** Saves to `localStorage` immediately (works offline)
- **Cloud sync:** Small API Gateway endpoint receives additions. Next Lambda run merges into trip.json.
- **Conflict resolution:** Last-write-wins. For 2 users on a personal trip, this is sufficient.

---

## Infrastructure as Code

AWS CDK (Python) for all infrastructure. Single `cdk deploy` to stand up:
- S3 bucket + CloudFront distribution
- Lambda function + EventBridge schedule
- API Gateway endpoint (for on-the-fly additions)
- Secrets Manager secret (Gmail OAuth token)
- IAM roles

`cdk destroy` after trip for clean teardown.

---

## Out of Scope

- Multi-user authentication / login
- Database (DynamoDB etc.) — trip.json is the "database"
- Push notifications (PWA on iOS Chrome doesn't support them reliably)
- Booking/payment integration (read-only — we surface info, not transact)
- Post-trip features (photo sharing, expense tracking)
