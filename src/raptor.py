"""RAPTOR (Round-bAsed Public Transit Optimized Router) on the GTFS timetable.

Earliest-arrival, Pareto-optimal in (arrival time, number of vehicle trips). Supports multi-origin starts with
access-walk offsets, multi-destination egress walks, footpath transfers, and one-to-all queries.
Scheduled times only: no real-time data is used or implied.
"""
from __future__ import annotations
import numpy as np
from .config import MIN_TRANSFER_S

INF = 10**9


class RaptorResult:
    def __init__(self, tt, sd, tau, par_best, par_trip, source_walk, t0):
        self.tt, self.sd, self.tau, self.par_best, self.par_trip, self.source_walk, self.t0 = tt, sd, tau, par_best, par_trip, source_walk, t0
        self.best = np.minimum.reduce(tau)            # best arrival per stop over all rounds

    def _round_of(self, s, k):
        for j in range(k, -1, -1):
            if s in self.par_best[j]:
                return j
        return None

    def legs_to(self, stop: int, k: int):
        """Reconstruct the leg list for reaching `stop` using at most k vehicle trips."""
        tt, legs, s, kk = self.tt, [], stop, k
        while True:
            j = self._round_of(s, kk)
            if j is None or j == 0:
                break
            e = self.par_best[j][s]
            if e[0] == "W":
                frm, secs = e[1], e[2]
                legs.append(dict(kind="walk", from_stop=frm, to_stop=s, secs=secs))
                s = frm
                e = self.par_trip[j][s]
            else:
                e = self.par_trip[j][s] if e[0] != "T" else e
            _, p, row, ib, ia, a_time = e[:6]
            view = self.sd.view(p)
            stops = tt.pat_stops[p]
            legs.append(dict(kind="trip", pattern=p, trip_idx=int(view.trip[row]), board_stop=int(stops[ib]), alight_stop=int(stops[ia]),
                             board_pos=ib, alight_pos=ia, dep=int(view.dep[row, ib]), arr=int(view.arr[row, ia])))
            s = int(stops[ib]); kk = j - 1
        legs.reverse()
        return legs, s


def raptor(tt, sd, sources: dict, t0: int, targets: dict | None = None, max_rounds: int = 5, cap: int | None = None,
           min_transfer: int = MIN_TRANSFER_S) -> RaptorResult:
    """sources: {stop_idx: arrival_time_s at that stop (already incl. access walk)}; targets: {stop_idx: egress_walk_s}."""
    S = tt.n_stops
    bound = INF if cap is None else cap
    tau = [np.full(S, INF, dtype=np.int64) for _ in range(max_rounds + 1)]
    best = np.full(S, INF, dtype=np.int64)
    par_best = [dict() for _ in range(max_rounds + 1)]; par_trip = [dict() for _ in range(max_rounds + 1)]
    marked = set()
    for s, t in sources.items():
        tau[0][s] = t; best[s] = t; marked.add(s); par_best[0][s] = ("S", t - t0)
    tgt_best = INF
    def tgt_update(s, a):
        nonlocal tgt_best, bound
        if targets and s in targets:
            tgt_best = min(tgt_best, a + targets[s]); bound = min(bound, tgt_best) if cap is None else min(cap, tgt_best)
    for s, t in sources.items():
        tgt_update(s, t)
    fp_ptr, fp_to, fp_s = tt.fp_ptr, tt.fp_to, tt.fp_s
    for k in range(1, max_rounds + 1):
        Q: dict[int, int] = {}
        for s in marked:
            for p, i in tt.stop_patterns[s]:
                if p not in Q or i < Q[p]:
                    Q[p] = i
        marked_t = {}
        prev, cur_tau = tau[k - 1], tau[k]
        cur_tau[:] = prev
        buf = 0 if k == 1 else min_transfer
        for p, i0 in Q.items():
            view = sd.view(p)
            if view is None:
                continue
            stops = tt.pat_stops[p]; D, A = view.dep, view.arr; m = D.shape[0]; n = len(stops)
            row = -1; ib = -1
            for i in range(i0, n):
                s = int(stops[i])
                if row >= 0:
                    a = int(A[row, i])
                    if a < best[s] and a < bound:
                        cur_tau[s] = a; best[s] = a; marked_t[s] = (a, p, row, ib, i); par_trip[k][s] = ("T", p, row, ib, i, a); par_best[k][s] = par_trip[k][s]
                        tgt_update(s, a)
                ready = prev[s]
                if ready < INF:
                    ready += buf
                    if row < 0 or ready <= D[row, i]:
                        col = D[:, i]
                        if view.fifo:
                            j = int(np.searchsorted(col, ready, "left"))
                            if j >= m: continue
                        else:
                            ok = np.flatnonzero(col >= ready)
                            if ok.size == 0: continue
                            j = int(ok[np.argmin(col[ok])])
                        if row < 0 or col[j] < D[row, i]:
                            row, ib = j, i
                            if D[row, i] > bound:
                                break
        new_marked = set(marked_t)
        for s, (a, *_r) in list(marked_t.items()):
            for q in range(fp_ptr[s], fp_ptr[s + 1]):
                nb = int(fp_to[q]); a2 = a + int(fp_s[q])
                if a2 < best[nb] and a2 < bound:
                    cur_tau[nb] = a2; best[nb] = a2; par_best[k][nb] = ("W", s, int(fp_s[q])); new_marked.add(nb)
                    tgt_update(nb, a2)
        marked = new_marked
        if not marked:
            break
    return RaptorResult(tt, sd, tau, par_best, par_trip, {}, t0)


def pareto_journeys(res: RaptorResult, targets: dict, max_rounds: int = 5):
    """Best (arrival, trips) options to any target stop; only strictly-improving rounds are returned."""
    out, best_arr = [], INF
    for k in range(1, max_rounds + 1):
        cand = [(int(res.tau[k][s]) + e, s) for s, e in targets.items() if res.tau[k][s] < INF]
        if not cand: continue
        arr, s = min(cand)
        if arr < best_arr:
            best_arr = arr
            legs, src = res.legs_to(s, k)
            if legs and any(l["kind"] == "trip" for l in legs):
                out.append(dict(k=k, arrival=arr, stop=s, legs=legs, source_stop=src, egress_s=targets[s]))
    return out
