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
import duckdb
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
import json
import random
import urllib.request
import urllib.error

# =============================================================================
# Configuration
# =============================================================================

DB_PATH = "pancake_world.duckdb"
HISTORY_WINDOW = 20  # How many past ticks producers can see
NUM_TOPPINGS_PER_PRODUCER = 5
MAX_TOPPING_SWAPS = 3
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:0.6b"

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
    name: str
    # traits TBD - excluded for now

@dataclass
class Topping:
    id: int
    name: str

@dataclass
class ProducerOffering:
    producer_id: int
    fluffiness: int  # 1-5
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
    fluffiness: int

# =============================================================================
# Database Setup
# =============================================================================

SCHEMA_SQL = """
-- Core entities
CREATE TABLE IF NOT EXISTS producers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    creativity_bias INTEGER CHECK (creativity_bias BETWEEN 1 AND 5),
    risk_tolerance INTEGER CHECK (risk_tolerance BETWEEN 1 AND 5)
);

CREATE TABLE IF NOT EXISTS consumers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
    -- traits TBD, excluded for now
);

CREATE TABLE IF NOT EXISTS toppings (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- Tick state
CREATE TABLE IF NOT EXISTS ticks (
    id INTEGER PRIMARY KEY,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP  -- NULL until tick finishes
);

-- Per-tick snapshots (append-only)
CREATE TABLE IF NOT EXISTS producer_offerings (
    tick_id INTEGER REFERENCES ticks(id),
    producer_id INTEGER REFERENCES producers(id),
    fluffiness INTEGER CHECK (fluffiness BETWEEN 1 AND 5),
    PRIMARY KEY (tick_id, producer_id)
);

CREATE TABLE IF NOT EXISTS producer_toppings (
    tick_id INTEGER REFERENCES ticks(id),
    producer_id INTEGER REFERENCES producers(id),
    topping_id INTEGER REFERENCES toppings(id),
    PRIMARY KEY (tick_id, producer_id, topping_id)
);

-- Exclusivity: each topping used by at most one producer per tick
CREATE UNIQUE INDEX IF NOT EXISTS idx_exclusive_topping ON producer_toppings(tick_id, topping_id);

CREATE TABLE IF NOT EXISTS consumer_choices (
    tick_id INTEGER REFERENCES ticks(id),
    consumer_id INTEGER REFERENCES consumers(id),
    producer_id INTEGER REFERENCES producers(id),
    enticement_score INTEGER CHECK (enticement_score BETWEEN 1 AND 10),
    PRIMARY KEY (tick_id, consumer_id)
);

-- Derived stats (computed at end of tick)
CREATE TABLE IF NOT EXISTS producer_round_stats (
    tick_id INTEGER REFERENCES ticks(id),
    producer_id INTEGER REFERENCES producers(id),
    consumer_count INTEGER,
    market_share REAL,
    avg_enticement REAL,
    median_enticement REAL,
    PRIMARY KEY (tick_id, producer_id)
);
"""

# =============================================================================
# Seed Data
# =============================================================================

SEED_PRODUCERS = [
    ("Fluffy's Pancake Palace", 3, 3),   # Balanced
    ("Wild Stack Shack", 5, 5),          # Creative risk-taker
    ("Grandma's Griddle", 1, 1),         # Conservative traditionalist
]

SEED_CONSUMERS = [
    "Alex", "Blake", "Casey", "Dana", "Ellis",
    "Finley", "Gray", "Harper", "Indigo", "Jordan",
]

SEED_TOPPINGS = [
    "blueberries", "strawberries", "raspberries", "bananas", "chocolate chips",
    "whipped cream", "maple syrup", "honey", "peanut butter", "nutella",
    "bacon bits", "scrambled eggs", "cheddar cheese", "ham", "sausage crumbles",
    "walnuts", "pecans", "almonds", "coconut flakes", "granola",
    "cinnamon sugar", "powdered sugar", "caramel drizzle", "lemon zest", "vanilla cream",
]

