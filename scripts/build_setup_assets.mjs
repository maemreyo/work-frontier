import { copyFile, mkdir, rm, writeFile } from "node:fs/promises"
import { createHash } from "node:crypto"
import { readFile } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const destination = resolve(root, "backend/src/work_frontier/interfaces/setup_static")
const assets = resolve(destination, "assets")
const sources = new Map([
  ["setup.html", "frontend/setup.html"],
  ["assets/setup-center-element.js", "frontend/src/setup/setup-center-element.js"],
  ["assets/setup-api.js", "frontend/src/setup/setup-api.js"],
  ["assets/setup-model.js", "frontend/src/setup/setup-model.js"],
  ["assets/setup-center.css", "frontend/src/setup/setup-center.css"],
])

await rm(destination, { recursive: true, force: true })
await mkdir(assets, { recursive: true })
const manifest = {}
for (const [output, input] of sources) {
  const source = resolve(root, input)
  const target = resolve(destination, output)
  await mkdir(dirname(target), { recursive: true })
  await copyFile(source, target)
  const content = await readFile(source)
  manifest[output] = createHash("sha256").update(content).digest("hex")
}
await writeFile(resolve(destination, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`)
await writeFile(resolve(destination, "__init__.py"), '"""Packaged first-run Setup Center assets."""\n')
