"use client";

import type { StoredRepository } from "./types";

const STORAGE_KEY = "kage.repositories.v1";
const ACTIVE_KEY = "kage.activeRepository.v1";

function canPersist(): boolean {
  return typeof window !== "undefined" && Boolean(window.localStorage);
}

export function readRepositories(): StoredRepository[] {
  if (!canPersist()) return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (entry): entry is StoredRepository =>
        Boolean(entry) &&
        typeof entry === "object" &&
        typeof (entry as StoredRepository).repository_id === "string",
    );
  } catch {
    return [];
  }
}

export function saveRepository(repository: StoredRepository): StoredRepository[] {
  const existing = readRepositories().filter((entry) => entry.repository_id !== repository.repository_id);
  const next = [repository, ...existing].slice(0, 8);
  if (canPersist()) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      window.localStorage.setItem(ACTIVE_KEY, repository.repository_id);
    } catch {
      /* storage may be unavailable; session still works in memory */
    }
  }
  return next;
}

export function getActiveRepositoryId(): string | null {
  if (!canPersist()) return null;
  try {
    return window.localStorage.getItem(ACTIVE_KEY);
  } catch {
    return null;
  }
}

export function setActiveRepositoryId(repositoryId: string | null): void {
  if (!canPersist()) return;
  try {
    if (repositoryId) window.localStorage.setItem(ACTIVE_KEY, repositoryId);
    else window.localStorage.removeItem(ACTIVE_KEY);
  } catch {
    /* ignore */
  }
}

export function findRepository(repositoryId: string): StoredRepository | null {
  return readRepositories().find((entry) => entry.repository_id === repositoryId) ?? null;
}
