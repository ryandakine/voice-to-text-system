#!/usr/bin/env python3
"""CIMCO Inventory API Tools for LLM Function Calling.

This module provides tool definitions and implementations that allow an LLM
(like Gemini or GPT) to query and update the CIMCO inventory system.

Each function is designed to be called by the LLM via function/tool calling,
and returns structured data that the LLM can interpret and relay to the user.
"""

import os
import httpx
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# CIMCO API Configuration
CIMCO_API_URL = os.getenv("CIMCO_API_URL", "http://localhost:8081/api")
CIMCO_USER = os.getenv("CIMCO_USER", "worker")
CIMCO_PASS = os.getenv("CIMCO_PASS", "worker123")

# Session token (cached after login)
_session_token: Optional[str] = None


async def _ensure_session() -> str:
    """Ensure we have a valid session token, logging in if necessary."""
    global _session_token
    if _session_token:
        return _session_token
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{CIMCO_API_URL}/login",
            json={"username": CIMCO_USER, "password": CIMCO_PASS}
        )
        if response.status_code != 200:
            raise Exception(f"CIMCO login failed: {response.text}")
        
        data = response.json()
        _session_token = data.get("token")
        if not _session_token:
            raise Exception("No session token in login response")
        return _session_token


async def search_parts(query: str, zone: Optional[str] = None) -> dict:
    """Search for parts in the CIMCO inventory.
    
    Args:
        query: Search term (part name, number, or description)
        zone: Optional zone filter (e.g., "Zone A", "Zone B")
    
    Returns:
        Dictionary with 'parts' list and 'total' count
    """
    token = await _ensure_session()
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{CIMCO_API_URL}/get_parts_paginated",
            json={
                "session_token": token,
                "page": 1,
                "page_size": 20,
                "search_query": query,
                "zone_filter": zone
            }
        )
        if response.status_code != 200:
            return {"error": f"API error: {response.status_code}"}
        
        data = response.json()
        parts = data.get("items", [])
        total = data.get("total", len(parts))
        
        # Simplify for LLM consumption
        simplified_parts = []
        for p in parts[:10]:  # Limit to 10 for voice response
            simplified_parts.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "quantity": p.get("quantity", 0),
                "location": p.get("location", "Unknown"),
                "part_number": p.get("part_number", "N/A")
            })
        
        return {
            "parts": simplified_parts,
            "total": total,
            "showing": len(simplified_parts)
        }


async def get_part_details(part_id: int) -> dict:
    """Get detailed information about a specific part.
    
    Args:
        part_id: The unique ID of the part
    
    Returns:
        Dictionary with full part details
    """
    token = await _ensure_session()
    
    # Use search with empty query and filter by ID (workaround since no direct get_part endpoint)
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{CIMCO_API_URL}/get_parts_paginated",
            json={
                "session_token": token,
                "page": 1,
                "page_size": 100,
                "search_query": ""
            }
        )
        if response.status_code != 200:
            return {"error": f"API error: {response.status_code}"}
        
        data = response.json()
        parts = data.get("items", [])
        
        # Find the specific part
        for p in parts:
            if p.get("id") == part_id:
                return {
                    "found": True,
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "quantity": p.get("quantity", 0),
                    "min_quantity": p.get("min_quantity", 0),
                    "location": p.get("location", "Unknown"),
                    "zone": p.get("zone", "Unknown"),
                    "part_number": p.get("part_number", "N/A"),
                    "manufacturer": p.get("manufacturer", "Unknown"),
                    "category": p.get("category", "Unknown"),
                    "function_description": p.get("function_description", "")
                }
        
        return {"found": False, "error": f"Part ID {part_id} not found"}


async def update_quantity(part_id: int, change: int) -> dict:
    """Update the quantity of a part (add or subtract).
    
    Args:
        part_id: The unique ID of the part
        change: Quantity change (positive to add, negative to subtract)
    
    Returns:
        Dictionary with success status and new quantity
    """
    token = await _ensure_session()
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{CIMCO_API_URL}/update_part_quantity",
            json={
                "session_token": token,
                "id": part_id,
                "quantity_change": change
            }
        )
        if response.status_code != 200:
            return {"success": False, "error": f"API error: {response.status_code}"}
        
        return {"success": True, "change": change}


async def get_equipment_status() -> dict:
    """Get the status of all equipment.
    
    Returns:
        Dictionary with equipment list and health scores
    """
    token = await _ensure_session()
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{CIMCO_API_URL}/get_equipment",
            json={"session_token": token}
        )
        if response.status_code != 200:
            return {"error": f"API error: {response.status_code}"}
        
        equipment = response.json()
        
        # Simplify for voice
        simplified = []
        for e in equipment[:10]:
            simplified.append({
                "name": e.get("name"),
                "status": e.get("status", "Unknown"),
                "health_score": e.get("health_score", 0),
                "location": e.get("location", "Unknown")
            })
        
        return {"equipment": simplified, "total": len(equipment)}


