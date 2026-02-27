# SniperSight Security Architecture

This document outlines the security principles, API key handling, and threat mitigation strategies for SniperSight.

## Core Security Principles

### 1. Zero Client-Side Secrets

**Principle**: Exchange API keys and secrets NEVER touch the frontend or client-side code.

**Implementation**:
- ✅ All exchange API keys stored server-side only
- ✅ Keys loaded from environment variables or secure vault (AWS Secrets Manager, HashiCorp Vault)
- ✅ Frontend receives only profile names and capability flags
- ✅ All exchange API calls originate from backend
- ❌ NO keys in localStorage, sessionStorage, cookies, or frontend code
- ❌ NO keys in API responses or frontend-accessible endpoints

**Verification**:
```bash
# Check that API responses never include keys
curl http://localhost:8000/api/profiles | grep -i "api_key"
# Should return nothing

# Check frontend bundle doesn't contain keys
grep -r "BINANCE_API" ./dist/
# Should return nothing
```

---

### 2. Server-Side Execution Authority

**Principle**: All trading decisions and executions happen server-side with client acting as view layer only.

**Implementation**:
- ✅ Backend owns all trading logic
- ✅ Bot runs server-side loop independently of frontend
- ✅ Frontend sends high-level commands (`/api/bot/start`, `/api/bot/stop`)
- ✅ Backend validates all commands against user permissions
- ❌ Frontend cannot directly place orders
- ❌ Frontend cannot bypass risk limits

**Flow**:
```
Frontend: "Deploy SniperBot in PAPER mode with balanced profile"
    ↓
Backend: Validates user, checks profile capabilities, starts bot loop
    ↓
Bot Loop (server-side): Scans → Signals → Risk checks → Execution
    ↓
Frontend: Polls for status updates, displays results
```

---

### 3. Principle of Least Privilege

**Principle**: Exchange API keys have minimum required permissions; withdrawal capability explicitly denied.

**Required Permissions**:

#### Binance API Keys
- ✓ Enable Reading
- ✓ Enable Spot & Margin Trading (if using spot)
- ✓ Enable Futures (if using futures)
- ❌ **Enable Withdrawals** - MUST BE DISABLED

#### Bybit API Keys
- ✓ Contract Trading (Read-Write)
- ❌ **Withdraw** - MUST BE DISABLED

#### OKX API Keys
- ✓ Read
- ✓ Trade
- ❌ **Withdraw** - MUST BE DISABLED

**Rationale**: Even if API keys are compromised, attacker cannot withdraw funds—only open/close positions within configured risk limits.

---

### 4. Defense in Depth

**Principle**: Multiple layers of security controls prevent cascading failures.

**Layers**:

1. **Network Layer**:
   - HTTPS/TLS for all API traffic
   - IP whitelisting on exchange API keys (if supported)
   - Firewall rules restricting inbound connections

2. **Application Layer**:
   - JWT-based authentication for API access
   - Rate limiting per user and per endpoint
   - Input validation and sanitization
   - SQL injection prevention (parameterized queries)

3. **Business Logic Layer**:
   - Risk limits enforced before execution
   - Daily loss failsafe halts bot automatically
   - Max position size and leverage caps
   - Quality gates prevent low-quality signals from executing

4. **Data Layer**:
   - Environment variables for secrets (not hardcoded)
   - Secrets rotation capability
   - Audit logs for all trading activity
   - Database encryption at rest

---

## API Key Management

### Storage Options

#### Option 1: Environment Variables (Development)
```bash
# .env file (never committed to git)
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here
```

**Pros**: Simple, no external dependencies
**Cons**: Keys visible to anyone with server access
**Use Case**: Development, testing, small deployments

---

#### Option 2: AWS Secrets Manager (Production)
```python
import boto3
import json

def load_exchange_keys(exchange: str) -> dict:
    client = boto3.client('secretsmanager', region_name='us-east-1')
    secret_name = f"snipersight/{exchange}/api_keys"
    
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Usage
binance_keys = load_exchange_keys("binance")
api_key = binance_keys["api_key"]
api_secret = binance_keys["api_secret"]
```

**Pros**: Encrypted, audited, rotatable, role-based access
**Cons**: AWS dependency, additional cost
**Use Case**: Production deployments

---

#### Option 3: HashiCorp Vault (Production)
```python
import hvac

def load_exchange_keys(exchange: str) -> dict:
    client = hvac.Client(url='http://vault:8200')
    client.token = os.getenv('VAULT_TOKEN')
    
    secret = client.secrets.kv.v2.read_secret_version(
        path=f'snipersight/{exchange}'
    )
    return secret['data']['data']
```

