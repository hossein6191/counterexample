"""Mutate every defence and record which test killed each mutant.

A passing count is a claim. This table is evidence: each row names a change
that removes or inverts one defence in contracts/counterexample.py or
contracts/fixtures/bond.py, and the test that failed because of it. If any
mutant survives, no table is written and the exit code is 1: a defence with no
test that can fail is a defence that can be deleted by accident.

    python tools/mutate.py            # writes tests/MUTATIONS.md
"""
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "contracts" / "counterexample.py").read_text(encoding="utf-8")
FSRC = (ROOT / "contracts" / "fixtures" / "bond.py").read_text(encoding="utf-8")
PYTEST = [sys.executable, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider",
          str(ROOT / "tests" / "test_pure.py")]

# (name, before, after) against the register, or (name, before, after, "bond").
MUTATIONS = [
    ("the fence does nothing",
     'return str(raw).replace("<", "(").replace(">", ")")', 'return str(raw)'),
    ("the fence deletes instead of replacing",
     'return str(raw).replace("<", "(").replace(">", ")")',
     'return str(raw).replace("<", "").replace(">", "")'),
    ("the claim reaches the judge unfenced",
     'return "\\n".join(str(i + 1) + ". " + _fence(c) for i, c in enumerate(clauses))',
     'return "\\n".join(str(i + 1) + ". " + str(c) for i, c in enumerate(clauses))'),
    ("the case reaches the judge unfenced",
     'case_block = "<<<CASE>>>\\n" + _fence(case_text)[:MAX_CASE_CHARS] + "\\n<<<END CASE>>>"',
     'case_block = "<<<CASE>>>\\n" + str(case_text)[:MAX_CASE_CHARS] + "\\n<<<END CASE>>>"'),
    ("a claim longer than the index space is judged through a sample of itself",
     '        if len(clauses) > MAX_CLAUSES:\n            _fail("a claim is at most " + str(MAX_CLAUSES) + " clauses and this one is "\n                  + str(len(clauses)) + "; every clause is judged, so none may be left out")\n', ''),
    ("text the fence would rewrite is judged anyway",
     '        if "<" in str(text) or ">" in str(text):\n            _fail(what + " cannot contain < or >, because they are replaced before the judge "\n                  "reads it; write the comparison in words")\n', ''),
    ("a day its month does not have is a date",
     '    if day > lengths[month - 1]:\n        return -1\n', ''),
    ("an id may be written in look-alike characters",
     '        allowed = "abcdefghijklmnopqrstuvwxyz0123456789-_"', '        allowed = "abcdefghijklmnopqrstuvwxyz0123456789-_"\n        value = "".join(c if c in allowed else "x" for c in value)'),
    ("the validators need not agree that the two readings split",
     '                    and str(theirs.get("split", "")) == str(mine["split"]))', ')'),
    ("a validator whose own judge misbehaves escapes instead of disagreeing",
     '            try:\n                mine = leader_fn()\n            except Exception:', '            if True:\n                mine = leader_fn()\n            if False:'),
    ("a refused amendment is thrown away instead of recorded",
     '        attempt_id = self._record(parent_id, "amendment", wording, verdict, clause, reason, now)\n        if verdict != HOLDS:',
     '        attempt_id = ""\n        if verdict != HOLDS:'),
    ("the same wording may be put to the counterexample again",
     '        if parent_id + "|" + _digest(wording) in self.tried:', '        if False:'),
    ("the second presentation order lists the words the same way",
     '    if reverse:\n        words.reverse()\n', ''),
    ("the second presentation order shows the same material first",
     '    if reverse:\n        parts[2], parts[3] = parts[3], parts[2]\n', ''),
    ("two readings that disagree are resolved in favour of the first",
     '            if a_verdict != b_verdict or a_clause != b_clause:', '            if False:'),
    ("the validators need not agree which clause broke",
     '                    and str(theirs.get("clause", "")) == str(mine["clause"])\n', '\n'),
    ("the judge may answer outside the set",
     '    if verdict not in VERDICTS:\n        raise gl.vm.UserError(ERROR_LLM + " the judge answered outside the set: " + verdict[:40])\n', ''),
    ("the judge may point at a clause the claim does not have",
     '        if clause < 1 or clause > clause_count:\n            raise gl.vm.UserError(\n                ERROR_LLM + " the judge pointed at clause " + str(clause)\n                + ", and this claim has " + str(clause_count)\n            )\n', ''),
    ("the stored sentence comes from the judge instead of the contract",
     '        reason = _why(verdict, clause, split)\n        attempt_id = self._record(claim_id, "case", case, verdict, clause, reason, now)',
     '        reason = str(clauses)[:MAX_REASON_CHARS]\n        attempt_id = self._record(claim_id, "case", case, verdict, clause, reason, now)'),
    ("an id may be anything",
     '        if not value or len(value) > MAX_ID_CHARS or not all(c in allowed for c in value):',
     '        if False:'),
    ("a claim with nothing to point at is accepted",
     '        if not clauses:\n            _fail("a claim needs at least one readable clause")\n', ''),
    ("the window has no bounds",
     '        if days < MIN_WINDOW_DAYS or days > MAX_WINDOW_DAYS:', '        if False:'),
    ("the author may challenge their own claim",
     '        if gl.message.sender_address == claim.author:\n            _fail("the author of a claim cannot challenge it")\n', ''),
    ("the same case may be judged again",
     '        if key in self.tried:', '        if False:'),
    ("a closed window still takes cases",
     '        if _window_closed(str(claim.posted_at), now, int(claim.window_days)):', '        if False:'),
    ("a case that breaks the claim leaves it standing",
     '        if verdict == VIOLATES:\n            claim.status = STATUS_BROKEN', '        if False:\n            claim.status = STATUS_BROKEN'),
    ("an unclear round counts as a survival",
     '        elif verdict == HOLDS:', '        elif verdict != VIOLATES:'),
    ("a claim can be withdrawn after somebody has worked on it",
     '        if int(claim.attempts) > 0:', '        if False:'),
    ("a stranger may withdraw a claim",
     '        claim = self._mine(claim_id)\n        if claim.status != STATUS_STANDING:\n            _fail("only a standing claim can be withdrawn; this one is " + str(claim.status))',
     '        claim_id = self._clean_id(claim_id)\n        claim = self.claims[claim_id]\n        if claim.status != STATUS_STANDING:\n            _fail("only a standing claim can be withdrawn; this one is " + str(claim.status))'),
    ("only the author may close a window, so a bond only they can unlock",
     '        claim = self.claims[claim_id]\n        if claim.status != STATUS_STANDING:\n            _fail("only a standing claim is closed; this one is " + str(claim.status))',
     '        claim = self.claims[claim_id]\n        if gl.message.sender_address != claim.author:\n            _fail("only the author closes")\n        if claim.status != STATUS_STANDING:\n            _fail("only a standing claim is closed; this one is " + str(claim.status))'),
    ("a window closes before its time",
     '        if not _window_closed(str(claim.posted_at), now, int(claim.window_days)):', '        if True:\n            pass\n        if False:'),
    ("an unreadable clock closes the window",
     '    if not posted_at or not now:\n        return False\n', '    if not posted_at or not now:\n        return True\n'),
    ("a clock that went backwards closes the window",
     '    return days >= window_days', '    return days >= window_days or days < 0'),
    ("an amendment is admitted without being judged",
     '        verdict, clause, split = self._judge(clauses, case)\n        reason = _why(verdict, clause, split)\n        attempt_id = self._record(parent_id, "amendment", wording, verdict, clause, reason, now)',
     '        verdict, clause, split = (HOLDS, 0, False)\n        reason = _why(verdict, clause, split)\n        attempt_id = self._record(parent_id, "amendment", wording, verdict, clause, reason, now)'),
    ("an amendment nobody could agree about is admitted",
     '        if verdict != HOLDS:\n            # Refused, and recorded as refused. Raising here would roll the\n            # record back and let the same wording be tried until a round\n            # agreed with it, which is the laundry this route exists to close.\n            return json.dumps({"ok": False, "attempt": attempt_id, "verdict": verdict,\n                               "clause": clause, "reason": reason,\n                               "why": "the counterexample still breaks this wording"\n                                      if verdict == VIOLATES\n                                      else "the validators could not agree that it escapes"})\n',
     '        if verdict == VIOLATES:\n            return json.dumps({"ok": False, "attempt": attempt_id, "verdict": verdict,\n                               "clause": clause, "reason": reason, "why": "still breaks"})\n'),
    ("a stranger may amend somebody else's claim",
     '        if gl.message.sender_address != parent.author:\n            _fail("only the author of " + parent_id + " may amend it")\n', ''),
    ("an unbroken claim may be amended",
     '        if parent.status != STATUS_BROKEN:\n            _fail("only a broken claim is amended; " + parent_id + " is " + str(parent.status))\n', ''),
    ("bond: a claim posted by a stranger under that name is paid",
     '        if author != self.claimant.as_hex.lower():', '        if False:', "bond"),
    ("bond: the funder is paid instead of the account that broke the claim",
     '            payee = gl.Address(str(decision["to"]))', '            payee = self.funder', "bond"),
    ("bond: a register that cannot be read locks the stake",
     '        except Exception:\n            return {"do": PAY_FUNDER, "why": "the register could not be read", "status": ""}',
     '        except Exception:\n            raise', "bond"),
    ("bond: a claim still standing is settled",
     '        if decision["do"] == WAIT:\n            _fail(str(decision["why"]) + ", so there is nothing to settle yet")\n', '', "bond"),
    ("bond: a stake is paid out twice",
     '        if self.settled:\n            _fail("this bond has already been settled")\n', '', "bond"),
    ("bond: a broken claim naming nobody pays the zero address",
     '            if who.lower() == ZERO:\n                return {"do": PAY_FUNDER, "status": status,\n                        "why": "the claim is broken but the register names nobody who broke it"}\n', '', "bond"),
    ("bond: a second account may donate to somebody else's stake",
     '        if self.funder.as_hex.lower() != ZERO and gl.message.sender_address != self.funder:\n            self._pay(gl.message.sender_address, value)\n            return json.dumps({"ok": False, "reason": "this bond already has a funder, and only "\n                                                      "one address can be refunded; your funds were returned"})\n', '', "bond"),
    ("bond: money may be staked on a question already answered",
     '        decision = self._decision()\n        if decision["do"] != WAIT:\n            self._pay(gl.message.sender_address, value)\n            return json.dumps({"ok": False, "reason": "this claim is already decided ("\n                                                      + str(decision.get("status", "")) + "); your funds were returned"})\n', '', "bond"),
    ("bond: the claimant is paid a prize for breaking their own claim",
     '            if who.lower() == self.claimant.as_hex.lower():\n                # The account that staked the money is the account that broke\n                # the claim. Whatever happened there, it is not a prize.\n                return {"do": PAY_FUNDER, "status": status,\n                        "why": "the claim was broken by the account this bond was staked for"}\n', '', "bond"),
    ("bond: the stake leaves before the contract latches",
     '        self.pool = gl.u256(0)\n        self.settled = True\n        self._pay(payee, amount)', '        self._pay(payee, amount)\n        self.pool = gl.u256(0)\n        self.settled = True', "bond"),
    ("bond: money sent to a settled bond is kept",
     '            if value > gl.u256(0):\n                self._pay(gl.message.sender_address, value)\n', '', "bond"),
]