async def get_inventory_stats() -> dict:
    """Get overall inventory statistics.
    
    Returns:
        Dictionary with summary stats (total parts, low stock count, etc.)
    """
    token = await _ensure_session()
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{CIMCO_API_URL}/get_stats",
            json={"session_token": token}
        )
        if response.status_code != 200:
            return {"error": f"API error: {response.status_code}"}
        
        return response.json()


async def get_low_stock_items() -> dict:
    """Get items that are below minimum quantity.
    
    Returns:
        Dictionary with list of low-stock parts
    """
    # First get all parts, then filter by low stock
    result = await search_parts("")
    if "error" in result:
        return result
    
    # Note: This is a simplified approach. In production, you'd want a dedicated
    # low-stock endpoint in the CIMCO API.
    return {
        "note": "Low stock filtering requires dedicated API endpoint",
        "total_parts": result.get("total", 0)
    }


# Tool definitions for LLM function calling (OpenAI/Gemini format)
CIMCO_TOOLS = [
    {
        "name": "search_parts",
        "description": "Search for parts in the CIMCO inventory by name, part number, or description. Use this when the user asks about specific parts or wants to find something.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term (part name, number, or keywords)"
                },
                "zone": {
                    "type": "string",
                    "description": "Optional zone filter (e.g., 'Zone A', 'Zone B', 'Zone C')"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_part_details",
        "description": "Get detailed information about a specific part by its ID. Use this after searching to get more info about a particular item.",
        "parameters": {
            "type": "object",
            "properties": {
                "part_id": {
                    "type": "integer",
                    "description": "The unique ID of the part"
                }
            },
            "required": ["part_id"]
        }
    },
    {
        "name": "update_quantity",
        "description": "Add or subtract from a part's quantity. Use positive numbers to add stock, negative to remove.",
        "parameters": {
            "type": "object",
            "properties": {
                "part_id": {
                    "type": "integer",
                    "description": "The unique ID of the part to update"
                },
                "change": {
                    "type": "integer",
                    "description": "Quantity change (positive to add, negative to subtract)"
                }
            },
            "required": ["part_id", "change"]
        }
    },
    {
        "name": "get_equipment_status",
        "description": "Get the status and health scores of all equipment in the yard.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_inventory_stats",
        "description": "Get overall inventory statistics and summary.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
]


# Mapping function names to implementations
TOOL_FUNCTIONS = {
    "search_parts": search_parts,
    "get_part_details": get_part_details,
    "update_quantity": update_quantity,
    "get_equipment_status": get_equipment_status,
    "get_inventory_stats": get_inventory_stats
}


async def execute_tool(tool_name: str, arguments: dict) -> dict:
    """Execute a tool by name with the given arguments.
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Dictionary of arguments for the tool
    
    Returns:
        Result from the tool execution
    """
    if tool_name not in TOOL_FUNCTIONS:
        return {"error": f"Unknown tool: {tool_name}"}
    
    func = TOOL_FUNCTIONS[tool_name]
    try:
        result = await func(**arguments)
        return result
    except Exception as e:
        return {"error": str(e)}


async def control_home(action: str, target: str) -> dict:
    """Control smart home devices via Home Assistant.
    
    Args:
        action: The action to perform ("unlock", "lock", "turn_on", "turn_off")
        target: The target device ("door", "lights")
    
    Returns:
        Dictionary with result status
    """
    # For now, we only support unlocking the door via the webhook we created
    if action == "unlock" and "door" in target:
        try:
            # We use the straightforward webhook approach
            async with httpx.AsyncClient(timeout=5.0) as client:
                # We can call the webhook endpoint on the HA instance
                # Since this runs on the Pi, localhost:8123 or 192.168.12.249 works
                webhook_url = "http://192.168.12.249:8123/api/webhook/unlock_door_on_arrival"
                await client.post(webhook_url)
                return {"success": True, "message": "Door unlocking initiated"}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    return {"success": False, "error": f"Unsupported action/target: {action} {target}"}

# Add to tools list
CIMCO_TOOLS.append({
    "name": "control_home",
    "description": "Control smart home devices like locks and lights.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["unlock", "lock", "turn_on", "turn_off"]},
            "target": {"type": "string"}
        },
        "required": ["action", "target"]
    }
})

# Add to functions map
TOOL_FUNCTIONS["control_home"] = control_home