def init_db(conn: duckdb.DuckDBPyConnection, reset: bool = False) -> None:
    """Initialize database schema and seed data."""
    if reset:
        print("🗑️  Dropping all tables...")
        conn.execute("DROP TABLE IF EXISTS producer_round_stats")
        conn.execute("DROP TABLE IF EXISTS consumer_choices")
        conn.execute("DROP TABLE IF EXISTS producer_toppings")
        conn.execute("DROP TABLE IF EXISTS producer_offerings")
        conn.execute("DROP TABLE IF EXISTS ticks")
        conn.execute("DROP TABLE IF EXISTS toppings")
        conn.execute("DROP TABLE IF EXISTS consumers")
        conn.execute("DROP TABLE IF EXISTS producers")
    
    print("📋 Creating schema...")
    # DuckDB doesn't have executescript, so split and execute each statement
    for statement in SCHEMA_SQL.split(";"):
        statement = statement.strip()
        if statement:
            conn.execute(statement)
    
    # Check if already seeded
    existing = conn.execute("SELECT COUNT(*) FROM producers").fetchone()[0]
    if existing > 0:
        print("✅ Database already seeded.")
        return
    
    print("🌱 Seeding data...")
    
    # Seed producers
    for i, (name, creativity, risk) in enumerate(SEED_PRODUCERS, start=1):
        conn.execute(
            "INSERT INTO producers (id, name, creativity_bias, risk_tolerance) VALUES (?, ?, ?, ?)",
            [i, name, creativity, risk]
        )
    
    # Seed consumers
    for i, name in enumerate(SEED_CONSUMERS, start=1):
        conn.execute("INSERT INTO consumers (id, name) VALUES (?, ?)", [i, name])
    
    # Seed toppings
    for i, name in enumerate(SEED_TOPPINGS, start=1):
        conn.execute("INSERT INTO toppings (id, name) VALUES (?, ?)", [i, name])
    
    print(f"✅ Seeded {len(SEED_PRODUCERS)} producers, {len(SEED_CONSUMERS)} consumers, {len(SEED_TOPPINGS)} toppings.")

# =============================================================================
# State Retrieval
# =============================================================================

def get_producers(conn: duckdb.DuckDBPyConnection) -> list[Producer]:
    """Get all producers."""
    rows = conn.execute("SELECT id, name, creativity_bias, risk_tolerance FROM producers ORDER BY id").fetchall()
    return [Producer(id=r[0], name=r[1], creativity_bias=r[2], risk_tolerance=r[3]) for r in rows]

def get_consumers(conn: duckdb.DuckDBPyConnection) -> list[Consumer]:
    """Get all consumers."""
    rows = conn.execute("SELECT id, name FROM consumers ORDER BY id").fetchall()
    return [Consumer(id=r[0], name=r[1]) for r in rows]

def get_all_toppings(conn: duckdb.DuckDBPyConnection) -> list[Topping]:
    """Get all available toppings."""
    rows = conn.execute("SELECT id, name FROM toppings ORDER BY id").fetchall()
    return [Topping(id=r[0], name=r[1]) for r in rows]

