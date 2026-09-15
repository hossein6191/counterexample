/* Does the new narrowing settle? Post, break, then amend three times over, so a
   one-off agreement is not mistaken for a wording that works. */
import { createClient, createAccount } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";
import { generatePrivateKey } from "viem/accounts";
import { readFileSync } from "node:fs";
const RPC = "https://studio-next.genlayer.com/api";
const NETWORK = { ...studioDevnet, rpcUrls: { default: { http: [RPC] } } };
const rpc = async (m, p) => { for (let i = 0; i < 8; i++) { try { const r = await fetch(RPC, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: m, params: p }) }); return (await r.json()).result; } catch (e) { await new Promise((x) => setTimeout(x, 2500)); } } };
const dflt = async (c) => { const d = await c.estimateTransactionFees({}); return { distribution: d.distribution, feeValue: d.feeValue }; };
const feesFor = async (c, A, fn, args) => { try { const e = await c.estimateTransactionFeesForWrite({ address: A, functionName: fn, args }); return { distribution: e.distribution, messageAllocations: e.messageAllocations, feeValue: e.feeValue }; } catch (x) { return await dflt(c); } };
const wait = async (tx) => { for (let i = 0; i < 90; i++) { await new Promise((r) => setTimeout(r, 4000)); const t = await rpc("eth_getTransactionByHash", [tx]); if (t?.status === "ACCEPTED" || t?.status === "FINALIZED") { const lr = t.consensus_data?.leader_receipt, one = Array.isArray(lr) ? lr[0] : lr; let msg = ""; try { msg = Buffer.from(one.result, "base64").toString("utf8").replace(/[^\x20-\x7e]/g, " ").trim(); } catch (e) {} let j = null; const b = msg.indexOf("{"); if (b !== -1) { try { j = JSON.parse(msg.slice(b)); } catch (e) {} } let a = 0, d = 0, idl = 0; for (const k in (t.consensus_data?.votes || {})) { const v = t.consensus_data.votes[k]; if (v === "agree") a++; else if (v === "disagree") d++; else idl++; } return { msg, j, exec: one?.execution_result, applied: a * 2 > a + d + idl, votes: `${a}/${d}/${idl}` }; } } return { msg: "TIMEOUT", exec: "" }; };
const page = readFileSync("/Users/hossein/primitives-deploy/index.html", "utf8");
const strOf = (n) => eval(page.match(new RegExp("const " + n + "=(\"[\\s\\S]*?\");", "m"))[1]);
const CLAIM = strOf("CLAIM"), BREAKS = strOf("BREAKS"), NARROWED = strOf("NARROWED");
console.log("narrowing under test:\n  " + NARROWED + "\n");
const A1 = createAccount(generatePrivateKey()), B1 = createAccount(generatePrivateKey());
for (const a of [A1, B1]) await rpc("sim_fundAccount", { account_address: a.address, amount: 400e18 });
const ca = createClient({ chain: NETWORK, account: A1 }), cb = createClient({ chain: NETWORK, account: B1 });
const send = async (c, A, fn, args) => await wait(await c.writeContract({ address: A, functionName: fn, args, fees: await feesFor(c, A, fn, args) }));
const code = readFileSync("/Volumes/T9/project:genlayer/counterexample/contracts/counterexample.py");
let good = 0;
for (let round = 1; round <= 3; round++) {
  const dh = await ca.deployContract({ code, args: [], fees: await dflt(ca) });
  const REG = (await ca.waitForTransactionReceipt({ hash: dh, waitUntil: "decided", retries: 40, interval: 4000, fullTransaction: true }))?.data?.contract_address;
  await send(ca, REG, "post", ["under500", CLAIM, 7]);
  await send(cb, REG, "challenge", ["under500", BREAKS]);
  const r = await send(ca, REG, "amend", ["under500v2", "under500", NARROWED, 7]);
  const ok = r.j?.ok === true;
  if (ok) good++;
  console.log(`round ${round}: ${ok ? "ADMITTED" : "refused"} · ${r.votes} · ${r.j?.verdict || ""} ${r.j?.why || ""}`);
}
console.log(`\n${good} of 3 rounds admitted the narrowing`);
