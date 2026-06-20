"""Claude-backed reasoning agent for Phase 4."""

import os
from typing import Dict, Optional


class ClaudeAgent:
    """Claude API Agent - 真实推理"""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-6", incident_dir: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self.incident_dir = incident_dir
        self.client = None

        if not self.api_key:
            raise ValueError("需要ANTHROPIC_API_KEY环境变量或api_key参数")

    def _ensure_client(self):
        """延迟初始化client"""
        if self.client is None:
            try:
                import anthropic

                self.client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("需要安装anthropic: pip install anthropic")

    def _get_tools(self) -> list:
        """定义Claude可以使用的工具"""
        return [
            {
                "name": "read_file",
                "description": "读取incident目录中的文件",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "文件名，如 signal_bundle.yaml, structured_record.yaml",
                        }
                    },
                    "required": ["filename"],
                },
            },
            {
                "name": "list_files",
                "description": "列出incident目录中的文件",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        ]

    def _execute_tool(self, tool_name: str, tool_input: Dict) -> str:
        """执行工具调用"""
        if not self.incident_dir:
            return "错误: 未指定incident目录"

        from pathlib import Path

        incident_path = Path(self.incident_dir)

        if tool_name == "list_files":
            files = [f.name for f in incident_path.glob("*.yaml")]
            return "\n".join(files)
        if tool_name == "read_file":
            filename = tool_input.get("filename")
            file_path = incident_path / filename

            if not file_path.exists():
                return f"文件不存在: {filename}"

            try:
                with open(file_path) as f:
                    return f.read()
            except Exception as exc:
                return f"读取失败: {exc}"

        return "未知工具"

    def reason(self, observations: Dict) -> Dict:
        """调用Claude API进行推理（使用tool use读取文件）"""
        self._ensure_client()

        prompt = f"""你是故障根因分析专家。

当前incident目录: {self.incident_dir}

可用工具:
- list_files: 查看目录中的文件
- read_file: 读取具体文件内容

请分析这个incident，输出JSON格式：
{{
    "hypothesis_status": "supported|refuted|insufficient|pending",
    "confidence": 0.0-1.0,
    "reasoning": "推理过程",
    "evidence_refs": ["structured_record.details...", "signal_bundle..."],
    "validation_actions": [{{"action": "..."}}, ...],
    "findings": [{{"type": "...", "content": "...", "evidence": [], "affects": []}}, ...]
}}

evidence_refs只能引用当前incident证据路径，例如structured_record、signal_bundle、collection_report、deepening_findings、deep_analysis_results或verification_requests；不要引用历史经验、runbook或用户线索作为直接证据。"""

        messages = [{"role": "user", "content": prompt}]
        max_iterations = 5

        try:
            for _ in range(max_iterations):
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    messages=messages,
                    tools=self._get_tools() if self.incident_dir else None,
                )

                if response.stop_reason == "tool_use":
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            result = self._execute_tool(block.name, block.input)
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": result,
                                }
                            )

                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": tool_results})
                elif response.stop_reason == "end_turn":
                    text = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            text += block.text

                    return self._parse_response(text)

            raise Exception("Claude超过最大工具调用次数")

        except Exception as exc:
            return {
                "hypothesis_status": "insufficient",
                "confidence": 0.3,
                "reasoning": f"Agent调用失败: {exc}",
                "validation_actions": [],
                "findings": [],
                "causal_chain_update": None,
            }

    def _build_prompt(self, observations: Dict) -> str:
        """构建推理prompt"""
        return f"""你是一个故障根因分析专家。基于以下证据，分析假设的合理性。

## 当前观察

### 假设状态
{self._format_hypothesis_status(observations.get("hypothesis_status", {}))}

### 最近发现
{self._format_findings(observations.get("recent_findings", []))}

### 我的验证结果
{self._format_validations(observations.get("my_validations", []))}

### 针对我的反驳
{self._format_refutations(observations.get("refutations_against_me", []))}

## 输出要求

返回JSON格式，包含：
- hypothesis_status: "supported" | "refuted" | "insufficient" | "pending"
- confidence: 0.0-1.0
- reasoning: 推理过程（1-2句话）
- evidence_refs: 当前incident证据路径列表，只能引用structured_record、signal_bundle、collection_report、deepening_findings、deep_analysis_results或verification_requests
- validation_actions: [{{"action": "验证动作描述"}}] (如需要)
- findings: [{{"type": "support|refutation|gap", "content": "发现内容", "evidence": [], "affects": []}}]

JSON:"""

    def _format_hypothesis_status(self, status: Dict) -> str:
        if not status:
            return "无其他假设状态"
        lines = []
        for hyp_id, info in status.items():
            lines.append(f"- {hyp_id}: {info.get('status')} (置信度: {info.get('confidence', 0):.2f})")
        return "\n".join(lines)

    def _format_findings(self, findings: list) -> str:
        if not findings:
            return "暂无发现"
        lines = []
        for finding in findings[-5:]:
            lines.append(f"- [{finding.get('type')}] {finding.get('content')}")
        return "\n".join(lines)

    def _format_validations(self, validations: list) -> str:
        if not validations:
            return "暂无验证结果"
        lines = []
        for validation in validations:
            lines.append(f"- {validation.get('action')}: {validation.get('result')}")
        return "\n".join(lines)

    def _format_refutations(self, refutations: list) -> str:
        if not refutations:
            return "无反驳"
        lines = []
        for refutation in refutations:
            lines.append(f"- {refutation.get('reason')}")
        return "\n".join(lines)

    def _parse_response(self, text: str) -> Dict:
        """解析Claude返回的JSON"""
        import json
        import re

        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if not json_match:
            raise ValueError(f"未找到JSON响应: {text[:200]}")

        result = json.loads(json_match.group())
        required = ["hypothesis_status", "confidence", "reasoning"]
        for field in required:
            if field not in result:
                raise ValueError(f"缺少字段: {field}")

        result.setdefault("validation_actions", [])
        result.setdefault("findings", [])
        result.setdefault("evidence_refs", [])
        result.setdefault("causal_chain_update", None)
        return result
