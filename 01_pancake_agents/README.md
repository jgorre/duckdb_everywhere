# Pancake Agents World 🥞

## Overview

**Pancake Agents World** is an LLM-powered **multi-agent economic simulation** where AI-driven producers and consumers compete in a pancake marketplace. Each simulation "tick" represents one round of economic competition where producers choose topping combinations and consumers make purchasing decisions—all powered by LLM reasoning (via Ollama).

### Core Concept

- **Producers** are competitive restaurants trying to maximize customer market share
- **Consumers** have unique personality traits that influence their topping preferences
- **Toppings** are the competitive currency—limited supply, exclusive ownership per tick
- **LLM Integration**: Both producers and consumers make decisions via prompted LLM responses, not hard-coded logic

This creates an **emergent economic system** where personality clashes, competitive pressure, and market dynamics play out through natural language reasoning.

---

## Database Schema

All data is persisted in **DuckDB** (`pancake_world.duckdb`) with the following tables:

### Core Entities

#### `producers` (Immutable)
Represents restaurants/makers competing for market share.

| Column | Type | Range | Purpose |
|--------|------|-------|---------|
| `id` | INTEGER | - | Primary key |
| `name` | TEXT | - | Producer name (e.g., "Fluffy's Pancake Palace") |
| `creativity_bias` | INTEGER | 1-5 | How much they like unusual combinations |
| `risk_tolerance` | INTEGER | 1-5 | How willing they are to change their menu |

**Seed Data**: 3 producers with distinct personalities:
- **Fluffy's Pancake Palace** (3, 3) – Balanced
- **Wild Stack Shack** (5, 5) – Risk-taker, creative
- **Grandma's Griddle** (1, 1) – Conservative traditionalist

#### `consumers` (Immutable)
Represents individual customers with personality preferences.

| Column | Type | Range | Purpose |
|--------|------|-------|---------|
| `id` | INTEGER | - | Primary key |
| `openness` | INTEGER | 1-5 | Willingness to try unusual flavor combos |
| `pickiness` | INTEGER | 1-5 | How critical/demanding they are |
| `impulsivity` | INTEGER | 1-5 | Gut feeling vs deliberate decision-making |
| `indulgence` | INTEGER | 1-5 | Preference for rich/decadent options |
| `nostalgia` | INTEGER | 1-5 | Preference for classic/comforting flavors |

**Seed Data**: 10 diverse consumers with varied trait combinations (e.g., adventurous impulsive indulger vs. traditional picky nostalgic).

#### `toppings` (Immutable)
Available topping options for pancakes. Organized by category:

| Category | Examples |
|----------|----------|
| Classic Sweet | blueberry, strawberry, banana, chocolate chip, whipped cream |
| Syrups/Spreads | maple syrup, honey, peanut butter, nutella, caramel |
| Savory | bacon, fried egg, cheddar cheese, goat cheese, prosciutto |
| Nuts/Seeds | walnut, pistachio, almond, black sesame, candied pecan |
| Exotic | matcha powder, lavender honey, mango, passion fruit, cardamom sugar |

**Total**: 30 available toppings

### Time-Series State (Per Tick)

#### `ticks`
Each row represents one simulation round. Ticks track when they start and complete.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER | Primary key (auto-incrementing) |
| `started_at` | TIMESTAMP | When the tick began |
| `completed_at` | TIMESTAMP | When the tick finished (NULL until complete) |

#### `producer_offerings` (Snapshot)
Records which producers participated in each tick.

| Column | Type | Constraint |
|--------|------|-----------|
| `tick_id` | INTEGER FK | References `ticks.id` |
| `producer_id` | INTEGER FK | References `producers.id` |
| `PK` | (tick_id, producer_id) | - |

#### `producer_toppings` (Snapshot)
The actual menu (toppings) each producer offered in each tick.

