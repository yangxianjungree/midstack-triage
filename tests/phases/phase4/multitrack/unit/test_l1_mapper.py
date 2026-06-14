"""L1TemplateMapper单元测试"""

import pytest
from phases.phase4.multitrack.l1_mapper import L1TemplateMapper


def test_map_from_symptom_connection_refused():
    """测试connection refused症状映射"""
    mapper = L1TemplateMapper()
    hypotheses = mapper.map_from_symptom("connection refused")

    assert len(hypotheses) > 0
    assert "网络分区" in hypotheses


def test_map_from_symptom_with_component():
    """测试症状+组件映射"""
    mapper = L1TemplateMapper()
    hypotheses = mapper.map_from_symptom("timeout", "mongodb")

    assert len(hypotheses) > 0
    assert any("网络" in h or "服务" in h or "复制集" in h for h in hypotheses)


def test_map_from_l1_output():
    """测试从L1输出映射"""
    mapper = L1TemplateMapper()
    l1_data = {
        "primary_symptom": "dns resolution failed",
        "affected_component": "pulsar"
    }

    hypotheses = mapper.map_from_l1_output(l1_data)

    assert len(hypotheses) > 0
    assert len(hypotheses) <= 5


def test_fallback_for_unknown_symptom():
    """测试未知症状的fallback"""
    mapper = L1TemplateMapper()
    hypotheses = mapper.map_from_symptom("unknown error xyz")

    assert len(hypotheses) == 3
    assert all("unknown error xyz" in h for h in hypotheses)
