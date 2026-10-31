"""Scenario checks (docs/format.md): walks every possible playthrough -
scene together with flags - so it also finds situations where the player
is stuck, endings that cannot be reached and loops without a way out.

    python -m engine.check scenariusz/sala_pod_zegarem.md
"""

from __future__ import annotations

import sys
from collections import deque
from dataclasses import dataclass, field

from .scenario import MAX_OPTIONS, Scenario, ScenarioError, load

MAX_STATES = 200_000  # (scene, flags) combinations - guard against flag explosion


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def _where(scene, line=None) -> str:
    return f"{scene.id} (linia {line or scene.line})"


def _flags_text(flags) -> str:
    return "{" + ", ".join(sorted(flags)) + "}" if flags else "bez flag"


def check(scenario: Scenario) -> Report:
    report = Report()
    scenes = scenario.scenes

    # --- Static: each scene on its own ---
    set_somewhere, used = set(), set()
    for scene in scenes.values():
        set_somewhere |= set(scene.set_flags)
        used |= set(scene.text_conditions())
        texts = set()
        for option in scene.options:
            if option.target not in scenes:
                report.errors.append(f"{_where(scene, option.line)}: opcja prowadzi do "
                                     f"nieistniejącej sceny {option.target!r}")
            if option.text in texts:
                report.warnings.append(f"{_where(scene, option.line)}: powtórzony tekst opcji "
                                       f"{option.text!r}")
            texts.add(option.text)
            used |= {flag for flag, _ in option.conditions}
            set_somewhere |= set(option.set_flags)
        if scene.ending and scene.options:
            report.errors.append(f"{_where(scene)}: zakończenie nie może mieć opcji")
        if not scene.ending and not scene.options:
            report.errors.append(f"{_where(scene)}: scena bez opcji, a nie jest zakończeniem "
                                 f"(> koniec: ...)")
        if not any(scene.paragraphs):
            report.warnings.append(f"{_where(scene)}: scena bez tekstu")

    # Stops without a choice cost the player a press and give nothing -
    # rare, and never two in a row
    single = {s.id for s in scenes.values() if not s.ending and len(s.options) == 1}
    for scene_id in sorted(single):
        target = scenes[scene_id].options[0].target
        if target in single:
            report.warnings.append(f"{_where(scenes[scene_id])}: dwie sceny z jedną opcją pod rząd "
                                   f"({scene_id} -> {target}) - połącz je albo daj wybór")
    for flag in sorted(used - set_somewhere):
        report.warnings.append(f"flaga {flag!r} jest sprawdzana, ale nigdzie nie ustawiana")
    for flag in sorted(set_somewhere - used):
        report.warnings.append(f"flaga {flag!r} jest ustawiana, ale nigdzie nie sprawdzana")

    # --- Dynamic: every playthrough (scene + flags) from the start ---
    start = (scenario.start, frozenset(scenes[scenario.start].enter(set())))
    depth = {start: 0}  # fewest choices to reach the state
    edges: dict[tuple, list[tuple]] = {}
    queue = deque([start])
    stuck_reported, crowded_reported = set(), set()
    while queue:
        state = queue.popleft()
        scene_id, flags = state
        scene = scenes[scene_id]
        options = scene.visible_options(set(flags))
        if not scene.ending and not options and scene.options and scene_id not in stuck_reported:
            stuck_reported.add(scene_id)
            report.errors.append(f"{_where(scene)}: gracz utknął - przy fladze "
                                 f"{_flags_text(flags)} żadna opcja nie jest widoczna")
        if len(options) > MAX_OPTIONS and scene_id not in crowded_reported:
            crowded_reported.add(scene_id)
            report.errors.append(f"{_where(scene)}: {len(options)} widoczne opcje naraz przy "
                                 f"{_flags_text(flags)} (max {MAX_OPTIONS})")
        edges[state] = []
        for option in options:
            if option.target not in scenes:
                continue
            nxt = (option.target,
                   frozenset(scenes[option.target].enter(option.apply(set(flags)))))
            edges[state].append(nxt)
            if nxt not in depth:
                if len(depth) >= MAX_STATES:
                    report.errors.append(f"za dużo kombinacji scen i flag (> {MAX_STATES}) - "
                                         f"sprawdzanie przerwane")
                    return report
                depth[nxt] = depth[state] + 1
                queue.append(nxt)

    reached = {scene_id for scene_id, _ in depth}
    for scene in scenes.values():
        if scene.id not in reached:
            kind = "zakończenie" if scene.ending else "scena"
            report.errors.append(f"{_where(scene)}: {kind} nieosiągalne - nie da się do niego dojść"
                                 if scene.ending else
                                 f"{_where(scene)}: {kind} nieosiągalna - nie da się do niej dojść")

    # States from which no ending can be reached (loops without a way out)
    reverse: dict[tuple, list[tuple]] = {s: [] for s in edges}
    for state, targets in edges.items():
        for target in targets:
            reverse.setdefault(target, []).append(state)
    can_finish = {s for s in edges if scenes[s[0]].ending}
    queue = deque(can_finish)
    while queue:
        for previous in reverse.get(queue.popleft(), []):
            if previous not in can_finish:
                can_finish.add(previous)
                queue.append(previous)
    trapped = sorted({s[0] for s in edges if s not in can_finish and edges[s]})
    for scene_id in trapped:
        report.errors.append(f"{_where(scenes[scene_id])}: pętla bez wyjścia - stąd nie da się "
                             f"dojść do żadnego zakończenia")

    ending_depths = [d for (scene_id, _), d in depth.items() if scenes[scene_id].ending]
    report.stats = {
        "sceny": len(scenes),
        "zakończenia": len(scenario.endings),
        "sceny z jedną opcją": f"{len(single)} z {len(scenes) - len(scenario.endings)}",
        "stany (scena + flagi)": len(depth),
        "najkrótsza rozgrywka (wybory)": min(ending_depths) if ending_depths else None,
        "najdłuższa rozgrywka (wybory)": _longest(start, edges, scenes),
    }
    return report


def _longest(start, edges, scenes):
    """Most choices to an ending - None when a loop makes it unlimited."""
    memo, visiting = {}, set()

    def walk(state):
        if state in memo:
            return memo[state]
        if state in visiting:
            raise _Loop
        visiting.add(state)
        best = 0 if scenes[state[0]].ending else -1
        for target in edges.get(state, []):
            sub = walk(target)
            if sub >= 0:
                best = max(best, sub + 1)
        visiting.discard(state)
        memo[state] = best
        return best

    sys.setrecursionlimit(max(10_000, sys.getrecursionlimit()))
    try:
        result = walk(start)
    except _Loop:
        return None
    return result if result >= 0 else None


class _Loop(Exception):
    pass


def main(paths: list[str]) -> int:
    failed = False
    for path in paths:
        try:
            report = check(load(path))
        except ScenarioError as e:
            print(f"BŁĄD FORMATU: {e}")
            failed = True
            continue
        print(f"== {path}")
        for error in report.errors:
            print(f"  BŁĄD: {error}")
        for warning in report.warnings:
            print(f"  uwaga: {warning}")
        for name, value in report.stats.items():
            print(f"  {name}: {'bez ograniczeń (pętla)' if value is None and 'najdłuższa' in name else value}")
        failed |= bool(report.errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