def get_latest_completed_tick(conn: duckdb.DuckDBPyConnection) -> Optional[int]:
    """Get the most recent completed tick ID, or None if no ticks yet."""
    result = conn.execute(
        "SELECT id FROM ticks WHERE completed_at IS NOT NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return result[0] if result else None

def get_producer_current_toppings(conn: duckdb.DuckDBPyConnection, producer_id: int, tick_id: int) -> list[int]:
    """Get topping IDs for a producer from a specific tick."""
    rows = conn.execute(
        "SELECT topping_id FROM producer_toppings WHERE producer_id = ? AND tick_id = ? ORDER BY topping_id",
        [producer_id, tick_id]
    ).fetchall()
    return [r[0] for r in rows]

def get_producer_current_fluffiness(conn: duckdb.DuckDBPyConnection, producer_id: int, tick_id: int) -> int:
    """Get fluffiness for a producer from a specific tick."""
    result = conn.execute(
        "SELECT fluffiness FROM producer_offerings WHERE producer_id = ? AND tick_id = ?",
        [producer_id, tick_id]
    ).fetchone()
    return result[0] if result else 3  # Default to middle fluffiness

def get_producer_history(conn: duckdb.DuckDBPyConnection, producer_id: int, limit: int = HISTORY_WINDOW) -> list[ProducerHistory]:
    """Get historical stats for a producer (most recent first)."""
    rows = conn.execute("""
        SELECT 
            s.tick_id,
            s.consumer_count,
            s.market_share,
            s.avg_enticement,
            s.median_enticement,
            o.fluffiness,
            GROUP_CONCAT(t.name ORDER BY t.name) as topping_names
        FROM producer_round_stats s
        JOIN producer_offerings o ON s.tick_id = o.tick_id AND s.producer_id = o.producer_id
        JOIN producer_toppings pt ON s.tick_id = pt.tick_id AND s.producer_id = pt.producer_id
        JOIN toppings t ON pt.topping_id = t.id
        WHERE s.producer_id = ?
        GROUP BY s.tick_id, s.consumer_count, s.market_share, s.avg_enticement, s.median_enticement, o.fluffiness
        ORDER BY s.tick_id DESC
        LIMIT ?
    """, [producer_id, limit]).fetchall()
    
    return [
        ProducerHistory(
            tick_id=r[0],
            consumer_count=r[1],
            market_share=r[2],
            avg_enticement=r[3],
            median_enticement=r[4],
            fluffiness=r[5],
            toppings=r[6].split(",") if r[6] else []
        )
        for r in rows
    ]

def get_toppings_used_last_tick(conn: duckdb.DuckDBPyConnection, tick_id: int) -> dict[int, list[int]]:
    """Get mapping of producer_id -> topping_ids from a tick."""
    rows = conn.execute(
        "SELECT producer_id, topping_id FROM producer_toppings WHERE tick_id = ?",
        [tick_id]
    ).fetchall()
    
    result: dict[int, list[int]] = {}
    for producer_id, topping_id in rows:
        if producer_id not in result:
            result[producer_id] = []
        result[producer_id].append(topping_id)
    return result

# =============================================================================
# Tick Management
# =============================================================================

def cleanup_incomplete_tick(conn: duckdb.DuckDBPyConnection) -> None:
    """Remove any incomplete tick and its associated data."""
    incomplete = conn.execute(
        "SELECT id FROM ticks WHERE completed_at IS NULL"
    ).fetchone()
    
    if incomplete:
        tick_id = incomplete[0]
        print(f"🧹 Cleaning up incomplete tick {tick_id}...")
        conn.execute("DELETE FROM producer_round_stats WHERE tick_id = ?", [tick_id])
        conn.execute("DELETE FROM consumer_choices WHERE tick_id = ?", [tick_id])
        conn.execute("DELETE FROM producer_toppings WHERE tick_id = ?", [tick_id])
        conn.execute("DELETE FROM producer_offerings WHERE tick_id = ?", [tick_id])
        conn.execute("DELETE FROM ticks WHERE id = ?", [tick_id])

def start_tick(conn: duckdb.DuckDBPyConnection) -> int:
    """Start a new tick and return its ID."""
    # Get next tick ID
    result = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM ticks").fetchone()
    tick_id = result[0]
    
    conn.execute(
        "INSERT INTO ticks (id, started_at) VALUES (?, ?)",
        [tick_id, datetime.now()]
    )
    print(f"🎬 Started tick {tick_id}")
    return tick_id

def complete_tick(conn: duckdb.DuckDBPyConnection, tick_id: int) -> None:
    """Mark a tick as complete."""
    conn.execute(
        "UPDATE ticks SET completed_at = ? WHERE id = ?",
        [datetime.now(), tick_id]
    )
    print(f"✅ Completed tick {tick_id}")

# =============================================================================
# LLM Integration (Placeholders)
# =============================================================================

def build_producer_prompt(
    producer: Producer,
    current_toppings: list[str],
    current_fluffiness: int,
    all_toppings: list[str],
    history: list[ProducerHistory],
    is_first_tick: bool
) -> str:
    """Build the prompt for a producer's decision."""
    
    creativity_desc = {
        1: "extremely traditional - you stick to classic, proven combinations",
        2: "somewhat traditional - you prefer familiar toppings with occasional twists", 
        3: "balanced - you mix classic choices with occasional experimentation",
        4: "quite creative - you enjoy trying unusual combinations",
        5: "wildly creative - you love bold, unexpected topping choices"
    }
    
    risk_desc = {
        1: "extremely risk-averse - you rarely change what's working",
        2: "cautious - you make small, careful adjustments",
        3: "moderate - you're willing to make reasonable changes",
        4: "bold - you're comfortable making significant changes",
        5: "a risk junkie - you love shaking things up dramatically"
    }
    
    prompt = f"""You are {producer.name}, a pancake producer competing for customers.

YOUR PERSONALITY:
- Creativity: {producer.creativity_bias}/5 - You are {creativity_desc[producer.creativity_bias]}
- Risk tolerance: {producer.risk_tolerance}/5 - You are {risk_desc[producer.risk_tolerance]}

YOUR CURRENT OFFERING:
- Toppings: {', '.join(current_toppings) if current_toppings else '(none yet)'}
- Fluffiness: {current_fluffiness}/5

AVAILABLE TOPPINGS (you MUST choose ONLY from this exact list - use these exact names):
"""
    for topping in all_toppings:
        prompt += f"  - {topping}\n"
    
    prompt += """
RULES:
- You must have exactly 5 toppings
- You may swap 0 to 3 toppings this round
- Fluffiness can be set to any value 1-5
- Toppings are exclusive: if another producer claims a topping you want, you may not get it
- IMPORTANT: Use the EXACT topping names from the list above. Do not abbreviate or modify them.
"""

    if history and not is_first_tick:
        prompt += "\nYOUR RECENT PERFORMANCE:\n"
        for h in history[:10]:  # Show last 10 in prompt, even though we store 20
            prompt += f"- Tick {h.tick_id}: {h.consumer_count} customers ({h.market_share:.1%} share), "
            prompt += f"avg enticement {h.avg_enticement:.1f}/10, toppings: {', '.join(h.toppings)}, fluffiness: {h.fluffiness}\n"
    else:
        prompt += "\nThis is your first round - no history yet. Make your best initial offering!\n"

    prompt += """
RESPOND WITH JSON ONLY:
{
    "reasoning": "brief explanation of your strategy",
    "keep_toppings": ["topping1", "topping2", ...],  // toppings to definitely keep (0-5)
    "wanted_toppings": ["topping1", "topping2", ...], // new toppings you want, in priority order
    "fluffiness": 3  // your chosen fluffiness 1-5
}
"""
    return prompt

def build_consumer_prompt(
    consumer: Consumer,
    offerings: dict[str, dict]  # producer_name -> {toppings: [...], fluffiness: int}
) -> str:
    """Build the prompt for a consumer's choice."""
    
    prompt = f"""You are {consumer.name}, a hungry customer choosing where to get pancakes.

TODAY'S OFFERINGS:
"""
    for producer_name, offering in offerings.items():
        prompt += f"\n{producer_name}:\n"
        prompt += f"  - Toppings: {', '.join(offering['toppings'])}\n"
        prompt += f"  - Fluffiness: {offering['fluffiness']}/5\n"

    prompt += """
Choose the pancake offering that appeals to you most. Consider the combination of toppings and fluffiness level.

ENTICEMENT SCORE GUIDE:
- 1-3: Disappointed - the options are unappealing, you're settling for the least bad choice
- 4-5: Meh - it's okay, nothing special, you'll eat it but won't remember it
- 6-7: Satisfied - good combination, you're happy with your choice
- 8-9: Excited - this looks delicious, you can't wait to eat it
- 10: Perfect - this is exactly what you wanted, couldn't be better

Be honest with your score. Not every meal is a 7.

RESPOND WITH JSON ONLY:
{
    "reasoning": "brief explanation of why you chose this",
    "chosen_producer": "Producer Name Here",
    "enticement_score": 5  // how excited you are about this choice, 1-10 (use the guide above)
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
    current_fluffiness: int,
    all_toppings: list[str],
    history: list[ProducerHistory],
    is_first_tick: bool
) -> dict:
    """Get producer's decision from LLM."""
    prompt = build_producer_prompt(
        producer, current_toppings, current_fluffiness, all_toppings, history, is_first_tick
    )
    
    print(f"  🤖 Asking {producer.name} for decision...")
    response = call_llm(prompt)
    
    # Validate and sanitize the response
    if response:
        # Filter keep_toppings to only valid ones the producer actually has
        valid_keep = [t for t in response.get("keep_toppings", []) if t in current_toppings]
        # Filter wanted_toppings to only valid topping names
        valid_wanted = [t for t in response.get("wanted_toppings", []) if t in all_toppings and t not in valid_keep]
        # Clamp fluffiness to 1-5
        fluffiness = response.get("fluffiness", 3)
        if not isinstance(fluffiness, int) or fluffiness < 1 or fluffiness > 5:
            fluffiness = 3
        
        response = {
            "reasoning": response.get("reasoning", ""),
            "keep_toppings": valid_keep,
            "wanted_toppings": valid_wanted,
            "fluffiness": fluffiness
        }
        print(f"    → Keep: {valid_keep}, Want: {valid_wanted[:5]}..., Fluffiness: {fluffiness}")
    
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
            "wanted_toppings": wanted,
            "fluffiness": random.randint(1, 5)
        }
    
    return response

