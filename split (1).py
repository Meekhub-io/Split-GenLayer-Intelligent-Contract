# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *


class Split(gl.Contract):
    """
    Milestone-gated revenue/royalty split contract for GenLayer.

    This is a thirdweb-style Split contract (fixed payees, weighted
    shares, pull-safe accounting) extended with a genuine Intelligent
    Contract mechanism: payouts stay locked until a real-world milestone
    has been independently verified by validators.

      - Define a fixed set of payees, each with an integer number of
        "shares" (weights). A payee's cut is share / total_shares.
      - Anyone can send GEN into the contract via deposit().
      - The owner calls check_milestone(). Each validator independently
        fetches `milestone_url` and judges, via GenLayer's equivalence
        principle, whether `milestone_criteria` is satisfied. Only once
        validators reach consensus is the boolean result committed.
      - distribute() / release() only pay out once milestone_reached is
        True. The non-deterministic check materially gates the
        contract's core action — it is not a side feature.

    Accounting uses the same "total received / already released" pattern
    as OpenZeppelin's PaymentSplitter, so it stays correct even if
    distribute() is called multiple times as new funds keep arriving.
    """

    owner: Address
    payees: DynArray[Address]
    shares: TreeMap[Address, u256]
    total_shares: u256
    total_received: u256
    total_released: u256
    released: TreeMap[Address, u256]

    milestone_url: str
    milestone_criteria: str
    milestone_reached: bool

    def __init__(
        self,
        payees: list[str],
        shares_list: list[int],
        milestone_url: str,
        milestone_criteria: str,
    ):
        if len(payees) == 0:
            raise Exception("Split: no payees")
        if len(payees) != len(shares_list):
            raise Exception("Split: payees/shares length mismatch")

        total = u256(0)
        for addr_str, share in zip(payees, shares_list):
            if share <= 0:
                raise Exception("Split: each share must be > 0")

            addr = Address(addr_str)
            if addr in self.shares:
                raise Exception("Split: duplicate payee")

            self.payees.append(addr)
            self.shares[addr] = u256(share)
            self.released[addr] = u256(0)
            total += u256(share)

        self.owner = gl.message.sender_address
        self.total_shares = total
        self.total_received = u256(0)
        self.total_released = u256(0)

        self.milestone_url = milestone_url
        self.milestone_criteria = milestone_criteria
        self.milestone_reached = False

    # --- milestone check (material non-deterministic mechanism) --------

    @gl.public.write
    def check_milestone(self) -> None:
        """
        Have validators independently fetch `milestone_url` and judge,
        via the equivalence principle, whether `milestone_criteria` is
        satisfied. distribute()/release() are gated on the result.
        """
        if gl.message.sender_address != self.owner:
            raise Exception("Split: only owner can check the milestone")

        url = self.milestone_url
        criteria_text = self.milestone_criteria

        def get_input() -> str:
            # Non-deterministic: each validator independently fetches
            # the page — content, timing, and rendering can vary.
            return gl.nondet.web.render(url, mode="text")

        answer = gl.eq_principle.prompt_non_comparative(
            get_input,
            task=(
                "Based on the page content provided, determine whether "
                f"the following milestone has been reached: {criteria_text}. "
                "Respond with exactly one word: True or False."
            ),
            criteria="""
            The response must be exactly one word — either "True" or
            "False" — and must correctly reflect, based on the page
            content, whether the stated milestone has been reached.
            """,
        )

        self.milestone_reached = str(answer).strip().lower().startswith("true")

    @gl.public.write
    def reset_milestone(self) -> None:
        """Owner-only: re-lock payouts, e.g. before checking a new milestone."""
        if gl.message.sender_address != self.owner:
            raise Exception("Split: only owner can reset the milestone")
        self.milestone_reached = False

    # --- funding ---------------------------------------------------------

    @gl.public.write.payable
    def deposit(self) -> None:
        """Send GEN here to have it split among the payees."""
        self.total_received += u256(gl.message.value)

    # --- distribution ------------------------------------------------------

    @gl.public.write
    def distribute(self) -> None:
        """Pay every payee their currently owed share, once the milestone has been reached."""
        if not self.milestone_reached:
            raise Exception("Split: milestone not yet reached, call check_milestone() first")
        for payee in self.payees:
            self._release(payee)

    @gl.public.write
    def release(self, payee: str) -> None:
        """Pay a single payee their currently owed share, once the milestone has been reached."""
        if not self.milestone_reached:
            raise Exception("Split: milestone not yet reached, call check_milestone() first")
        self._release(Address(payee))

    def _release(self, payee: Address) -> None:
        share = self.shares.get(payee)
        if share is None or share == 0:
            raise Exception("Split: account has no shares")

        already_released = self.released[payee]
        owed = (self.total_received * share) // self.total_shares - already_released

        if owed == 0:
            return

        self.released[payee] = already_released + owed
        self.total_released += owed

        gl.get_contract_at(payee).emit_transfer(value=int(owed))

    # --- views -------------------------------------------------------------

    @gl.public.view
    def get_payees(self) -> list[str]:
        return [str(p) for p in self.payees]

    @gl.public.view
    def get_shares(self, payee: str) -> int:
        return int(self.shares.get(Address(payee), u256(0)))

    @gl.public.view
    def get_released(self, payee: str) -> int:
        return int(self.released.get(Address(payee), u256(0)))

    @gl.public.view
    def get_total_shares(self) -> int:
        return int(self.total_shares)

    @gl.public.view
    def get_total_received(self) -> int:
        return int(self.total_received)

    @gl.public.view
    def get_total_released(self) -> int:
        return int(self.total_released)

    @gl.public.view
    def get_milestone_reached(self) -> bool:
        return self.milestone_reached
