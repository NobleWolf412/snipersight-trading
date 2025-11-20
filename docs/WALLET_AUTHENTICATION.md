# Crypto Wallet Authentication

## Overview

SniperSight now supports secure wallet-based authentication using Web3 wallets like MetaMask. Users can connect their crypto wallets to authenticate and access trading features without traditional username/password credentials.

## Security Features

### 🔒 What We Store
- **Public wallet address** - Used for identification only
- **Chain ID** - To track which network the user is connected to
- **Connection timestamp** - For session management

### ✅ What We DON'T Store
- **Private keys** - Never leave the user's wallet
- **Seed phrases** - Never requested or accessed
- **Transaction signatures** - Only used when user explicitly approves

### 🛡️ Security Principles

1. **Non-custodial**: Private keys remain in the user's wallet at all times
2. **Read-only authentication**: We only request the public address
3. **User approval required**: All actions require explicit user confirmation
4. **Network awareness**: Automatically detects network changes
5. **Session persistence**: Wallet connection persists between page reloads using secure KV storage

## Supported Wallets

### ✅ Currently Supported
- **MetaMask** - Full support for browser extension and mobile app

### 🚧 Coming Soon
- **WalletConnect** - Universal wallet connection protocol
- **Coinbase Wallet** - Native Coinbase wallet integration

## Supported Networks

The wallet system supports the following blockchain networks:

| Network | Chain ID | Status |
|---------|----------|--------|
| Ethereum Mainnet | 1 | ✅ Supported |
| BNB Smart Chain | 56 | ✅ Supported |
| Polygon | 137 | ✅ Supported |
| Arbitrum One | 42161 | ✅ Supported |
| Optimism | 10 | ✅ Supported |
| Base | 8453 | ✅ Supported |

## Usage Guide

### For Users

1. **Connect Wallet**
   - Click the "Connect Wallet" button in the navigation bar
   - Select your wallet provider (currently MetaMask)
   - Approve the connection request in your wallet
   - Your wallet address will appear in the navigation bar

2. **Switch Networks**
   - Click on your connected wallet address
   - Select the desired network from the list
   - Approve the network switch in your wallet

3. **Disconnect**
   - Click on your connected wallet address
   - Click the "Disconnect Wallet" button
   - Your session will be cleared

### For Developers

#### Using the Wallet Context

```tsx
import { useWallet } from '@/context/WalletContext';

function MyComponent() {
  const { wallet, isConnected, connect, disconnect } = useWallet();

  if (isConnected) {
    return <div>Connected: {wallet?.address}</div>;
  }

  return <button onClick={() => connect('metamask')}>Connect</button>;
}
```

#### Gating Features Behind Wallet Authentication

```tsx
import { WalletGate } from '@/components/WalletGate';

function TradingFeature() {
  return (
    <WalletGate message="Connect your wallet to access trading">
      <div>Protected trading content</div>
    </WalletGate>
  );
}
```

#### Checking Wallet Connection in Hooks

```tsx
import { useRequireWallet } from '@/hooks/use-require-wallet';

function MyComponent() {
  const isConnected = useRequireWallet('Please connect wallet to continue');
  
  if (!isConnected) return null;
  
  return <div>Wallet-protected content</div>;
}
```

## API Reference

### WalletContext

#### State

```typescript
interface WalletConnection {
  address: string;              // User's wallet address
  chainId: number;             // Connected network chain ID
  connectedAt: number;         // Connection timestamp
  provider: 'metamask' | 'walletconnect' | 'coinbase' | null;
}

interface WalletContextType {
  wallet: WalletConnection | null;
  isConnected: boolean;
  isConnecting: boolean;
  connect: (provider) => Promise<void>;
  disconnect: () => Promise<void>;
  switchChain: (chainId: number) => Promise<void>;
}
```

#### Methods

**`connect(provider: 'metamask' | 'walletconnect' | 'coinbase')`**
- Initiates wallet connection
- Throws error if wallet not installed
- Returns Promise that resolves when connected

**`disconnect()`**
- Clears wallet connection
- Removes persisted session data
- Returns Promise

**`switchChain(chainId: number)`**
- Requests network switch in wallet
- Updates stored chain ID
- Throws error if network not added to wallet

### Components

**`<WalletConnect />`**
- Drop-in button component for wallet connection
- Shows wallet address when connected
- Displays network switcher in modal
- Handles all connection states

**`<WalletGate>`**
- Wrapper component for protected content
- Shows connection prompt if not authenticated
- Customizable fallback message

Props:
```typescript
interface WalletGateProps {
  children: ReactNode;
  message?: string;              // Custom message
  showFallback?: boolean;        // Show UI or just hide content
}
```

## Event Handling

The wallet system automatically handles:

- **Account changes**: Updates stored address when user switches accounts
- **Network changes**: Updates chain ID when user switches networks
- **Disconnection**: Clears session when wallet disconnects
- **Page reload**: Maintains connection state across refreshes

## Best Practices

### Security

1. **Never request private keys** - The wallet handles all signing
2. **Validate addresses** - Always verify wallet addresses on the backend
3. **Use HTTPS** - Wallet connections require secure context
4. **Inform users** - Clearly communicate what data you access

### User Experience

1. **Clear messaging** - Explain why wallet connection is needed
2. **Handle errors gracefully** - Show helpful messages for common issues
3. **Support disconnection** - Always allow users to disconnect easily
4. **Persist sessions** - Keep users logged in between visits (using KV storage)

### Development

1. **Test with multiple wallets** - Each wallet has quirks
2. **Handle network mismatches** - Gracefully prompt network switches
3. **Monitor connection state** - Use context to avoid stale data
4. **Implement fallbacks** - Handle wallet not installed scenarios

## Troubleshooting

### Common Issues

**"MetaMask not installed"**
- User needs to install MetaMask browser extension
- Direct them to metamask.io

**Network switch fails**
- User may need to manually add the network to their wallet
- Provide network configuration details

**Connection rejected**
- User declined connection in wallet
- Prompt them to try again

**Stale connection**
- Clear browser cache and reconnect
- Or disconnect and reconnect wallet

## Future Enhancements

- [ ] Sign-in with Ethereum (SIWE) for enhanced security
- [ ] Multi-wallet support (connect multiple wallets)
- [ ] Hardware wallet support (Ledger, Trezor)
- [ ] Mobile wallet deep linking
- [ ] ENS name resolution and display
- [ ] Wallet transaction history integration
- [ ] Gas estimation for operations

## Learn More

- [MetaMask Documentation](https://docs.metamask.io/)
- [WalletConnect Protocol](https://docs.walletconnect.com/)
- [EIP-1193: Ethereum Provider API](https://eips.ethereum.org/EIPS/eip-1193)
- [Web3 Security Best Practices](https://consensys.github.io/smart-contract-best-practices/)
