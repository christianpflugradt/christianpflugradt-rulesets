// Print the default export of a Semantic Release config module as JSON.
// Regular expressions and functions become strings so the verdict never depends on code.
import { pathToFileURL } from "node:url";

try {
  const { default: config } = await import(pathToFileURL(process.argv[2]).href);
  process.stdout.write(JSON.stringify(config, (_key, value) =>
    value instanceof RegExp ? String(value) : typeof value === "function" ? "[function]" : value));
} catch (error) {
  process.stderr.write(`${error?.message ?? error}\n`);
  process.exit(1);
}
