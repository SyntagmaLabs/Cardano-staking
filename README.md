# Cardano Staking Dashboard

A lightweight single-page dashboard for monitoring Cardano staking across a large multi-wallet portfolio. Built with Python/Quart and Blockfrost.

---

## What it does

- Shows staking status, balance, and rewards for every wallet in your list
- Groups wallets by entity (e.g. Fireblocks Parent, USA, CAYMAN)
- Aggregates totals correctly — wallets sharing a stake key are counted once, not multiplied
- Shows which pools the portfolio is delegating to
- Filter and search the wallet table by entity or address
- Each address links directly to cardanoscan.io
- Manual refresh button + automatic refresh every hour

---

## Setup

**Requirements:** Python 3.11+

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
BLOCKFROST_API_KEY=mainnetXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

Get a free API key at [blockfrost.io](https://blockfrost.io) — the free tier allows 50,000 requests/day which is more than enough.

**Run:**

```bash
python app.py
```

Then open `http://localhost:5000/cardano`

---

## Wallet List

Add your wallet addresses to the CSV file in the project root:

```
Cardano_wallet_addresses_xlsx_-_Sheet1.csv
```

Expected columns:

```
name,sym,blockchain,address
ADA Fireblocks Parent,ADA,Cardano,addr1q9zrp5...
ADA Fireblocks CAYMAN,ADA,Cardano,addr1q8y2mv...
```

The `name` column is used to group wallets into entities on the dashboard. All wallets with the same name are aggregated together.

---

## Project Structure

```
app.py                            # Quart app entry point + background refresh loop
routes/
  cardano.py                      # /cardano page + /api/cardano/* endpoints
data/
  cardano_data.py                 # Blockfrost fetcher + aggregation logic
  historical_data/cardano/
    staking_summary.json          # Cached aggregated data (auto-generated)
    wallet_details.json           # Cached per-wallet data (auto-generated)
    _cardano_meta.json            # Last refresh timestamp (auto-generated)
  Cardano_wallet_addresses_xlsx_-_Sheet1.csv   # Your wallet list
static/
  css/cardano.css
  js/cardano.js
www/
  templates/app.html              # Base layout
  views/cardano.html              # Dashboard template
logs/
  app.log
.env
requirements.txt
```

---

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /cardano` | Dashboard page |
| `GET /api/cardano/summary` | Aggregated totals, entities, and pool breakdown |
| `GET /api/cardano/wallets` | Per-wallet detail list (optional `?entity=` filter) |
| `GET /api/cardano/refresh` | Trigger a manual data refresh from Blockfrost |

---

## A Note on Balances

Blockfrost reports `controlled_amount` at the **stake key** level, not the payment address level. A Fireblocks vault typically creates many payment addresses all pointing to a single stake key. The dashboard deduplicates by stake key before summing any totals, so the numbers shown are the true economic balances rather than address-count × balance-per-key.