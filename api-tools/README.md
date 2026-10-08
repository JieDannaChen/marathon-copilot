# COROS接入更新

当前COROS入口已迁移为MCP。连接方式、读取命令、数据范围及推送边界见[COROS MCP说明](README_MCP.md)。下文涉及旧Token/邮箱/密码或Web API的内容是历史说明，不能作为当前COROS接入步骤。

# GitHub Enterprise API Client

Python CLI tool for interacting with GitHub Enterprise REST API.

**Requirements:** Python 3.7+ with `requests` library (no other dependencies).

## Setup

```bash
# 1. Install requests (if not already available)
pip install requests

# 2. Copy env template and fill in your tokens
cp .env.example .env
vi .env

# 3. Test connectivity
python3 api_client.py github whoami
```

---

## CLI Usage

### GitHub Enterprise

```bash
python3 api_client.py github whoami
python3 api_client.py github repos                                      # Your repos
python3 api_client.py github repos --org MyOrg                           # Org repos
python3 api_client.py github repo --owner MyOrg --repo MyRepo
python3 api_client.py github branches --owner MyOrg --repo MyRepo
python3 api_client.py github issues --owner MyOrg --repo MyRepo
python3 api_client.py github issues --owner MyOrg --repo MyRepo --state closed
python3 api_client.py github issue --owner MyOrg --repo MyRepo --number 42
python3 api_client.py github create-issue --owner MyOrg --repo MyRepo --title "Bug: ..."
python3 api_client.py github pulls --owner MyOrg --repo MyRepo
python3 api_client.py github pull --owner MyOrg --repo MyRepo --number 10
python3 api_client.py github search-issues --query "repo:MyOrg/MyRepo is:open label:bug"
python3 api_client.py github search-code --query "org:MyOrg filename:Dockerfile FROM"
python3 api_client.py github search-repos --query "org:MyOrg language:python"
```

---

## Python Import Usage

```python
from api_client import GitHubClient

gh = GitHubClient()
user = gh.whoami()
issues = gh.list_issues("MyOrg", "MyRepo", state="open")
```

---

## File Structure

```
api-tools/
  api_client.py     # Main script (CLI + importable library)
  .env.example      # Token template (copy to .env)
  .env              # Your tokens (gitignored)
  .gitignore
  README.md
```
