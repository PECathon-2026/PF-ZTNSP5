export type TreeNode = {
  name: string;
  path: string;
  file: boolean;
  children: TreeNode[];
};

function ensureDir(root: TreeNode, segments: string[], fullPath: string): TreeNode {
  let node = root;
  for (let index = 0; index < segments.length; index += 1) {
    const isFile = index === segments.length - 1;
    const segment = segments[index];
    const path = segments.slice(0, index + 1).join("/");
    let next = node.children.find((child) => child.name === segment && child.file === isFile);
    if (!next) {
      next = { name: segment, path, file: isFile, children: [] };
      node.children.push(next);
    }
    node = next;
  }
  node.path = fullPath || node.path;
  return node;
}

export function buildTree(paths: string[]): TreeNode {
  const root: TreeNode = { name: "", path: "", file: false, children: [] };
  for (const raw of paths) {
    const normalized = raw.replace(/\\/g, "/").replace(/^\.\//, "").replace(/^\/+/, "");
    if (!normalized) continue;
    const segments = normalized.split("/").filter(Boolean);
    if (segments.length === 0) continue;
    ensureDir(root, segments, normalized);
  }
  sortTree(root);
  return root;
}

function sortTree(node: TreeNode): void {
  node.children.sort((a, b) => {
    if (a.file !== b.file) return a.file ? 1 : -1;
    return a.name.localeCompare(b.name);
  });
  for (const child of node.children) sortTree(child);
}

export function countNodes(node: TreeNode): number {
  let total = 0;
  for (const child of node.children) {
    total += 1;
    if (!child.file) total += countNodes(child);
  }
  return total;
}
