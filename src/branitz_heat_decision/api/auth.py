from fastapi import Security, HTTPException, Depends, Request
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from starlette.status import HTTP_403_FORBIDDEN, HTTP_401_UNAUTHORIZED
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict
import jwt
from pydantic import BaseModel

# Configuration
SECRET_KEY = "your-secret-key-change-in-production"  # Load from env
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# API Key storage (replace with database in production)
API_KEYS_DB = {
    "fh_demo_key_123": {
        "tenant": "fraunhofer_iis",
        "rate_limit": 1000,  # requests per hour
        "allowed_origins": ["*.fraunhofer.de", "*.iis.fraunhofer.de"],
        "permissions": ["read", "simulate", "export"],
        "expires": None  # Never
    },
    "fh_researcher_456": {
        "tenant": "fraunhofer_eas",
        "rate_limit": 100,
        "permissions": ["read", "simulate"],
        "expires": "2024-12-31"
    }
}

# OAuth2 scheme for JWT
oauth2_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

class User(BaseModel):
    id: str
    tenant: str
    email: Optional[str] = None
    permissions: list = []
    is_admin: bool = False

class APIKeyManager:
    def __init__(self):
        self._usage_counts: Dict[str, int] = {}
        self._last_reset = datetime.now()
    
    def validate_api_key(self, api_key: str) -> Optional[Dict]:
        """Validate API key and return tenant info"""
        if not api_key or api_key not in API_KEYS_DB:
            return None
        
        key_data = API_KEYS_DB[api_key]
        
        # Check expiration
        if key_data.get("expires"):
            exp = datetime.strptime(key_data["expires"], "%Y-%m-%d")
            if datetime.now() > exp:
                return None
        
        return key_data
    
    def check_rate_limit(self, api_key: str) -> bool:
        """Check if API key has exceeded rate limit"""
        # Reset counters hourly
        if datetime.now() - self._last_reset > timedelta(hours=1):
            self._usage_counts = {}
            self._last_reset = datetime.now()
        
        key_data = API_KEYS_DB.get(api_key, {})
        limit = key_data.get("rate_limit", 100)
        current = self._usage_counts.get(api_key, 0)
        
        if current >= limit:
            return False
        
        self._usage_counts[api_key] = current + 1
        return True
    
    def create_key(self, tenant: str, permissions: list, expires_days: int = 365) -> str:
        """Generate new API key (admin only)"""
        raw_key = f"fh_{tenant}_{secrets.token_urlsafe(16)}"
        hashed = hashlib.sha256(raw_key.encode()).hexdigest()[:32]
        
        API_KEYS_DB[hashed] = {
            "tenant": tenant,
            "permissions": permissions,
            "created": datetime.now().isoformat(),
            "expires": (datetime.now() + timedelta(days=expires_days)).strftime("%Y-%m-%d")
        }
        
        return raw_key

key_manager = APIKeyManager()

async def verify_access(
    request: Request,
    api_key: Optional[str] = Security(api_key_header),
    token: Optional[HTTPAuthorizationCredentials] = Security(oauth2_scheme)
) -> User:
    """
    Combined authentication: API Key (for service access) or JWT (for UI users)
    """
    # Try API Key first (for programmatic access)
    if api_key:
        key_data = key_manager.validate_api_key(api_key)
        if not key_data:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail="Invalid or expired API key"
            )
        
        if not key_manager.check_rate_limit(api_key):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again in 1 hour."
            )
        
        # Check origin for browser requests
        origin = request.headers.get("origin", "")
        allowed = key_data.get("allowed_origins", ["*"])
        if not any(origin.endswith(domain.replace("*.", "")) for domain in allowed):
            if origin:  # Only check if origin header present (browser request)
                raise HTTPException(
                    status_code=HTTP_403_FORBIDDEN,
                    detail="Origin not allowed for this API key"
                )
        
        return User(
            id=f"api_{api_key[:8]}",
            tenant=key_data["tenant"],
            permissions=key_data["permissions"]
        )
    
    # Try JWT token (for logged-in web users)
    if token:
        try:
            payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            return User(
                id=payload["sub"],
                tenant=payload["tenant"],
                email=payload.get("email"),
                permissions=payload.get("permissions", ["read"]),
                is_admin=payload.get("is_admin", False)
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    # Demo mode - allow limited access without auth
    if request.url.path in ["/health", "/demo/status", "/docs", "/"]:
        return User(id="anonymous", tenant="public", permissions=["read"])
    
    raise HTTPException(
        status_code=HTTP_401_UNAUTHORIZED,
        detail="API Key or Bearer token required",
        headers={"WWW-Authenticate": "Bearer"},
    )

def require_permissions(required: list):
    """Dependency factory for permission checking"""
    async def checker(user: User = Depends(verify_access)):
        if not all(p in user.permissions for p in required):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {required}"
            )
        return user
    return checker

# Admin endpoints
async def verify_admin(user: User = Depends(verify_access)):
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    return user
