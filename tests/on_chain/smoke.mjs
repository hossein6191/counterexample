/* Counterexample against the live GenLayer Studio Next network.
 *
 * The claim to prove: validators who each read the same two texts agree not
 * only that a case breaks a claim but on which numbered clause it breaks, and
 * the route out of a broken claim is judged by the same standard as the break.
 *
 *   node tests/on_chain/smoke.mjs
 */
import { createClient, createAccount } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";
import { generatePrivateKey } from "viem/accounts";
import { readFileSync } from "node:fs";

const RPC = "https://studio-next.genlayer.com/api";
/* Studio Next (consensus v0.6, chain 61997): every write carries a quoted fee. The SDK simulates
   the call and quotes what it saw; a call the contract refuses cannot be simulated, so the
   default quote is used and the refusal lands on chain with its reason. Unused fee comes back. */
const NETWORK = { ...studioDevnet, rpcUrls: { default: { http: [RPC] } } };
const feesFor = async (client, address, fn, args) => {
  try { const e = await client.estimateTransactionFeesForWrite({ address, functionName: fn, args }); return { distribution: e.distribution, messageAllocations: e.messageAllocations, feeValue: e.feeValue }; }
  catch (x) { const d = await client.estimateTransactionFees({}); return { distribution: d.distribution, feeValue: d.feeValue }; }
};
const deployFees = async (client) => { const d = await client.estimateTransactionFees({}); return { distribution: d.distribution, feeValue: d.feeValue }; };
const rpc = async (m, p) => {
  let last;
  for (let i = 0; i < 8; i++) {
    try {
      const r = await fetch(RPC, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: m, params: p }) });
      return (await r.json()).result;
    } catch (e) { last = e; await new Promise((x) => setTimeout(x, 2500)); }
  }
  throw last;
};
let pass = 0, fail = 0;
const ok = (n, c, d = "") => { c ? pass++ : fail++; console.log(`${c ? "PASS" : "FAIL"}  ${n}${d ? "  · " + d : ""}`); };

const CLAIM = "Every invoice we issued in August was under 500 dollars. "
            + "Every invoice we issued in August was paid within 30 days.";
const MISSES = "Invoice 41 was issued on 4 August for 120 dollars and was paid on 20 August.";
const BREAKS = "Invoice 58 was issued on 21 August for 940 dollars.";
const REWORD = "All of the invoices we issued in August were under 500 dollars. "
             + "Every invoice we issued in August was paid within 30 days.";
const NARROWED = "Every invoice we issued between 1 and 10 August was under 500 dollars. "
               + "Every invoice we issued in August was paid within 30 days.";

const authorKey = generatePrivateKey(); const author = createAccount(authorKey);
const challenger = createAccount(generatePrivateKey());
const stranger = createAccount(generatePrivateKey());
await rpc("sim_fundAccount", { account_address: author.address, amount: 600e18 });
await rpc("sim_fundAccount", { account_address: challenger.address, amount: 400e18 });
const ca = createClient({ chain: NETWORK, account: author });
const cc = createClient({ chain: NETWORK, account: challenger });
const rd = createClient({ chain: NETWORK });
const code = readFileSync(new URL("../../contracts/counterexample.py", import.meta.url));
const dh = await ca.deployContract({ code, args: [], fees: await deployFees(ca) });
const A = (await ca.waitForTransactionReceipt({ hash: dh, waitUntil: "decided", retries: 40, interval: 4000, fullTransaction: true }))?.data?.contract_address;
console.log("Counterexample at", A);
console.log("author", author.address, "· challenger", challenger.address, "\n");

