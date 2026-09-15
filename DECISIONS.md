# Decisions

The things a reader would otherwise have to guess at, and what is measured rather than assumed.

## The boundary

| owner | what it owns |
|---|---|
| a caller | the words of a claim and the words of a case; nothing else |
| this contract | the clause numbering, the prompt, both presentation orders, the closed answer set, the dedupe key, the clocks, and every state change |
| the validators | one judgement, run independently, on texts they can both read |
| a consumer | the money, bound to an address it knew before the register was consulted |

Nothing about the world is looked up. The only question is whether two texts are consistent
with each other, which is exactly the kind of question a group of readers can agree on and a
deterministic checker cannot answer at all.

## Why agree on a clause number, not only on a word

A verdict of `violates` alone leaves the reason unpinned: two validators can both say a claim
broke while privately disagreeing about what it said. Making them name the clause turns that
private disagreement into a public one, and the contract stores `unclear` instead of a
confident wrong answer.

The numbering is built in code by `_clauses`, from the claim as written, so the index space is
the contract's. If the model chose the numbering, "clause 3" would mean whatever each node
felt like, and agreement on it would be worth nothing.

## Why `holds` covers "the claim does not cover this"

Without that sentence in the prompt, a case the claim says nothing about splits validators
between `holds` and `unclear` forever. With it, the three words partition the space cleanly:
the case contradicts the claim, the case can coexist with the claim, or the claim's wording
does not settle it. Only the third is a fact about the *claim*, and it is the one that does
not count as a survival.

## Why an `unclear` round is not a survival

A survival count is the only positive number this contract produces, so it has to mean one
thing. `unclear` says the claim's own wording failed to settle a case; treating that as a
point in the claim's favour would reward vague claims, which are exactly the claims that
survive by being unfalsifiable.

## Why the judge is never asked for prose

Two validators write different sentences about the same verdict, so a stored sentence would be
one node's words kept forever under the authority of everybody's agreement, and a hostile
leader would have a free-text channel into permanent storage. So the judge returns only a word,
a clause number and whether its two readings split, all three of which every validator derives
for itself and compares exactly. The sentence a reader sees is written by `_why` from those
three values. Nothing unagreed is stored, and nothing unagreed is returned.

The thing a refused party actually wants is in the row already: `claim()` returns the text of
the clause the case made false.

## Why the author may not challenge, and why withdrawal closes early

Both are the same hole seen twice: a claimant who can also be the challenger controls the
number that makes their claim look tested. So the author is the one excluded account, and a
claim can be pulled back only while nobody has spent work on it. After the first case, the
claim is committed, whatever it costs its author.

**This does not close the hole, and the documents should not pretend it does.** One excluded
address is no defence against a second address, which anybody can make for nothing. What it
buys is that the obvious version costs an extra account and an extra fee. Where it matters,
which is where money is, the bond checks the thing the register cannot: a stake is never paid
to a breaker who is the account the stake was placed for.

## Why the same case cannot be tried twice

Judging is not free and models are not deterministic. Without the digest, a challenger could
resubmit a losing case until a round went their way, which would turn a consensus verdict into
a lottery with a fee. The digest normalises case and whitespace, so a reshaped copy is the same
case. A materially different case is a different question and is allowed: it costs another fee
and another round, and the register is the better for it.

The same key covers amendments, and it is why a refused amendment is **recorded rather than
raised**. A raise rolls the whole transaction back, including the record of the refusal, and a
route out whose failures leave no trace is a route somebody can walk until it opens.

## Why the amendment is judged rather than granted

A route out of a refusal is the difference between a register and a graveyard. But a route
nobody checks is a laundry: reword the claim, lose the counterexample, keep the reputation. So
the stored counterexample is put to the new wording by the same validators under the same rule,
and the amendment is admitted only if they agree it escapes. `unclear` refuses, because an
amendment admitted on a maybe is a claim nobody tested.

## Why the bond is a separate contract

The register answers a question; the bond obeys the answer. Keeping them apart means the
register can be read by anything, and a reader of the bond can see the whole settlement rule on
one page. It also keeps the register free of value, so no path through a judgement can move
money by accident.

## Measured on GenLayer Studio Next (chain 61997, consensus v0.6), 16 September 2026

- The whole story runs: a claim posted, a case that misses it, the same case refused a second
  hearing, a counterexample that breaks it, both amendment outcomes, the refused amendment
  refused a re-roll, and the bond deployed twice against the real register and read across
  contracts. **18 of 18** checks from throwaway accounts.
- Every round settled with **3 validators agreeing**; the amendment round had 1 disagreeing,
  which is the two-order rule doing its job on a genuinely borderline rewording.
- Deterministic refusals land on chain with their reason and cost a fee quote of about 0.1 GEN
  from the default preset, most of it refunded. A call the contract refuses cannot be simulated,
  so `estimateTransactionFeesForWrite` fails and the default quote is used; the refusal itself
  is unaffected. Judged writes quote about 0.0006 GEN.
- `genvm-lint check` passes its three checks on both files. Its SDK validation step cannot load
  the v0.6 runner (`5jycge4q…`) in version 0.11.0; that is the linter, not the contract, and the
  contract deploys and runs.

## Not verified

- Value transfers emitted by a contract are **recorded but not executed** on Studio Next at the
  time of writing. The bond is deployed on chain and its decisions are read there through
  `would_pay`, including the refusal to pay a bond tied to the wrong claimant, but no coin has
  moved on this network. Everything about `settle` past the decision is exercised only in the
  offline suite, against a stub. The settlement rule is small and readable for exactly that
  reason.
- Nothing here has been run on a production GenLayer network.
