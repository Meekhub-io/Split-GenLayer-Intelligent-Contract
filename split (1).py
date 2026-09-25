# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *


class Split(gl.Contract):
    """
    Revenue/royalty split contract, equivalent in behavior to thirdweb's
    Split contract:

      - Define a fixed set of payees, each with an integer number of
        "shares" (weights). They don't need to sum to 100 — a payee's
        cut is share / total_shares.
      - Anyone can send GEN into the contract via deposit().
      - Calling distribute() pays every payee their owed amount at once.
      - Calling release(payee) pays just one payee (useful if one
        recipient's transfer is failing and you don't want to block
        the others).

    Accounting uses the same "total received / already released" pattern
    as OpenZeppelin's PaymentSplitter, so it stays correct even if
    distribute() is called multiple times as new funds keep arriving.
    """

    payees: DynArray[Address]
    shares: TreeMap[Address, u256]
    total_shares: u256
    total_received: u256
    total_released: u256
    released: TreeMap[Address, u256]

    def __init__(self, payees: list[str], shares_list: list[int]):
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

        self.total_shares = total
        self.total_received = u256(0)
        self.total_released = u256(0)

    # --- funding -------------------------------------------------------

    @gl.public.write.payable
    def deposit(self) -> None:
        """Send GEN here to have it split among the payees."""
        self.total_received += u256(gl.message.value)

    # --- distribution ----------------------------------------------------

    @gl.public.write
    def distribute(self) -> None:
        """Pay every payee their currently owed share."""
        for payee in self.payees:
            self._release(payee)

    @gl.public.write
    def release(self, payee: str) -> None:
        """Pay a single payee their currently owed share."""
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

    # --- views -----------------------------------------------------------

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