const wait = async (tx) => {
  for (let i = 0; i < 90; i++) {
    await new Promise((r) => setTimeout(r, 4000));
    const t = await rpc("eth_getTransactionByHash", [tx]);
    if (t?.status === "CANCELED") return { msg: "CANCELED", exec: "CANCELED", votes: { a: 0, d: 0, idl: 0 }, applied: false };
    if (t?.status === "ACCEPTED" || t?.status === "FINALIZED") {
      const lr = t.consensus_data?.leader_receipt, one = Array.isArray(lr) ? lr[0] : lr;
      let msg = ""; try { msg = Buffer.from(one.result, "base64").toString("utf8").replace(/[^\x20-\x7e]/g, " ").trim(); } catch (e) {}
      let a = 0, d = 0, idl = 0;
      for (const k in (t.consensus_data?.votes || {})) { const v = t.consensus_data.votes[k]; if (v === "agree") a++; else if (v === "disagree") d++; else idl++; }
      let j = null; const b = msg.indexOf("{"); if (b !== -1) { try { j = JSON.parse(msg.slice(b)); } catch (e) {} }
      return { msg, j, exec: one?.execution_result, votes: { a, d, idl }, applied: a * 2 > a + d + idl, tx };
    }
  }
  return { msg: "TIMEOUT", exec: "", votes: { a: 0, d: 0, idl: 0 }, applied: false };
};
const send = async (client, fn, args) => await wait(await client.writeContract({ address: A, functionName: fn, args, fees: await feesFor(client, A, fn, args) }));
const view = async (fn, args = []) => await rd.readContract({ address: A, functionName: fn, args });
const tally = (r) => `${r.votes.a} agree, ${r.votes.d} disagree, ${r.votes.idl} idle`;
const retry = async (client, fn, args, label) => {
  let r = await send(client, fn, args);
  if (!r.applied && r.exec !== "ERROR") { console.log(`      ${label}: ${tally(r)}, nothing stored; asking once more`); r = await send(client, fn, args); }
  return r;
};

// 1. the claim goes on the record, split into clauses by the contract
const posted = await send(ca, "post", ["under500", CLAIM, 7]);
ok("a claim is posted with its clauses numbered by the contract",
   posted.j?.ok === true && posted.j?.clauses?.length === 2, JSON.stringify(posted.j?.clauses || posted.msg.slice(0, 90)));

// 2. a claim the battery cannot index is refused before any model runs
const bad = await send(ca, "post", ["nowindow", CLAIM, 0]);
ok("a window outside the bounds is refused before any validator is asked",
   bad.exec === "ERROR" && bad.msg.includes("1 to 365 days"), bad.msg.slice(0, 80));

// 3. the author cannot farm a survival count out of their own cases
const own = await send(ca, "challenge", ["under500", MISSES]);
ok("the author cannot challenge their own claim",
   own.exec === "ERROR" && own.msg.includes("cannot challenge it"), own.msg.slice(0, 80));

// 4. a case the claim covers leaves it standing, and counts
const misses = await retry(cc, "challenge", ["under500", MISSES], "a case that should miss");
ok("a case the claim covers is judged holds, and the validators agree",
   misses.applied && misses.j?.verdict === "holds", `${tally(misses)} -> ${misses.j?.verdict || misses.msg.slice(0, 70)}`);
ok("a miss counts as one survival", Number(await view("survived", ["under500"])) === 1);

// 5. the same case is never judged twice
const again = await send(cc, "challenge", ["under500", "  " + MISSES.toUpperCase() + " "]);
ok("the same case cannot be judged again in another shape",
   again.exec === "ERROR" && again.msg.includes("already been judged"), again.msg.slice(0, 80));

// 6. a case that breaks it, and the clause they agreed it breaks
const breaks = await retry(cc, "challenge", ["under500", BREAKS], "the counterexample");
ok("a counterexample breaks the claim and the validators agree which clause",
   breaks.applied && breaks.j?.verdict === "violates" && breaks.j?.clause === 1,
   `${tally(breaks)} -> clause ${breaks.j?.clause} · ${String(breaks.j?.reason || "").slice(0, 70)}`);