| Column | Type | Constraint |
|--------|------|-----------|
| `tick_id` | INTEGER FK | References `ticks.id` |
| `producer_id` | INTEGER FK | References `producers.id` |
| `topping_id` | INTEGER FK | References `toppings.id` |
| `PK` | (tick_id, producer_id, topping_id) | - |
| `UNIQUE INDEX` | (tick_id, topping_id) | **Exclusivity**: each topping used by ≤1 producer per tick |

#### `consumer_choices` (Snapshot)
Records which producer each consumer chose and their satisfaction level.

| Column | Type | Range | Purpose |
|--------|------|-------|---------|
| `tick_id` | INTEGER FK | - | References `ticks.id` |
| `consumer_id` | INTEGER FK | - | References `consumers.id` |
| `producer_id` | INTEGER FK | - | Which producer they chose |
| `enticement_score` | INTEGER | 1-10 | Satisfaction: 1-3 (disappointed), 4-5 (meh), 6-7 (satisfied), 8-9 (excited), 10 (perfect) |
| `PK` | (tick_id, consumer_id) | - | Each consumer picks exactly once per tick |

### Analytics (Derived)

#### `producer_round_stats`
End-of-tick statistics computed from consumer choices. Enables trend analysis and market share tracking.

| Column | Type | Purpose |
|--------|------|---------|
| `tick_id` | INTEGER FK | References `ticks.id` |
| `producer_id` | INTEGER FK | References `producers.id` |
| `consumer_count` | INTEGER | Total customers acquired |
| `market_share` | REAL | `consumer_count / total_consumers_in_tick` |
| `avg_enticement` | REAL | Mean enticement score from their customers |
| `median_enticement` | REAL | Median enticement score |
| `PK` | (tick_id, producer_id) | - |

---

## How the World Works

### Tick Lifecycle (One Simulation Round)

```
┌──────────────────────────────────────────────────────────────┐
│                       🎬 Start Tick                           │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  Phase 1: Producer Menu Decisions (LLM-Powered)              │
│  ─────────────────────────────────────────────────────────── │
│  • First Tick: Random initialization (no decisions)          │
│  • Subsequent Ticks: Each producer gets LLM prompt with:     │
│    - Their personality (creativity, risk tolerance)          │
│    - Current menu                                            │
│    - Recent performance history (last 20 ticks)             │
│    - ALL available toppings                                  │
│  • Producer's goal: Maximize future market share             │
│  • Decision: Keep some toppings, request new ones            │
│  • Output: (keep_toppings, wanted_toppings)                  │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  Phase 2: Topping Allocation (Conflict Resolution)           │
│  ─────────────────────────────────────────────────────────── │
│  • Problem: Multiple producers want same toppings            │
│  • Solution: Rotating priority (fair allocation)             │
│    - First-picker rotates by tick_id: tick1→P0, tick2→P1... │
│  • Algorithm:                                                │
│    1. Lock in all "keep" toppings (guaranteed)               │
│    2. Round-robin allocate "wanted" toppings by priority     │
│    3. Fill remaining slots with unclaimed toppings           │
│  • Result: Each producer gets exactly 5 toppings (exclusive) │
│  • Uniqueness constraint: Each topping max 1 producer/tick   │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  Phase 3: Consumer Choices (LLM-Powered)                     │
│  ─────────────────────────────────────────────────────────── │
│  • Each consumer sees: 3 anonymous menu options (A, B, C)    │
│  • Each consumer gets LLM prompt with:                       │
│    - Their personality traits (openness, pickiness, etc.)    │
│    - Trait-driven guidance (what appeals to them)            │
│    - The 3 topping combinations offered today                │
│  • Consumer's goal: Pick the menu that best fits their taste │
│  • Decision: Which option (A/B/C) and satisfaction score 1-10│
│  • Output: (chosen_option, enticement_score)                 │
│  • Menu names hidden: Anonymous labels prevent brand loyalty │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  Phase 4: Statistics & Analysis                              │
│  ─────────────────────────────────────────────────────────── │
│  • For each producer, compute:                               │
│    - customer_count: Total consumers who chose them          │
│    - market_share: % of total customers                      │
│    - avg_enticement: Mean satisfaction from their customers  │
│    - median_enticement: Median satisfaction                  │
│  • Persist to `producer_round_stats` table                   │
│  • Display results to user                                   │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                       ✅ Tick Complete                        │
│              (Ready for next simulation round)                │
└──────────────────────────────────────────────────────────────┘
```