def consumer_llm_choose(consumer: Consumer, offerings: dict[str, dict]) -> dict:
    """Get consumer's choice from LLM."""
    prompt = build_consumer_prompt(consumer, offerings)
    
    print(f"  🧑 Asking {consumer.name} to choose...")
    response = call_llm(prompt)
    
    # MOCK RESPONSE for testing without LLM
    if not response:
        producer_names = list(offerings.keys())
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
            fluffiness=decision.get("fluffiness", 3),
            topping_ids=topping_ids
        ))
        print(f"  📦 {producer.name}: {producer_final_toppings[producer.id]} (fluffiness {decision.get('fluffiness', 3)})")
    
    return offerings

# =============================================================================
# Persistence
# =============================================================================

def persist_offerings(conn: duckdb.DuckDBPyConnection, tick_id: int, offerings: list[ProducerOffering]) -> None:
    """Persist producer offerings for this tick."""
    for offering in offerings:
        conn.execute(
            "INSERT INTO producer_offerings (tick_id, producer_id, fluffiness) VALUES (?, ?, ?)",
            [tick_id, offering.producer_id, offering.fluffiness]
        )
        for topping_id in offering.topping_ids:
            conn.execute(
                "INSERT INTO producer_toppings (tick_id, producer_id, topping_id) VALUES (?, ?, ?)",
                [tick_id, offering.producer_id, topping_id]
            )

