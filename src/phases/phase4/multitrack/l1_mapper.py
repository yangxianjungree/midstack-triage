"""L1 Template Mapper - 将L1层输入映射为Phase4初始假设"""

from typing import List, Dict, Optional
from pathlib import Path
import json


class L1TemplateMapper:
    """L1层输入到Phase4假设的映射器"""

    def __init__(self, template_path: Optional[Path] = None):
        self.template_path = template_path or Path(__file__).parent / "l1_templates.json"
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict:
        """加载L1模板配置"""
        if not self.template_path.exists():
            return self._get_default_templates()

        with open(self.template_path) as f:
            return json.load(f)

    def _get_default_templates(self) -> Dict:
        """默认模板"""
        return {
            "symptom_patterns": {
                "connection_refused": ["网络分区", "服务未启动", "防火墙规则"],
                "timeout": ["网络延迟", "服务响应慢", "资源耗尽"],
                "dns_resolution_failed": ["DNS配置错误", "DNS服务故障"],
                "high_latency": ["网络拥塞", "服务过载", "数据库慢查询"],
                "authentication_failed": ["密钥过期", "权限配置错误", "IAM角色问题"]
            },
            "component_patterns": {
                "mongodb": ["复制集状态异常", "索引缺失", "内存不足"],
                "pulsar": ["Broker不可用", "Topic配置错误", "消费者积压"],
                "kubernetes": ["Pod驱逐", "资源配额限制", "节点NotReady"]
            }
        }

    def map_from_symptom(self, symptom: str, component: Optional[str] = None) -> List[str]:
        """根据症状生成初始假设"""
        hypotheses = []

        # 从症状模式匹配
        for pattern, hyps in self.templates["symptom_patterns"].items():
            if pattern.replace("_", " ") in symptom.lower():
                hypotheses.extend(hyps)

        # 从组件模式匹配
        if component:
            comp_hyps = self.templates["component_patterns"].get(component.lower(), [])
            hypotheses.extend(comp_hyps)

        # 去重并限制数量
        hypotheses = list(dict.fromkeys(hypotheses))[:5]

        # 如果无匹配，生成通用假设
        if not hypotheses:
            hypotheses = [
                f"{symptom} - 配置错误",
                f"{symptom} - 资源问题",
                f"{symptom} - 依赖故障"
            ]

        return hypotheses

    def map_from_l1_output(self, l1_data: Dict) -> List[str]:
        """从L1层输出生成假设"""
        symptom = l1_data.get("primary_symptom", "")
        component = l1_data.get("affected_component")

        return self.map_from_symptom(symptom, component)
