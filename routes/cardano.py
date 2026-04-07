"""
routes/cardano.py
-----------------
Cardano staking dashboard page + API endpoints.
All reads are pure disk — no Blockfrost calls during request handling.

Endpoints:
  GET /cardano                      — dashboard page
  GET /api/cardano/summary          — aggregated staking summary
  GET /api/cardano/wallets          — per-wallet staking details
  GET /api/cardano/refresh          — manual trigger for data refresh
"""

import json
import os

from quart import Blueprint, render_template, jsonify, request
import data.cardano_data as cardano_data

cardano_bp = Blueprint("cardano", __name__)


@cardano_bp.route("/cardano")
async def cardano_page():
    return await render_template("cardano.html", active_page="cardano")


@cardano_bp.route("/api/cardano/summary")
async def cardano_summary():
    """
    Returns the aggregated staking summary from disk.
    Injects updated_at from the meta file so the JS can display it.
    """
    try:
        data = cardano_data.load_staking_summary()
        if not data:
            return jsonify({"error": "No Cardano data yet — initialising or API key missing"}), 503

        # Inject updated_at from the meta file into the response
        meta = cardano_data._load_meta()
        if meta.get("updated_at"):
            data["updated_at"] = meta["updated_at"]

        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@cardano_bp.route("/api/cardano/wallets")
async def cardano_wallets():
    """
    Returns per-wallet staking details.
    Optional query param: ?entity=ADA+Fireblocks+CAYMAN to filter by entity.
    """
    try:
        entity_filter = request.args.get("entity", "").strip()
        details = cardano_data.load_wallet_details()
        if not details:
            return jsonify([])
        if entity_filter:
            details = [w for w in details if w.get("entity_name") == entity_filter]
        return jsonify(details)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@cardano_bp.route("/api/cardano/refresh")
async def cardano_refresh():
    """Manual refresh trigger — calls Blockfrost and updates disk cache."""
    api_key = os.getenv("BLOCKFROST_API_KEY", "")
    if not api_key:
        return jsonify({"error": "BLOCKFROST_API_KEY not configured in environment"}), 400
    try:
        ok = await cardano_data.refresh_cardano_data(api_key)
        if ok:
            return jsonify({"status": "ok", "message": "Cardano data refreshed"})
        return jsonify({"error": "Refresh failed — check server logs"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500