def _env(**extra):
    return dict(os.environ, PYTHONDONTWRITEBYTECODE="1", **extra)


def run(main_path: pathlib.Path, fixture_path: pathlib.Path) -> str:
    out = subprocess.run(PYTEST, env=_env(COUNTEREXAMPLE_SOURCE=str(main_path), BOND_SOURCE=str(fixture_path)),
                         capture_output=True, text=True, cwd=ROOT)
    if out.returncode == 0:
        return ""
    text = out.stdout + out.stderr
    if "error during collection" in text or "IndentationError" in text or "SyntaxError" in text:
        raise RuntimeError("the mutant does not even import; that is a broken anchor, not a killed defence")
    m = re.search(r"FAILED tests/test_pure\.py::(\S+)", text)
    if not m:
        raise RuntimeError("a test failed but its name could not be read:\n" + text[-800:])
    return m.group(1)


def main() -> int:
    baseline = subprocess.run(PYTEST, env=_env(), capture_output=True, text=True, cwd=ROOT)
    if baseline.returncode != 0:
        print("the unmutated suite does not pass; a mutation table over a failing suite proves nothing")
        print((baseline.stdout + baseline.stderr)[-600:])
        return 3
    rows, escaped = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for entry in MUTATIONS:
            name, old, new = entry[0], entry[1], entry[2]
            target = entry[3] if len(entry) > 3 else "register"
            base = FSRC if target == "bond" else SRC
            if base.count(old) != 1:
                print(f"  ! anchor found {base.count(old)} times, expected once: {name}")
                return 2
            k = len(rows) + len(escaped)
            main_path = pathlib.Path(tmp) / f"counterexample_{k}.py"
            fixture_path = pathlib.Path(tmp) / f"bond_{k}.py"
            main_path.write_text(base.replace(old, new) if target == "register" else SRC, encoding="utf-8")
            fixture_path.write_text(base.replace(old, new) if target == "bond" else FSRC, encoding="utf-8")
            killer = run(main_path, fixture_path)
            (rows if killer else escaped).append((name, killer))
            print(f"  {'killed ' if killer else 'ESCAPED'}  {name}" + (f"  <- {killer}" if killer else ""))
    if escaped:
        print(f"\n{len(escaped)} mutant(s) escaped; no table written.")
        return 1
    table = ["# Mutations", "",
             f"{len(rows)} defences in `contracts/counterexample.py` and `contracts/fixtures/bond.py`, "
             "each removed or inverted in turn, and the test that failed because of it. Generated by "
             "`tools/mutate.py`; it refuses to write this file if any mutant survives.", "",
             "| defence removed | killed by |", "|---|---|"] + [f"| {n} | `{k}` |" for n, k in rows] + [""]
    (ROOT / "tests" / "MUTATIONS.md").write_text("\n".join(table), encoding="utf-8")
    print(f"\n{len(rows)} / {len(rows)} killed · tests/MUTATIONS.md written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
