"""测试ClaudeAgent的tool use功能"""

from phases.phase4.multitrack.agents import ClaudeAgent


def test_claude_agent_list_files_tool(tmp_path):
    """测试list_files工具"""
    # 创建测试文件
    (tmp_path / "signal_bundle.yaml").write_text("test: data")
    (tmp_path / "structured_record.yaml").write_text("test: data")

    agent = ClaudeAgent(api_key="test-key", incident_dir=str(tmp_path))

    result = agent._execute_tool("list_files", {})

    assert "signal_bundle.yaml" in result
    assert "structured_record.yaml" in result


def test_claude_agent_read_file_tool(tmp_path):
    """测试read_file工具"""
    test_content = "middleware: mongodb\nstatus: abnormal"
    (tmp_path / "test.yaml").write_text(test_content)

    agent = ClaudeAgent(api_key="test-key", incident_dir=str(tmp_path))

    result = agent._execute_tool("read_file", {"filename": "test.yaml"})

    assert result == test_content


def test_claude_agent_read_nonexistent_file(tmp_path):
    """测试读取不存在的文件"""
    agent = ClaudeAgent(api_key="test-key", incident_dir=str(tmp_path))

    result = agent._execute_tool("read_file", {"filename": "missing.yaml"})

    assert "不存在" in result


def test_claude_agent_tools_definition():
    """测试工具定义格式"""
    agent = ClaudeAgent(api_key="test-key", incident_dir="/tmp")

    tools = agent._get_tools()

    assert len(tools) == 2
    assert tools[0]["name"] == "read_file"
    assert tools[1]["name"] == "list_files"
    assert "input_schema" in tools[0]
