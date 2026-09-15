# Counterexample

**A claim is never proved. It is only left unbroken, and this says by whom, and where it broke.**

Somebody writes a general claim in plain words and puts it on the record with a window.
Anybody else may try to break it by describing one concrete case. Every validator reads
the same two texts and answers one narrow question, twice, in both presentation orders:

> taking the claim exactly as written, and the case exactly as described, does the case
> make the claim false?

The answer is one of three words, and when it is `violates` the validators must also agree
on **which numbered clause of the claim** the case makes false. Agreeing on *where* a claim
breaks is a much stronger thing to agree on than agreeing *that* it broke, and it is what
this contract puts on chain.

The contract never says `true`. A claim that survives says only that nobody broke it here.

## What is in the box

| path | what |
|---|---|
| `contracts/counterexample.py` | the register: claims, clauses, cases, verdicts, the amendment route, `stands` |
| `contracts/fixtures/bond.py` | the consequence: a stake that can only be taken by the account the register says broke the claim |
| `tests/test_pure.py` | 84 tests with a GenLayer stub, including static checks over the parsed source |
| `tools/mutate.py` → `tests/MUTATIONS.md` | 49 defences removed one at a time, each killed by a named test |
| `tests/on_chain/smoke.mjs` | the same story against Studio Next, from a throwaway account |
| `DECISIONS.md` | the boundary, and the decisions that are not obvious from the code |

## The question the validators are asked

Only one, and it is deliberately the narrowest useful one.

- **Not** whether the claim is wise, whether the case is likely, or whether anybody behaved well.
- **Not** anything outside the two texts.
- `violates` only when the case, happening as described, makes the claim false **as written**.
- `holds` when the case can be true while the claim stays true, **including when the claim
  simply does not cover the case**. That clause is what keeps the answer set clean.
- `unclear` when the claim's own wording does not settle it.

The claim is split into numbered clauses **by the contract**, not by the model, so clause 3
means the same thing on every validator and to every later reader. Nothing is truncated: a
claim with more clauses than the index space is refused at the door, because a claim judged
through the first twelve of its sentences is a claim nobody judged, and the rest would still
be stored, covered by `stands`, and paid out on.

Angle brackets are refused in claims and cases as well. They are replaced before the judge
reads them, which keeps the boundary but would turn `under < 500` into `under ( 500`, so the
contract refuses the text and says to write the comparison in words rather than judge a
sentence nobody wrote.

## What crosses consensus

Each validator runs the whole judgement itself; nothing the leader saw is trusted. What must
match, exactly, is the pair the contract stores: **the word and the clause number**.

| stored | agreed on | why |
|---|---|---|
| `verdict` | yes | one of three words from a closed set |
| `clause` | yes | an index into the contract's own numbering, so "where" is agreed too |
| `split` | yes | whether the two readings disagreed, which is why the answer is `unclear` |
| `reason` | n/a | written by the contract from the three agreed values; the judge is never asked for prose |

Both orders in one block: the claim is shown before the case in one run and after it in the
other, with the three words listed the other way round. Read one way it breaks the claim and
read the other way it does not means the **claim's wording** failed, so the stored answer is
`unclear`. An ordering bias becomes a value, never a tolerance.

Every text that reaches the judge is fenced by replacement (`<` → `(`, `>` → `)`) inside an
explicit untrusted-data boundary. Both texts are written by strangers, so both are fenced.
Length is preserved, so a cap applied before the fence still holds after it. Storage keeps
what was actually written.

## Who may do what

| call | who | what it can do |
|---|---|---|
| `post` | anyone | puts a claim on the record; the sender becomes its author |
| `withdraw` | the author, before the first case | takes a claim back while nobody has spent work on it |
| `challenge` | anyone **but the author** | one case, judged once; only `violates` changes the claim |
| `amend` | the author of a **broken** claim | a narrowed successor, admitted only if judged to escape the counterexample |
| `close` | anyone, after the window | freezes an unbroken claim; deterministic, no model |
| `stands`, `survived`, `claim`, … | anyone, free | read |

The author is the one account that may not challenge: an author who can file cases against
themselves can farm a survival count out of cases they knew would fail. That is the cheapest
defence, not a complete one, since nothing stops the same person using a second address. So
the money path checks what the register cannot: the bond refuses to pay a breaker who is the
account the stake was placed for. Withdrawal closes at the **first case**, not the first
breakage, because withdrawing after that erases somebody else's work and, with a bond
attached, their prize.

The same case is never judged twice against the same claim, and neither is the same proposed
amendment: both are keyed by sha256 of the text with case and whitespace normalised. A
genuinely different case is a different question and is welcome; what is closed is
resubmitting the one that just lost until a round comes out the other way.

## The way out is judged too

A refusal that leaves nowhere to go is not a refusal, and a way out that nobody checks is a
laundry. So the author of a broken claim may post a narrowed successor, and the stored
counterexample is put to the new wording by the same validators under the same rule:

- it still breaks the new wording → **refused, at the same clause**, and the refusal is
  written to the record rather than thrown away. Raising would roll the record back and let
  the same wording be tried until a round agreed with it, which is the laundry this route
  exists to close
- it no longer breaks it → the successor is admitted, `amends` pointing at the parent
- the validators cannot agree → refused, rather than admitted on a maybe

The parent keeps its scar forever. A claim's history of being broken and narrowed is the
most useful thing on the register.

## The consequence

`contracts/fixtures/bond.py` is a stake behind one claim. While the claim stands the money is
locked; if somebody breaks it, the stake goes to **the account the register recorded as the
breaker** and to nobody else; if the window closes unbroken, it comes back.

The bond binds three things before any money moves: the register address, the claim id, and
the address the funder independently knows to be the claimant. **A name is a handle, not
authority**: claim ids are first come first served, so if the claim under that name turns out
to have been posted by somebody else, the bond pays nobody and returns the money. A register
that cannot be read refunds too, because a locked bond is worse than an early one.

## Running it

```bash
pip install -r requirements-dev.txt && python -m pytest -q tests/   # 84 tests, no network, under a second
python tools/mutate.py                       # 49 mutants, all must die, writes tests/MUTATIONS.md
genvm-lint check contracts/counterexample.py contracts/fixtures/bond.py
npm ci                                       # genlayer-js 2.0.0-rc.1 and viem 2.56.5, from the lockfile
node tests/on_chain/smoke.mjs                # Studio Next, throwaway account funded from the faucet
```

The on-chain suite deploys a fresh register from a throwaway account, posts a claim, has a
second account miss it, break it, and be refused a re-roll, walks the amendment route through
both outcomes, then deploys the bond twice against the real register and reads what each one
would pay. It prints the addresses it deployed.

## Rules this was built under

Coarse values from a closed set, with the uncertainty inside the value. Both presentation
orders in one block. Every write bound to its sender, tested, with the deliberately open ones
listed with their reason. Provenance on every row. A refusal that leaves a way out, and a way
out that is judged. Fence by replacement, never deletion. Calendar arithmetic in integers,
because floats and `datetime` trap the VM in deterministic mode. And a mutation table, because
a passing count is a claim and a killed mutant is evidence.
