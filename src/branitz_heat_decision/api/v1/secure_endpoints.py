from fastapi import APIRouter, Depends, HTTPException
from .schemas import SimulationRequest, SimulationResult
from ..auth import verify_access, require_permissions, verify_admin, key_manager, User
from typing import Optional
from datetime import datetime
from ..auth import API_KEYS_DB

router = APIRouter()

@router.post("/simulate", 
             response_model=SimulationResult,
             dependencies=[Depends(require_permissions(["simulate"]))])
async def secure_simulate(
    request: SimulationRequest,
    user: User = Depends(verify_access)
):
    """
    Run simulation with tenant isolation.
    Results are scoped to the user's organization.
    """
    # Add tenant context to request
    request.tenant_id = user.tenant
    
    # Log access for audit
    print(f"[AUDIT] User {user.id} ({user.tenant}) started simulation {request.request_id}")
    
    # Run simulation (existing logic)
    # ... simulation code ...
    simulation_results = {} # Mock
    
    # Tag results with tenant
    result = {
        **simulation_results,
        "tenant": user.tenant,
        "access_level": "restricted" if user.tenant != "fraunhofer_admin" else "full"
    }
    
    return result

@router.get("/admin/keys", dependencies=[Depends(verify_admin)])
async def list_api_keys():
    """Admin: List all API keys (hashed)"""
    return {
        "keys": [
            {
                "id": k[:8] + "****",
                "tenant": v["tenant"],
                "created": v.get("created"),
                "expires": v.get("expires"),
                "active": v.get("expires") is None or v.get("expires") > datetime.now().strftime("%Y-%m-%d")
            }
            for k, v in API_KEYS_DB.items()
        ]
    }

@router.post("/admin/keys", dependencies=[Depends(verify_admin)])
async def create_api_key(tenant: str, permissions: list, expires_days: int = 365):
    """Admin: Create new API key for tenant"""
    new_key = key_manager.create_key(tenant, permissions, expires_days)
    return {
        "api_key": new_key,
        "warning": "Store this key securely - it will not be shown again",
        "tenant": tenant,
        "permissions": permissions
    }

@router.get("/user/me")
async def get_current_user(user: User = Depends(verify_access)):
    """Get current user info"""
    return {
        "id": user.id,
        "tenant": user.tenant,
        "permissions": user.permissions,
        "is_admin": user.is_admin
    }
