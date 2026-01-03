"""
Pancake Agents Simulation
=========================
One run = one tick. Producers compete for consumer market share via LLM-powered decisions.

Usage:
    python main.py              # Run one tick
    python main.py --init       # Initialize DB with schema + seed data
    python main.py --reset      # Drop all tables and reinitialize
"""

import argparse
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
import json
import random
import time
import urllib.request
import urllib.error

# =============================================================================
# Configuration
# =============================================================================

# PostgreSQL connection config - defaults to NodePort for local development
DB_USER = os.getenv("DB_USER", "pancake_db_reader_writer")
DB_PASSWORD = os.getenv("DB_PASSWORD", "supersecretpasswordoftheages")
DB_HOST = os.getenv("DB_HOST", "192.168.64.2")
DB_PORT = os.getenv("DB_PORT", "30032")
DB_NAME = os.getenv("DB_NAME", "happy_pancakes")

HISTORY_WINDOW = 20  # How many past ticks producers can see
NUM_TOPPINGS_PER_PRODUCER = 5
MAX_TOPPING_SWAPS = 3
OLLAMA_BASE_URL = "http://localhost:30134"
OLLAMA_MODEL = "gemma3:1b"

# =============================================================================
# Ollama Health Check
# =============================================================================

def check_ollama_available() -> bool:
    """Check if Ollama is running and accessible."""
    try:
        req = urllib.request.Request(OLLAMA_BASE_URL, method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                print(f"✅ Ollama is running at {OLLAMA_BASE_URL}")
                return True
    except urllib.error.URLError as e:
        print(f"❌ Ollama not available at {OLLAMA_BASE_URL}: {e.reason}")
    except Exception as e:
        print(f"❌ Ollama check failed: {e}")
    return False

# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Producer:
    id: int
    name: str
    creativity_bias: int  # 1-5
    risk_tolerance: int   # 1-5

@dataclass
class Consumer:
    id: int
    openness: int       # 1-5: willingness to try unusual combinations
    pickiness: int      # 1-5: how critical/demanding they are
    impulsivity: int    # 1-5: gut feeling vs deliberate weighing
    indulgence: int     # 1-5: preference for rich, decadent options
    nostalgia: int      # 1-5: preference for classic, comforting flavors

@dataclass
class Topping:
    id: int
    name: str

@dataclass
class ProducerOffering:
    producer_id: int
    topping_ids: list[int]

@dataclass
class ConsumerChoice:
    consumer_id: int
    producer_id: int
    enticement_score: int  # 1-10

@dataclass 
class ProducerHistory:
    tick_id: int
    consumer_count: int
    market_share: float
    avg_enticement: float
    median_enticement: float
    toppings: list[str]

# =============================================================================
# Database Setup
# =============================================================================

# Schema SQL split into individual statements for PostgreSQL
SCHEMA_STATEMENTS = [
    # Core entities
    """CREATE TABLE IF NOT EXISTS producers (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        creativity_bias INTEGER CHECK (creativity_bias BETWEEN 1 AND 5),
        risk_tolerance INTEGER CHECK (risk_tolerance BETWEEN 1 AND 5)
    )""",
    
    """CREATE TABLE IF NOT EXISTS consumers (
        id SERIAL PRIMARY KEY,
        openness INTEGER CHECK (openness BETWEEN 1 AND 5),
        pickiness INTEGER CHECK (pickiness BETWEEN 1 AND 5),
        impulsivity INTEGER CHECK (impulsivity BETWEEN 1 AND 5),
        indulgence INTEGER CHECK (indulgence BETWEEN 1 AND 5),
        nostalgia INTEGER CHECK (nostalgia BETWEEN 1 AND 5)
    )""",
    
    """CREATE TABLE IF NOT EXISTS toppings (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    )""",
    
    # Tick state
    """CREATE TABLE IF NOT EXISTS ticks (
        id SERIAL PRIMARY KEY,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP  -- NULL until tick finishes
    )""",
    
    # Per-tick snapshots (append-only)
    """CREATE TABLE IF NOT EXISTS producer_offerings (
        tick_id INTEGER REFERENCES ticks(id),
        producer_id INTEGER REFERENCES producers(id),
        PRIMARY KEY (tick_id, producer_id)
    )""",
    
    """CREATE TABLE IF NOT EXISTS producer_toppings (
        tick_id INTEGER REFERENCES ticks(id),
        producer_id INTEGER REFERENCES producers(id),
        topping_id INTEGER REFERENCES toppings(id),
        PRIMARY KEY (tick_id, producer_id, topping_id)
    )""",
    
    """CREATE TABLE IF NOT EXISTS consumer_choices (
        tick_id INTEGER REFERENCES ticks(id),
        consumer_id INTEGER REFERENCES consumers(id),
        producer_id INTEGER REFERENCES producers(id),
        enticement_score INTEGER CHECK (enticement_score BETWEEN 1 AND 10),
        PRIMARY KEY (tick_id, consumer_id)
    )""",
    
    # Derived stats (computed at end of tick)
    """CREATE TABLE IF NOT EXISTS producer_round_stats (
        tick_id INTEGER REFERENCES ticks(id),
        producer_id INTEGER REFERENCES producers(id),
        consumer_count INTEGER,
        market_share REAL,
        avg_enticement REAL,
        median_enticement REAL,
        PRIMARY KEY (tick_id, producer_id)
    )""",
]

# Separate index creation (CREATE UNIQUE INDEX IF NOT EXISTS not universally supported)
INDEX_SQL = """CREATE UNIQUE INDEX IF NOT EXISTS idx_exclusive_topping ON producer_toppings(tick_id, topping_id)"""

# =============================================================================
# Seed Data
# =============================================================================

SEED_PRODUCERS = [
    ("Fluffy's Pancake Palace", 3, 3),   # Balanced
    ("Wild Stack Shack", 5, 5),          # Creative risk-taker
    ("Grandma's Griddle", 1, 1),         # Conservative traditionalist
]

SEED_CONSUMERS = [
    # (openness, pickiness, impulsivity, indulgence, nostalgia)
    (5, 2, 5, 4, 1),  # Adventurous impulsive indulger
    (1, 5, 1, 2, 5),  # Traditional picky deliberate nostalgic
    (3, 3, 3, 3, 3),  # Perfectly balanced
    (5, 4, 2, 5, 1),  # Open picky deliberate indulger
    (1, 1, 5, 1, 5),  # Simple impulsive nostalgic
    (4, 2, 4, 3, 2),  # Open easy-going impulsive moderate
    (2, 5, 1, 4, 4),  # Cautious picky deliberate indulgent nostalgic
    (5, 1, 3, 2, 1),  # Adventurous easy-going balanced simple
    (3, 4, 5, 5, 2),  # Moderate picky impulsive indulgent
    (2, 2, 2, 3, 5),  # Cautious easy-going deliberate nostalgic
]

SEED_TOPPINGS = [
    # Classic sweet
    "blueberry", "strawberry", "banana", "chocolate chip", "whipped cream",
    # Syrups & spreads
    "maple syrup", "honey", "peanut butter", "nutella", "caramel",
    # Savory
    "bacon", "fried egg", "cheddar cheese", "goat cheese", "prosciutto",
    # Nuts & seeds
    "walnut", "pistachio", "almond", "black sesame", "candied pecan",
    # Exotic
    "matcha powder", "lavender honey", "mango", "passion fruit", "cardamom sugar",
]

def init_db(conn, reset: bool = False) -> None:
    """Initialize database schema and seed data."""
    cur = conn.cursor()
    
    if reset:
        print("🗑️  Dropping all tables...")
        cur.execute("DROP TABLE IF EXISTS producer_round_stats CASCADE")
        cur.execute("DROP TABLE IF EXISTS consumer_choices CASCADE")
        cur.execute("DROP TABLE IF EXISTS producer_toppings CASCADE")
        cur.execute("DROP TABLE IF EXISTS producer_offerings CASCADE")
        cur.execute("DROP TABLE IF EXISTS ticks CASCADE")
        cur.execute("DROP TABLE IF EXISTS toppings CASCADE")
        cur.execute("DROP TABLE IF EXISTS consumers CASCADE")
        cur.execute("DROP TABLE IF EXISTS producers CASCADE")
        conn.commit()
    
    print("📋 Creating schema...")
    for statement in SCHEMA_STATEMENTS:
        cur.execute(statement)
    
    # Create index (may already exist)
    try:
        cur.execute(INDEX_SQL)
    except psycopg2.errors.DuplicateTable:
        conn.rollback()  # Index already exists, continue
    
    conn.commit()
    
    # Check if already seeded
    cur.execute("SELECT COUNT(*) FROM producers")
    existing = cur.fetchone()[0]
    if existing > 0:
        print("✅ Database already seeded.")
        cur.close()
        return
    
    print("🌱 Seeding data...")
    
    # Seed producers - use INSERT with explicit IDs and reset sequence
    for i, (name, creativity, risk) in enumerate(SEED_PRODUCERS, start=1):
        cur.execute(
            "INSERT INTO producers (id, name, creativity_bias, risk_tolerance) VALUES (%s, %s, %s, %s)",
            (i, name, creativity, risk)
        )
    cur.execute("SELECT setval('producers_id_seq', %s)", (len(SEED_PRODUCERS),))
    
    # Seed consumers
    for i, (openness, pickiness, impulsivity, indulgence, nostalgia) in enumerate(SEED_CONSUMERS, start=1):
        cur.execute(
            "INSERT INTO consumers (id, openness, pickiness, impulsivity, indulgence, nostalgia) VALUES (%s, %s, %s, %s, %s, %s)",
            (i, openness, pickiness, impulsivity, indulgence, nostalgia)
        )
    cur.execute("SELECT setval('consumers_id_seq', %s)", (len(SEED_CONSUMERS),))
    
    # Seed toppings
    for i, name in enumerate(SEED_TOPPINGS, start=1):
        cur.execute("INSERT INTO toppings (id, name) VALUES (%s, %s)", (i, name))
    cur.execute("SELECT setval('toppings_id_seq', %s)", (len(SEED_TOPPINGS),))
    
    conn.commit()
    cur.close()
    print(f"✅ Seeded {len(SEED_PRODUCERS)} producers, {len(SEED_CONSUMERS)} consumers, {len(SEED_TOPPINGS)} toppings.")

# =============================================================================
# State Retrieval
# =============================================================================

def get_producers(conn) -> list[Producer]:
    """Get all producers."""
    cur = conn.cursor()
    cur.execute("SELECT id, name, creativity_bias, risk_tolerance FROM producers ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    return [Producer(id=r[0], name=r[1], creativity_bias=r[2], risk_tolerance=r[3]) for r in rows]

def get_consumers(conn) -> list[Consumer]:
    """Get all consumers."""
    cur = conn.cursor()
    cur.execute("SELECT id, openness, pickiness, impulsivity, indulgence, nostalgia FROM consumers ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    return [Consumer(id=r[0], openness=r[1], pickiness=r[2], impulsivity=r[3], indulgence=r[4], nostalgia=r[5]) for r in rows]

def get_all_toppings(conn) -> list[Topping]:
    """Get all available toppings."""
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM toppings ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    return [Topping(id=r[0], name=r[1]) for r in rows]

def get_latest_completed_tick(conn) -> Optional[int]:
    """Get the most recent completed tick ID, or None if no ticks yet."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM ticks WHERE completed_at IS NOT NULL ORDER BY id DESC LIMIT 1")
    result = cur.fetchone()
    cur.close()
    return result[0] if result else None

def get_producer_current_toppings(conn, producer_id: int, tick_id: int) -> list[int]:
    """Get topping IDs for a producer from a specific tick."""
    cur = conn.cursor()
    cur.execute(
        "SELECT topping_id FROM producer_toppings WHERE producer_id = %s AND tick_id = %s ORDER BY topping_id",
        (producer_id, tick_id)
    )
    rows = cur.fetchall()
    cur.close()
    return [r[0] for r in rows]

def get_producer_history(conn, producer_id: int, limit: int = HISTORY_WINDOW) -> list[ProducerHistory]:
    """Get historical stats for a producer (most recent first)."""
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            s.tick_id,
            s.consumer_count,
            s.market_share,
            s.avg_enticement,
            s.median_enticement,
            string_agg(t.name, ',' ORDER BY t.name) as topping_names
        FROM producer_round_stats s
        JOIN producer_offerings o ON s.tick_id = o.tick_id AND s.producer_id = o.producer_id
        JOIN producer_toppings pt ON s.tick_id = pt.tick_id AND s.producer_id = pt.producer_id
        JOIN toppings t ON pt.topping_id = t.id
        WHERE s.producer_id = %s
        GROUP BY s.tick_id, s.consumer_count, s.market_share, s.avg_enticement, s.median_enticement
        ORDER BY s.tick_id DESC
        LIMIT %s
    """, (producer_id, limit))
    rows = cur.fetchall()
    cur.close()
    
    return [
        ProducerHistory(
            tick_id=r[0],
            consumer_count=r[1],
            market_share=r[2],
            avg_enticement=r[3],
            median_enticement=r[4],
            toppings=r[5].split(",") if r[5] else []
        )
        for r in rows
    ]

def get_toppings_used_last_tick(conn, tick_id: int) -> dict[int, list[int]]:
    """Get mapping of producer_id -> topping_ids from a tick."""
    cur = conn.cursor()
    cur.execute(
        "SELECT producer_id, topping_id FROM producer_toppings WHERE tick_id = %s",
        (tick_id,)
    )
    rows = cur.fetchall()
    cur.close()
    
    result: dict[int, list[int]] = {}
    for producer_id, topping_id in rows:
        if producer_id not in result:
            result[producer_id] = []
        result[producer_id].append(topping_id)
    return result

# =============================================================================
# Tick Management
# =============================================================================

def cleanup_incomplete_tick(conn) -> None:
    """Remove any incomplete tick and its associated data."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM ticks WHERE completed_at IS NULL")
    incomplete = cur.fetchone()
    
    if incomplete:
        tick_id = incomplete[0]
        print(f"🧹 Cleaning up incomplete tick {tick_id}...")
        cur.execute("DELETE FROM producer_round_stats WHERE tick_id = %s", (tick_id,))
        cur.execute("DELETE FROM consumer_choices WHERE tick_id = %s", (tick_id,))
        cur.execute("DELETE FROM producer_toppings WHERE tick_id = %s", (tick_id,))
        cur.execute("DELETE FROM producer_offerings WHERE tick_id = %s", (tick_id,))
        cur.execute("DELETE FROM ticks WHERE id = %s", (tick_id,))
        conn.commit()
    cur.close()

def start_tick(conn) -> int:
    """Start a new tick and return its ID."""
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ticks (started_at) VALUES (%s) RETURNING id",
        (datetime.now(),)
    )
    tick_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    print(f"🎬 Started tick {tick_id}")
    return tick_id

def complete_tick(conn, tick_id: int) -> None:
    """Mark a tick as complete."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE ticks SET completed_at = %s WHERE id = %s",
        (datetime.now(), tick_id)
    )
    conn.commit()
    cur.close()
    print(f"✅ Completed tick {tick_id}")

# =============================================================================
# LLM Integration (Placeholders)
# =============================================================================

def build_producer_prompt(
    producer: Producer,
    current_toppings: list[str],
    all_toppings: list[str],
    history: list[ProducerHistory],
    is_first_tick: bool
) -> str:
    """Build the prompt for a producer's decision."""
    
    # Build history analysis section
    history_section = ""
    urgent_warning = ""
    
    if history and not is_first_tick:
        recent = history[0] if history else None
        if recent:
            if recent.market_share == 0:
                urgent_warning = f"\n🚨 CRISIS: You got ZERO customers last round! Your current menu is FAILING. You MUST change something!\n"
            elif recent.market_share < 0.2:
                urgent_warning = f"\n⚠️ WARNING: You only got {recent.market_share:.0%} market share. Consider making changes!\n"
            elif recent.market_share > 0.5:
                urgent_warning = f"\n✅ GREAT: You dominated with {recent.market_share:.0%} market share. Your strategy is working!\n"
        
        history_section = "\nYOUR RECENT PERFORMANCE:\n"
        for h in history[:5]:
            status = "💀" if h.market_share == 0 else "⚠️" if h.market_share < 0.2 else "✅" if h.market_share > 0.4 else "😐"
            history_section += f"{status} Tick {h.tick_id}: {h.consumer_count} customers ({h.market_share:.0%} share), toppings: {', '.join(h.toppings)}\n"
    else:
        history_section = "\nThis is your FIRST ROUND - pick an interesting starting menu!\n"
    
    # Personality-driven guidance
    if producer.risk_tolerance >= 4:
        risk_guidance = "You LOVE making big changes. Swap 2-3 toppings when things aren't working!"
    elif producer.risk_tolerance <= 2:
        risk_guidance = "You prefer stability. Only swap 1 topping at most, even if struggling."
    else:
        risk_guidance = "You make reasonable changes. Swap 1-2 toppings if performance is poor."
    
    if producer.creativity_bias >= 4:
        creativity_guidance = "You love UNUSUAL combinations - mix sweet and savory, try bold pairings!"
    elif producer.creativity_bias <= 2:
        creativity_guidance = "You prefer CLASSIC combinations - stick to traditional pancake toppings."
    else:
        creativity_guidance = "You balance classic and creative - some traditional, some unique."

    topping_list = ", ".join(all_toppings)
    current_menu = ', '.join(current_toppings) if current_toppings else '(none yet)'
    
    prompt = f"""You are {producer.name}, competing for customers in a pancake market.

🎯 GOAL: Get MORE CUSTOMERS than your competitors!
{urgent_warning}
YOUR PERSONALITY:
- {risk_guidance}
- {creativity_guidance}

YOUR CURRENT MENU: {current_menu}
{history_section}
ALL AVAILABLE TOPPINGS: {topping_list}

TASK: Pick your ideal menu of 5 toppings from the list above.
- You may keep some from your current menu or swap them out
- Use EXACT topping names from the list
- ⚠️ List 7-10 toppings in order of preference! Competitors may take your top choices.
- Your first 5 available toppings will become your menu

RESPOND WITH JSON ONLY:
{{
    "reasoning": "brief explanation of your strategy",
    "desired_toppings": ["top_choice", "2nd", "3rd", "4th", "5th", "backup1", "backup2", "backup3"]
}}
"""
    return prompt

def build_consumer_prompt(
    consumer: Consumer,
    offerings: dict[str, dict]  # producer_name -> {toppings: [...], label: "A"}
) -> str:
    """Build the prompt for a consumer's choice."""
    
    # Build personality description from traits
    openness_desc = {
        1: "You strongly prefer familiar, traditional combinations. Unusual pairings make you uncomfortable.",
        2: "You lean toward classic choices but might try something slightly different.",
        3: "You're open to both traditional and creative options.",
        4: "You enjoy trying new and interesting combinations.",
        5: "You LOVE unusual, bold, unexpected flavor combinations. The weirder, the better!"
    }
    
    pickiness_desc = {
        1: "You're very easy to please - almost anything sounds good to you.",
        2: "You're fairly easy-going about food choices.",
        3: "You have moderate standards for what you'll enjoy.",
        4: "You're quite particular - only certain combinations will satisfy you.",
        5: "You're VERY picky and hard to please. Most options disappoint you."
    }
    
    impulsivity_desc = {
        1: "You carefully analyze every option before deciding.",
        2: "You take your time weighing the choices.",
        3: "You balance gut feeling with consideration.",
        4: "You tend to go with your first instinct.",
        5: "You decide instantly based on what catches your eye first!"
    }
    
    indulgence_desc = {
        1: "You prefer light, simple options. Rich foods don't appeal to you.",
        2: "You lean toward lighter fare.",
        3: "You enjoy both light and rich options equally.",
        4: "You're drawn to richer, more decadent choices.",
        5: "You CRAVE indulgence! Chocolate, caramel, cream - the richer the better!"
    }
    
    nostalgia_desc = {
        1: "You don't care about 'classic' - you want something fresh and modern.",
        2: "Traditional options don't particularly appeal to you.",
        3: "You appreciate both classic and modern options.",
        4: "You're drawn to comforting, classic flavors.",
        5: "You LOVE nostalgic, homestyle flavors - things that remind you of childhood!"
    }
    
    prompt = f"""You are Consumer #{consumer.id}, choosing where to get pancakes.

YOUR PERSONALITY:
- Openness ({consumer.openness}/5): {openness_desc[consumer.openness]}
- Pickiness ({consumer.pickiness}/5): {pickiness_desc[consumer.pickiness]}
- Impulsivity ({consumer.impulsivity}/5): {impulsivity_desc[consumer.impulsivity]}
- Indulgence ({consumer.indulgence}/5): {indulgence_desc[consumer.indulgence]}
- Nostalgia ({consumer.nostalgia}/5): {nostalgia_desc[consumer.nostalgia]}

TODAY'S PANCAKE OPTIONS:
"""
    # Show offerings with abstract labels (A, B, C) - no brand names
    for producer_name, offering in offerings.items():
        label = offering['label']
        prompt += f"\nOption {label}:\n"
        prompt += f"  - Toppings: {', '.join(offering['toppings'])}\n"

    prompt += """
Which option appeals to you most based on the toppings?
Respond with the option NUMBER (1, 2, or 3).

ENTICEMENT SCORE (be honest based on your pickiness!):
- 1-3: Disappointed - settling for the least bad choice
- 4-5: Meh - okay but nothing special
- 6-7: Satisfied - good, you're happy
- 8-9: Excited - looks delicious!
- 10: Perfect - exactly what you wanted

RESPOND WITH JSON ONLY:
{
    "reasoning": "why these toppings appeal to you",
    "chosen_option": "<1 or 2 or 3>",
    "enticement_score": <1-10>
}
"""
    return prompt

def call_llm(prompt: str) -> dict:
    """
    Call Ollama and parse JSON response.
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,  # Get complete response at once
    }
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
            response_text = result.get("response", "")
            
            # Print raw response for debugging
            print(f"    📝 Raw LLM response:")
            print(f"    {'-'*40}")
            for line in response_text.strip().split('\n'):
                print(f"    {line}")
            print(f"    {'-'*40}")
            
            # Try to extract JSON from the response
            # LLMs sometimes wrap JSON in markdown code blocks
            json_text = response_text
            if "```json" in json_text:
                json_text = json_text.split("```json")[1].split("```")[0]
            elif "```" in json_text:
                json_text = json_text.split("```")[1].split("```")[0]
            
            # Try to find JSON object in the text
            start_idx = json_text.find("{")
            end_idx = json_text.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                json_text = json_text[start_idx:end_idx]
            
            parsed = json.loads(json_text)
            return parsed
            
    except json.JSONDecodeError as e:
        print(f"    ⚠️ Failed to parse LLM JSON response: {e}")
        return {}
    except Exception as e:
        print(f"    ⚠️ LLM call failed: {e}")
        return {}

def producer_llm_decide(
    producer: Producer,
    current_toppings: list[str],
    all_toppings: list[str],
    history: list[ProducerHistory],
    is_first_tick: bool
) -> dict:
    """Get producer's decision from LLM."""
    prompt = build_producer_prompt(
        producer, current_toppings, all_toppings, history, is_first_tick
    )
    
    print(f"  🤖 Asking {producer.name} for decision...")
    response = call_llm(prompt)
    
    # Build case-insensitive lookup
    topping_lower_to_actual = {t.lower(): t for t in all_toppings}
    current_lower = {t.lower() for t in current_toppings}
    
    # Process the new "desired_toppings" format
    if response and response.get("desired_toppings"):
        # Normalize to lowercase and map back to actual names
        desired = []
        for t in response.get("desired_toppings", []):
            actual = topping_lower_to_actual.get(t.lower())
            if actual and actual not in desired:
                desired.append(actual)
        
        # Compute keep vs wanted from the desired list
        # Keep = toppings that are both in current menu AND in desired list
        keep_toppings = [t for t in desired if t.lower() in current_lower]
        # Wanted = toppings in desired list that are NOT in current menu
        wanted_toppings = [t for t in desired if t.lower() not in current_lower]
        
        response = {
            "reasoning": response.get("reasoning", ""),
            "keep_toppings": keep_toppings,
            "wanted_toppings": wanted_toppings
        }
        print(f"    → Keep: {keep_toppings}, Want: {wanted_toppings[:5]}...")
    else:
        response = None
    
    # Fallback to mock if LLM failed or returned empty
    if not response or (not response.get("keep_toppings") and not response.get("wanted_toppings")):
        print(f"    ⚠️ LLM response insufficient, using mock fallback")
        # Random mock behavior based on traits
        num_swaps = min(MAX_TOPPING_SWAPS, random.randint(0, producer.risk_tolerance))
        keep = current_toppings[:(NUM_TOPPINGS_PER_PRODUCER - num_swaps)] if current_toppings else []
        available = [t for t in all_toppings if t not in keep]
        # Request more than needed to handle conflicts - ask for up to 9 (3 producers * 3 max swaps)
        num_wanted = min(len(available), (NUM_TOPPINGS_PER_PRODUCER - len(keep)) + 6)
        wanted = random.sample(available, num_wanted)
        
        response = {
            "reasoning": "Mock decision based on personality traits",
            "keep_toppings": keep,
            "wanted_toppings": wanted
        }
    
    return response

def consumer_llm_choose(consumer: Consumer, offerings: dict[str, dict], label_to_producer: dict[str, str], debug_mapping: list[str]) -> dict:
    """Get consumer's choice from LLM."""
    prompt = build_consumer_prompt(consumer, offerings)
    
    print(f"  🧑 Consumer #{consumer.id} (O{consumer.openness}/P{consumer.pickiness}/I{consumer.impulsivity}/D{consumer.indulgence}/N{consumer.nostalgia}) [{', '.join(debug_mapping)}]")
    response = call_llm(prompt)
    
    # Map option label back to producer name
    if response:
        chosen_label = response.get("chosen_option", "").strip()
        chosen_producer = label_to_producer.get(chosen_label)
        if chosen_producer:
            response["chosen_producer"] = chosen_producer
        else:
            response["chosen_producer"] = None  # Will trigger random fallback
    
    # MOCK RESPONSE for testing without LLM
    if not response:
        producer_names = list(label_to_producer.values())
        chosen = random.choice(producer_names)
        response = {
            "reasoning": "Mock choice",
            "chosen_producer": chosen,
            "enticement_score": random.randint(4, 9)
        }
    
    return response

# =============================================================================
# Topping Allocation (Conflict Resolution)
# =============================================================================

def resolve_topping_conflicts(
    producer_decisions: list[tuple[Producer, dict]],
    tick_id: int,
    all_toppings: list[Topping]
) -> list[ProducerOffering]:
    """
    Resolve topping conflicts using rotating priority.
    First pick rotates based on tick_id.
    """
    num_producers = len(producer_decisions)
    first_pick_idx = (tick_id - 1) % num_producers  # -1 because tick_id starts at 1
    
    # Build priority order
    priority_order = list(range(num_producers))
    priority_order = priority_order[first_pick_idx:] + priority_order[:first_pick_idx]
    
    print(f"  🎯 Topping allocation priority this tick: {[producer_decisions[i][0].name for i in priority_order]}")
    
    topping_name_to_id = {t.name: t.id for t in all_toppings}
    claimed_toppings: set[str] = set()
    offerings: list[ProducerOffering] = []
    
    # First pass: lock in kept toppings (these are guaranteed)
    producer_kept: dict[int, list[str]] = {}  # producer_id -> kept topping names
    for producer, decision in producer_decisions:
        kept = decision.get("keep_toppings", [])
        producer_kept[producer.id] = kept
        claimed_toppings.update(kept)
    
    # Second pass: allocate wanted toppings by priority
    producer_final_toppings: dict[int, list[str]] = {p.id: list(producer_kept[p.id]) for p, _ in producer_decisions}
    
    # Round-robin allocation of wanted toppings
    max_rounds = NUM_TOPPINGS_PER_PRODUCER  # Safety limit
    for round_num in range(max_rounds):
        made_progress = False
        for idx in priority_order:
            producer, decision = producer_decisions[idx]
            current = producer_final_toppings[producer.id]
            
            if len(current) >= NUM_TOPPINGS_PER_PRODUCER:
                continue  # Already full
            
            wanted = decision.get("wanted_toppings", [])
            for topping_name in wanted:
                if topping_name in claimed_toppings:
                    continue  # Already claimed
                if topping_name not in topping_name_to_id:
                    continue  # Invalid topping
                
                # Claim it!
                current.append(topping_name)
                claimed_toppings.add(topping_name)
                made_progress = True
                break  # One topping per round per producer
        
        if not made_progress:
            break
    
    # Fill any gaps with random unclaimed toppings
    all_topping_names = [t.name for t in all_toppings]
    for producer, decision in producer_decisions:
        current = producer_final_toppings[producer.id]
        while len(current) < NUM_TOPPINGS_PER_PRODUCER:
            available = [t for t in all_topping_names if t not in claimed_toppings]
            if not available:
                print(f"  ⚠️ Warning: Not enough toppings for {producer.name}!")
                break
            filler = random.choice(available)
            current.append(filler)
            claimed_toppings.add(filler)
    
    # Build offerings
    for producer, decision in producer_decisions:
        topping_ids = [topping_name_to_id[name] for name in producer_final_toppings[producer.id]]
        offerings.append(ProducerOffering(
            producer_id=producer.id,
            topping_ids=topping_ids
        ))
        print(f"  📦 {producer.name}: {producer_final_toppings[producer.id]}")
    
    return offerings

# =============================================================================
# Persistence
# =============================================================================

def persist_offerings(conn, tick_id: int, offerings: list[ProducerOffering]) -> None:
    """Persist producer offerings for this tick."""
    cur = conn.cursor()
    for offering in offerings:
        cur.execute(
            "INSERT INTO producer_offerings (tick_id, producer_id) VALUES (%s, %s)",
            (tick_id, offering.producer_id)
        )
        for topping_id in offering.topping_ids:
            cur.execute(
                "INSERT INTO producer_toppings (tick_id, producer_id, topping_id) VALUES (%s, %s, %s)",
                (tick_id, offering.producer_id, topping_id)
            )
    conn.commit()
    cur.close()

def persist_choice(conn, tick_id: int, consumer_id: int, producer_id: int, enticement_score: int) -> None:
    """Persist a consumer's choice."""
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO consumer_choices (tick_id, consumer_id, producer_id, enticement_score) VALUES (%s, %s, %s, %s)",
        (tick_id, consumer_id, producer_id, enticement_score)
    )
    conn.commit()
    cur.close()

