# Split — GenLayer Intelligent Contract

A revenue/royalty split contract for GenLayer, equivalent in behavior to
thirdweb's `Split` contract on EVM chains.

Define a fixed set of payees, each with an integer number of **shares**
(weights). Anyone can send GEN into the contract, and calling `distribute()`
pays every payee their proportional cut. Because this logic is fully
deterministic math, it runs as an ordinary write transaction — no LLM or
web-consensus overhead.

Accounting follows the same "total received / already released" pattern as
OpenZeppelin's `PaymentSplitter`, so repeated `distribute()` calls stay fair
even as more funds arrive between calls.

## Files

- `split.py` — the contract.

## Requirements

- Node.js 18+ and npm (for the GenLayer CLI)
- Python 3.12+ (for writing/testing contracts)

## Setup

```bash
npm install -g genlayer

# Use the hosted Studio network...
genlayer network set studionet

# ...or run a local validator network instead
genlayer init
genlayer up
```

Local network RPC defaults to `http://localhost:4000/api`.

## Lint (optional)

```bash
genvm-lint check split.py
```

## Constructor arguments

```
Split(payees: list[str], shares_list: list[int])
```

| Arg | Description |
|---|---|
| `payees` | List of recipient addresses, e.g. `["0xAaa...", "0xBbb..."]` |
| `shares_list` | List of integer weights, same order as `payees`, e.g. `[50, 50]` |

Shares don't need to sum to 100 — a payee's cut is `share / total_shares`.
`[1, 1, 2]` gives 25% / 25% / 50%, same as `[25, 25, 50]`.

## Deploy

**CLI:**

```bash
genlayer deploy \
  --contract split.py \
  --args '[["0xPayee1...", "0xPayee2..."], [50, 50]]'
```

**Python (`genlayer-test` / `gltest`):**

```python
from gltest import get_contract_factory, get_default_account

factory = get_contract_factory("Split")
contract = factory.deploy(args=[
    ["0xPayee1...", "0xPayee2..."],
    [50, 50],
])
```

**TypeScript (`genlayer-js`):** deploy through your usual `genlayer-js`
client, passing the same two constructor args.

## Usage

**Fund the split** — call `deposit()` as a payable write transaction, with
`value` set to the amount of GEN you're sending:

```python
contract.deposit().transact(value=1_000_000)
```

> Funds must be sent through `deposit()` to be tracked. A raw transfer
> straight to the contract's address won't be picked up, since GenVM
> contracts don't have an implicit fallback function the way Solidity
> contracts do.

**Pay out all payees:**

```python
contract.distribute().transact()
```

**Pay out a single payee** (useful if one recipient's transfer is failing
and you don't want it to block the others):

```python
contract.release(args=["0xPayee1..."]).transact()
```

## Read methods (views, free)

| Method | Returns |
|---|---|
| `get_payees()` | List of all payee addresses |
| `get_shares(payee)` | That payee's share weight |
| `get_released(payee)` | Total already paid to that payee |
| `get_total_shares()` | Sum of all share weights |
| `get_total_received()` | Total GEN ever deposited |
| `get_total_released()` | Total GEN ever paid out |

## Known limitations

- Deposits must go through `deposit()` — see note above.
- Payee list and shares are fixed at deploy time; this contract has no
  functions to add, remove, or reweight payees after deployment. Add an
  owner-gated `update_shares()` method if you need that.
- `emit_transfer` syntax may evolve with the GenLayer SDK — check
  [docs.genlayer.com](https://docs.genlayer.com) for the current API before
  deploying to a live network.
