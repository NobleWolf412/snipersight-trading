# Exchange Profiles

This document describes the exchange profile system, environment variable configuration, and capability management for SniperSight.

## Overview

**Exchange profiles** are server-side abstractions that manage exchange API credentials and operational modes. They provide a secure layer between the frontend UI and actual exchange API keys.

## Profile Structure

Each profile defines:
- **Exchange** - Which exchange to connect to (Binance, Bybit, OKX, etc.)
- **Mode** - Operational mode (data, paper, live)
- **Capabilities** - What operations are enabled
- **Environment Variables** - Which env vars hold the API keys

## Standard Profiles

### Data-Only Profiles

Used for Scanner Mode where no execution capability is needed.

| Profile Name    | Exchange | Mode | Data | Paper | Live | Requires Keys |
|-----------------|----------|------|------|-------|------|---------------|
| `Phemex_Data`   | Phemex   | data | ✓    | ✗     | ✗    | ✗             |
| `Bybit_Data`    | Bybit    | data | ✓    | ✗     | ✗    | ✗             |
| `OKX_Data`      | OKX      | data | ✓    | ✗     | ✗    | ✗             |
| `Bitget_Data`   | Bitget   | data | ✓    | ✗     | ✗    | ✗             |

**Note**: Phemex is the default exchange adapter (no geo-blocking for US users).

**Use Cases**:
- Scanner Mode market data fetching
- Public API endpoints only
- No API keys required
- Read-only OHLCV and ticker data

---

### Paper Trading Profiles

Used for SniperBot Mode in PAPER/Training Mode.

| Profile Name     | Exchange | Mode  | Data | Paper | Live | Requires Keys |
|------------------|----------|-------|------|-------|------|---------------|
| `Binance_Paper`  | Binance  | paper | ✓    | ✓     | ✗    | ✗             |
| `Bybit_Paper`    | Bybit    | paper | ✓    | ✓     | ✗    | ✗             |
| `OKX_Paper`      | OKX      | paper | ✓    | ✓     | ✗    | ✗             |

**Use Cases**:
- Bot training mode with simulated execution
- No real orders sent to exchange
- Internal paper account simulation
- No API keys required (uses public data only)

**Implementation**:
```python
class PaperExecutor:
    def execute_order(self, order: Order) -> ExecutionResult:
        # Simulate order execution locally
        self.paper_account.open_position(order)
        return ExecutionResult(status="filled", simulated=True)
```

---

### Live Trading Profiles

Used for SniperBot Mode in LIVE mode with real execution.

| Profile Name    | Exchange | Mode | Data | Paper | Live | Requires Keys |
|-----------------|----------|------|------|-------|------|---------------|
| `Binance_Live`  | Binance  | live | ✓    | ✓    | ✓    | ✓             |
| `Bybit_Live`    | Bybit    | live | ✓    | ✓    | ✓    | ✓             |
| `OKX_Live`      | OKX      | live | ✓    | ✓    | ✓    | ✓             |

**Use Cases**:
- Real trading with real funds
- Requires valid exchange API keys
- Subject to exchange rate limits
- Full execution authority

**Security Requirements**:
- API keys stored server-side only
- Keys loaded from environment variables or secure vault
- Never transmitted to frontend
- Validated on server startup

---

## Environment Variables

Exchange API credentials are configured via environment variables.

### Binance

```bash
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_API_SECRET=your_binance_api_secret_here
```

**Required Permissions** (for LIVE mode):
- ✓ Enable Reading
- ✓ Enable Spot & Margin Trading
- ✗ Enable Withdrawals (NOT required)

**API Key Setup**:
1. Log in to Binance → API Management
2. Create new API Key
3. Enable "Enable Reading" and "Enable Spot & Margin Trading"
4. Whitelist server IP address (recommended)
5. Save API Key and Secret to environment

---

### Bybit

```bash
BYBIT_API_KEY=your_bybit_api_key_here
BYBIT_API_SECRET=your_bybit_api_secret_here
```

**Required Permissions**:
- ✓ Read-Write for Contract Trading
- ✗ Withdraw (NOT required)

**API Key Setup**:
1. Log in to Bybit → API Management
2. Create new API Key
3. Enable "Contract Trading" with Read-Write
4. Whitelist server IP (recommended)
5. Save to environment

---

### OKX

```bash
OKX_API_KEY=your_okx_api_key_here
OKX_API_SECRET=your_okx_api_secret_here
OKX_PASSPHRASE=your_okx_passphrase_here
```

