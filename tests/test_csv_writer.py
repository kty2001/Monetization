import pytest

from repository.csv_writer import append_csv


def test_append_csv_rejects_schema_mismatch(tmp_path):
    path = tmp_path / "novels.csv"
    append_csv([{"novel_id": "1", "title": "A"}], path)

    with pytest.raises(ValueError, match="헤더"):
        append_csv([{"novel_id": "2", "title": "B", "like_count": 5}], path)

    # 실패한 시도가 파일을 훼손하지 않았는지 확인
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 2


def test_append_csv_allows_matching_schema(tmp_path):
    path = tmp_path / "novels.csv"
    append_csv([{"novel_id": "1", "title": "A"}], path)
    append_csv([{"novel_id": "2", "title": "B"}], path)

    lines = path.read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 3
