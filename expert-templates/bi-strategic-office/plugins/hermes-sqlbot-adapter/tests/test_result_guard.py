"""Result truncation tests."""

from __future__ import annotations

from sqlbot_adapter.security.result_guard import apply_result_guards, truncate_rows


def test_hard_limit_truncates_not_discard():
    rows = [{"i": i} for i in range(50)]
    sliced, truncated, original, warnings = truncate_rows(rows, model_limit=10, hard_limit=20)
    assert original == 50
    assert len(sliced) == 10
    assert truncated is True
    assert any("硬上限" in w for w in warnings)


def test_column_limit():
    cols = [f"c{i}" for i in range(60)]
    rows = [{f"c{i}": i for i in range(60)}]
    sliced, kept, truncated, original, warnings = apply_result_guards(
        "汇总查询本月销售额",
        rows,
        columns=cols,
        model_limit=100,
        hard_limit=1000,
        max_columns=50,
        skip_detail_check=True,
    )
    assert len(kept) == 50
    assert any("列数" in w for w in warnings)
