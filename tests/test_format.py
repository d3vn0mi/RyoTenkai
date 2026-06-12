import ryotenkai


def test_render_table_basic():
    out = ryotenkai.render_table(["ID", "Name"], [["0", "handler"]])
    assert "ID" in out and "Name" in out and "handler" in out
    # Header, separator, one data row.
    assert len(out.splitlines()) == 3


def test_render_table_empty():
    assert ryotenkai.render_table(["ID"], []) == "(none)"


def test_format_jobs():
    out = ryotenkai.format_jobs({"0": "Exploit: multi/handler"})
    assert "0" in out and "multi/handler" in out


def test_format_sessions():
    out = ryotenkai.format_sessions(
        {"1": {"type": "meterpreter", "tunnel_peer": "10.0.0.5", "info": "WORKGROUP"}}
    )
    assert "meterpreter" in out and "10.0.0.5" in out


def test_format_exploit_result_success():
    out = ryotenkai.format_exploit_result({"status": "success", "raw_output": "PID 99"})
    assert "PID 99" in out


def test_format_exploit_result_error():
    out = ryotenkai.format_exploit_result({"status": "error", "message": "nope"})
    assert "nope" in out
