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


def test_append_csv_ignores_empty_rows(tmp_path):
    path = tmp_path / "novels.csv"
    append_csv([{"novel_id": "1", "title": "A"}], path)

    # 빈 배치는 no-op이어야 한다(컬럼 0개가 스키마 불일치로 오진단되지 않도록).
    append_csv([], path)

    lines = path.read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 2


def test_append_csv_with_empty_rows_does_not_create_file(tmp_path):
    path = tmp_path / "novels.csv"

    append_csv([], path)

    assert not path.exists()
