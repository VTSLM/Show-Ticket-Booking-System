"""
Distance helpers for "shows near me".

* Distances are straight-line (great-circle / haversine) in kilometres.
* A venue uses its own latitude/longitude when set (exact). If it has none, it is
  placed at the centre of its city (approximate) so it can still be found.
"""
import math
from typing import Iterable, Optional

EARTH_RADIUS_KM = 6371.0088
DEFAULT_RADIUS_KM = 100.0

# name, state, latitude, longitude
_CITY_ROWS = [
    # Gujarat
    ("Ahmedabad", "Gujarat", 23.0225, 72.5714), ("Gandhinagar", "Gujarat", 23.2156, 72.6369),
    ("Surat", "Gujarat", 21.1702, 72.8311), ("Vadodara", "Gujarat", 22.3072, 73.1812),
    ("Rajkot", "Gujarat", 22.3039, 70.8022), ("Bhavnagar", "Gujarat", 21.7645, 72.1519),
    ("Jamnagar", "Gujarat", 22.4707, 70.0577), ("Junagadh", "Gujarat", 21.5222, 70.4579),
    ("Anand", "Gujarat", 22.5645, 72.9289), ("Nadiad", "Gujarat", 22.6916, 72.8634),
    ("Mehsana", "Gujarat", 23.5880, 72.3693), ("Bhuj", "Gujarat", 23.2420, 69.6669),
    ("Morbi", "Gujarat", 22.8173, 70.8378), ("Navsari", "Gujarat", 20.9467, 72.9520),
    ("Bharuch", "Gujarat", 21.7051, 72.9959), ("Vapi", "Gujarat", 20.3893, 72.9106),
    ("Patan", "Gujarat", 23.8493, 72.1266), ("Surendranagar", "Gujarat", 22.7277, 71.6486),
    # Maharashtra & Goa
    ("Mumbai", "Maharashtra", 19.0760, 72.8777), ("Navi Mumbai", "Maharashtra", 19.0330, 73.0297),
    ("Thane", "Maharashtra", 19.2183, 72.9781), ("Pune", "Maharashtra", 18.5204, 73.8567),
    ("Nagpur", "Maharashtra", 21.1458, 79.0882), ("Nashik", "Maharashtra", 19.9975, 73.7898),
    ("Aurangabad", "Maharashtra", 19.8762, 75.3433), ("Kolhapur", "Maharashtra", 16.7050, 74.2433),
    ("Solapur", "Maharashtra", 17.6599, 75.9064), ("Amravati", "Maharashtra", 20.9374, 77.7796),
    ("Panaji", "Goa", 15.4909, 73.8278), ("Margao", "Goa", 15.2993, 73.9580),
    ("Vasco da Gama", "Goa", 15.3982, 73.8113),
    # North
    ("Delhi", "Delhi", 28.6139, 77.2090), ("Gurugram", "Haryana", 28.4595, 77.0266),
    ("Noida", "Uttar Pradesh", 28.5355, 77.3910), ("Faridabad", "Haryana", 28.4089, 77.3178),
    ("Ghaziabad", "Uttar Pradesh", 28.6692, 77.4538), ("Chandigarh", "Chandigarh", 30.7333, 76.7794),
    ("Mohali", "Punjab", 30.7046, 76.7179), ("Ludhiana", "Punjab", 30.9010, 75.8573),
    ("Amritsar", "Punjab", 31.6340, 74.8723), ("Jalandhar", "Punjab", 31.3260, 75.5762),
    ("Patiala", "Punjab", 30.3398, 76.3869), ("Panipat", "Haryana", 29.3909, 76.9635),
    ("Rohtak", "Haryana", 28.8955, 76.6066), ("Ambala", "Haryana", 30.3782, 76.7767),
    ("Hisar", "Haryana", 29.1492, 75.7217), ("Karnal", "Haryana", 29.6857, 76.9905),
    ("Jaipur", "Rajasthan", 26.9124, 75.7873), ("Jodhpur", "Rajasthan", 26.2389, 73.0243),
    ("Udaipur", "Rajasthan", 24.5854, 73.7125), ("Kota", "Rajasthan", 25.2138, 75.8648),
    ("Ajmer", "Rajasthan", 26.4499, 74.6399), ("Bikaner", "Rajasthan", 28.0229, 73.3119),
    ("Lucknow", "Uttar Pradesh", 26.8467, 80.9462), ("Kanpur", "Uttar Pradesh", 26.4499, 80.3319),
    ("Varanasi", "Uttar Pradesh", 25.3176, 82.9739), ("Agra", "Uttar Pradesh", 27.1767, 78.0081),
    ("Prayagraj", "Uttar Pradesh", 25.4358, 81.8463), ("Meerut", "Uttar Pradesh", 28.9845, 77.7064),
    ("Mathura", "Uttar Pradesh", 27.4924, 77.6737), ("Aligarh", "Uttar Pradesh", 27.8974, 78.0880),
    ("Bareilly", "Uttar Pradesh", 28.3670, 79.4304), ("Moradabad", "Uttar Pradesh", 28.8386, 78.7733),
    ("Gorakhpur", "Uttar Pradesh", 26.7606, 83.3732), ("Jhansi", "Uttar Pradesh", 25.4484, 78.5685),
    ("Dehradun", "Uttarakhand", 30.3165, 78.0322), ("Haridwar", "Uttarakhand", 29.9457, 78.1642),
    ("Shimla", "Himachal Pradesh", 31.1048, 77.1734), ("Srinagar", "Jammu & Kashmir", 34.0837, 74.7973),
    ("Jammu", "Jammu & Kashmir", 32.7266, 74.8570),
    # Central & East
    ("Bhopal", "Madhya Pradesh", 23.2599, 77.4126), ("Indore", "Madhya Pradesh", 22.7196, 75.8577),
    ("Gwalior", "Madhya Pradesh", 26.2183, 78.1828), ("Jabalpur", "Madhya Pradesh", 23.1815, 79.9864),
    ("Ujjain", "Madhya Pradesh", 23.1765, 75.7885), ("Raipur", "Chhattisgarh", 21.2514, 81.6296),
    ("Bhilai", "Chhattisgarh", 21.2090, 81.4285), ("Bilaspur", "Chhattisgarh", 22.0797, 82.1409),
    ("Patna", "Bihar", 25.5941, 85.1376), ("Gaya", "Bihar", 24.7914, 85.0002),
    ("Ranchi", "Jharkhand", 23.3441, 85.3096), ("Jamshedpur", "Jharkhand", 22.8046, 86.2029),
    ("Dhanbad", "Jharkhand", 23.7957, 86.4304), ("Kolkata", "West Bengal", 22.5726, 88.3639),
    ("Howrah", "West Bengal", 22.5958, 88.2636), ("Siliguri", "West Bengal", 26.7271, 88.3953),
    ("Durgapur", "West Bengal", 23.5204, 87.3119), ("Bhubaneswar", "Odisha", 20.2961, 85.8245),
    ("Cuttack", "Odisha", 20.4625, 85.8830), ("Guwahati", "Assam", 26.1445, 91.7362),
    ("Shillong", "Meghalaya", 25.5788, 91.8933), ("Imphal", "Manipur", 24.8170, 93.9368),
    ("Agartala", "Tripura", 23.8315, 91.2868), ("Gangtok", "Sikkim", 27.3389, 88.6065),
    # South
    ("Hyderabad", "Telangana", 17.3850, 78.4867), ("Secunderabad", "Telangana", 17.4399, 78.4983),
    ("Warangal", "Telangana", 17.9689, 79.5941), ("Vijayawada", "Andhra Pradesh", 16.5062, 80.6480),
    ("Visakhapatnam", "Andhra Pradesh", 17.6868, 83.2185), ("Guntur", "Andhra Pradesh", 16.3067, 80.4365),
    ("Tirupati", "Andhra Pradesh", 13.6288, 79.4192), ("Nellore", "Andhra Pradesh", 14.4426, 79.9865),
    ("Kakinada", "Andhra Pradesh", 16.9891, 82.2475), ("Rajahmundry", "Andhra Pradesh", 17.0005, 81.8040),
    ("Bengaluru", "Karnataka", 12.9716, 77.5946), ("Mysuru", "Karnataka", 12.2958, 76.6394),
    ("Mangaluru", "Karnataka", 12.9141, 74.8560), ("Hubballi", "Karnataka", 15.3647, 75.1240),
    ("Belagavi", "Karnataka", 15.8497, 74.4977), ("Chennai", "Tamil Nadu", 13.0827, 80.2707),
    ("Coimbatore", "Tamil Nadu", 11.0168, 76.9558), ("Madurai", "Tamil Nadu", 9.9252, 78.1198),
    ("Tiruchirappalli", "Tamil Nadu", 10.7905, 78.7047), ("Salem", "Tamil Nadu", 11.6643, 78.1460),
    ("Tirunelveli", "Tamil Nadu", 8.7139, 77.7567), ("Vellore", "Tamil Nadu", 12.9165, 79.1325),
    ("Thanjavur", "Tamil Nadu", 10.7870, 79.1378), ("Erode", "Tamil Nadu", 11.3410, 77.7172),
    ("Puducherry", "Puducherry", 11.9416, 79.8083), ("Kochi", "Kerala", 9.9312, 76.2673),
    ("Thiruvananthapuram", "Kerala", 8.5241, 76.9366), ("Kozhikode", "Kerala", 11.2588, 75.7804),
    ("Thrissur", "Kerala", 10.5276, 76.2144), ("Kannur", "Kerala", 11.8745, 75.3704),
    ("Kollam", "Kerala", 8.8932, 76.6141), ("Alappuzha", "Kerala", 9.4981, 76.3388),
]

