"""Persistent homology of Vietoris–Rips filtrations, bottleneck distance and a display projection.

Pure Python (no numpy), so that results are reproducible in the executable and hashes are stable.
Specification: ``docs/specs/ph_vietoris_rips.md`` (v0.1). Section numbers in comments refer to it.

Design constraints (spec s 2, D1 to D5): no lens or filter function, no cover of a reference space, no
clustering within cover elements and no graph of clusters. The classical multidimensional scaling
projection below is used only to draw points on a page (D4); nothing here reads it.

Conventions. A distance matrix is a list of lists, symmetric, with a zero diagonal. The Rips complex at
scale e contains every vertex, every edge {i, j} with D[i][j] <= e and every triangle whose three edges are
present. A bar [birth, death) is alive at e when birth <= e < death; ``death`` is ``None`` for a class
that is not killed within the computed filtration (essential).
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Sequence

Matrix = Sequence[Sequence[float]]


@dataclass
class Bar:
    dimension: int
    birth: float
    death: float | None
    birth_simplex: tuple[int, ...]
    death_simplex: tuple[int, ...] | None
    members: tuple[int, ...] = ()        # H0: vertices of the component that dies (or survives)
    cycle: tuple[int, ...] = ()          # H1: a cycle born with the class, as a closed vertex sequence

    @property
    def persistence(self) -> float | None:
        return None if self.death is None else self.death - self.birth


@dataclass
class Persistence:
    n: int
    bars: list[Bar] = field(default_factory=list)
    edges: int = 0
    triangles: int = 0
    zero_pairs: dict[int, int] = field(default_factory=dict)  # dimension -> pairs with zero persistence
    budget_reached: bool = False
    max_scale: float | None = None

    def diagram(self, dimension: int) -> list[Bar]:
        return [b for b in self.bars if b.dimension == dimension]


# ---------------------------------------------------------------------------------------------- checks
def check_matrix(D: Matrix) -> None:
    n = len(D)
    for i in range(n):
        if len(D[i]) != n:
            raise ValueError("distance matrix must be square")
        if D[i][i] != 0:
            raise ValueError("distance matrix must have a zero diagonal")
        for j in range(i + 1, n):
            d = D[i][j]
            if not isinstance(d, (int, float)) or d != d or d in (math.inf, -math.inf) or d < 0:
                raise ValueError("distances must be finite and non-negative")
            if D[j][i] != d:
                raise ValueError("distance matrix must be symmetric")


# ---------------------------------------------------------------------------------------------- persistence
def rips_persistence(D: Matrix, max_dimension: int = 1, max_scale: float | None = None,
                     simplex_budget: int = 3_000_000, algorithm: str = "cohomology") -> Persistence:
    """Persistence pairs in dimensions 0 and (optionally) 1 of the Vietoris–Rips filtration (spec s 4).

    H0 by union-find over edges in filtration order (s 4.2); H1 by persistent cohomology with clearing, or
    (``algorithm="homology"``, for cross-checking) by reduction of the triangle boundary matrix (s 4.3).
    """
    check_matrix(D)
    if max_dimension not in (0, 1):
        raise ValueError("max_dimension must be 0 or 1")
    n = len(D)
    out = Persistence(n=n, max_scale=max_scale, zero_pairs={0: 0, 1: 0})

    # Edges in filtration order: value, then vertex indices (s 4.1). Ties do not affect the diagram.
    edges = sorted((float(D[i][j]), i, j) for i in range(n) for j in range(i + 1, n)
                   if max_scale is None or D[i][j] <= max_scale)
    out.edges = len(edges)
    order: dict[tuple[int, int], int] = {(i, j): t for t, (_, i, j) in enumerate(edges)}

    # H0: elder rule with ties broken by the smallest vertex index; the root is the smallest vertex.
    parent = list(range(n))
    members: dict[int, list[int]] = {i: [i] for i in range(n)}

    def find(x: int) -> int:
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    negative: set[int] = set()
    for t, (d, i, j) in enumerate(edges):
        ri, rj = find(i), find(j)
        if ri == rj:
            continue
        negative.add(t)
        keep, die = (ri, rj) if ri < rj else (rj, ri)
        if d > 0:
            out.bars.append(Bar(0, 0.0, d, (die,), (i, j), tuple(sorted(members[die]))))
        else:
            out.zero_pairs[0] += 1
        parent[die] = keep
        members[keep].extend(members.pop(die))
    for root in sorted(members):
        out.bars.append(Bar(0, 0.0, None, (root,), None, tuple(sorted(members[root]))))

    if max_dimension < 1:
        return out

    # Bound the number of triangles (s 4.5): count them as edges are added and, if the budget would be
    # exceeded, truncate the filtration below the first edge value at which it is, so that every triangle
    # up to the effective maximum scale is present and the pairing is exact there.
    neighbours: list[set[int]] = [set() for _ in range(n)]
    count = 0
    cut = len(edges)
    for t, (_, i, j) in enumerate(edges):
        count += len(neighbours[i] & neighbours[j])
        if count > simplex_budget:
            cut = t
            break
        neighbours[i].add(j)
        neighbours[j].add(i)
    if cut < len(edges):
        out.budget_reached = True
        limit = edges[cut][0]
        kept = [e for e in edges if e[0] < limit]
        if not kept:
            raise ValueError("simplex budget too small for any edge")
        truncated = rips_persistence(D, max_dimension, max_scale=kept[-1][0], simplex_budget=simplex_budget,
                                     algorithm=algorithm)
        truncated.budget_reached = True
        return truncated

    out.triangles = count
    E = len(edges)
    paired: dict[int, int] = {}  # edge order -> triangle key (persistence pair in dimension 1)
    if algorithm == "cohomology":
        # Persistent cohomology with clearing (de Silva, Morozov and Vejdemo-Johansson 2011; Bauer 2021):
        # coboundary columns of the edges not already paired in dimension 0, in reverse filtration order,
        # pivot the earliest triangle. The pairs are those of persistent homology.
        pivot_owner: dict[int, set[int]] = {}
        for t in range(E - 1, -1, -1):
            if t in negative:
                continue
            _, i, j = edges[t]
            col: set[int] = set()
            for k in neighbours[i] & neighbours[j]:
                a = order[(i, k) if i < k else (k, i)]
                b = order[(j, k) if j < k else (k, j)]
                o1, o2, o3 = sorted((t, a, b), reverse=True)
                col.add((o1 * E + o2) * E + o3)
            while col:
                low = min(col)
                other = pivot_owner.get(low)
                if other is None:
                    break
                col ^= other
            if col:
                low = min(col)
                pivot_owner[low] = col
                paired[t] = low
    elif algorithm == "homology":
        # Standard reduction of the triangle boundary matrix (Edelsbrunner, Letscher and Zomorodian 2002);
        # kept as an independent cross-check of the cohomology algorithm.
        triangles: list[int] = []
        for i in range(n):
            for j in sorted(k for k in neighbours[i] if k > i):
                for k in sorted(m for m in neighbours[i] & neighbours[j] if m > j):
                    o1, o2, o3 = sorted((order[(i, j)], order[(i, k)], order[(j, k)]), reverse=True)
                    triangles.append((o1 * E + o2) * E + o3)
        triangles.sort()
        owner_of: dict[int, set[int]] = {}
        for key in triangles:
            col = set(_faces(key, E))
            while col:
                low = max(col)
                other = owner_of.get(low)
                if other is None:
                    break
                col ^= other
            if col:
                low = max(col)
                owner_of[low] = col
                paired[low] = key
    else:
        raise ValueError("algorithm must be 'cohomology' or 'homology'")

    for t in sorted(paired):
        key = paired[t]
        birth, death = edges[t][0], edges[key // (E * E)][0]
        if death > birth:
            a, b = edges[t][1], edges[t][2]
            out.bars.append(Bar(1, birth, death, (a, b), _vertices(_faces(key, E), edges),
                                cycle=_cycle(a, b, t, edges)))
        else:
            out.zero_pairs[1] += 1
    for t, (d, i, j) in enumerate(edges):
        if t not in negative and t not in paired:
            out.bars.append(Bar(1, d, None, (i, j), None, cycle=_cycle(i, j, t, edges)))
    return out


def _faces(key: int, E: int) -> tuple[int, int, int]:
    return key // (E * E), (key // E) % E, key % E


def _vertices(tri: tuple[int, int, int], edges: list[tuple[float, int, int]]) -> tuple[int, ...]:
    return tuple(sorted({v for t in tri for v in edges[t][1:]}))


def _cycle(a: int, b: int, t: int, edges: list[tuple[float, int, int]]) -> tuple[int, ...]:
    """A cycle born with edge t = {a, b}: the edge plus a shortest path (fewest edges) from b to a through
    edges earlier in the filtration (spec s 4.4). It represents a class born at t, not necessarily the
    shortest or the unique representative."""
    adj: dict[int, list[int]] = {}
    for u in range(t):
        _, i, j = edges[u]
        adj.setdefault(i, []).append(j)
        adj.setdefault(j, []).append(i)
    prev = {b: b}
    queue = deque([b])
    while queue:
        x = queue.popleft()
        if x == a:
            break
        for y in sorted(adj.get(x, ())):
            if y not in prev:
                prev[y] = x
                queue.append(y)
    if a not in prev:
        return ()
    path = [a]
    while path[-1] != b:
        path.append(prev[path[-1]])
    return tuple(path) + (a,)


# ---------------------------------------------------------------------------------------------- summaries
def betti_curve(p: Persistence) -> list[tuple[float, int, int]]:
    """(scale, b0, b1) at every critical value of the filtration (spec s 5.1)."""
    values = sorted({0.0} | {b.birth for b in p.bars} | {b.death for b in p.bars if b.death is not None})
    rows = []
    for e in values:
        alive = [b for b in p.bars if b.birth <= e and (b.death is None or e < b.death)]
        rows.append((e, sum(1 for b in alive if b.dimension == 0),
                     sum(1 for b in alive if b.dimension == 1)))
    return rows


def betti_at(p: Persistence, e: float) -> tuple[int, int]:
    alive = [b for b in p.bars if b.birth <= e and (b.death is None or e < b.death)]
    return sum(1 for b in alive if b.dimension == 0), sum(1 for b in alive if b.dimension == 1)


# ---------------------------------------------------------------------------------------------- bottleneck
def bottleneck(A: Sequence[Bar], B: Sequence[Bar]) -> float | None:
    """Bottleneck distance between two diagrams of the same dimension (spec s 5.2).

    Finite points are matched to each other (cost: L-infinity distance) or to the diagonal (cost: half the
    persistence). Essential classes are matched among themselves by birth; if their numbers differ the
    distance is infinite and ``None`` is returned. Feasibility at a threshold uses the Mendelsohn–Dulmage
    theorem: a perfect matching exists if and only if there is a matching covering every point of A that
    cannot go to the diagonal and one covering every such point of B.
    """
    fa = [(x.birth, x.death) for x in A if x.death is not None]
    fb = [(x.birth, x.death) for x in B if x.death is not None]
    ea = sorted(x.birth for x in A if x.death is None)
    eb = sorted(x.birth for x in B if x.death is None)
    if len(ea) != len(eb):
        return None
    essential = max((abs(x - y) for x, y in zip(ea, eb)), default=0.0)
    return max(essential, _bottleneck_finite(fa, fb))


def _linf(p: tuple[float, float], q: tuple[float, float]) -> float:
    return max(abs(p[0] - q[0]), abs(p[1] - q[1]))


def _bottleneck_finite(fa: list[tuple[float, float]], fb: list[tuple[float, float]]) -> float:
    if not fa and not fb:
        return 0.0
    half_a = [(d - b) / 2 for b, d in fa]
    half_b = [(d - b) / 2 for b, d in fb]
    cross = [[_linf(p, q) for q in fb] for p in fa]
    candidates = sorted({0.0, *half_a, *half_b, *(c for row in cross for c in row)})

    def matches_all(big: list[int], cost: list[list[float]], eps: float) -> bool:
        match: dict[int, int] = {}

        def augment(u: int, seen: set[int]) -> bool:
            for v, c in enumerate(cost[u]):
                if c <= eps and v not in seen:
                    seen.add(v)
                    if v not in match or augment(match[v], seen):
                        match[v] = u
                        return True
            return False

        return all(augment(u, set()) for u in big)

    cross_t = [list(col) for col in zip(*cross)] if cross else [[] for _ in fb]

    def feasible(eps: float) -> bool:
        big_a = [i for i, h in enumerate(half_a) if h > eps]
        big_b = [j for j, h in enumerate(half_b) if h > eps]
        return matches_all(big_a, cross, eps) and matches_all(big_b, cross_t, eps)

    lo, hi = 0, len(candidates) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if feasible(candidates[mid]):
            hi = mid
        else:
            lo = mid + 1
    return candidates[lo]


# ---------------------------------------------------------------------------------------------- display only
def classical_mds(D: Matrix, dims: int = 2, max_iter: int = 3000, tol: float = 1e-12) -> tuple[list[list[float]], float, bool]:
    """Classical multidimensional scaling by power iteration with deflation (spec s 6). For display only
    (D4). Returns coordinates, the share of the trace of the centred Gram matrix captured, and whether
    every eigenvector converged."""
    n = len(D)
    if n == 0:
        return [], 0.0, True
    sq = [[float(D[i][j]) ** 2 for j in range(n)] for i in range(n)]
    row = [sum(r) / n for r in sq]
    grand = sum(row) / n
    B = [[-0.5 * (sq[i][j] - row[i] - row[j] + grand) for j in range(n)] for i in range(n)]
    trace = sum(B[i][i] for i in range(n))
    vectors: list[list[float]] = []
    values: list[float] = []
    converged = True
    for k in range(dims):
        v = [((i * 37 + 11 * k) % 17 + 1) / 17.0 for i in range(n)]
        lam = 0.0
        ok = False
        for _ in range(max_iter):
            for u in vectors:
                dot = sum(a * b for a, b in zip(v, u))
                v = [a - dot * b for a, b in zip(v, u)]
            norm = math.sqrt(sum(a * a for a in v))
            if norm == 0:
                break
            v = [a / norm for a in v]
            w = [sum(B[i][j] * v[j] for j in range(n)) for i in range(n)]
            for u in vectors:
                dot = sum(a * b for a, b in zip(w, u))
                w = [a - dot * b for a, b in zip(w, u)]
            lam_new = sum(a * b for a, b in zip(w, v))
            wn = math.sqrt(sum(a * a for a in w))
            if wn == 0:
                lam = 0.0
                ok = True
                break
            w = [a / wn for a in w]
            delta = max(abs(a - b) for a, b in zip(w, v))
            v, lam = w, lam_new
            if delta < tol:
                ok = True
                break
        if not ok and lam > 1e-12 * max(1.0, abs(trace)):
            converged = False
        big = max(range(n), key=lambda i: (abs(v[i]), -i))
        if v[big] < 0:
            v = [-a for a in v]
        vectors.append(v)
        values.append(max(lam, 0.0))
    coords = [[vectors[k][i] * math.sqrt(values[k]) for k in range(dims)] for i in range(n)]
    share = (sum(values) / trace) if trace > 0 else 0.0
    return coords, share, converged
