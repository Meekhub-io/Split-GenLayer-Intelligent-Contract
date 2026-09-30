# Split — Milestone-Gated Intelligent Contract

A revenue/royalty split contract for GenLayer, inspired by thirdweb's
`Split` contract — with a genuine Intelligent Contract mechanism layered
on top: payouts stay locked until a real-world milestone has been
independently verified by validators.

Deterministic percentage math alone doesn't use any of what makes
GenLayer different, so this version adds a **non-deterministic gate**:
the contract owner points it at a webpage and a plain-English criterion
(e.g. "the campaign page confirms the funding goal has been reached").
Each validator independently fetches that page and judges it against the
criterion using GenLayer's equivalence principle. Only once validators
agree does `milestone_reached` flip to `True` — and only then can funds
be distributed.

## Files

- `split.py` — the contract.

## How it works

```
deploy(payees, shares_list, milestone_url, milestone_criteria)
        │
        ▼
   deposit() ──► funds accumulate in the contract, tracked in total_received
        │
        ▼
   check_milestone() ──► validators independently fetch milestone_url
        │                and judge it against milestone_criteria
        │                (equivalence principle consensus)
        ▼
   milestone_reached = True
        │
        ▼
   distribute() / release(payee) ──► funds paid out proportional to shares
```

If `check_milestone()` hasn't been called yet, or validators judged the
criterion unmet, `distribute()` and `release()` both revert with
`"milestone not yet reached"`.

## Requirements

- Node.js 18+ and npm (for the GenLayer CLI)
- Python 3.12+ (for writing/testing contracts locally)

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

## Lint before deploying

Always check this locally before uploading to Studio — most "could not
load contract schema" / deploy errors are caught here first:

```bash
pip install genvm-linter
genvm-lint check split.py
genvm-lint schema split.py
```

## Constructor arguments

```
Split(
    payees: list[str],
    shares_list: list[int],
    milestone_url: str,
    milestone_criteria: str,
)
```

| Arg | Description |
|---|---|
| `payees` | Recipient addresses, e.g. `["0xAaa...", "0xBbb..."]` |
| `shares_list` | Integer weights, same order as `payees`, e.g. `[50, 50]` |
| `milestone_url` | A public webpage validators will check before unlocking payouts |
| `milestone_criteria` | Plain-English description of what "reached" means, e.g. `"the page confirms the funding goal has been hit"` |

Shares don't need to sum to 100 — a payee's cut is `share / total_shares`.
`[1, 1, 2]` gives 25% / 25% / 50%, same as `[25, 25, 50]`.

The deploying account automatically becomes `owner` — the only address
allowed to call `check_milestone()` and `reset_milestone()`.

## Deploy

**GenLayer Studio:** paste the four constructor values into the
"Constructor Inputs" panel as shown above and click **Deploy split.py**.

**CLI:**

```bash
genlayer deploy \
  --contract split.py \
  --args '[
    ["0xPayee1...", "0xPayee2..."],
    [50, 50],
    "https://example.com/campaign-status",
    "the page confirms the funding goal has been reached"
  ]'
```

**Python (`genlayer-test` / `gltest`):**

```python
from gltest import get_contract_factory

factory = get_contract_factory("Split")
contract = factory.deploy(args=[
    ["0xPayee1...", "0xPayee2..."],
    [50, 50],
    "https://example.com/campaign-status",
    "the page confirms the funding goal has been reached",
])
```

**TypeScript (`genlayer-js`):** deploy through your usual `genlayer-js`
client, passing the same four constructor args in order.

## Usage

**1. Fund the split** — call `deposit()` as a payable write transaction:

```python
contract.deposit().transact(value=1_000_000)
```

> Funds must go through `deposit()` to be tracked. A raw transfer
> straight to the contract's address isn't picked up, since GenVM
> contracts don't have an implicit fallback function the way Solidity
> contracts do.

**2. Check the milestone** — owner-only. This is the step where
validators independently fetch `milestone_url` and reach consensus:

```python
contract.check_milestone().transact(account=owner_account)
```

Call `get_milestone_reached()` to confirm it flipped to `True` before
trying to pay out.

**3. Pay out all payees:**

```python
contract.distribute().transact()
```

**4. Or pay out a single payee** (useful if one recipient's transfer is
failing and you don't want it to block the others):

```python
contract.release(args=["0xPayee1..."]).transact()
```

**Re-gating for a second milestone** — owner-only, locks payouts again:

```python
contract.reset_milestone().transact(account=owner_account)
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
| `get_milestone_reached()` | Whether payouts are currently unlocked |

## Testing without hitting a real webpage

`genlayer-test` lets you mock the non-deterministic calls so tests are
deterministic:

```python
from gltest.types import MockedLLMResponse

mock_response: MockedLLMResponse = {
    "eq_principle_prompt_non_comparative": {
        "funding goal": True
    }
}
```

See `genlayer-test`'s docs for wiring mocked validators into a
`transaction_context`.

## Known limitations / things to verify against current docs

- **API names shift.** `gl.nondet.web.render`, `gl.eq_principle.prompt_non_comparative`,
  and the pinned runner hash in the header comment are all current as of
  writing, but GenVM's SDK naming has changed before (e.g.
  `gl.get_webpage` → `gl.nondet.web.render`). Run `genvm-lint check` before
  every deploy, and check [docs.genlayer.com](https://docs.genlayer.com)
  if it fails.
- **Deposits must go through `deposit()`** — see the note above.
- **Fixed payee list.** Payees and shares are set at deploy time; there's
  no method to add, remove, or reweight payees afterward.
- **Single milestone gate.** One `milestone_url` / `milestone_criteria`
  pair per contract. For multiple sequential milestones, either redeploy
  or extend the contract to store a list of milestones with its own
  reached-flag per entry.
- **Trust in the source page.** The milestone check is only as reliable
  as the page you point it at — use a source that's hard to spoof or
  that itself has some authority (an official status page, a public
  ledger, etc.).
