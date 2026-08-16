import pytest

from nimora import Nimora, NimoraError


def build():
    n = Nimora()
    n.add_story(
        title='Energy markets steady',
        summary='Wholesale energy markets remained stable throughout the trading session.',
        url='https://example.test/a',
        image_alt='Transmission towers at sunset',
        priority=5,
        tags=['energy', 'markets'],
    )
    n.add_story(
        title='City transport update',
        summary='The metropolitan transport authority published its latest service update.',
        url='https://example.test/b',
        image_alt='City bus at a station',
        priority=2,
        tags=['city'],
    )
    return n


def test_story_id_is_deterministic():
    assert Nimora.make_story_id('A title', 'https://example.test') == Nimora.make_story_id('A title', 'https://example.test')


def test_priority_ordering_is_deterministic():
    n = build()
    assert [x.title for x in n.ordered_stories()] == ['Energy markets steady', 'City transport update']


def test_mobile_uses_single_column_width():
    n = build()
    cards = n.compose(viewport='mobile')
    assert cards[0].width == 390


def test_tablet_uses_two_columns():
    n = build()
    cards = n.compose(viewport='tablet')
    assert cards[0].width == (768 - 16) // 2


def test_desktop_uses_three_columns():
    n = build()
    cards = n.compose(viewport='desktop')
    assert cards[0].width == (1440 - 32) // 3


def test_accessibility_report_passes_for_complete_stories():
    assert build().accessibility_report()['pass'] is True


def test_accessibility_report_finds_missing_alt_and_short_summary():
    n = Nimora()
    n.add_story(title='News', summary='Too short', url='https://example.test/x')
    report = n.accessibility_report()
    codes = {x['code'] for x in report['issues']}
    assert 'summary-too-short' in codes
    assert 'missing-image-alt' in codes


def test_tag_filtering():
    n = build()
    assert [x.title for x in n.ordered_stories(tag='energy')] == ['Energy markets steady']


def test_manifest_is_reproducible():
    n = build()
    assert n.evidence_manifest()['manifest_hash'] == n.evidence_manifest()['manifest_hash']


def test_manifest_comparison_reports_added_story():
    n = build()
    before = n.evidence_manifest()
    added = n.add_story(
        title='Third story',
        summary='A sufficiently descriptive summary for the newly added story in this feed.',
        url='https://example.test/c',
        image_alt='Illustration',
    )
    after = n.evidence_manifest()
    diff = Nimora.compare_manifests(before, after)
    assert diff['changed'] is True
    assert diff['added'] == [added.story_id]


def test_invalid_viewport_is_rejected():
    with pytest.raises(NimoraError):
        Nimora.viewport_width('watch')
