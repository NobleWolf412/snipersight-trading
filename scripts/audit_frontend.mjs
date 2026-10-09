// Read-only frontend inventory. Unreachable is a review candidate, never deletion permission.
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

const root = process.cwd();
const relative = file => path.relative(root, file).replaceAll('\\', '/');
const walk = directory => fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
  const file = path.join(directory, entry.name);
  return entry.isDirectory() ? walk(file) : [file];
});
const files = walk(path.join(root, 'src')).filter(file => /\.[cm]?[jt]sx?$/.test(file));
const active = files.filter(file => !relative(file).startsWith('src/_archive/'));
const config = ts.readConfigFile(path.join(root, 'tsconfig.json'), ts.sys.readFile);
const options = ts.parseJsonConfigFileContent(config.config, ts.sys, root).options;
const dependencies = new Map();
const unresolved = [];
const packageImports = new Set();
const records = active.map(file => {
  const source = fs.readFileSync(file, 'utf8');
  const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
  const imports = [];
  let inlineStyles = 0;
  function visit(node) {
    if (ts.isJsxAttribute(node) && node.name.getText(ast) === 'style') inlineStyles++;
    let specifier;
    if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) specifier = node.moduleSpecifier.text;
    if (ts.isCallExpression(node) && (node.expression.kind === ts.SyntaxKind.ImportKeyword || node.expression.getText(ast) === 'require') && node.arguments.length === 1 && ts.isStringLiteral(node.arguments[0])) specifier = node.arguments[0].text;
    if (specifier) {
      imports.push(specifier);
      if (!specifier.startsWith('.') && !specifier.startsWith('@/')) packageImports.add(specifier.startsWith('@') ? specifier.split('/').slice(0, 2).join('/') : specifier.split('/')[0]);
    }
    ts.forEachChild(node, visit);
  }
  visit(ast);
  const targets = imports.flatMap(specifier => {
    const resolved = ts.resolveModuleName(specifier, file, options, ts.sys).resolvedModule;
    if (resolved && !resolved.isExternalLibraryImport) return [path.resolve(resolved.resolvedFileName)];
    if (!resolved && (specifier.startsWith('.') || specifier.startsWith('@/')) && !/\.(css|svg|png|jpg|json)$/.test(specifier)) unresolved.push({ file: relative(file), specifier });
    return [];
  });
  dependencies.set(file, targets);
  return { file: relative(file), lines: source.split(/\r?\n/).length, bytes: Buffer.byteLength(source), inlineStyles, imports };
});
function reachable(roots) {
  const seen = new Set();
  const stack = [...roots];
  while (stack.length) {
    const file = stack.pop();
    if (seen.has(file)) continue;
    seen.add(file);
    stack.push(...(dependencies.get(file) ?? []));
  }
  return seen;
}
const appRoots = [path.join(root, 'src/main.tsx')];
const supportRoots = active.filter(file => /\.(test|spec|stories)\.[jt]sx?$/.test(file));
const app = reachable(appRoots);
const supported = reachable([...appRoots, ...supportRoots]);
const inventory = {
  schemaVersion: 1,
  scope: 'Static literal imports/exports from main.tsx, active tests and stories. Excludes archive; declarations, CSS classes, computed imports, config globs and external scripts require manual reference/provenance checks.',
  activeFiles: active.length,
  archivedFiles: files.length - active.length,
  appReachableFiles: active.filter(file => app.has(file)).length,
  supportRoots: supportRoots.map(relative),
  unreachableCandidates: records.filter(record => !supported.has(path.join(root, record.file)) && !record.file.endsWith('.d.ts')),
  largestFiles: [...records].sort((a, b) => b.lines - a.lines).slice(0, 15),
  inlineStyleCount: records.reduce((total, record) => total + record.inlineStyles, 0),
  packageImports: [...packageImports].sort(),
  unresolved,
};
const outputIndex = process.argv.indexOf('--output');
if (outputIndex >= 0) {
  const output = process.argv[outputIndex + 1];
  if (!output) throw new Error('--output requires a path');
  fs.writeFileSync(path.resolve(root, output), JSON.stringify(inventory, null, 2) + '\n');
}
console.log(JSON.stringify({ ...inventory, largestFiles: inventory.largestFiles.map(({file, lines, inlineStyles}) => ({file, lines, inlineStyles})), unreachableCandidates: inventory.unreachableCandidates.map(({file,lines}) => ({file,lines})) }, null, 2));
