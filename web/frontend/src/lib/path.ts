export function getByPath(obj: unknown, path: string): unknown {
  let cur: unknown = obj
  for (const seg of path.split(/\.|\[|\]\.?/).filter(Boolean)) {
    if (cur == null) return undefined
    if (/^\d+$/.test(seg)) {
      cur = (cur as unknown[])[Number(seg)]
    } else {
      cur = (cur as Record<string, unknown>)[seg]
    }
  }
  return cur
}
