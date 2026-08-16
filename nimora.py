from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
from typing import Iterable


def _hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class Story:
    story_id: str
    title: str
    summary: str
    url: str
    image_alt: str = ''
    priority: int = 0
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Card:
    story_id: str
    slot: int
    width: int
    height: int
    prominence: str


class NimoraError(ValueError):
    pass


class Nimora:
    VIEWPORTS = {
        'mobile': 390,
        'tablet': 768,
        'desktop': 1440,
    }

    def __init__(self) -> None:
        self._stories: dict[str, Story] = {}

    @staticmethod
    def make_story_id(title: str, url: str) -> str:
        title = title.strip()
        url = url.strip()
        if not title or not url:
            raise NimoraError('title and url are required')
        return _hash({'title': title.casefold(), 'url': url})[:20]

    def add_story(
        self,
        *,
        title: str,
        summary: str,
        url: str,
        image_alt: str = '',
        priority: int = 0,
        tags: Iterable[str] = (),
    ) -> Story:
        title = title.strip()
        summary = summary.strip()
        url = url.strip()
        if not title or not summary or not url:
            raise NimoraError('title, summary and url are required')
        if not isinstance(priority, int):
            raise NimoraError('priority must be an integer')
        story_id = self.make_story_id(title, url)
        story = Story(
            story_id=story_id,
            title=title,
            summary=summary,
            url=url,
            image_alt=image_alt.strip(),
            priority=priority,
            tags=tuple(sorted({t.strip().casefold() for t in tags if t.strip()})),
        )
        self._stories[story_id] = story
        return story

    def ordered_stories(self, *, tag: str | None = None) -> list[Story]:
        rows = list(self._stories.values())
        if tag:
            needle = tag.strip().casefold()
            rows = [s for s in rows if needle in s.tags]
        return sorted(rows, key=lambda s: (-s.priority, s.title.casefold(), s.story_id))

    @classmethod
    def viewport_width(cls, viewport: str | int) -> int:
        if isinstance(viewport, int):
            if viewport < 240:
                raise NimoraError('viewport too small')
            return viewport
        key = viewport.strip().casefold()
        if key not in cls.VIEWPORTS:
            raise NimoraError(f'unknown viewport: {viewport}')
        return cls.VIEWPORTS[key]

    def compose(self, *, viewport: str | int = 'desktop', limit: int = 12) -> list[Card]:
        width = self.viewport_width(viewport)
        if limit <= 0:
            return []
        if width < 600:
            columns = 1
        elif width < 1000:
            columns = 2
        else:
            columns = 3
        gap = 16
        card_width = max(1, (width - gap * (columns - 1)) // columns)
        rows = self.ordered_stories()[:limit]
        cards: list[Card] = []
        for idx, story in enumerate(rows):
            prominence = 'lead' if idx == 0 else ('major' if idx < columns else 'standard')
            height = int(card_width * (0.62 if prominence == 'lead' else 0.72))
            cards.append(Card(
                story_id=story.story_id,
                slot=idx,
                width=card_width,
                height=height,
                prominence=prominence,
            ))
        return cards

    def accessibility_report(self) -> dict:
        issues: list[dict] = []
        for story in self.ordered_stories():
            if len(story.title) < 4:
                issues.append({'story_id': story.story_id, 'code': 'title-too-short'})
            if len(story.summary) < 20:
                issues.append({'story_id': story.story_id, 'code': 'summary-too-short'})
            if not story.image_alt:
                issues.append({'story_id': story.story_id, 'code': 'missing-image-alt'})
        return {
            'story_count': len(self._stories),
            'issue_count': len(issues),
            'issues': issues,
            'pass': not issues,
        }

    def evidence_manifest(self, *, viewport: str | int = 'desktop') -> dict:
        cards = [asdict(c) for c in self.compose(viewport=viewport)]
        report = self.accessibility_report()
        payload = {
            'viewport_width': self.viewport_width(viewport),
            'stories': [asdict(s) for s in self.ordered_stories()],
            'cards': cards,
            'accessibility': report,
        }
        payload['manifest_hash'] = _hash(payload)
        return payload

    @staticmethod
    def compare_manifests(before: dict, after: dict) -> dict:
        before_ids = [x['story_id'] for x in before.get('stories', [])]
        after_ids = [x['story_id'] for x in after.get('stories', [])]
        return {
            'changed': before.get('manifest_hash') != after.get('manifest_hash'),
            'added': sorted(set(after_ids) - set(before_ids)),
            'removed': sorted(set(before_ids) - set(after_ids)),
            'before_hash': before.get('manifest_hash'),
            'after_hash': after.get('manifest_hash'),
        }
