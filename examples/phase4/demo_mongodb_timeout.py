"""真实场景演示：MongoDB连接超时故障诊断"""

import json
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phase4_multitrack import LeadOrchestrator, L1TemplateMapper


def simulate_mongodb_timeout_incident():
    """模拟真实故障场景"""

    print("=" * 60)
    print("场景：生产环境MongoDB连接超时")
    print("=" * 60)

    # 1. L1层输出（已识别症状）
    l1_output = {
        "primary_symptom": "connection timeout",
        "affected_component": "mongodb",
        "timestamp": "2026-06-13T04:00:00Z",
        "error_message": "pymongo.errors.ServerSelectionTimeoutError"
    }
    print(f"\n[L1输出] 症状: {l1_output['primary_symptom']}")
    print(f"         组件: {l1_output['affected_component']}")

    # 2. 映射为初始假设
    mapper = L1TemplateMapper()
    hypotheses = mapper.map_from_l1_output(l1_output)

    print(f"\n[Phase 4] 生成 {len(hypotheses)} 个初始假设:")
    for i, h in enumerate(hypotheses, 1):
        print(f"  {i}. {h}")

    # 3. 创建推理引擎
    incident_dir = Path(".local/examples/phase4/demo_mongodb_timeout")
    incident_dir.mkdir(parents=True, exist_ok=True)

    orch = LeadOrchestrator(incident_dir, hypotheses)

    # 4. 模拟推理过程（实际会调用Agent，这里mock演示）
    print(f"\n[推理循环] 最多 {orch.max_rounds} 轮...")

    # Mock推理逻辑：第一个假设最终被支持
    for i, track in enumerate(orch.tracks.values()):
        if i == 0:  # 第一个假设：网络延迟
            track._reason = lambda obs: {
                "hypothesis_status": "supported",
                "confidence": 0.85,
                "reasoning": "发现大量慢查询和网络重传",
                "validation_actions": [],
                "findings": [{
                    "type": "support",
                    "content": "metrics显示P99延迟 > 5s",
                    "evidence": ["metrics_001"],
                    "affects": []
                }],
                "causal_chain_update": None
            }
        else:  # 其他假设：证据不足或被反驳
            track._reason = lambda obs: {
                "hypothesis_status": "insufficient",
                "confidence": 0.3,
                "reasoning": "缺少关键证据",
                "validation_actions": [],
                "findings": [],
                "causal_chain_update": None
            }

    # 5. 运行推理
    result = orch.run()

    # 6. 输出结果
    print(f"\n推理完成，共 {result['total_rounds']} 轮")
    print("\n" + "=" * 60)
    print("最终结论")
    print("=" * 60)

    for hyp in result['hypotheses']:
        status = hyp['status']['status']
        confidence = hyp['status']['confidence']

        status_emoji = {
            'supported': '✓',
            'refuted': '✗',
            'insufficient': '?',
            'pending': '⋯'
        }.get(status, '-')

        print(f"\n{status_emoji} 假设: {hyp['final_text']}")
        print(f"  状态: {status} (置信度: {confidence:.2f})")

    # 7. 导出详细报告
    report_path = incident_dir / "final_report.json"
    with open(report_path, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n详细报告已保存: {report_path}")
    print(f"黑板数据: {incident_dir / 'reasoning-board.yaml'}")

    return result


if __name__ == "__main__":
    result = simulate_mongodb_timeout_incident()

    print("\n" + "=" * 60)
    print("验证方式")
    print("=" * 60)
    print("1. 查看 ./.local/examples/phase4/demo_mongodb_timeout/reasoning-board.yaml - 完整推理过程")
    print("2. 查看 ./.local/examples/phase4/demo_mongodb_timeout/final_report.json - 最终结论")
    print("3. 运行测试: python3 -m pytest tests/phase4_multitrack/ -v")
