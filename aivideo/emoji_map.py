"""Topic-to-emoji mapping for decorative slide elements."""

TOPIC_EMOJI = {
    "health": "Health", "disease": "Disease", "malaria": "Malaria",
    "medicine": "Medicine", "hospital": "Hospital", "patient": "Patient",
    "vaccine": "Vaccine", "blood": "Blood", "heart": "Heart",
    "brain": "Brain", "body": "Body",
    "science": "Science", "atom": "Atom", "chemistry": "Chemistry",
    "biology": "Biology", "physics": "Physics", "research": "Research",
    "experiment": "Experiment", "cell": "Cell", "dna": "DNA", "energy": "Energy",
    "money": "Money", "finance": "Finance", "economy": "Economy", "cost": "Cost",
    "income": "Income", "budget": "Budget", "investment": "Investment",
    "code": "Code", "software": "Software", "computer": "Computer",
    "data": "Data", "algorithm": "Algorithm", "internet": "Internet",
    "world": "World", "country": "Country", "africa": "Africa", "global": "Global",
    "city": "City", "region": "Region", "map": "Map",
    "people": "People", "community": "Community", "family": "Family",
    "children": "Children", "student": "Student", "teacher": "Teacher",
    "learn": "Learn", "education": "Education", "school": "School",
    "idea": "Idea", "concept": "Concept", "knowledge": "Knowledge",
    "warning": "Warning", "danger": "Danger", "risk": "Risk",
    "solution": "Solution", "success": "Success", "result": "Result",
    "water": "Water", "tree": "Tree", "environment": "Environment",
}

ICON_EMOJI = {
    "book":    "book",
    "health":  "health",
    "money":   "money",
    "science": "science",
    "code":    "code",
    "globe":   "globe",
    "people":  "people",
    "idea":    "idea",
    "warning": "warning",
    "check":   "check",
}

def get_emoji(text, icon="book"):
    low = text.lower()
    for kw in TOPIC_EMOJI:
        if kw in low:
            return TOPIC_EMOJI[kw]
    return ICON_EMOJI.get(icon, "item")

def get_decorative(icon, n=3):
    extras = {
        "health":  ["medicine", "clinic", "body"],
        "science": ["chemistry", "experiment", "atom"],
        "money":   ["finance", "budget", "investment"],
        "code":    ["software", "data", "algorithm"],
        "globe":   ["region", "map", "travel"],
        "people":  ["team", "community", "education"],
        "idea":    ["concept", "knowledge", "insight"],
        "warning": ["danger", "risk", "cause"],
        "check":   ["success", "result", "protect"],
        "book":    ["learn", "study", "knowledge"],
    }
    base = [ICON_EMOJI.get(icon, "item")]
    return (base + extras.get(icon, ["item", "fact", "note"]))[:n]
