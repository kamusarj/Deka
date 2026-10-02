import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { JSDOM, VirtualConsole } from "jsdom";

const dist = new URL("../dist/", import.meta.url);
const html = readFileSync(new URL("index.html", dist), "utf8");
const errors = [];
const networkCalls = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on("jsdomError", (error) => errors.push(error.message));
virtualConsole.on("error", (...args) => errors.push(args.map(String).join(" ")));
const dom = new JSDOM(html, {
  url: "https://deka-demo.test/",
  runScripts: "outside-only",
  pretendToBeVisual: true,
  virtualConsole,
});
const { window } = dom;
const document = window.document;
const checks = [];
let printCount = 0;

function blockNetwork(kind, destination) {
  networkCalls.push({ kind, destination: String(destination) });
  throw new Error(`Unexpected ${kind} connection: ${destination}`);
}
window.fetch = (url) => blockNetwork("fetch", url);
window.XMLHttpRequest.prototype.open = function (_method, url) { blockNetwork("XMLHttpRequest", url); };
window.WebSocket = class { constructor(url) { blockNetwork("WebSocket", url); } };
window.print = () => { printCount += 1; };
window.matchMedia = () => ({ matches: false });

async function waitFor(predicate, label) {
  const deadline = Date.now() + 2500;
  while (Date.now() < deadline) {
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  throw new Error(`Timed out: ${label}`);
}

function findButton(label, scope = document) {
  const button = [...scope.querySelectorAll("button")].find((item) => item.textContent.trim() === label);
  assert.ok(button, `Button missing: ${label}`);
  return button;
}

async function navigate(path) {
  window.location.hash = path;
  await waitFor(() => window.location.hash === `#${path}`, `navigate to ${path}`);
  // Allow React Router to consume the browser hashchange event.
  await new Promise((resolve) => window.setTimeout(resolve, 20));
}

try {
  for (const element of document.querySelectorAll("[src], link[rel='stylesheet']")) {
    const source = element.getAttribute("src") || element.getAttribute("href");
    const url = new URL(source, window.location.href);
    assert.equal(url.origin, window.location.origin, `External asset: ${source}`);
    const path = new URL(`.${url.pathname}`, dist);
    assert.ok(existsSync(path), `Missing build asset: ${fileURLToPath(path)}`);
    if (url.pathname.endsWith(".css")) {
      const css = readFileSync(path, "utf8");
      for (const match of css.matchAll(/url\(["']?(\/fonts\/[^)"']+)["']?\)/g)) {
        assert.ok(existsSync(new URL(`.${match[1]}`, dist)), `Missing local font: ${match[1]}`);
      }
    }
  }
  checks.push("built scripts, styles and local fonts exist");

  for (const script of document.querySelectorAll("script")) {
    const source = script.getAttribute("src");
    window.eval(source ? readFileSync(new URL(`.${source}`, dist), "utf8") : script.textContent);
  }
  await waitFor(() => document.querySelector("h1")?.textContent.includes("Soạn đề"), "production landing render");
  checks.push("production landing renders");

  await navigate("/create");
  await waitFor(() => document.querySelector("form"), "create screen");
  const grade = document.querySelector("select");
  grade.value = "9";
  grade.dispatchEvent(new window.Event("change", { bubbles: true }));
  await waitFor(() => document.querySelector("textarea").value.includes("Ohm"), "grade 9 topic");
  findButton("Tạo bộ đề mẫu ↗").click();
  await waitFor(() => document.querySelectorAll("article").length === 4, "generated exam");
  assert.match(document.querySelector("h1").textContent, /KHTN 9/);
  const generatedPath = window.location.hash.slice(1);
  checks.push("production creates a grade 9 exam");

  findButton("Duyệt câu hỏi", document.querySelector("article")).click();
  await waitFor(() => document.querySelector(".demo-progress").textContent.includes("1/4"), "question approval");
  await navigate("/question-bank");
  await waitFor(() => document.querySelectorAll(".demo-bank-row").length === 1, "approved bank question");
  const saved = JSON.parse(window.localStorage.getItem("deka-public-demo-v1"));
  assert.equal(saved[0].questions[0].approved, true);
  checks.push("approval reaches the bank and storage");

  await navigate(generatedPath);
  await waitFor(() => document.querySelectorAll("article").length === 4, "exam return");
  findButton("Ma trận").click();
  await waitFor(() => document.querySelector("table"), "matrix tab");
  assert.deepEqual([...document.querySelectorAll("tbody tr:first-child td")].map((item) => item.textContent), ["1 câu", "1 câu", "2 câu", "4 câu"]);
  findButton("Bản đặc tả").click();
  await waitFor(() => document.querySelector("table").textContent.includes("Vận dụng định luật Ohm"), "specification tab");
  findButton("Đáp án & rubric").click();
  await waitFor(() => document.querySelector(".demo-answer-list"), "answers tab");
  assert.equal(document.querySelectorAll(".demo-scoring").length, 4);
  findButton("In bản xem trước").click();
  assert.equal(printCount, 1);
  checks.push("matrix, specification, answers and print work");

  findButton("Nhân bản đề").click();
  await waitFor(() => document.querySelector("h1").textContent.includes("bản sao"), "duplicate exam");
  assert.notEqual(window.location.hash.slice(1), generatedPath);
  assert.equal(JSON.parse(window.localStorage.getItem("deka-public-demo-v1")).length, 3);
  checks.push("duplicate gets a distinct route and stored entry");

  assert.deepEqual(networkCalls, [], "The demo must not call an API");
  assert.deepEqual(errors, [], "Production runtime errors");
  checks.push("zero API connections and runtime errors");
  console.log(JSON.stringify({ status: "passed", checks }, null, 2));
} finally {
  window.close();
}