**Required Permissions**:
- ✓ Read
- ✓ Trade
- ✗ Withdraw (NOT required)

**API Key Setup**:
1. Log in to OKX → API Management
2. Create new API Key with passphrase
3. Enable "Read" and "Trade" permissions
4. Save API Key, Secret, and Passphrase to environment

---

## Profile Configuration (Backend)

### Python Implementation

```python
from dataclasses import dataclass
from typing import Dict, Optional
import os

@dataclass
class ProfileCapabilities:
    data_enabled: bool
    paper_enabled: bool
    live_enabled: bool
    keys_valid: bool

@dataclass
class ExchangeProfile:
    name: str
    exchange: str
    mode: str  # "data" | "paper" | "live"
    env_vars: Dict[str, str]
    capabilities: ProfileCapabilities
    
    @classmethod
    def from_config(cls, name: str, exchange: str, mode: str) -> "ExchangeProfile":
        env_vars = cls._get_env_vars(exchange)
        capabilities = cls._check_capabilities(exchange, mode, env_vars)
        
        return cls(
            name=name,
            exchange=exchange,
            mode=mode,
            env_vars=env_vars,
            capabilities=capabilities
        )
    
    @staticmethod
    def _get_env_vars(exchange: str) -> Dict[str, str]:
        if exchange == "binance":
            return {
                "api_key": "BINANCE_API_KEY",
                "api_secret": "BINANCE_API_SECRET"
            }
        elif exchange == "bybit":
            return {
                "api_key": "BYBIT_API_KEY",
                "api_secret": "BYBIT_API_SECRET"
            }
        elif exchange == "okx":
            return {
                "api_key": "OKX_API_KEY",
                "api_secret": "OKX_API_SECRET",
                "passphrase": "OKX_PASSPHRASE"
            }
        else:
            raise ValueError(f"Unknown exchange: {exchange}")
    
    @staticmethod
    def _check_capabilities(
        exchange: str,
        mode: str,
        env_vars: Dict[str, str]
    ) -> ProfileCapabilities:
        # Check if API keys are present in environment
        keys_present = all(
            os.getenv(var_name) is not None
            for var_name in env_vars.values()
        )
        
        # Validate keys if present (ping exchange API)
        keys_valid = False
        if keys_present and mode == "live":
            keys_valid = _validate_exchange_keys(exchange, env_vars)
        
        return ProfileCapabilities(
            data_enabled=True,  # Always can fetch public data
            paper_enabled=True if mode in ["paper", "live"] else False,
            live_enabled=keys_valid if mode == "live" else False,
            keys_valid=keys_valid
        )

def _validate_exchange_keys(exchange: str, env_vars: Dict[str, str]) -> bool:
    """
    Validates API keys by making a test authenticated request.
    Returns True if keys are valid, False otherwise.
    """
    try:
        if exchange == "binance":
            from binance.client import Client
            api_key = os.getenv(env_vars["api_key"])
            api_secret = os.getenv(env_vars["api_secret"])
            client = Client(api_key, api_secret)
            client.get_account()  # Test authenticated endpoint
            return True
        # Similar for other exchanges
    except Exception as e:
        print(f"API key validation failed for {exchange}: {e}")
        return False
```

### Profile Registry

```python
class ProfileRegistry:
    def __init__(self):
        self.profiles: Dict[str, ExchangeProfile] = {}
        self._initialize_profiles()
    
    def _initialize_profiles(self):
        # Data-only profiles
        self.profiles["Binance_Data"] = ExchangeProfile.from_config(
            "Binance_Data", "binance", "data"
        )
        self.profiles["Bybit_Data"] = ExchangeProfile.from_config(
            "Bybit_Data", "bybit", "data"
        )
        
        # Paper profiles
        self.profiles["Binance_Paper"] = ExchangeProfile.from_config(
            "Binance_Paper", "binance", "paper"
        )
        self.profiles["Bybit_Paper"] = ExchangeProfile.from_config(
            "Bybit_Paper", "bybit", "paper"
        )
        
        # Live profiles
        self.profiles["Binance_Live"] = ExchangeProfile.from_config(
            "Binance_Live", "binance", "live"
        )
        self.profiles["Bybit_Live"] = ExchangeProfile.from_config(
            "Bybit_Live", "bybit", "live"
        )
    
    def get_profile(self, name: str) -> Optional[ExchangeProfile]:
        return self.profiles.get(name)
    
    def list_profiles(self) -> List[ExchangeProfile]:
        return list(self.profiles.values())
    
    def get_profiles_for_mode(self, mode: str) -> List[ExchangeProfile]:
        """Returns profiles suitable for a given mode (data/paper/live)."""
        return [
            p for p in self.profiles.values()
            if (mode == "data" and p.capabilities.data_enabled) or
               (mode == "paper" and p.capabilities.paper_enabled) or
               (mode == "live" and p.capabilities.live_enabled)
        ]
```

