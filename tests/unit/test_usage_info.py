"""UsageInfo 数据类与 OpenAI usage 解析测试。"""

from open_fox.core.adapters.base import UsageInfo


def test_usage_info_defaults():
    u = UsageInfo()
    assert u.prompt_tokens == 0
    assert u.completion_tokens == 0
    assert u.total_tokens == 0
    assert u.cache_hit_tokens == 0
    assert u.cache_miss_tokens == 0
    assert u.reasoning_tokens == 0


def test_from_openai_usage_basic():
    """标准 OpenAI usage 解析。"""
    data = {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
    }
    u = UsageInfo.from_openai_usage(data)
    assert u.prompt_tokens == 100
    assert u.completion_tokens == 50
    assert u.total_tokens == 150
    assert u.cache_hit_tokens == 0
    assert u.cache_miss_tokens == 100  # miss = prompt - hit


def test_from_openai_usage_with_cache_hit():
    """OpenAI cached_tokens 解析（缓存命中统计）。"""
    data = {
        "prompt_tokens": 1000,
        "completion_tokens": 200,
        "total_tokens": 1200,
        "prompt_tokens_details": {"cached_tokens": 800},
    }
    u = UsageInfo.from_openai_usage(data)
    assert u.cache_hit_tokens == 800
    assert u.cache_miss_tokens == 200  # 1000 - 800


def test_from_openai_usage_with_reasoning():
    """OpenAI reasoning_tokens 解析（o1/o3 等推理模型）。"""
    data = {
        "prompt_tokens": 10,
        "completion_tokens": 100,
        "total_tokens": 110,
        "completion_tokens_details": {"reasoning_tokens": 80},
    }
    u = UsageInfo.from_openai_usage(data)
    assert u.reasoning_tokens == 80


def test_from_openai_usage_empty():
    """None 或空 dict 都返回默认 UsageInfo。"""
    assert UsageInfo.from_openai_usage(None).total_tokens == 0
    assert UsageInfo.from_openai_usage({}).total_tokens == 0


def test_from_openai_usage_partial():
    """缺字段时不抛错，默认为 0。

    total_tokens 缺省时 fallback 为 prompt + completion（估算总消耗）。
    """
    data = {"prompt_tokens": 50}
    u = UsageInfo.from_openai_usage(data)
    assert u.prompt_tokens == 50
    assert u.completion_tokens == 0
    # total_tokens 缺省时为 prompt + completion 估算
    assert u.total_tokens == 50


def test_iadd_accumulation():
    """两个 UsageInfo 累加。"""
    a = UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15,
                  cache_hit_tokens=8, cache_miss_tokens=2, reasoning_tokens=3)
    b = UsageInfo(prompt_tokens=20, completion_tokens=10, total_tokens=30,
                  cache_hit_tokens=15, cache_miss_tokens=5, reasoning_tokens=7)
    a += b
    assert a.prompt_tokens == 30
    assert a.completion_tokens == 15
    assert a.total_tokens == 45
    assert a.cache_hit_tokens == 23
    assert a.cache_miss_tokens == 7
    assert a.reasoning_tokens == 10


def test_iadd_chained():
    """多次累加。"""
    usage = UsageInfo()
    for _ in range(5):
        usage += UsageInfo(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    assert usage.prompt_tokens == 50
    assert usage.completion_tokens == 100
    assert usage.total_tokens == 150


def test_cache_miss_clamps_to_zero():
    """当 cached_tokens > prompt_tokens（异常数据）时不出现负数。"""
    data = {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "prompt_tokens_details": {"cached_tokens": 200},  # 异常：>prompt
    }
    u = UsageInfo.from_openai_usage(data)
    assert u.cache_hit_tokens == 200
    assert u.cache_miss_tokens == 0  # 被 clamp 到 0