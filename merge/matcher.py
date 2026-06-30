from __future__ import annotations

from rapidfuzz.fuzz import token_sort_ratio

from models import CandidateProfile


class CandidateMatcher:
    """Deterministic union-find matcher honoring identifier priority."""

    def __init__(self, name_threshold: float = 90.0) -> None:
        if not 0 <= name_threshold <= 100:
            raise ValueError("name_threshold must be between 0 and 100")
        self.name_threshold = name_threshold

    def group(self, profiles: list[CandidateProfile]) -> list[list[CandidateProfile]]:
        parents = list(range(len(profiles)))

        def find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def union(left: int, right: int) -> None:
            left_root, right_root = find(left), find(right)
            if left_root != right_root:
                parents[max(left_root, right_root)] = min(left_root, right_root)

        for left in range(len(profiles)):
            for right in range(left + 1, len(profiles)):
                if self.is_match(profiles[left], profiles[right]):
                    union(left, right)

        grouped: dict[int, list[CandidateProfile]] = {}
        for index, profile in enumerate(profiles):
            grouped.setdefault(find(index), []).append(profile)
        return [grouped[key] for key in sorted(grouped)]

    def is_match(self, left: CandidateProfile, right: CandidateProfile) -> bool:
        if set(left.emails) & set(right.emails):
            return True
        if set(left.phones) & set(right.phones):
            return True
        left_links = {value for value in left.links.model_dump().values() if value}
        right_links = {value for value in right.links.model_dump().values() if value}
        if left_links & right_links:
            return True
        if any((
            self._conflict(left.emails, right.emails),
            self._conflict(left.phones, right.phones),
            self._conflict(left_links, right_links),
        )):
            return False
        if not left.full_name or not right.full_name:
            return False
        return token_sort_ratio(left.full_name.casefold(), right.full_name.casefold()) >= self.name_threshold

    @staticmethod
    def _conflict(left: object, right: object) -> bool:
        return bool(left and right and not set(left) & set(right))  # type: ignore[arg-type]