---

## API Response Format

When the frontend requests available profiles, the backend returns:

```json
{
  "profiles": [
    {
      "name": "Binance_Data",
      "exchange": "binance",
      "mode": "data",
      "data_enabled": true,
      "paper_enabled": false,
      "live_enabled": false
    },
    {
      "name": "Binance_Paper",
      "exchange": "binance",
      "mode": "paper",
      "data_enabled": true,
      "paper_enabled": true,
      "live_enabled": false
    },
    {
      "name": "Binance_Live",
      "exchange": "binance",
      "mode": "live",
      "data_enabled": true,
      "paper_enabled": true,
      "live_enabled": true
    }
  ]
}
```

**Security Guarantee**: API keys are NEVER included in this response.

---

## Frontend Usage

The frontend uses profile capabilities to enable/disable UI features:

```typescript
// Fetch available profiles
const profiles = await fetch('/api/profiles').then(r => r.json())

// Filter profiles for Scanner Mode (data only)
const dataProfiles = profiles.profiles.filter(p => p.data_enabled)

// Filter profiles for Bot PAPER mode
const paperProfiles = profiles.profiles.filter(p => p.paper_enabled)

// Filter profiles for Bot LIVE mode
const liveProfiles = profiles.profiles.filter(p => p.live_enabled)

// Enable LIVE mode button only if live-enabled profile exists
const canUseLiveMode = liveProfiles.length > 0
```

**UI Logic**:
- Show only `data_enabled` profiles in Scanner Mode
- Show only `paper_enabled` profiles when Bot Mode = PAPER
- Show only `live_enabled` profiles when Bot Mode = LIVE
- Disable "Deploy SniperBot" in LIVE mode if no `live_enabled` profiles available

---

## Security Best Practices

### Server-Side Only

✅ **DO**:
- Store API keys in environment variables on server
- Load keys on server startup
- Validate keys on server startup
- Execute all trades server-side
- Expose only profile names and capability flags to frontend

❌ **DON'T**:
- Send API keys to frontend
- Store API keys in frontend localStorage/sessionStorage
- Include keys in API responses
- Allow frontend to specify custom keys
- Log API keys in plaintext

### Key Rotation

If API keys are compromised:
1. Revoke old keys on exchange immediately
2. Generate new keys
3. Update environment variables on server
4. Restart server to reload keys
5. Frontend requires no changes

### Access Control

- Implement user authentication for API access
- Restrict `/api/bot/*` endpoints to authenticated users
- Consider role-based access (e.g., only "bot_operator" role can start bot)
- Rate limit bot operations per user

### Monitoring

- Log all bot executions with timestamps
- Alert on unexpected API key errors
- Monitor exchange API rate limit usage
- Track daily PnL and position exposure

---

## Environment File Template

Create a `.env` file (never commit to git):

```bash
# Binance
BINANCE_API_KEY=
BINANCE_API_SECRET=

# Bybit
BYBIT_API_KEY=
BYBIT_API_SECRET=

# OKX
OKX_API_KEY=
OKX_API_SECRET=
OKX_PASSPHRASE=

# Application
JWT_SECRET=your_jwt_secret_here
DATABASE_URL=postgresql://user:pass@localhost/snipersight
```

Add to `.gitignore`:
```
.env
*.env
.env.*
!.env.example
```

---

## Deployment Checklist

Before deploying SniperBot in LIVE mode:

- [ ] API keys configured in production environment
- [ ] Keys validated against exchange (test authenticated request)
- [ ] IP whitelist configured on exchange (if supported)
- [ ] Withdrawal permissions DISABLED on exchange API keys
- [ ] Environment variables loaded correctly (check logs)
- [ ] Profile capabilities reporting correctly (`GET /api/profiles`)
- [ ] Test paper mode execution first
- [ ] Verify risk limits enforced
- [ ] Monitoring and alerting configured
- [ ] Emergency stop procedure documented