def compute_and_persist_stats(conn, tick_id: int, producers: list[Producer]) -> None:
    """Compute and persist round statistics for each producer."""
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM consumer_choices WHERE tick_id = %s", (tick_id,))
    total_consumers = cur.fetchone()[0]
    
    for producer in producers:
        # Get consumer count and enticement scores
        cur.execute(
            "SELECT enticement_score FROM consumer_choices WHERE tick_id = %s AND producer_id = %s",
            (tick_id, producer.id)
        )
        rows = cur.fetchall()
        
        consumer_count = len(rows)
        market_share = consumer_count / total_consumers if total_consumers > 0 else 0
        
        if rows:
            scores = [r[0] for r in rows]
            avg_enticement = sum(scores) / len(scores)
            sorted_scores = sorted(scores)
            mid = len(sorted_scores) // 2
            median_enticement = (sorted_scores[mid] + sorted_scores[~mid]) / 2
        else:
            avg_enticement = 0
            median_enticement = 0
        
        cur.execute(
            """INSERT INTO producer_round_stats 
               (tick_id, producer_id, consumer_count, market_share, avg_enticement, median_enticement)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (tick_id, producer.id, consumer_count, market_share, avg_enticement, median_enticement)
        )
        
        print(f"  📊 {producer.name}: {consumer_count} customers ({market_share:.1%}), avg enticement {avg_enticement:.1f}")
    
    conn.commit()
    cur.close()

# =============================================================================
# Main Tick Loop
# =============================================================================

def initialize_first_tick_offerings(
    producers: list[Producer],
    all_toppings: list[Topping]
) -> list[ProducerOffering]:
    """
    Initialize offerings for first tick with random exclusive toppings.
    Shuffle all toppings and deal 5 to each producer.
    """
    print("  🎲 Shuffling and dealing toppings...")
    
    # Shuffle topping IDs
    topping_ids = [t.id for t in all_toppings]
    random.shuffle(topping_ids)
    
    offerings = []
    for i, producer in enumerate(producers):
        # Deal 5 toppings to each producer
        start_idx = i * NUM_TOPPINGS_PER_PRODUCER
        producer_topping_ids = topping_ids[start_idx:start_idx + NUM_TOPPINGS_PER_PRODUCER]
        
        topping_names = [t.name for t in all_toppings if t.id in producer_topping_ids]
        print(f"  📦 {producer.name}: {topping_names}")
        
        offerings.append(ProducerOffering(
            producer_id=producer.id,
            topping_ids=producer_topping_ids
        ))
    
    return offerings


def run_tick(conn) -> None:
    """Run a single tick of the simulation."""
    tick_start_time = time.time()
    
    # 1. Cleanup incomplete tick if exists
    cleanup_incomplete_tick(conn)
    
    # 2. Start new tick
    tick_id = start_tick(conn)
    
    # 3. Load entities
    producers = get_producers(conn)
    consumers = get_consumers(conn)
    all_toppings = get_all_toppings(conn)
    all_topping_names = [t.name for t in all_toppings]
    topping_id_to_name = {t.id: t.name for t in all_toppings}
    
    # 4. Determine if this is the first tick
    last_tick = get_latest_completed_tick(conn)
    is_first_tick = last_tick is None
    
    # 5. Handle producer phase differently for first tick vs subsequent ticks
    if is_first_tick:
        # First tick: random initialization, no LLM decisions
        print("\n🎰 Phase 1: Random Initialization (First Tick)")
        print("  Producers get random toppings - no decisions yet.")
        offerings = initialize_first_tick_offerings(producers, all_toppings)
    else:
        # Subsequent ticks: LLM-powered producer decisions
        print("\n📝 Phase 1: Producer Decisions")
        producer_decisions: list[tuple[Producer, dict]] = []
        
        for producer in producers:
            current_topping_ids = get_producer_current_toppings(conn, producer.id, last_tick)
            current_topping_names = [topping_id_to_name[tid] for tid in current_topping_ids]
            history = get_producer_history(conn, producer.id)
            
            decision = producer_llm_decide(
                producer,
                current_topping_names,
                all_topping_names,
                history,
                is_first_tick=False
            )
            producer_decisions.append((producer, decision))
        
        # Show what each producer requested
        print("\n📋 Producer Requests (before allocation):")
        for producer, decision in producer_decisions:
            keep = decision.get("keep_toppings", [])
            want = decision.get("wanted_toppings", [])
            print(f"  {producer.name}: keep {keep} + want {want}")
        
        # Resolve topping conflicts
        print("\n🎲 Phase 2: Topping Allocation")
        offerings = resolve_topping_conflicts(producer_decisions, tick_id, all_toppings)
    
    # 7. Persist producer offerings
    persist_offerings(conn, tick_id, offerings)
    
    # 8. Build offerings dict for consumers with abstract labels
    producer_id_to_name = {p.id: p.name for p in producers}
    offerings_for_consumers: dict[str, dict] = {}
    label_to_producer: dict[str, str] = {}  # "A" -> "Fluffy's Pancake Palace"
    labels = ["A", "B", "C", "D", "E"]  # Support up to 5 producers
    
    for i, offering in enumerate(offerings):
        producer_name = producer_id_to_name[offering.producer_id]
        topping_names = [topping_id_to_name[tid] for tid in offering.topping_ids]
        label = labels[i]
        offerings_for_consumers[producer_name] = {
            "toppings": topping_names,
            "label": label
        }
        label_to_producer[label] = producer_name
    
    # 9. Consumer decisions
    print("\n🍽️ Phase 3: Consumer Choices")
    producer_name_to_id = {p.name: p.id for p in producers}
    
    for consumer in consumers:
        # Randomize option order for each consumer to avoid position bias
        producer_names = list(offerings_for_consumers.keys())
        random.shuffle(producer_names)
        
        # Use simple numbers but randomized order
        number_labels = ["1", "2", "3"]
        
        # Build shuffled offerings with number labels
        shuffled_offerings: dict[str, dict] = {}
        consumer_label_to_producer: dict[str, str] = {}
        debug_mapping = []
        for i, producer_name in enumerate(producer_names):
            label = number_labels[i]
            shuffled_offerings[producer_name] = {
                "toppings": offerings_for_consumers[producer_name]["toppings"],
                "label": label
            }
            consumer_label_to_producer[label] = producer_name
            # Abbreviate producer name for debug
            short_name = producer_name.split("'")[0] if "'" in producer_name else producer_name[:8]
            debug_mapping.append(f"{label}={short_name}")
        
        choice = consumer_llm_choose(consumer, shuffled_offerings, consumer_label_to_producer, debug_mapping)
        chosen_name = choice.get("chosen_producer", "")
        chosen_id = producer_name_to_id.get(chosen_name)
        
        if chosen_id is None:
            # Fallback: random choice
            chosen_id = random.choice(producers).id
            print(f"  ⚠️ Consumer #{consumer.id} made invalid choice, randomly assigned")
        
        enticement = choice.get("enticement_score", 5)
        persist_choice(conn, tick_id, consumer.id, chosen_id, enticement)
    
    # 10. Compute and persist stats
    print("\n📈 Phase 4: Round Statistics")
    compute_and_persist_stats(conn, tick_id, producers)
    
    # 11. Mark tick complete
    complete_tick(conn, tick_id)
    
    elapsed = time.time() - tick_start_time
    print(f"\n🎉 Tick complete! (⏱️ {elapsed:.1f}s)")

# =============================================================================
# Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Pancake Agents Simulation")
    parser.add_argument("--init", action="store_true", help="Initialize DB with schema + seed data")
    parser.add_argument("--reset", action="store_true", help="Drop all tables and reinitialize")
    args = parser.parse_args()
    
    print(f"🔗 Connecting to PostgreSQL at {DB_HOST}:{DB_PORT}/{DB_NAME}...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        print("✅ Connected to PostgreSQL!")
    except psycopg2.Error as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        return
    
    if args.init or args.reset:
        init_db(conn, reset=args.reset)
        if not args.reset:
            conn.close()
            return  # Just init, don't run tick
    
    # Ensure DB is initialized
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM producers LIMIT 1")
        cur.close()
    except psycopg2.Error:
        print("Database not initialized. Run with --init first.")
        conn.close()
        return
    
    # Check Ollama is available
    if not check_ollama_available():
        print("🛑 Aborting: Ollama must be running to proceed.")
        conn.close()
        return
    
    run_tick(conn)
    conn.close()

if __name__ == "__main__":
    main()
