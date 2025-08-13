#!/bin/zsh

# 示範如何加載與使用 YAML 配置
echo "示範 TrailTag 配置文件加載..."
cd "$(dirname "$0")"
cd ..

python -c "
import yaml
import os
from pprint import pprint

# 設置配置文件路徑
agents_yaml = os.path.join('src', 'trailtag', 'config', 'agents.yaml')
tasks_yaml = os.path.join('src', 'trailtag', 'config', 'tasks.yaml')

# 加載配置
print('加載 agents.yaml...')
with open(agents_yaml, 'r') as f:
    agents_config = yaml.safe_load(f)
    print('Agents 配置:')
    pprint(agents_config)
    print()

print('加載 tasks.yaml...')
with open(tasks_yaml, 'r') as f:
    tasks_config = yaml.safe_load(f)
    print('Tasks 配置:')
    pprint(tasks_config)
"