### LLM Integration

**Producers & Consumers make decisions via LLM prompts**, not hard-coded rules. This enables:

- **Natural reasoning**: Producers can explain *why* they're changing their menu
- **Emergent behavior**: Producers might discover creative combinations the developer didn't anticipate
- **Consumer agency**: Consumers apply their personality traits to real trade-offs

#### Producer LLM Decision Flow

```python
prompt = f"""
You are {producer.name}, competing for customers in a pancake market.

🎯 GOAL: Get MORE CUSTOMERS than your competitors!
{urgent_warning if crisis else ""}

YOUR PERSONALITY:
- Risk Tolerance: {"You LOVE big changes" if risk >= 4 else "You prefer stability" if risk <= 2 else "You make reasonable changes"}
- Creativity: {"You love UNUSUAL combinations" if creativity >= 4 else "You prefer CLASSIC combinations" if creativity <= 2 else "You balance classic and creative"}

YOUR CURRENT MENU: {current_menu}
YOUR RECENT PERFORMANCE:
{history of last 5 ticks with market share, customer count}

ALL AVAILABLE TOPPINGS: {all_toppings}

TASK: Pick your ideal menu.
⚠️ List 7-10 toppings in order of preference!
Competitors may take your top choices.

RESPOND WITH JSON:
{{
    "reasoning": "brief explanation",
    "desired_toppings": ["top_choice", "2nd", "3rd", "4th", "5th", "backup1", "backup2"]
}}
"""
response = call_llm(prompt)  # Uses Ollama with gemma3:1b
```

#### Consumer LLM Choice Flow

```python
prompt = f"""
You are Consumer #{consumer.id}, choosing where to get pancakes.

YOUR PERSONALITY:
- Openness ({openness}/5): {trait_description}
- Pickiness ({pickiness}/5): {trait_description}
- Impulsivity ({impulsivity}/5): {trait_description}
- Indulgence ({indulgence}/5): {trait_description}
- Nostalgia ({nostalgia}/5): {trait_description}

TODAY'S PANCAKE OPTIONS:
Option A: [toppings]
Option B: [toppings]
Option C: [toppings]

Which option appeals to you most based on the toppings?
ENTICEMENT SCORE (based on pickiness):
- 1-3: Disappointed
- 4-5: Meh
- 6-7: Satisfied
- 8-9: Excited
- 10: Perfect

RESPOND WITH JSON:
{{
    "reasoning": "why these toppings appeal to you",
    "chosen_option": "<1 or 2 or 3>",
    "enticement_score": <1-10>
}}
"""
response = call_llm(prompt)  # Uses Ollama with gemma3:1b
```

### Key Simulation Features

