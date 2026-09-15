# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

"""Bond: money that can only be taken by breaking the claim it stands behind.

This is the consequence, and it is the reason the register's verdict is worth
reaching consensus about. A contract that stores a verdict and stops has
produced an opinion; this one reads that verdict and moves money, and there is
no path through it that pays somebody who did not break the claim.

Somebody stakes money behind a claim they posted on a Counterexample register.
While the claim stands, the stake is locked. If a challenger breaks it, the
register records who did it, and the stake goes to that account and to nobody
else. If the window closes with the claim unbroken, the stake comes back.

The bond is tied at construction to the register address, the claim id, and
the address the funder independently knows to be the claimant. A claim id is
first come first served on the register, so the id alone is never authority:
if the claim under that name turns out to have been posted by somebody else,
this bond pays nobody and returns the money. A register that cannot be read
refunds as well, because a locked bond is worse than an early one.

It is a fixture: small on purpose, and here to be read.
"""

import json
import typing

import genlayer as gl


ZERO = "0x0000000000000000000000000000000000000000"

PAY_BREAKER = "breaker"
PAY_FUNDER = "funder"
WAIT = "wait"


def _fail(message: str) -> typing.NoReturn:
    raise gl.vm.UserError("[EXPECTED] " + message)


class Bond(gl.contract.Contract):
    register: gl.Address     # the Counterexample register holding the claim
    claim_id: str            # the claim this money stands behind
    claimant: gl.Address     # who the funder knows the author to be, bound before any money moved
    funder: gl.Address       # who put the money in, and who gets it back if the claim stands
    pool: gl.u256
    settled: bool
    outcome_json: str

    def __init__(self, register: str, claim_id: str, claimant: str) -> None:
        self.register = gl.Address(register)
        cleaned = str(claim_id).strip().lower()
        if not cleaned:
            _fail("a bond names the claim it stands behind")
        self.claim_id = cleaned
        self.claimant = gl.Address(str(claimant).strip())
        self.funder = gl.Address(ZERO)
        self.pool = gl.u256(0)
        self.settled = False
        self.outcome_json = "{}"

    @gl.public.write.payable
    def fund(self) -> str:
        """Put money behind the claim. One funder, and only while it is still at risk.

        This never raises. Value sent with a refused payable call is not
        returned by the chain, it is simply stranded in the contract, so a call
        that cannot be honoured is accepted, refunded explicitly, and told why.
        A refusal that costs the caller their money is not a refusal.

        Two refusals matter. A second account may not add to somebody else's
        bond, because only one address can be refunded and the second would be
        making a gift it never agreed to. And nobody may add to a bond whose
        claim has already been decided, because that money would have been
        staked on a question with a known answer.
        """
        value = gl.message.value
        if self.settled:
            if value > gl.u256(0):
                self._pay(gl.message.sender_address, value)
            return json.dumps({"ok": False, "reason": "this bond is already settled; your funds were returned"})
        if value == gl.u256(0):
            return json.dumps({"ok": False, "reason": "send an amount greater than zero"})
        if self.funder.as_hex.lower() != ZERO and gl.message.sender_address != self.funder:
            self._pay(gl.message.sender_address, value)
            return json.dumps({"ok": False, "reason": "this bond already has a funder, and only "
                                                      "one address can be refunded; your funds were returned"})
        decision = self._decision()
        if decision["do"] != WAIT:
            self._pay(gl.message.sender_address, value)
            return json.dumps({"ok": False, "reason": "this claim is already decided ("
                                                      + str(decision.get("status", "")) + "); your funds were returned"})
        if self.funder.as_hex.lower() == ZERO:
            self.funder = gl.message.sender_address
        self.pool = gl.u256(int(self.pool) + int(value))
        return json.dumps({"ok": True, "pool": str(int(self.pool)), "funder": self.funder.as_hex})

    # ------------------------------------------------------------- the decision

    def _decision(self) -> dict:
        """What the register already decided, as pay the breaker, refund, or wait.

        Read synchronously through ordinary views: no model runs here, no
        validator is asked anything, and two people running it get the same
        answer. The judgement was made and agreed elsewhere; this obeys it once.
        """
        try:
            register = gl.contract.get_at(self.register)
            row = json.loads(str(register.view().claim(str(self.claim_id))))
        except Exception:
            return {"do": PAY_FUNDER, "why": "the register could not be read", "status": ""}
        if not isinstance(row, dict) or "error" in row:
            return {"do": PAY_FUNDER, "why": "the register holds no claim under that name", "status": ""}
        author = str(row.get("author", ZERO)).lower()
        if author != self.claimant.as_hex.lower():
            return {"do": PAY_FUNDER, "status": str(row.get("status", "")),
                    "why": "the claim under that name was posted by " + author
                           + ", not by the account this bond was tied to"}
        status = str(row.get("status", ""))
        if status == "broken":
            broken = row.get("broken") or {}
            who = str(broken.get("by", ZERO))
            if who.lower() == ZERO:
                return {"do": PAY_FUNDER, "status": status,
                        "why": "the claim is broken but the register names nobody who broke it"}
            if who.lower() == self.claimant.as_hex.lower():
                # The account that staked the money is the account that broke
                # the claim. Whatever happened there, it is not a prize.
                return {"do": PAY_FUNDER, "status": status,
                        "why": "the claim was broken by the account this bond was staked for"}
            return {"do": PAY_BREAKER, "status": status, "to": who,
                    "why": "clause " + str(broken.get("clause", 0)) + " was made false"}
        if status == "stood":
            return {"do": PAY_FUNDER, "status": status,
                    "why": "the window closed with the claim unbroken"}
        if status == "withdrawn":
            return {"do": PAY_FUNDER, "status": status, "why": "the claim was withdrawn before any work"}
        return {"do": WAIT, "status": status,
                "why": "the claim is still standing; close it on the register when its window ends"}

    @gl.public.write
    def settle(self) -> str:
        """Pay the account the register says broke the claim, or return the stake."""
        if self.settled:
            _fail("this bond has already been settled")
        if self.pool == gl.u256(0):
            _fail("there is nothing in this bond")
        decision = self._decision()
        if decision["do"] == WAIT:
            _fail(str(decision["why"]) + ", so there is nothing to settle yet")
        amount = self.pool
        if decision["do"] == PAY_BREAKER:
            payee = gl.Address(str(decision["to"]))
        else:
            payee = self.funder
        # Latch before paying: the state this contract will be read in next is
        # written before anything leaves it, whatever the chain layer does with
        # the message afterwards.
        self.pool = gl.u256(0)
        self.settled = True
        self._pay(payee, amount)
        outcome = {"paid": str(decision["do"]), "to": payee.as_hex, "amount": str(int(amount)),
                   "status": str(decision.get("status", "")), "why": str(decision["why"])}
        self.outcome_json = json.dumps(outcome)
        return json.dumps({"ok": True, **outcome})

    def _pay(self, address: typing.Any, amount: typing.Any) -> None:
        """Send value to an account. Paying a wallet is a message to the chain layer."""
        gl.contract.get_at(gl.Address(str(address))).emit_transfer(value=amount)

    # -------------------------------------------------------------------- views

    @gl.public.view
    def would_pay(self) -> str:
        """What `settle` will do, readable for free before anybody signs."""
        decision = self._decision()
        if decision["do"] == WAIT:
            return "nobody: " + str(decision["why"])
        if decision["do"] == PAY_BREAKER:
            return "breaker " + str(decision.get("to", ""))
        return "funder: " + str(decision["why"])

    @gl.public.view
    def status(self) -> str:
        return json.dumps({
            "register": self.register.as_hex,
            "claim": str(self.claim_id),
            "claimant": self.claimant.as_hex,
            "funder": self.funder.as_hex if self.funder.as_hex.lower() != ZERO else None,
            "pool": str(int(self.pool)),
            "settled": bool(self.settled),
            "outcome": json.loads(str(self.outcome_json)),
        })
