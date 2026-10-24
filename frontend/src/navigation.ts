export function safeNextPath(): string {
  const candidate = new URLSearchParams(window.location.search).get("next");
  if (!candidate) return "/";

  try {
    const target = new URL(candidate, window.location.origin);
    return target.origin === window.location.origin
      ? `${target.pathname}${target.search}${target.hash}`
      : "/";
  } catch {
    return "/";
  }
}