**Pros**: Platform-agnostic, dynamic secrets, audit trail
**Cons**: Additional infrastructure, complexity
**Use Case**: Multi-cloud or on-premise production

---

### Key Rotation Procedure

When API keys need rotation:

1. **Generate new keys on exchange** (Binance/Bybit/OKX dashboard)
2. **Update server environment**:
   ```bash
   # Option 1: Update .env and restart
   vim .env  # Update BINANCE_API_KEY and BINANCE_API_SECRET
   systemctl restart snipersight

   # Option 2: Update AWS Secrets Manager
   aws secretsmanager update-secret \
     --secret-id snipersight/binance/api_keys \
     --secret-string '{"api_key":"NEW_KEY","api_secret":"NEW_SECRET"}'
   
   # Trigger app reload (or restart)
   ```
3. **Verify new keys work** (`GET /api/profiles` should show `live_enabled: true`)
4. **Revoke old keys on exchange**
5. **Monitor logs** for any authentication errors

**Frontend Impact**: NONE (frontend never knew about old keys or new keys)

---

## Authentication & Authorization

### User Authentication

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload  # Contains user_id, roles, etc.
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/api/bot/start")
async def start_bot(request: BotStartRequest, user=Depends(verify_token)):
    if "bot_operator" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    # ... start bot logic
