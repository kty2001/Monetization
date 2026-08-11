from datetime import datetime

from entity.novel_stats import NovelStats

CRAWLED_AT = datetime(2026, 1, 1, 12, 0, 0)
RUN_ID = "20260101_120000"

SAMPLE_ITEM = {
    "nvSrl": 592090,
    "nvSumEntry": 146,
    "nvSumComment": 320,
    "nvSumScore": 9.8,
    "nvSumPurchased": 29379,
    "nvSumRented": 0,
    "nvSumHit": 250182,
    "nvSumGood": 1200,
    "nvSumPrefer": 3400,
    "nvSumChar": 987654,
    "nvGnMain": "1",
    "nvGnSub": "5",
    "nvOptFinish": 0,
    "nvOptAdult": 0,
    "nvOptExclusive": 1,
}


def test_from_list_item_maps_known_fields():
    stats = NovelStats.from_list_item(
        SAMPLE_ITEM, section="pl.serial", crawled_at=CRAWLED_AT, run_id=RUN_ID
    )

    assert stats.novel_id == "592090"
    assert stats.section == "pl.serial"
    assert stats.entry_count == 146
    assert stats.purchased_count == 29379
    assert stats.rented_count == 0
    assert stats.hit_count == 250182
    assert stats.is_finished is False
    assert stats.is_exclusive is True
    assert stats.run_id == RUN_ID


def test_from_list_item_handles_missing_fields():
    stats = NovelStats.from_list_item(
        {"nvSrl": 1}, section="nv.free", crawled_at=CRAWLED_AT, run_id=RUN_ID
    )

    assert stats.novel_id == "1"
    assert stats.purchased_count is None
    assert stats.is_finished is None
