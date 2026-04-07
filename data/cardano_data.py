"""
data/cardano_data.py
--------------------
Fetches Cardano staking data for a list of wallet addresses via Blockfrost API.
"""

import json
import os
import asyncio
from datetime import datetime, timezone

import aiohttp
from loguru import logger

DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "historical_data", "cardano"
)

SUMMARY_FILE = os.path.join(DATA_DIR, "staking_summary.json")
DETAILS_FILE = os.path.join(DATA_DIR, "wallet_details.json")
META_FILE    = os.path.join(DATA_DIR, "_cardano_meta.json")

TTL_HOURS = 1
BLOCKFROST_BASE = "https://cardano-mainnet.blockfrost.io/api/v0"

WALLETS_CSV = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "data", "Cardano_wallet_addresses.csv"
)

WALLET_LIST = [
    {"name": "ADA Fireblocks Parent",    "address": "addr1q9zrp5puzh68f6cr6fch4aayzk9edguaf502na9edhc00tw7fxdtuqk56k5aueh6yu2qz6gm56wj8ttyhnyrw9e8fh4q3uv0cp"},
    {"name": "ADA Fireblocks Parent",    "address": "addr1q85jatcayqhjk8er2hp7djx672wmqkvr5p05njrpptwmqs77fxdtuqk56k5aueh6yu2qz6gm56wj8ttyhnyrw9e8fh4q8u35az"},
    {"name": "ADA Fireblocks OTC",       "address": "addr1q95839wucc5mwcjqz3r3v9cjrry5x4hv085gea3plq8a9f9l8wxumhsc8qvl7w544cy8kz0vf4gklnsah6st06n0hcfs04mzy3"},
    {"name": "ADA Fireblocks USA",       "address": "addr1q872xzgm4dr8ta2nwv78jzfmt8cde4v37y2e6tuu8vz6lwjksd9hxhrcl5mff7q3kn4g423dakdtjl5dm0c5qxz7puzs4ttqr3"},
    {"name": "ADA Fireblocks Securities","address": "addr1qyde0tj4nhtzpdcepzty3jd9k9esykvh8tz5phd45mm57644tta5xlrskhdn8ntvekjf7l7zskv0lxdaz54dcpcfnpysnxwzpr"},
    {"name": "ADA Fireblocks CAYMAN",    "address": "addr1q8y2mvnvyzzmc7f3a4069y06taxyjuafyhfw20x65y82d4c84adwr9qhnx2e6wgmz0zupacuz30p4e338znj4tsdkdcs55lcrd"},
    {"name": "ADA Fireblocks Parent (Staking)", "address": "addr1qy3pdelhk5qgmpy9wjnfs6y72hycswt2apj83m45hqc927n59qr6qhyxuvgjras4sy7mgjtgqkl2lenhks48lunlcv5surur8p"},
    {"name": "ADA Fireblocks Parent (HRP)",     "address": "addr1q8x8qpsuw23u7vc8w6lktk3dfwg0zgucjpwf7dqd4dv3wmpuy7zhy006vzfhp2ajr3eagd58j5nvtkjr5hp3v98e4jqqpv99gr"},
    {"name": "ADA Fireblocks B2C2 Lux", "address": "addr1qx7yfntgycarl6gchwmtql53sazaevj8p60fqaq2lkssuaqz8gt9gncwydda5c935tqsax5tv8p5exr2d3mq6a8av4sqxm3ffm"},
]


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_meta() -> dict:
    try:
        with open(META_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_meta(meta: dict):
    _ensure_dir()
    with open(META_FILE, "w") as f:
        json.dump(meta, f, indent=2)


def should_refresh() -> bool:
    if not os.path.exists(SUMMARY_FILE):
        return True
    meta = _load_meta()
    last = meta.get("updated_at")
    if not last:
        return True
    age = datetime.now(timezone.utc).timestamp() - datetime.fromisoformat(last).timestamp()
    return age > TTL_HOURS * 3600


def load_staking_summary() -> dict:
    try:
        with open(SUMMARY_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_wallet_details() -> list:
    try:
        with open(DETAILS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def load_wallets_from_csv() -> list:
    csv_candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Cardano_wallet_addresses_xlsx_-_Sheet1.csv"),
        "/mnt/user-data/uploads/Cardano_wallet_addresses_xlsx_-_Sheet1.csv",
        WALLETS_CSV,
    ]
    for path in csv_candidates:
        if os.path.exists(path):
            try:
                import csv
                wallets = []
                with open(path, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get('address') and row.get('name'):
                            wallets.append({
                                "name":    row['name'].strip(),
                                "address": row['address'].strip(),
                            })
                if wallets:
                    logger.info(f"Loaded {len(wallets)} wallets from {path}")
                    return wallets
            except Exception as e:
                logger.warning(f"CSV load failed ({path}): {e}")
    logger.info(f"Using inline wallet list ({len(WALLET_LIST)} wallets)")
    return WALLET_LIST


async def _fetch_json(session: aiohttp.ClientSession, url: str, api_key: str):
    headers = {"project_id": api_key}
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status == 200:
                return await resp.json(content_type=None)
            if resp.status == 404:
                return None
            logger.warning(f"Blockfrost HTTP {resp.status}: {url}")
            return None
    except Exception as e:
        logger.error(f"Blockfrost fetch error {url}: {e}")
        return None


async def _fetch_account(session: aiohttp.ClientSession, address: str, api_key: str):
    addr_data = await _fetch_json(session, f"{BLOCKFROST_BASE}/addresses/{address}", api_key)
    if not addr_data:
        return None

    stake_address = addr_data.get("stake_address")
    if not stake_address:
        return {
            "address":          address,
            "stake_address":    None,
            "staked":           False,
            "active":           False,
            "balance_lovelace": int(addr_data.get("amount", [{}])[0].get("quantity", 0))
                                  if addr_data.get("amount") else 0,
            "pool_id":          None,
            "pool_name":        None,
            "rewards_sum":      0,
            "withdrawals":      0,
            "reserves":         0,
            "treasury":         0,
            "live_stake":       0,
            "active_epoch":     None,
        }

    acct = await _fetch_json(session, f"{BLOCKFROST_BASE}/accounts/{stake_address}", api_key)
    if not acct:
        return None

    pool_id   = acct.get("pool_id")
    pool_name = None

    if pool_id:
        pool_meta = await _fetch_json(session, f"{BLOCKFROST_BASE}/pools/{pool_id}/metadata", api_key)
        if pool_meta:
            pool_name = pool_meta.get("name") or pool_meta.get("ticker")

    return {
        "address":          address,
        "stake_address":    stake_address,
        "staked":           bool(pool_id),
        "active":           acct.get("active", False),
        "balance_lovelace": int(acct.get("controlled_amount", 0) or 0),
        "pool_id":          pool_id,
        "pool_name":        pool_name,
        "rewards_sum":      int(acct.get("rewards_sum", 0) or 0),
        "withdrawals":      int(acct.get("withdrawals_sum", 0) or 0),
        "reserves":         int(acct.get("reserves_sum", 0) or 0),
        "treasury":         int(acct.get("treasury_sum", 0) or 0),
        "live_stake":       int(acct.get("live_stake", 0) or 0),
        "active_epoch":     acct.get("active_epoch"),
    }


def _lovelace_to_ada(lovelace: int) -> float:
    return round(lovelace / 1_000_000, 6)


def _aggregate_summary(wallet_results: list) -> dict:
    """
    Aggregate per-wallet results into entity groups and totals.
    """
    entities: dict = {}
    pool_map: dict = {}

    entity_seen_stake: dict = {}  # entity_name -> set of counted stake_addresses
    global_seen_stake: set  = set()

    for w in wallet_results:
        name       = w["entity_name"]
        stake_addr = w.get("stake_address")

        if name not in entities:
            entities[name] = {
                "name":              name,
                "wallet_count":      0,
                "staking_count":     0,
                "total_stake_ada":   0.0,
                "total_rewards_ada": 0.0,
                "total_live_ada":    0.0,
                "pools":             set(),
                "wallets":           [],
            }
            entity_seen_stake[name] = set()

        e = entities[name]
        e["wallet_count"] += 1

        # Only sum balance/rewards once per unique stake key per entity
        is_new_for_entity = (stake_addr is None) or (stake_addr not in entity_seen_stake[name])
        if is_new_for_entity:
            e["total_stake_ada"]   += _lovelace_to_ada(w.get("balance_lovelace", 0))
            e["total_rewards_ada"] += _lovelace_to_ada(w.get("rewards_sum", 0))
            e["total_live_ada"]    += _lovelace_to_ada(w.get("live_stake", 0))
            if stake_addr:
                entity_seen_stake[name].add(stake_addr)

        if w.get("staked"):
            e["staking_count"] += 1

        if w.get("pool_id"):
            e["pools"].add(w["pool_id"])
            pid = w["pool_id"]
            if pid not in pool_map:
                raw_name = (w.get("pool_name") or "").strip()
                display  = raw_name if raw_name else pid[:20] + "…"
                pool_map[pid] = {
                    "pool_id":         pid,
                    "pool_name":       display,
                    "wallet_count":    0,
                    "total_stake_ada": 0.0,
                    "_seen_stake":     set(),
                }
            pool_map[pid]["wallet_count"] += 1
            # Pool stake = deduplicated controlled ADA delegating to it
            if stake_addr not in pool_map[pid]["_seen_stake"]:
                pool_map[pid]["total_stake_ada"] += _lovelace_to_ada(w.get("balance_lovelace", 0))
                if stake_addr:
                    pool_map[pid]["_seen_stake"].add(stake_addr)

        e["wallets"].append({
            "address":        w["address"],
            "stake_address":  stake_addr,
            "staked":         w.get("staked", False),
            "active":         w.get("active", False),
            "balance_ada":    _lovelace_to_ada(w.get("balance_lovelace", 0)),
            "rewards_ada":    _lovelace_to_ada(w.get("rewards_sum", 0)),
            "live_stake_ada": _lovelace_to_ada(w.get("live_stake", 0)),
            "pool_id":        w.get("pool_id"),
            "pool_name":      w.get("pool_name"),
            "active_epoch":   w.get("active_epoch"),
        })

        if stake_addr:
            global_seen_stake.add(stake_addr)

    for e in entities.values():
        e["pools"] = sorted(e["pools"])

    for p in pool_map.values():
        p.pop("_seen_stake", None)

    # Global totals — deduplicated across all entities
    seen_for_totals: set  = set()
    total_stake_ada   = 0.0
    total_rewards_ada = 0.0
    total_live_ada    = 0.0

    for w in wallet_results:
        sa = w.get("stake_address")
        if sa is None or sa not in seen_for_totals:
            total_stake_ada   += _lovelace_to_ada(w.get("balance_lovelace", 0))
            total_rewards_ada += _lovelace_to_ada(w.get("rewards_sum", 0))
            total_live_ada    += _lovelace_to_ada(w.get("live_stake", 0))
            if sa:
                seen_for_totals.add(sa)

    totals = {
        "wallet_count":      len(wallet_results),
        "staking_count":     sum(1 for w in wallet_results if w.get("staked")),
        "total_stake_ada":   round(total_stake_ada,   6),
        "total_rewards_ada": round(total_rewards_ada, 6),
        "total_live_ada":    round(total_live_ada,    6),
        "unique_pools":      len(pool_map),
        "unique_stake_keys": len(seen_for_totals),
    }

    return {
        "entities": {k: v for k, v in sorted(entities.items())},
        "totals":   totals,
        "pools":    sorted(pool_map.values(), key=lambda p: p["total_stake_ada"], reverse=True),
    }


async def refresh_cardano_data(api_key: str = "") -> bool:
    if not api_key:
        api_key = os.getenv("BLOCKFROST_API_KEY", "")
    if not api_key:
        logger.warning("Cardano: BLOCKFROST_API_KEY not set — using cached data only")
        return False

    _ensure_dir()
    wallets = load_wallets_from_csv()
    logger.info(f"Cardano: fetching staking data for {len(wallets)} wallets via Blockfrost...")

    sem = asyncio.Semaphore(5)

    async def _fetch_one(session, wallet):
        async with sem:
            result = await _fetch_account(session, wallet["address"], api_key)
            if result:
                result["entity_name"] = wallet["name"]
            else:
                result = {
                    "entity_name":      wallet["name"],
                    "address":          wallet["address"],
                    "stake_address":    None,
                    "staked":           False,
                    "active":           False,
                    "balance_lovelace": 0,
                    "pool_id":          None,
                    "pool_name":        None,
                    "rewards_sum":      0,
                    "withdrawals":      0,
                    "live_stake":       0,
                    "active_epoch":     None,
                }
            return result

    async with aiohttp.ClientSession() as session:
        tasks = [_fetch_one(session, w) for w in wallets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    wallet_results = []
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"Cardano wallet fetch error: {r}")
        elif r:
            wallet_results.append(r)

    if not wallet_results:
        logger.error("Cardano: no wallet data returned")
        return False

    summary = _aggregate_summary(wallet_results)

    with open(SUMMARY_FILE, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    wallet_details = []
    for w in wallet_results:
        wallet_details.append({
            "entity_name":     w.get("entity_name"),
            "address":         w.get("address"),
            "stake_address":   w.get("stake_address"),
            "staked":          w.get("staked", False),
            "active":          w.get("active", False),
            "balance_ada":     _lovelace_to_ada(w.get("balance_lovelace", 0)),
            "rewards_ada":     _lovelace_to_ada(w.get("rewards_sum", 0)),
            "live_stake_ada":  _lovelace_to_ada(w.get("live_stake", 0)),
            "pool_id":         w.get("pool_id"),
            "pool_name":       w.get("pool_name"),
            "active_epoch":    w.get("active_epoch"),
            "withdrawals_ada": _lovelace_to_ada(w.get("withdrawals", 0)),
            "reserves_ada":    _lovelace_to_ada(w.get("reserves", 0)),
            "treasury_ada":    _lovelace_to_ada(w.get("treasury", 0)),
        })

    with open(DETAILS_FILE, "w") as f:
        json.dump(wallet_details, f, indent=2, default=str)

    _save_meta({
        "updated_at":   datetime.now(timezone.utc).isoformat(),
        "wallet_count": len(wallet_results),
    })

    staking = summary["totals"]["staking_count"]
    total   = summary["totals"]["wallet_count"]
    ada     = summary["totals"]["total_stake_ada"]
    keys    = summary["totals"]["unique_stake_keys"]
    logger.info(f"Cardano: saved — {staking}/{total} wallets staking, "
                f"{ada:,.2f} ADA across {keys} unique stake keys")
    return True