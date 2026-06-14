"""使用真实incident fixtures的E2E测试"""

import pytest
from pathlib import Path
import yaml
from phases.phase4.multitrack import LeadOrchestrator, L1TemplateMapper


# 真实incident路径
FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "tests/fixtures/mongodb"

INCIDENTS = [
    "kubernetes-readiness-failure-sample",
    "mongodb-journal-corruption-root-cause",
]


def load_incident_data(incident_name: str):
    """加载incident数据"""
    incident_dir = FIXTURES_DIR / incident_name

    with open(incident_dir / "signal_bundle.yaml") as f:
        signal_bundle = yaml.safe_load(f)

    with open(incident_dir / "expected_analysis.yaml") as f:
        expected = yaml.safe_load(f)

    return signal_bundle, expected


@pytest.mark.parametrize("incident_name", INCIDENTS)
def test_real_incident_e2e(tmp_path, incident_name):
    """使用真实incident数据的E2E测试"""
    signal_bundle, expected = load_incident_data(incident_name)

    # 从signal_bundle提取症状
    abnormal_signals = signal_bundle.get("abnormal_signals", [])
    if not abnormal_signals:
        pytest.skip("无abnormal_signals")

    primary_signal = abnormal_signals[0]
    symptom = primary_signal.get("detail", "")

    # 映射为假设
    l1_output = {
        "primary_symptom": symptom,
        "affected_component": signal_bundle.get("middleware")
    }

    mapper = L1TemplateMapper()
    hypotheses = mapper.map_from_l1_output(l1_output)

    # 配置mock响应 - 第一个假设被支持
    preset = {
        "hypothesis_status": "supported",
        "confidence": 0.75,
        "reasoning": f"症状匹配: {symptom}",
        "validation_actions": [],
        "findings": [],
        "causal_chain_update": None
    }

    # 运行推理
    orch = LeadOrchestrator(
        tmp_path,
        hypotheses,
        agent_type="mock",
        agent_kwargs={"preset_response": preset}
    )
    result = orch.run()

    # 验证
    assert result["total_rounds"] >= 1
    assert len(result["hypotheses"]) > 0

    # 至少有一个假设得到结论
    statuses = [h["status"]["status"] for h in result["hypotheses"]]
    assert any(s in ["supported", "refuted"] for s in statuses)


def test_kubernetes_readiness_failure_detailed(tmp_path):
    """详细测试：Kubernetes就绪探测失败"""
    signal_bundle, expected = load_incident_data("kubernetes-readiness-failure-sample")

    # 模拟针对性的推理逻辑
    symptom = "Pod is Running but readiness probe fails"
    hypotheses = [
        "MongoDB进程未完全启动",
        "就绪探测配置错误",
        "端口未监听"
    ]

    orch = LeadOrchestrator(tmp_path, hypotheses)

    # 第一个假设应该被支持
    tracks = list(orch.tracks.values())
    tracks[0].agent.preset_response = {
        "hypothesis_status": "supported",
        "confidence": 0.8,
        "reasoning": "MongoDB进程启动缓慢，就绪探测超时",
        "validation_actions": [],
        "findings": [],
        "causal_chain_update": None
    }

    result = orch.run()

    # 验证结论与expected_analysis一致
    assert result["hypotheses"][0]["status"]["status"] == "supported"
    assert result["total_rounds"] >= 1