#### 1. **Topping Exclusivity**
- Each topping can be offered by **at most 1 producer per tick**
- Creates scarcity-driven competition
- Incentivizes diversity (producers can't all copy the winning menu)
- Database constraint: `UNIQUE INDEX (tick_id, topping_id)`

#### 2. **Rotating Priority**
- Producer who gets first pick of new toppings rotates each tick
- Fair system: `first_pick_idx = (tick_id - 1) % num_producers`
- Prevents dominant strategies like "always pick first"
- Enables weaker producers to catch up

#### 3. **History Window**
- Producers can see their recent performance (last 20 ticks)
- Context: "You got 0 customers last round! You MUST change something!"
- Enables adaptive strategies vs. static menus

#### 4. **Consumer Anonymity**
- Consumers see menu options as "1, 2, 3" (not brand names)
- Prevents brand loyalty decisions (measures topping quality, not brand)
- Option order randomized per consumer (prevents position bias)

#### 5. **Crisis Detection**
- When market_share = 0%, producer gets urgent warning in prompt
- Encourages producers to make dramatic changes
- Adds drama and adaptation incentives

---

## Running the Simulation

### Prerequisites
- **Python 3.10+**
- **DuckDB**: `pip install duckdb`
- **Ollama**: Running with `gemma3:1b` model
  - Install: https://ollama.ai
  - Run: `ollama serve`

### Initialize Database
```bash
python main.py --init
```
- Creates schema
- Seeds 3 producers, 10 consumers, 30 toppings
- Ready for first tick

### Reset Database (Nuke & Restart)
```bash
python main.py --reset
```
- Drops all tables
- Reinitializes schema and seed data
- Safe to run multiple times

### Run One Tick
```bash
python main.py
```
- Executes one full simulation round
- Requires Ollama running
- Prints progress and results to console
- Persists all data to DuckDB

### Extract to Iceberg (Advanced)
```bash
python extract_to_iceberg.py
```
- Copies all tables from DuckDB to Apache Iceberg (via Lakekeeper)
- Enables data exploration in BI tools (Superset, Grafana, etc.)
- Skips extraction if source tables don't exist

---

## Configuration Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `DB_PATH` | `pancake_world.duckdb` | Local DuckDB database file |
| `HISTORY_WINDOW` | 20 | How many past ticks producers can see |
| `NUM_TOPPINGS_PER_PRODUCER` | 5 | Menu size (each producer gets exactly 5) |
| `MAX_TOPPING_SWAPS` | 3 | Max toppings to change per tick |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `gemma3:1b` | LLM model (lightweight, fast) |

---

## Data Analysis Queries

### Top Performers Over Time
```sql
SELECT 
    producer_id,
    ROUND(AVG(market_share), 3) AS avg_market_share,
    ROUND(AVG(avg_enticement), 1) AS avg_customer_satisfaction,
    COUNT(*) AS ticks_completed
FROM producer_round_stats
GROUP BY producer_id
ORDER BY avg_market_share DESC;
```

### Producer Menu Evolution
```sql
SELECT 
    tick_id,
    producer_id,
    GROUP_CONCAT(name ORDER BY name) AS toppings,
    market_share
FROM producer_toppings
JOIN toppings ON toppings.id = producer_toppings.topping_id
JOIN producer_round_stats ON 
    producer_round_stats.tick_id = producer_toppings.tick_id 
    AND producer_round_stats.producer_id = producer_toppings.producer_id
WHERE producer_id = 1
ORDER BY tick_id DESC
LIMIT 10;
```

### Consumer Satisfaction Distribution
```sql
SELECT 
    producer_id,
    enticement_score,
    COUNT(*) AS customer_count
FROM consumer_choices
WHERE tick_id = 5  -- Or latest tick
GROUP BY producer_id, enticement_score
ORDER BY producer_id, enticement_score;
```

---

## Future Enhancements

- **Collaborative Producers**: Teams instead of competitors
- **Price Competition**: Add pricing dynamics beyond toppings
- **Inventory Decay**: Toppings become stale, expire
- **Consumer Learning**: Consumers remember past experiences
- **Marketing**: Producers can advertise to influence choices
- **Supply Chains**: Topping sourcing, logistics
- **Seasonal Menus**: External events affect topping availability

---

## Notes

- **Simulation Speed**: Each tick takes ~20-30 seconds (LLM inference time)
- **Deterministic Seeding**: Set `random.seed()` for reproducible simulations
- **Scalability**: Current implementation supports ~30 consumers/producers; beyond that, O(n²) LLM calls may bottleneck
- **Error Handling**: Failed LLM calls fall back to mock decisions (random choices)
- **Debugging**: Enable `echo=True` in SQLAlchemy to see SQL statements

---

*Created: December 2025 | Purpose: Learning Kubernetes + Data Pipelines via emergent multi-agent simulation*