```

### Role-Based Access Control (RBAC)

**Roles**:
- `scanner_user`: Can trigger scans, view signals (read-only)
- `bot_operator`: Can deploy bot in PAPER mode
- `bot_admin`: Can deploy bot in LIVE mode
- `admin`: Full system access

**Permissions Matrix**:

| Endpoint                | scanner_user | bot_operator | bot_admin | admin |
|-------------------------|--------------|--------------|-----------|-------|
| `POST /api/scan`        | ✓            | ✓            | ✓         | ✓     |
| `GET /api/signals/*`    | ✓            | ✓            | ✓         | ✓     |
| `POST /api/bot/start` (PAPER) | ✗      | ✓            | ✓         | ✓     |
| `POST /api/bot/start` (LIVE)  | ✗      | ✗            | ✓         | ✓     |
| `POST /api/bot/stop`    | ✗            | ✓            | ✓         | ✓     |
| `GET /api/bot/positions`| ✗            | ✓            | ✓         | ✓     |

---

## Input Validation & Sanitization

### API Request Validation

```python
from pydantic import BaseModel, Field, validator

class BotStartRequest(BaseModel):
    mode: str = Field(..., regex="^(OFF|PAPER|LIVE)$")
    profile: str = Field(..., min_length=1, max_length=50)
    exchange_profile: str
    risk_config: RiskConfig
    scan_interval_minutes: int = Field(ge=5, le=60)
    
    @validator("mode")
    def validate_mode(cls, v, values):
        # Additional business logic validation
        if v == "LIVE":
            # Check user permissions, profile capabilities, etc.
            pass
        return v
    
    @validator("exchange_profile")
    def validate_exchange_profile(cls, v):
        # Ensure profile exists and is valid
        profile = profile_registry.get_profile(v)
        if not profile:
            raise ValueError(f"Invalid exchange profile: {v}")
        return v
```

**Validation Rules**:
- ✅ All string inputs length-limited
- ✅ Numeric inputs range-validated
- ✅ Enum values whitelisted
- ✅ SQL injection prevented via parameterized queries
- ✅ XSS prevented via output encoding
- ✅ Path traversal prevented via input sanitization

---

## Rate Limiting

### Per-User Rate Limits

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/scan")
@limiter.limit("10/minute")
async def scan(request: ScanRequest, user=Depends(verify_token)):
    # Max 10 scans per minute per user
    pass

@app.post("/api/bot/start")
@limiter.limit("5/hour")
async def start_bot(request: BotStartRequest, user=Depends(verify_token)):
    # Max 5 bot starts per hour per user (prevent abuse)
    pass
```

### Exchange API Rate Limits

```python
class RateLimitedAdapter:
    def __init__(self, exchange: str):
        self.exchange = exchange
        self.request_times = []
        self.limits = {
            "binance": {"requests": 1200, "window": 60},  # 1200/min
            "bybit": {"requests": 120, "window": 60},     # 120/min
        }
    
    def _check_rate_limit(self):
        now = time.time()
        window = self.limits[self.exchange]["window"]
        max_requests = self.limits[self.exchange]["requests"]
        
        # Remove old requests outside window
        self.request_times = [t for t in self.request_times if now - t < window]
        
        if len(self.request_times) >= max_requests:
            sleep_time = window - (now - self.request_times[0])
            time.sleep(sleep_time)
        
        self.request_times.append(now)
    
    def fetch_ohlcv(self, symbol: str, timeframe: str):
        self._check_rate_limit()
        # Make exchange API call
```

---

## Audit Logging

### What to Log

**Security Events**:
- User login/logout
- Failed authentication attempts
- Permission denied errors
- API key validation failures
- Bot mode changes (especially OFF → LIVE)

**Trading Events**:
- Bot start/stop commands
- Position opens/closes
- Risk limit violations
- Daily loss limit hits
- Manual position overrides

**System Events**:
- Server startup/shutdown
- Configuration changes
- Exchange API errors
- Database connection issues

### Log Format

```python
import logging
import json
from datetime import datetime

class AuditLogger:
    def __init__(self):
        self.logger = logging.getLogger("audit")
        handler = logging.FileHandler("audit.log")
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_event(self, event_type: str, user_id: str, data: dict):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "data": data
        }
        self.logger.info(json.dumps(log_entry))

# Usage
audit_logger.log_event(
    event_type="bot_started",
    user_id="user_123",
    data={
        "mode": "LIVE",
        "profile": "balanced",
        "exchange_profile": "Binance_Live",
        "ip_address": request.client.host
    }
)
```

**Log Retention**: Keep audit logs for minimum 90 days; archive for regulatory compliance if needed.

---

## Incident Response

### Suspected Key Compromise

**Immediate Actions**:
1. **Revoke compromised keys** on exchange immediately
2. **Stop all bots** using those keys (`POST /api/bot/stop`)
3. **Review open positions** - close if suspicious
4. **Check audit logs** for unauthorized activity
5. **Generate new keys** with different permissions if possible
6. **Update server environment** with new keys
7. **Notify users** if multi-tenant system

### Unauthorized Trading Activity

**Detection**:
- Positions opened outside configured hours
- Symbols traded that aren't in configured universe
- Position sizes exceeding configured limits
- Rapid-fire orders (potential bot compromise)

**Response**:
1. **Halt bot immediately**
2. **Close suspicious positions**
3. **Review audit logs** for source of activity
4. **Check server logs** for intrusion attempts
5. **Verify API key permissions** haven't been escalated
6. **Consider rotating keys** as precaution

---

## Security Checklist

### Pre-Deployment

- [ ] All API keys stored server-side (environment variables or vault)
- [ ] Withdrawal permissions DISABLED on all exchange API keys
- [ ] HTTPS/TLS enabled for all endpoints
- [ ] Authentication required for all sensitive endpoints
- [ ] Rate limiting configured per user and per endpoint
- [ ] Input validation on all API requests
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (output encoding)
- [ ] Audit logging configured for security and trading events
- [ ] Frontend bundle checked for accidental key leaks
- [ ] `.env` file added to `.gitignore`
- [ ] IP whitelisting configured on exchange (if supported)
- [ ] Error messages don't leak sensitive information
- [ ] Database credentials secured
- [ ] JWT secret is strong and rotated periodically

### Runtime Monitoring

- [ ] Monitor failed authentication attempts
- [ ] Alert on API key validation failures
- [ ] Track daily PnL and position exposure
- [ ] Alert on daily loss limit approaching
- [ ] Monitor exchange API rate limit usage
- [ ] Log all bot mode changes
- [ ] Track manual position overrides
- [ ] Alert on unexpected errors or exceptions

### Periodic Review

- [ ] Review audit logs weekly for anomalies
- [ ] Rotate API keys quarterly (or per policy)
- [ ] Review user roles and permissions
- [ ] Update dependencies for security patches
- [ ] Test incident response procedures
- [ ] Verify backup and recovery processes
- [ ] Review and update this security document

---

## Compliance Considerations

### Data Protection

- **User Data**: Encrypt personally identifiable information (PII)
- **Trading Data**: Store audit logs securely
- **API Keys**: Never log in plaintext

### Financial Regulations

- **Disclaimer**: SniperSight is a tool; users responsible for compliance with local laws
- **KYC/AML**: Users must complete KYC on exchanges directly
- **Tax Reporting**: Users responsible for capital gains reporting
- **Record Keeping**: Audit logs provide trade history for tax purposes

---

## Contact & Reporting

**Security Issues**: Report to security@snipersight.example.com

**Bug Bounty**: Consider establishing program for responsible disclosure

**Incident Response**: Maintain on-call rotation for critical security incidents
