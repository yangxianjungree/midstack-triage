"""Phase 4多轨推理引擎使用示例"""

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phase4_multitrack import LeadOrchestrator, L1TemplateMapper


def example_basic_usage():
    """基础使用示例"""
    incident_dir = Path(".local/examples/phase4/basic_usage/test_001")
    incident_dir.mkdir(parents=True, exist_ok=True)

    # 方式1：直接指定假设
    hypotheses = [
        "MongoDB复制集主节点故障",
        "网络分区导致副本不可达",
        "磁盘空间不足"
    ]

    orchestrator = LeadOrchestrator(incident_dir, hypotheses)
    result = orchestrator.run()

    print(f"总轮次: {result['total_rounds']}")
    for hyp in result['hypotheses']:
        print(f"假设 {hyp['id']}: {hyp['final_text']}")
        print(f"  状态: {hyp['status']['status']}")
        print(f"  置信度: {hyp['status']['confidence']}")


def example_with_l1_mapper():
    """使用L1映射器的示例"""
    incident_dir = Path(".local/examples/phase4/basic_usage/test_002")
    incident_dir.mkdir(parents=True, exist_ok=True)

    # L1层输出
    l1_output = {
        "primary_symptom": "connection timeout",
        "affected_component": "pulsar"
    }

    # 映射为初始假设
    mapper = L1TemplateMapper()
    hypotheses = mapper.map_from_l1_output(l1_output)

    orchestrator = LeadOrchestrator(incident_dir, hypotheses)
    result = orchestrator.run()

    print(f"从症状 '{l1_output['primary_symptom']}' 生成 {len(hypotheses)} 个假设")
    print(f"推理完成，共 {result['total_rounds']} 轮")


if __name__ == "__main__":
    print("=== 示例1: 基础使用 ===")
    example_basic_usage()

    print("\n=== 示例2: L1映射器 ===")
    example_with_l1_mapper()