def persist_choice(conn: duckdb.DuckDBPyConnection, tick_id: int, consumer_id: int, producer_id: int, enticement_score: int) -> None:
    """Persist a consumer's choice."""
    conn.execute(
        "INSERT INTO consumer_choices (tick_id, consumer_id, producer_id, enticement_score) VALUES (?, ?, ?, ?)",
        [tick_id, consumer_id, producer_id, enticement_score]
    )

def compute_and_persist_stats(conn: duckdb.DuckDBPyConnection, tick_id: int, producers: list[Producer]) -> None:
    """Compute and persist round statistics for each producer."""
    total_consumers = conn.execute(
        "SELECT COUNT(*) FROM consumer_choices WHERE tick_id = ?", [tick_id]
    ).fetchone()[0]
    
    for producer in producers:
        # Get consumer count and enticement scores
        rows = conn.execute(
            "SELECT enticement_score FROM consumer_choices WHERE tick_id = ? AND producer_id = ?",
            [tick_id, producer.id]
        ).fetchall()
        
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
        
        conn.execute(
            """INSERT INTO producer_round_stats 
               (tick_id, producer_id, consumer_count, market_share, avg_enticement, median_enticement)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [tick_id, producer.id, consumer_count, market_share, avg_enticement, median_enticement]
        )
        
        print(f"  📊 {producer.name}: {consumer_count} customers ({market_share:.1%}), avg enticement {avg_enticement:.1f}")

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
        
        # Random fluffiness 1-5
        fluffiness = random.randint(1, 5)
        
        topping_names = [t.name for t in all_toppings if t.id in producer_topping_ids]
        print(f"  📦 {producer.name}: {topping_names} (fluffiness {fluffiness})")
        
        offerings.append(ProducerOffering(
            producer_id=producer.id,
            fluffiness=fluffiness,
            topping_ids=producer_topping_ids
        ))
    
    return offerings


def run_tick(conn: duckdb.DuckDBPyConnection) -> None:
    """Run a single tick of the simulation."""
    
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
        print("  Producers get random toppings and fluffiness - no decisions yet.")
        offerings = initialize_first_tick_offerings(producers, all_toppings)
    else:
        # Subsequent ticks: LLM-powered producer decisions
        print("\n📝 Phase 1: Producer Decisions")
        producer_decisions: list[tuple[Producer, dict]] = []
        
        for producer in producers:
            current_topping_ids = get_producer_current_toppings(conn, producer.id, last_tick)
            current_topping_names = [topping_id_to_name[tid] for tid in current_topping_ids]
            current_fluffiness = get_producer_current_fluffiness(conn, producer.id, last_tick)
            history = get_producer_history(conn, producer.id)
            
            decision = producer_llm_decide(
                producer,
                current_topping_names,
                current_fluffiness,
                all_topping_names,
                history,
                is_first_tick=False
            )
            producer_decisions.append((producer, decision))
        
        # Resolve topping conflicts
        print("\n🎲 Phase 2: Topping Allocation")
        offerings = resolve_topping_conflicts(producer_decisions, tick_id, all_toppings)
    
    # 7. Persist producer offerings
    persist_offerings(conn, tick_id, offerings)
    
    # 8. Build offerings dict for consumers
    producer_id_to_name = {p.id: p.name for p in producers}
    offerings_for_consumers: dict[str, dict] = {}
    for offering in offerings:
        producer_name = producer_id_to_name[offering.producer_id]
        topping_names = [topping_id_to_name[tid] for tid in offering.topping_ids]
        offerings_for_consumers[producer_name] = {
            "toppings": topping_names,
            "fluffiness": offering.fluffiness
        }
    
    # 9. Consumer decisions
    print("\n🍽️ Phase 3: Consumer Choices")
    producer_name_to_id = {p.name: p.id for p in producers}
    
    for consumer in consumers:
        choice = consumer_llm_choose(consumer, offerings_for_consumers)
        chosen_name = choice.get("chosen_producer", "")
        chosen_id = producer_name_to_id.get(chosen_name)
        
        if chosen_id is None:
            # Fallback: random choice
            chosen_id = random.choice(producers).id
            print(f"  ⚠️ {consumer.name} made invalid choice, randomly assigned")
        
        enticement = choice.get("enticement_score", 5)
        persist_choice(conn, tick_id, consumer.id, chosen_id, enticement)
    
    # 10. Compute and persist stats
    print("\n📈 Phase 4: Round Statistics")
    compute_and_persist_stats(conn, tick_id, producers)
    
    # 11. Mark tick complete
    complete_tick(conn, tick_id)
    print("\n🎉 Tick complete!")

# =============================================================================
# Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Pancake Agents Simulation")
    parser.add_argument("--init", action="store_true", help="Initialize DB with schema + seed data")
    parser.add_argument("--reset", action="store_true", help="Drop all tables and reinitialize")
    args = parser.parse_args()
    
    conn = duckdb.connect(DB_PATH)
    
    if args.init or args.reset:
        init_db(conn, reset=args.reset)
        if not args.reset:
            return  # Just init, don't run tick
    
    # Ensure DB is initialized
    try:
        conn.execute("SELECT 1 FROM producers LIMIT 1")
    except duckdb.CatalogException:
        print("Database not initialized. Run with --init first.")
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