const row = JSON.parse(String(await view("claim", ["under500"])));
ok("the row keeps who broke it, where, and with what",
   row.status === "broken" && row.broken?.by?.toLowerCase() === challenger.address.toLowerCase()
   && row.broken?.clause === 1 && row.broken?.clause_text.startsWith("Every invoice"),
   `${row.broken?.by?.slice(0, 10)} at clause ${row.broken?.clause}`);
ok("the gate says the claim no longer stands, for free", (await view("stands", ["under500"])) === false);

// 7. a broken claim takes no more work
const closed = await send(cc, "challenge", ["under500", "Invoice 77 was 600 dollars."]);
ok("a broken claim takes no more cases",
   closed.exec === "ERROR" && closed.msg.includes("only a standing claim"), closed.msg.slice(0, 70));

// 8. the way out is judged by the same standard, and the refusal is kept
const empty = await retry(ca, "amend", ["under500v2", "under500", REWORD, 7], "a reword that fixes nothing");
ok("a reword the counterexample still breaks is refused at the same clause, and recorded",
   empty.applied && empty.j?.ok === false && empty.j?.clause === 1 && !!empty.j?.attempt,
   `${tally(empty)} -> ${empty.j?.why || empty.msg.slice(0, 70)}`);
const reroll = await send(ca, "amend", ["under500v3", "under500", "  " + REWORD.toUpperCase() + " ", 7]);
ok("the same wording cannot be put to the counterexample again until a round agrees",
   reroll.exec === "ERROR" && reroll.msg.includes("already been put to the counterexample"), reroll.msg.slice(0, 100));

const narrowed = await retry(ca, "amend", ["under500v2", "under500", NARROWED, 7], "a real narrowing");
ok("a narrowing the counterexample misses is admitted, with its lineage",
   narrowed.applied && narrowed.j?.ok === true && narrowed.j?.amends === "under500",
   `${tally(narrowed)} -> ${narrowed.j?.claim || narrowed.msg.slice(0, 70)}`);
ok("the successor stands and the parent keeps its scar",
   (await view("stands", ["under500v2"])) === true && (await view("stands", ["under500"])) === false);

const attempts = JSON.parse(String(await view("attempts_of", ["under500"])));
ok("every judged text is on the record whatever it decided, cases and amendments alike",
   attempts.length === 4 && attempts.filter((a) => a.kind === "amendment").length === 2,
   attempts.map((a) => a.kind + ":" + a.verdict).join(", "));
ok("the stored sentence is the contract's, derived from the clause every validator agreed",
   attempts.some((a) => a.reason === "clause 1 is made false by this case"),
   attempts.map((a) => a.reason).join(" | ").slice(0, 120));

// 9. the consequence, deployed and read against the real register
const bondCode = readFileSync(new URL("../../contracts/fixtures/bond.py", import.meta.url));
const bh = await ca.deployContract({ code: bondCode, args: [A, "under500", author.address], fees: await deployFees(ca) });
const B = (await ca.waitForTransactionReceipt({ hash: bh, waitUntil: "decided", retries: 40, interval: 4000, fullTransaction: true }))?.data?.contract_address;
console.log("\nBond at", B);
const wouldPay = String(await rd.readContract({ address: B, functionName: "would_pay", args: [] }));
ok("the bond reads the broken claim across contracts, with no model and no consensus",
   wouldPay === "breaker " + challenger.address, wouldPay);
const squatted = await ca.deployContract({ code: bondCode, args: [A, "under500", stranger.address], fees: await deployFees(ca) });
const S = (await ca.waitForTransactionReceipt({ hash: squatted, waitUntil: "decided", retries: 40, interval: 4000, fullTransaction: true }))?.data?.contract_address;
const squattedSays = String(await rd.readContract({ address: S, functionName: "would_pay", args: [] }));
ok("a bond tied to the wrong claimant pays nobody: a name is a handle, not authority",
   squattedSays.startsWith("funder") && squattedSays.includes("not by the account"), squattedSays.slice(0, 90));

console.log(`\n${pass} passed, ${fail} failed  · register ${A}`);
process.exit(fail ? 1 : 0);