INDIA_CITIES: list[dict] = [
    {"name": n, "state": s, "lat": la, "lng": lo} for n, s, la, lo in _CITY_ROWS
]

# Other names people use for the same city
_ALIASES = {
    "bangalore": "bengaluru", "bombay": "mumbai", "calcutta": "kolkata", "madras": "chennai",
    "gurgaon": "gurugram", "trivandrum": "thiruvananthapuram", "cochin": "kochi",
    "baroda": "vadodara", "mysore": "mysuru", "poona": "pune", "vizag": "visakhapatnam",
    "benares": "varanasi", "banaras": "varanasi", "allahabad": "prayagraj",
    "pondicherry": "puducherry", "panjim": "panaji", "mangalore": "mangaluru",
    "belgaum": "belagavi", "hubli": "hubballi", "trichy": "tiruchirappalli",
    "calicut": "kozhikode", "new delhi": "delhi", "chhatrapati sambhajinagar": "aurangabad",
}

_BY_NAME = {c["name"].lower(): c for c in INDIA_CITIES}


def city_centroid(city: Optional[str]) -> Optional[tuple[float, float]]:
    """Centre of a known Indian city, or None when the name isn't recognised."""
    key = " ".join((city or "").lower().replace(",", " ").split())
    key = _ALIASES.get(key, key)
    c = _BY_NAME.get(key)
    return (c["lat"], c["lng"]) if c else None


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Straight-line distance between two points on Earth, in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def venue_point(venue: dict) -> Optional[tuple[float, float, bool]]:
    """(lat, lng, exact). exact=False means the point is the centre of the venue's city."""
    lat, lng = venue.get("latitude"), venue.get("longitude")
    if lat is not None and lng is not None:
        return float(lat), float(lng), True
    centre = city_centroid(venue.get("city"))
    return (centre[0], centre[1], False) if centre else None


def venues_with_distance(venues: Iterable[dict], lat: float, lng: float) -> list[dict]:
    """Every venue whose position is known, with its distance from (lat, lng) in km."""
    out = []
    for v in venues:
        point = venue_point(v)
        if point is None:
            continue
        d = haversine_km(lat, lng, point[0], point[1])
        out.append({"venue_id": v["id"], "distance_km": round(d, 2), "exact": point[2]})
    out.sort(key=lambda x: x["distance_km"])
    return out


def venues_within(
    venues: Iterable[dict], lat: float, lng: float, radius_km: float = DEFAULT_RADIUS_KM
) -> list[dict]:
    """Venues within radius_km of (lat, lng), nearest first, each with distance_km and exact."""
    found = []
    for v in venues:
        point = venue_point(v)
        if point is None:
            continue
        d = haversine_km(lat, lng, point[0], point[1])
        if d <= radius_km:
            found.append({"venue_id": v["id"], "distance_km": round(d, 2), "exact": point[2]})
    found.sort(key=lambda x: x["distance_km"])
    return found
