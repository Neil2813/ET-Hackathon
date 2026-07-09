from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from services.llm_provider import chat_complete
from db.orm_models import stage_smart_contract_db

logger = logging.getLogger(__name__)


async def draft_intelligent_rfq(
    incident_id: str,
    incident_payload: dict,
    route_options: list[dict],
    user_id: str
) -> dict:
    """
    Generate an LLM-drafted or template-drafted professional RFQ email body,
    and stage a corresponding smart contract cargo booking in the database.
    """
    event_title = incident_payload.get("event_title") or incident_payload.get("title") or "Supply Disruption"
    location = incident_payload.get("region") or incident_payload.get("location") or "Global Corridor"
    exposure = incident_payload.get("total_exposure_usd") or incident_payload.get("exposure_usd") or 5000000
    severity = str(incident_payload.get("severity") or "HIGH").upper()

    # Find the best route option to include in the RFQ
    best_route_label = "Cape of Good Hope (Alternate)"
    best_mode = "tanker_vlcc"
    if route_options:
        best_opt = route_options[0]
        best_route_label = f"{best_opt.get('lane', 'Alternate Route')} (Transit: {best_opt.get('transit_days', 'N/A')} days)"
        best_mode = best_opt.get("mode", "sea")

    # Select alternative supplier contact based on route mode
    supplier_email = "chartering@gulf-maritime.com"
    supplier_name = "Gulf Maritime Tankers Corp"
    if "air" in best_mode:
        supplier_email = "chartering@cargo-cargo.com"
        supplier_name = "Apex Air Cargo"
    elif "land" in best_mode or "rail" in best_mode:
        supplier_email = "inbound-logistics@rail-land.com"
        supplier_name = "Continental Overland Rail"

    subject = f"Urgent RFQ: Emergency Cargo Allocation - {event_title} ({location})"
    
    prompt = (
        f"You are the Lead Procurement and Chartering Agent at Praecantator.\n"
        f"We are dealing with a supply chain disruption: '{event_title}' in '{location}' with a severity of '{severity}'.\n"
        f"We want to request a quote from our alternative supplier partner '{supplier_name}'.\n"
        f"We expect the alternate route to be via: '{best_route_label}'.\n"
        f"Our estimated supply gap is around 150,000 Barrels (approx. 20,000 Metric Tons) of sweet crude.\n"
        f"Draft a formal, professional, and clear RFQ email to the supplier chartering team asking them to confirm:\n"
        f"1. Vessel or cargo capacity availability for this route.\n"
        f"2. Spot charter rates and total estimated cost.\n"
        f"3. Expected loading and departure date window.\n\n"
        f"Ensure the email has a professional greeting to '{supplier_name} Chartering Team' and a signature block from 'SupplyShield Global Supply Operations'.\n"
        f"Return ONLY the plain-text email body. No markdown formatting, no code fences, no headers."
    )

    system = "You are a senior logistics contract writer. Write clear, direct, and professional email bodies."

    # Try LLM drafting first, otherwise use fallback template
    try:
        email_body, _ = await chat_complete(prompt, system=system, max_tokens=600)
        email_body = email_body.strip()
    except Exception as exc:
        logger.warning("Failed to draft RFQ email via LLM: %s. Using template fallback.", exc)
        email_body = (
            f"Dear {supplier_name} Chartering Team,\n\n"
            f"We are contacting you regarding an urgent emergency cargo booking due to the ongoing disruption event '{event_title}' in {location}.\n\n"
            f"To maintain continuity of our supply lines, we request a spot charter quotation for transporting approximately 150,000 Barrels (20,000 MT) of crude oil.\n"
            f"Our preferred alternative shipping lane is via {best_route_label}.\n\n"
            f"Please verify your vessel availability, freight rates, and closest loading window. We look forward to your prompt response within the next 24 hours.\n\n"
            f"Best regards,\n"
            f"SupplyShield Global Supply Operations"
        )

    # 2. Stage the Smart Contract
    contract_id = f"tx_sc_{uuid.uuid4().hex[:10]}"
    deadline = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    
    staged_contract = stage_smart_contract_db(
        contract_id=contract_id,
        rfq_id=f"rfq_{uuid.uuid4().hex[:8]}",
        shipper=supplier_name,
        cargo_mt=20000.0,
        route_mode=best_mode,
        deadline_iso=deadline,
        status="STAGED"
    )

    return {
        "recipient": supplier_email,
        "subject": subject,
        "body": email_body,
        "staged_contract": staged_contract
    }
