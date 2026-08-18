import subprocess
import sys
from pathlib import Path


def test_migrate_writes_yaml_per_server(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("""
        mcp_servers:
          - name: fs
            transport: stdio
            command: npx
            args: ["@x/server-fs"]
          - name: remote
            transport: sse
            url: http://h/sse
            headers:
              Authorization: "Bearer ${TOKEN}"
    """, encoding="utf-8")
    out_dir = tmp_path / "mcps"
    result = subprocess.run(
        [sys.executable, "scripts/migrate_mcp_config.py",
         "--config", str(config), "--out", str(out_dir)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    fs_yaml = out_dir / "fs.yaml"
    remote_yaml = out_dir / "remote.yaml"
    assert fs_yaml.exists() and remote_yaml.exists()
    assert "name: fs" in fs_yaml.read_text(encoding="utf-8")
    assert '${TOKEN}' in remote_yaml.read_text(encoding="utf-8")


def test_migrate_skips_existing_files(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("""
        mcp_servers:
          - {name: fs, transport: stdio, command: echo}
    """, encoding="utf-8")
    out_dir = tmp_path / "mcps"
    out_dir.mkdir()
    (out_dir / "fs.yaml").write_text("existing\n", encoding="utf-8")
    subprocess.run([sys.executable, "scripts/migrate_mcp_config.py",
                    "--config", str(config), "--out", str(out_dir)],
                   capture_output=True, text=True)
    assert (out_dir / "fs.yaml").read_text(encoding="utf-8") == "existing\n"


def test_migrate_does_not_modify_config(tmp_path):
    config = tmp_path / "config.yaml"
    original = "mcp_servers:\n  - {name: x, transport: stdio, command: e}\n"
    config.write_text(original, encoding="utf-8")
    subprocess.run([sys.executable, "scripts/migrate_mcp_config.py",
                    "--config", str(config), "--out", str(tmp_path / "mcps")],
                   capture_output=True, text=True)
    assert config.read_text(encoding="utf-8") == original